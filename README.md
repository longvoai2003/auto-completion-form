# Auto Complete Form

Công cụ tự động điền Google Form cho từng học sinh trong file CSV, chụp ảnh màn hình kết quả, sau đó cắt ảnh điểm bằng `crop_screenshots.py`.

Quy trình gồm 2 bước:

1. `fill_form.py` — điền form và lưu ảnh vào `screenshots/<tên_csv>_csv/`
2. `crop_screenshots.py` — cắt ảnh từ `screenshots/<tên_csv>_csv/` vào `processed_screenshot/<tên_csv>_csv/`

## Yêu cầu

- Python 3.12 trở lên
- [uv](https://docs.astral.sh/uv/) (khuyến nghị)
- Playwright Chromium

## Cài đặt

```bash
uv sync
uv run playwright install chromium
```

Nếu không dùng `uv`, có thể tạo môi trường ảo và cài các thư viện cần thiết:

```bash
python -m venv .venv
source .venv/bin/activate
pip install playwright pillow openpyxl
playwright install chromium
```

## Cấu hình

Mở `form.py` để kiểm tra hoặc chỉnh sửa:

| Biến | Ý nghĩa |
| --- | --- |
| `FORM_URL` | URL Google Form cần điền |
| `UNIT` | Giá trị dropdown "Đơn vị" |
| `CHI_DOAN` | Giá trị "Chi đoàn" |
| `CLASS_CSV` | File CSV mặc định |
| `SCREENSHOT_DIR` | Thư mục gốc chứa ảnh chụp |
| `LOG_CSV` | File log mặc định |

Đáp án đúng được đọc tự động từ `dataset/chu_de_3_cac_ky_nang_so_co_ban_dap_an.txt`.

## Chuẩn bị file CSV

Đặt file CSV trong `dataset/csv/`, ví dụ `dataset/csv/Long.csv`.

File cần có header:

```csv
STT,Họ tên,Điện thoại
2,Lê Yến Chi,0985000422
3,Nguyễn Văn Tấn Dũng,0763889411
```

Lưu ý:

- Dòng nào không có `Họ tên` sẽ bị bỏ qua.
- Nên lưu file với encoding UTF-8.
- Tên file CSV quyết định tên thư mục ảnh:
  - `Long.csv` → `screenshots/Long_csv/`
  - `Nha_1.csv` → `screenshots/Nha_1_csv/`

## Bước 1 — Điền form bằng `fill_form.py`

### Chạy thử một học sinh (không gửi form)

```bash
uv run python fill_form.py --csv dataset/csv/Long.csv --limit 1 --dry-run
```

### Chạy thật

```bash
uv run python fill_form.py --csv dataset/csv/Long.csv
```

### Các tham số

| Tham số | Mặc định | Mô tả |
| --- | --- | --- |
| `--csv` | `dataset/csv/Long.csv` | File CSV học sinh cần xử lý |
| `--limit` | không giới hạn | Chỉ chạy tối đa N học sinh |
| `--start` | `1` | Bắt đầu từ học sinh thứ N (tính từ 1) |
| `--dry-run` | tắt | Điền form nhưng không bấm gửi |
| `--debug` | tắt | Lưu ảnh từng trang vào thư mục `debug/` |
| `--headless` | tắt | Chạy trình duyệt ẩn (mặc định hiện trình duyệt) |
| `--delay` | `1.5` | Thời gian chờ giữa các học sinh (giây) |

### Kết quả

Với `--csv dataset/csv/Long.csv`, ảnh được lưu tại:

```text
screenshots/Long_csv/
```

Tên ảnh có dạng:

```text
Long_02_le_yen_chi.png
```

Các file khác:

- Ảnh lỗi: `ERROR_<tên_csv>_<STT>_<tên>_attemptN.png`
- Ảnh debug (khi dùng `--debug`): `screenshots/<tên_csv>_csv/debug/...`
- Log:
  - `submissions.csv` nếu dùng file CSV mặc định `Long.csv`
  - `submissions_<tên_csv>.csv` nếu dùng file CSV khác

Khi chạy lại, các học sinh đã có trạng thái `submitted` trong file log sẽ được bỏ qua.

## Bước 2 — Cắt ảnh bằng `crop_screenshots.py`

Sau khi `fill_form.py` chạy xong:

```bash
uv run python crop_screenshots.py --src Long_csv
```

Lệnh trên sẽ:

- Đọc ảnh từ `screenshots/Long_csv/`
- Ghi ảnh đã cắt vào `processed_screenshot/Long_csv/`

Ví dụ khác:

```bash
uv run python crop_screenshots.py --src Nha_1_csv
```

### Các tham số

| Tham số | Mặc định | Mô tả |
| --- | --- | --- |
| `--src` | `Long_csv` | Thư mục con trong `screenshots/` (có thể truyền đường dẫn CSV) |
| `--dest` | `processed_screenshot/<tên_thư_mục_nguồn>` | Thư mục đầu ra tùy chỉnh |
| `--width` | `1009` | Chiều rộng ảnh sau khi cắt |
| `--height` | `735` | Chiều cao ảnh sau khi cắt |
| `--move` | tắt | Xóa ảnh nguồn sau khi cắt thành công |

Ảnh được cắt căn giữa theo chiều ngang và căn từ mép trên xuống.

## Quy trình đầy đủ

Ví dụ với file `dataset/csv/Nha_1.csv`:

```bash
# 1. Chạy thử 1 học sinh trước
uv run python fill_form.py --csv dataset/csv/Nha_1.csv --limit 1 --dry-run

# 2. Điền và gửi form cho toàn bộ học sinh
uv run python fill_form.py --csv dataset/csv/Nha_1.csv

# 3. Cắt ảnh điểm
uv run python crop_screenshots.py --src Nha_1_csv
```

Kết quả:

```text
screenshots/Nha_1_csv/          # ảnh gốc do fill_form.py tạo
processed_screenshot/Nha_1_csv/ # ảnh đã cắt
```

## Lưu ý

- Nên chạy `--dry-run --limit 1` trước khi chạy thật để kiểm tra form và đáp án.
- Không đóng cửa sổ trình duyệt khi chương trình đang chạy.
- Nếu đổi Google Form, cập nhật lại `FORM_URL`, `UNIT`, `CHI_DOAN` trong `form.py`.
- Nếu gặp lỗi thiếu trình duyệt, chạy lại `uv run playwright install chromium`.
