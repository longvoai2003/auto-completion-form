import re
import unicodedata
from pathlib import Path

ANSWER_FILE = (
    Path(__file__).resolve().parent
    / "dataset"
    / "chu_de_3_cac_ky_nang_so_co_ban_dap_an.txt"
)

MARKER = "[✓ ĐÁP ÁN ĐÚNG]"


def normalize(text: str) -> str:
    """Normalize Vietnamese text so answer/question text matches the form DOM."""
    if text is None:
        return ""
    s = unicodedata.normalize("NFC", str(text))
    s = s.replace("\u00a0", " ")
    s = (
        s.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
        .replace("…", "...")
    )
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_answers(path: Path = ANSWER_FILE) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[dict] = []
    current: dict | None = None

    for line in lines:
        m = re.match(r"^\s*Câu\s+(\d+)\.\s*(.*)$", line)
        if m:
            if current:
                blocks.append(current)
            current = {
                "num": int(m.group(1)),
                "question": m.group(2).strip(),
                "answers": [],
            }
            continue
        if current is None:
            continue
        if MARKER in line:
            answer = line.split(MARKER, 1)[1].strip()
            answer = re.sub(r"^[\s\-\]:\.]+", "", answer).strip()
            if answer and answer not in current["answers"]:
                current["answers"].append(answer)

    if current:
        blocks.append(current)

    for block in blocks:
        block["question_norm"] = normalize(block["question"])
        if len(block["answers"]) != 1:
            raise ValueError(
                f"Câu {block['num']} expected exactly 1 correct answer, "
                f"got {len(block['answers'])}: {block['answers']}"
            )
        block["answer"] = block["answers"][0]
        block["answer_norm"] = normalize(block["answers"][0])

    if len(blocks) != 30:
        raise ValueError(f"Expected 30 questions, parsed {len(blocks)}")

    nums = [b["num"] for b in blocks]
    if nums != list(range(1, 31)):
        raise ValueError(f"Question numbers are not 1..30: {nums}")

    return blocks


ANSWER_BLOCKS = parse_answers()
ANSWER_BY_QUESTION = {b["question_norm"]: b["answer_norm"] for b in ANSWER_BLOCKS}

if __name__ == "__main__":
    for b in ANSWER_BLOCKS:
        print(f"Câu {b['num']:2d}: {b['answer']}")
    print(f"\nTotal: {len(ANSWER_BLOCKS)} answers")
