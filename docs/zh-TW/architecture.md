# 架構一覽

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

## 架構概述
- `lazy_blacktea_pyqt.py` 為主程式，組合 UI 元件並處理跨模組訊號。
- `ui/` 負責呈現介面與資料流，透過 signal/slot 傳遞狀態與裝置事件。
- `utils/` 封裝 ADB、排程、結構化日誌與原生模組橋接。
- `config/` 提供預設值與使用者偏好設定持久化。
- `native_lbb/` 以 Rust 提供密集 I/O 操作的最佳化函式庫。
- `tests/` 統整測試金字塔，維持功能、性能與併發安全。

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
