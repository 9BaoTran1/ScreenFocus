# ScreenFocus – Giảm xao nhãng khi dùng máy tính

**ScreenFocus** là overlay toàn màn hình giúp bạn tập trung vào một vùng duy nhất. Phần còn lại bị blur hoặc tối đen, giảm xao nhãng hiệu quả.

> Chạy trên **Windows** (10/11), cần **Python 3.8+**.

---

## ✨ Tính năng

- **Blur overlay** – Làm mờ toàn bộ màn hình, chỉ giữ vùng focus trong suốt
- **Dark mode** – Chế độ đen hoàn toàn thay vì blur, nhẹ hơn cho mắt
- **Smart Focus** – Tự động bám theo cửa sổ đang active (thay vì theo chuột)
- **Resize** – Thay đổi kích thước vùng focus nhanh bằng phím
- **Click-through** – Vùng focus trong suốt, bạn vẫn click chuột bình thường

---

## 🚀 Cài đặt

```bash
# 1. Clone hoặc tải thư mục về
# 2. Tạo môi trường ảo
python -m venv venv
venv\Scripts\activate

# 3. Cài dependencies
pip install -r requirements.txt
```

### Dependencies

- `opencv-python` – Hiển thị overlay
- `mss` – Chụp màn hình nhanh
- `numpy` – Xử lý ảnh
- `keyboard` – Nhận phím tắt toàn cục
- `pyautogui` – Lấy vị trí chuột
- `pywin32` – API Windows (click-through, always-on-top)

---

## ▶️ Chạy

```bash
python overlay_mouse_blur.py
```

> ⚠️ Cần chạy với **quyền Admin** nếu dùng phím `keyboard` toàn cục.

---

## ⌨️ Phím tắt

| Phím | Chức năng |
|------|-----------|
| `Q` | Thoát |
| `R` | Refresh màn hình (chụp lại) |
| `W` | Bật/tắt **Smart Focus** (theo cửa sổ active) |
| `Z` | Bật/tắt **Dark Mode** (màn đen) |
| `]` | Phóng to vùng focus |
| `[` | Thu nhỏ vùng focus |

---

## 📖 Hướng dẫn sử dụng

1. **Chạy app** → overlay blur phủ toàn màn hình, vùng quanh chuột trong suốt
2. Di chuột đến đâu, vùng focus theo đến đó
3. Bấm `Z` để chuyển sang **Dark Mode** (đen hoàn toàn, nhẹ mắt hơn)
4. Bấm `W` để bật **Smart Focus** – vùng focus tự bám theo cửa sổ đang dùng
5. Dùng `[` / `]` để điều chỉnh kích thước vùng focus
6. Bấm `R` nếu nội dung màn hình thay đổi nhiều (refresh)
7. Bấm `Q` để thoát

---

## 🔨 Build thành .exe (không cần Python)

```bash
pip install pyinstaller
pyinstaller ScreenFocus.spec
```

File `.exe` sẽ nằm trong thư mục `dist/`.

---

## English Summary

**ScreenFocus** is a full-screen overlay that helps you focus on one area of the screen. Everything else is blurred or blacked out.

**Shortcuts:** `Q` quit · `R` refresh · `W` smart focus · `Z` dark mode · `[`/`]` resize

**Install:** `pip install -r requirements.txt` → `python overlay_mouse_blur.py`
