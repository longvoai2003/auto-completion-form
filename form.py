from pathlib import Path

FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSepUYRFVfx1xELqdjJ9tjOXldod2tia66ekNvUAtNY4M12XFg/viewform"
)

CLASS_NAME = "Long"
CLASS_CSV = Path("dataset/csv/Long.csv")

UNIT = "Đoàn phường Hòa Cường"
# CHI_DOAN = "THPT Nguyễn Hiền"
CHI_DOAN = "Trường CĐ Phương Đông Đà Nẵng"

# Entry IDs (kept for reference / possible direct POST fallback)
ENTRY_IDS = {
    "name": "123848646",
    "unit": "956990249",
    "chi_doan": "150881975",
    "phone": "528337292",
}

SCREENSHOT_DIR = Path("screenshots")
LOG_CSV = Path("submissions.csv")

DEFAULT_DELAY_SECONDS = 1.5
MAX_RETRIES = 2
