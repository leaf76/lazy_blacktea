# Lazy Blacktea

![Lazy Blacktea logo](assets/icons/icon_128x128.png)

[![Build Status](https://github.com/cy76/lazy_blacktea/workflows/build/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Test Status](https://github.com/cy76/lazy_blacktea/workflows/test/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> Current release: v0.0.39 | [English version](README.md)

## 為什麼選擇 Lazy Blacktea？
- 單一視窗即可掌握多台 Android 裝置狀態與操作排程。
- 內建常用自動化工作（安裝、錄製、截圖、shell 指令、logcat 串流）。
- 清楚的裝置資料表與進度指示，支援深淺色主題。
- Rust 原生模組協助處理大量 I/O 與檔案併發，加速操作效率。
- 內建測試與 CI 流程，降低改動風險。

## 快速開始
### 必要條件
- Python 3.8 以上版本。
- 已安裝 Android SDK Platform Tools，並將 `adb` 加入 `PATH`。
- macOS 或 Linux 桌面環境。
- （選用）若要編譯原生模組，需安裝 Rust 與 Cargo。

### 初次安裝
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

### 啟動應用程式
```bash
python3 lazy_blacktea_pyqt.py
```
若在無顯示器的環境（CI、遠端）執行，請加上 `QT_QPA_PLATFORM=offscreen`。

### 執行自動化測試
```bash
python3 tests/run_tests.py
```
建議在提交（commit）前完整跑過一次，以確保功能穩定。

## 主要功能
| 領域 | 說明 | 相關模組 |
| --- | --- | --- |
| 裝置管理 | 即時發現裝置、群組管理、動態更新 | `ui.async_device_manager`, `ui.device_manager` |
| 自動化操作 | 批次安裝、bug report、shell、錄影、截圖 | `ui.device_operations_manager`, `utils.adb_tools` |
| 檔案流程 | 裝置檔案瀏覽、預覽與輸出路徑協調 | `ui.device_file_browser_manager`, `utils.file_generation_utils` |
| 診斷工具 | Logcat 串流、錯誤分類、完成提示 | `ui.logcat_viewer`, `ui.console_manager`, `ui.error_handler` |
| 性能優化 | 去抖動刷新、批次 UI 更新、原生協助 | `utils.debounced_refresh`, `utils.task_dispatcher`, `native_lbb` |

## 介面預覽
![Lazy Blacktea overview in dark mode](assets/screenshots/Screenshot_0036.png)

## 專案結構導覽
| 路徑 | 用途 | 重點 |
| --- | --- | --- |
| `lazy_blacktea_pyqt.py` | 應用程式進入點 | 初始化 Qt、註冊管理器、設定日誌 |
| `ui/` | 視覺元件與控制器 | 裝置列表、工具面板、檔案瀏覽、logcat 檢視 |
| `utils/` | 共用工具 | ADB 包裝、日誌、排程、Qt 相依檢查、原生橋接 |
| `config/` | 設定檔 | 常數、偏好儲存、路徑與 logcat 選項 |
| `tests/` | 測試套件 | 單元、整合、性能煙霧測試，由 `tests/run_tests.py` 統一觸發 |
| `assets/` | 靜態資產 | Icon 與品牌素材 |
| `build_scripts/`, `build-scripts/` | 打包工具鏈 | PyInstaller spec、平台啟動腳本、構建輔助模組 |
| `native_lbb/` | Rust 原生專案 | 高頻操作（檔案、同步）最佳化 |
| `scripts/` | 自動化腳本 | 版本號更新 (`bump_version.py`) 等日常維運腳本 |

## 架構一覽
- `lazy_blacktea_pyqt.py` 為主程式，組合 UI 元件並處理跨模組訊號。
- `ui/` 負責呈現介面與資料流，透過 signal/slot 傳遞狀態與裝置事件。
- `utils/` 封裝 ADB、排程、結構化日誌與原生模組橋接。
- `config/` 提供預設值與使用者偏好設定持久化。
- `native_lbb/` 以 Rust 提供密集 I/O 操作的最佳化函式庫。
- `tests/` 統整測試金字塔，維持功能、性能與併發安全。

## 開發與工具
- 啟動腳本：`./start_lazy_blacktea.sh` 會檢查 Python 與 ADB 狀態再啟動 GUI。
- 常見開發指令：
  - `python3 -m pytest tests/test_async_device_performance.py`：併發相關測試。
  - `cargo build --release`（於 `native_lbb/`）：編譯原生模組。
- 建議依照 TDD 流程開發：先寫測試，再實作，再重構。

## 打包與發佈
- 使用 PyInstaller 規格檔（位於 `build-scripts/`）產生 macOS、Linux 安裝包。
- 平台腳本：
  - `build-scripts/build_macos.sh`
  - `build-scripts/build_linux.sh`
- 版本資訊維護：
  - `VERSION` 檔案
  - `config/constants.py::ApplicationConstants.APP_VERSION`
  - README `Current release` badge（手動同步或使用 `scripts/bump_version.py`）。

## 原生模組（Native Companion）
- `native_lbb` 為 Rust crate，提供批次檔案操作與中介資訊收集。
- 編譯方式：
  ```bash
  cd native_lbb
  cargo build --release
  ```
- Python 端透過 `utils.native_bridge` 載入對應的共享函式庫；請確認產物位於系統搜尋路徑或使用環境變數指定。

## 效能、監控與故障排除
- 主要性能作法：去抖動 refresh、批次 UI 更新、非同步 I/O，並透過 Rust 模組分擔重任。
- 日誌使用 `utils.common.get_logger` 提供結構化輸出與 trace ID，方便跨流程追蹤。
- 常見問題：
  - **ADB not found**：設定 `ANDROID_HOME` 或 `ANDROID_SDK_ROOT`，或在設定頁面自訂路徑。
  - **權限受限**：請確認裝置啟用 USB Debugging，必要時啟用 root。
  - **裝置偵測延遲**：重啟 ADB (`adb kill-server && adb start-server`)，清除 `/tmp/lazy_blacktea_*` 暫存。
  - **Qt 插件錯誤**：執行 `utils.qt_dependency_checker.check_and_fix_qt_dependencies()`，確認無警告。
  - **Headless 執行**：加入 `QT_QPA_PLATFORM=offscreen`。

## 社群與支援
- 問題回報：<https://github.com/cy76/lazy_blacktea/issues>
- 討論交流：<https://github.com/cy76/lazy_blacktea/discussions>
- 貢獻指南：[`CONTRIBUTING.md`](CONTRIBUTING.md)
- 安全性回報：請透過 GitHub Security Advisories 私訊。

## 如何貢獻
1. Fork 本專案並建立功能分支。
2. 依 TDD 流程撰寫測試與程式碼，保持提交小而聚焦，使用 Conventional Commits。
3. 執行 `python3 tests/run_tests.py`，確保測試通過並更新文件或效能數據。
4. 送出 Pull Request，附上測試結果、截圖（若為 UI 改動）與必要說明。

## 授權
Lazy Blacktea 以 [MIT License](LICENSE) 發佈；PyQt6 與其他相依套件沿用各自的授權條款。

## 後續規劃（Roadmap）
- 提供更完整的裝置自動化範本與腳本庫。
- 加入雲端同步設定、標籤與使用統計。
- 擴充 Windows 支援（探索中）。
- 增加教學模式與互動導覽。

喜歡這個專案嗎？歡迎按下 ⭐️、分享並回報使用心得！
