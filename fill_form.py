import argparse
import csv
import difflib
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from answers import ANSWER_BY_QUESTION, normalize
from form import (
    CHI_DOAN,
    CLASS_CSV,
    DEFAULT_DELAY_SECONDS,
    FORM_URL,
    LOG_CSV,
    MAX_RETRIES,
    SCREENSHOT_DIR,
    UNIT,
)

JS_QUESTIONS = r"""
() => {
  const items = [...document.querySelectorAll('div[role="listitem"]')];
  const out = [];
  items.forEach((q, qi) => {
    const radios = [...q.querySelectorAll('[role="radio"]')];
    if (!radios.length) return;
    const h = q.querySelector('div[role="heading"]');
    out.push({
      idx: qi,
      question: h ? h.innerText : '',
      options: radios.map((r, oi) => ({
        oi,
        value: r.getAttribute('data-value') || r.getAttribute('aria-label') || '',
        checked: r.getAttribute('aria-checked') === 'true'
      }))
    });
  });
  return out;
}
"""

JS_SECTION = r"""
() => {
  const headings = [...document.querySelectorAll('div[role="heading"]')].filter(
    (h) => !h.id
  );
  if (!headings.length) return '';
  return (headings[headings.length - 1].innerText || '').trim();
}
"""

CONFIRM_TEXTS = [
    "Đã ghi nhận phản hồi",
    "Câu trả lời của bạn đã được ghi lại",
    "Cảm ơn bạn",
    "Your response has been recorded",
    "Gửi câu trả lời khác",
]


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s-]+", "_", text)
    return text or "student"


def load_students(path: Path) -> list[dict]:
    students: list[dict] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Họ tên") or "").strip()
            phone = (row.get("Điện thoại") or "").strip()
            stt = (row.get("STT") or "").strip()
            if not name:
                continue
            students.append({"stt": stt, "name": name, "phone": phone})
    return students


def find_button(page, label: str):
    target = normalize(label)
    buttons = page.locator('div[role="button"], button')
    for i in range(buttons.count()):
        element = buttons.nth(i)
        try:
            if normalize(element.inner_text()) == target and element.is_visible():
                return element
        except Exception:
            continue
    return None


def find_clickable_containing(page, needle: str):
    target = normalize(needle)
    locator = page.locator(
        'a, div[role="button"], button, div[role="link"], span[role="link"]'
    )
    for i in range(locator.count()):
        element = locator.nth(i)
        try:
            if element.is_visible() and target in normalize(element.inner_text()):
                return element
        except Exception:
            continue
    return None


def extract_score(page) -> str:
    try:
        body = page.locator("body").inner_text()
    except Exception:
        return ""
    lines = [line.strip() for line in body.splitlines()]
    for i, line in enumerate(lines):
        if "Tổng điểm" in line:
            tail = line.split("Tổng điểm", 1)[1].strip()
            if tail:
                return f"Tổng điểm {tail}"
            for following in lines[i + 1 : i + 4]:
                if following:
                    return f"Tổng điểm {following}"
            return "Tổng điểm"
    return ""


def open_score_page(context, page):
    link = find_clickable_containing(page, "Xem điểm")
    if link is None:
        return page

    before = set(context.pages)
    try:
        link.click()
    except Exception:
        return page

    page.wait_for_timeout(1500)
    new_pages = [candidate for candidate in context.pages if candidate not in before]
    score_page = new_pages[-1] if new_pages else page

    try:
        score_page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass

    try:
        score_page.wait_for_function(
            """() => {
              const text = (document.body ? document.body.innerText : '').normalize('NFC');
              return text.includes('Tổng điểm');
            }""",
            timeout=20000,
        )
    except PlaywrightTimeoutError:
        pass

    score_page.wait_for_timeout(1200)
    return score_page


def wait_for_button(page, label: str, timeout: float = 15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        button = find_button(page, label)
        if button is not None:
            return button
        page.wait_for_timeout(200)
    return None


def wait_for_section_change(page, previous: str, timeout: float = 20.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            current = page.evaluate(JS_SECTION)
        except Exception:
            current = ""
        if current and current != previous:
            return current
        page.wait_for_timeout(200)
    raise RuntimeError(f"Page did not change from section: {previous!r}")


def fill_by_heading(page, heading: str, value: str) -> None:
    element = page.locator('div[role="heading"]', has_text=heading).first
    element.wait_for(state="visible", timeout=15000)
    hid = element.get_attribute("id")
    field = page.locator(f'input[aria-labelledby~="{hid}"]').first
    field.fill(value)


def select_unit(page, unit: str) -> None:
    listbox = page.get_by_role("listbox").first
    listbox.wait_for(state="visible", timeout=15000)

    for _ in range(6):
        if listbox.get_attribute("aria-expanded") != "true":
            listbox.click()
        page.wait_for_timeout(500)
        if listbox.get_attribute("aria-expanded") == "true":
            break
    else:
        raise RuntimeError("Đơn vị dropdown did not expand")

    target = page.locator(f'[role="option"][data-value="{unit}"]').last
    target.scroll_into_view_if_needed()
    target.click()
    page.wait_for_timeout(500)

    if listbox.get_attribute("aria-expanded") == "true":
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)


def answer_questions(page) -> list[dict]:
    questions = page.evaluate(JS_QUESTIONS)
    if not questions:
        return []

    results = []
    for q in questions:
        q_norm = normalize(q["question"])
        expected = ANSWER_BY_QUESTION.get(q_norm)

        if expected is None:
            close = difflib.get_close_matches(
                q_norm, list(ANSWER_BY_QUESTION), n=1, cutoff=0.85
            )
            if close:
                expected = ANSWER_BY_QUESTION[close[0]]
            else:
                raise RuntimeError(f"No answer found for question: {q['question']!r}")

        option_index = next(
            (o["oi"] for o in q["options"] if normalize(o["value"]) == expected),
            None,
        )
        if option_index is None:
            values = [normalize(o["value"]) for o in q["options"]]
            close = difflib.get_close_matches(expected, values, n=1, cutoff=0.85)
            if close:
                option_index = values.index(close[0])
            else:
                raise RuntimeError(
                    f"No matching option for {q['question']!r}; expected {expected!r}"
                )

        radio = (
            page.locator('div[role="listitem"]')
            .nth(q["idx"])
            .locator('[role="radio"]')
            .nth(option_index)
        )

        checked = False
        for _ in range(4):
            if radio.get_attribute("aria-checked") == "true":
                checked = True
                break
            radio.scroll_into_view_if_needed()
            page.wait_for_timeout(80)
            radio.click()
            for _ in range(15):
                if radio.get_attribute("aria-checked") == "true":
                    checked = True
                    break
                page.wait_for_timeout(100)
            if checked:
                break

        if not checked:
            raise RuntimeError(f"Could not select option for {q['question']!r}")

        results.append(
            {
                "question": q["question"],
                "answer": q["options"][option_index]["value"],
            }
        )

    return results


def wait_confirmation(page) -> str:
    page.wait_for_function(
        """(texts) => {
          const body = document.body ? document.body.innerText : '';
          return texts.some((t) => body.includes(t));
        }""",
        arg=CONFIRM_TEXTS,
        timeout=30000,
    )
    body = page.locator("body").inner_text()
    for text in CONFIRM_TEXTS:
        if text in body:
            return text
    return ""


def submit_student(
    page, context, student: dict, submit: bool, debug_dir: Path | None
) -> dict:
    page.goto(FORM_URL, wait_until="domcontentloaded")

    fill_by_heading(page, "Họ và tên", student["name"])
    if student["phone"]:
        fill_by_heading(page, "Số điện thoại", student["phone"])
    fill_by_heading(page, "Chi đoàn", CHI_DOAN)
    select_unit(page, UNIT)

    if debug_dir:
        page.screenshot(path=str(debug_dir / "page1_personal.png"), full_page=True)

    section = page.evaluate(JS_SECTION)
    next_button = wait_for_button(page, "Tiếp")
    if next_button is None:
        raise RuntimeError("Could not find 'Tiếp' on personal info page")
    next_button.click()
    section = wait_for_section_change(page, section)

    total_answered = 0
    page_no = 2

    while True:
        page.wait_for_timeout(300)
        answered = answer_questions(page)
        total_answered += len(answered)

        if debug_dir and answered:
            page.screenshot(
                path=str(debug_dir / f"page{page_no}_answered.png"), full_page=True
            )

        submit_button = find_button(page, "Gửi")
        if submit_button is not None:
            if debug_dir:
                page.screenshot(
                    path=str(debug_dir / "final_before_submit.png"), full_page=True
                )
            if not submit:
                return {
                    "status": "dry-run",
                    "confirmation": "",
                    "score": "",
                    "answered": total_answered,
                    "screenshot_page": page,
                }
            submit_button.click()
            confirmation = wait_confirmation(page)
            score_page = open_score_page(context, page)
            score = extract_score(score_page)

            if debug_dir:
                try:
                    (debug_dir / "post_submit.txt").write_text(
                        f"URL: {score_page.url}\n\n"
                        f"{score_page.locator('body').inner_text()}",
                        encoding="utf-8",
                    )
                    score_page.screenshot(
                        path=str(debug_dir / "score_page.png"), full_page=True
                    )
                except Exception:
                    pass

            return {
                "status": "submitted",
                "confirmation": confirmation,
                "score": score,
                "answered": total_answered,
                "screenshot_page": score_page,
            }

        next_button = find_button(page, "Tiếp")
        if next_button is None:
            page.wait_for_timeout(1000)
            next_button = find_button(page, "Tiếp")
        if next_button is None:
            body = page.locator("body").inner_text()
            if "bắt buộc" in body or "required" in body.lower():
                raise RuntimeError("Form reports a required question is unanswered")
            raise RuntimeError("Could not find 'Tiếp' or 'Gửi' button")

        next_button.click()
        section = wait_for_section_change(page, section)
        page_no += 1
        if page_no > 12:
            raise RuntimeError("Too many pages; navigation did not finish")


def append_log(log_csv: Path, row: dict) -> None:
    fields = [
        "stt",
        "ho_ten",
        "dien_thoai",
        "status",
        "confirmation",
        "score",
        "answered",
        "submitted_at",
        "screenshot",
    ]
    exists = log_csv.exists()
    with log_csv.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fields})


def load_submitted_stt(log_csv: Path) -> set[str]:
    if not log_csv.exists():
        return set()
    submitted = set()
    with log_csv.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "submitted" and row.get("stt"):
                submitted.add(row["stt"].strip())
    return submitted


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-fill the CHỦ ĐỀ 3 Google Form for each student."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=CLASS_CSV,
        help=f"Student CSV file to process (default: {CLASS_CSV})",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max students to run")
    parser.add_argument(
        "--start", type=int, default=1, help="Start from this 1-based student number"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fill the form but do not submit; screenshot the final page",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Save a screenshot of every page under the output folder's debug/",
    )
    parser.add_argument(
        "--headless", action="store_true", help="Run headless (default: headed)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="Delay between students in seconds",
    )
    args = parser.parse_args()

    csv_path: Path = args.csv
    if not csv_path.is_file():
        print(f"CSV file not found: {csv_path}")
        return 1

    class_name = csv_path.stem
    output_dir = SCREENSHOT_DIR / f"{class_name}_csv"
    log_csv = (
        LOG_CSV
        if csv_path.resolve() == CLASS_CSV.resolve()
        else LOG_CSV.with_name(f"{LOG_CSV.stem}_{slugify(class_name)}.csv")
    )

    students = load_students(csv_path)
    submitted = load_submitted_stt(log_csv)
    students = [s for s in students if s["stt"].strip() not in submitted]
    selected = students[args.start - 1 :]
    if args.limit is not None:
        selected = selected[: args.limit]

    if not selected:
        print("No students selected.")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    debug_root = output_dir / "debug" if args.debug else None

    print(
        f"Running {len(selected)} student(s) from {csv_path} "
        f"({'dry-run' if args.dry_run else 'SUBMIT'}, "
        f"{'headless' if args.headless else 'headed'}) -> {output_dir}"
    )

    success = 0
    failed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(
            viewport={"width": 1280, "height": 1600},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )
        context.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.resource_type in ("media",)
                or "youtube.com" in route.request.url
                or "googlevideo.com" in route.request.url
                else route.continue_()
            ),
        )

        for position, student in enumerate(selected, start=args.start):
            label = f"{student['stt']}. {student['name']} ({student['phone']})"
            debug_dir = None
            if debug_root:
                debug_dir = debug_root / slugify(
                    f"{class_name}_{student['stt']}_{student['name']}"
                )
                debug_dir.mkdir(parents=True, exist_ok=True)

            stt_token = (
                f"{int(student['stt']):02d}"
                if student["stt"].isdigit()
                else slugify(student["stt"])
            )
            screenshot_path = (
                output_dir
                / f"{class_name}_{stt_token}_{slugify(student['name'])}.png"
            )

            last_error = None
            for attempt in range(1, MAX_RETRIES + 2):
                page = context.new_page()
                try:
                    print(f"[{position}/{len(students)}] {label} ...", end=" ", flush=True)
                    result = submit_student(
                        page, context, student, not args.dry_run, debug_dir
                    )
                    shot_page = result.get("screenshot_page") or page
                    if shot_page is not page:
                        try:
                            page.close()
                        except Exception:
                            pass
                        page = shot_page
                    page.screenshot(path=str(screenshot_path), full_page=True)

                    append_log(
                        log_csv,
                        {
                            "stt": student["stt"],
                            "ho_ten": student["name"],
                            "dien_thoai": student["phone"],
                            "status": result["status"],
                            "confirmation": result["confirmation"],
                            "score": result.get("score", ""),
                            "answered": result["answered"],
                            "submitted_at": datetime.now().isoformat(timespec="seconds"),
                            "screenshot": str(screenshot_path),
                        }
                    )
                    extra = f", {result['score']}" if result.get("score") else ""
                    print(
                        f"{result['status']} (answered {result['answered']}{extra})"
                    )
                    success += 1
                    last_error = None
                    page.close()
                    break
                except Exception as exc:
                    last_error = exc
                    error_path = output_dir / (
                        f"ERROR_{class_name}_{stt_token}_{slugify(student['name'])}"
                        f"_attempt{attempt}.png"
                    )
                    try:
                        page.screenshot(path=str(error_path), full_page=True)
                    except Exception:
                        pass
                    print(f"attempt {attempt} failed: {exc}")
                    if attempt <= MAX_RETRIES:
                        try:
                            page.wait_for_timeout(1500)
                        except Exception:
                            break
                    try:
                        page.close()
                    except Exception:
                        pass
                    if not browser.is_connected():
                        break

            if last_error is not None:
                failed += 1
                append_log(
                    log_csv,
                    {
                        "stt": student["stt"],
                        "ho_ten": student["name"],
                        "dien_thoai": student["phone"],
                        "status": "error",
                        "confirmation": str(last_error),
                        "score": "",
                        "answered": "",
                        "submitted_at": datetime.now().isoformat(timespec="seconds"),
                        "screenshot": "",
                    }
                )

            if position < args.start + len(selected) - 1:
                time.sleep(args.delay)

        context.close()
        browser.close()

    print(f"\nDone. success={success} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
