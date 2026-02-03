# 快速開始

## 必要條件
- Python 3.8 以上版本。
- 已安裝 Android SDK Platform Tools，並將 `adb` 加入 `PATH`。
- macOS 或 Linux 桌面環境。
- （選用）若要編譯原生模組，需安裝 Rust 與 Cargo。

## 初次安裝
```bash
# 取得程式碼
git clone https://github.com/cy76/lazy_blacktea.git
cd lazy_blacktea

# 建議使用虛擬環境
python3 -m venv .venv
source .venv/bin/activate

# 安裝相依套件
pip install -r requirements.txt
```

## 啟動應用程式
```bash
python3 lazy_blacktea_pyqt.py
```
若在無顯示器的環境（CI、遠端）執行，請加上 `QT_QPA_PLATFORM=offscreen`。

## 執行自動化測試
```bash
python3 tests/run_tests.py
```
建議在提交（commit）前完整跑過一次，以確保功能穩定。
