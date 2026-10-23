import csv
from pathlib import Path

import openpyxl

XLSX = Path("dataset/Khoi12.xlsx")
OUT_DIR = Path("dataset/csv")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    header = ("stt", "họ tên", "điện thoại")
    for ws in wb.worksheets:
        name = ws.title.strip()
        out = OUT_DIR / f"{name}.csv"
        rows = [r for r in ws.iter_rows(values_only=True)
                if any(v is not None and str(v).strip() != "" for v in r)]
        start = next(i for i, r in enumerate(rows)
                     if tuple(str(v).strip().lower() for v in r[:3]) == header)
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for r in rows[start:]:
                writer.writerow(["" if v is None else v for v in r[:3]])
        print(f"{ws.title!r} -> {out} ({len(rows) - start} rows)")


if __name__ == "__main__":
    main()
