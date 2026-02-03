# Lazy Blacktea

![Lazy Blacktea logo](assets/icons/icon_128x128.png)

[![Build Status](https://github.com/cy76/lazy_blacktea/workflows/build/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Test Status](https://github.com/cy76/lazy_blacktea/workflows/test/badge.svg)](https://github.com/cy76/lazy_blacktea/actions)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> Current release: v0.0.49（2026-02-03） | [English version](README.md)
> Release notes：[`CHANGELOG.md`](CHANGELOG.md)

## 為什麼選擇 Lazy Blacktea？
- 單一視窗即可掌握多台 Android 裝置狀態與操作排程。
- 內建常用自動化工作（安裝、錄製、截圖、shell 指令、logcat 串流）。
- 清楚的裝置資料表與進度指示，支援深淺色主題。
- Rust 原生模組協助處理大量 I/O 與檔案併發，加速操作效率。
- 內建測試與 CI 流程，降低改動風險。

## 快速開始
完整安裝與測試步驟請見 [docs/zh-TW/quickstart.md](docs/zh-TW/quickstart.md)。

```bash
python3 lazy_blacktea_pyqt.py
```
若在無顯示器的環境（CI、遠端）執行，請加上 `QT_QPA_PLATFORM=offscreen`。

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

## 架構說明
專案導覽、模組責任與故障排除請見 [docs/zh-TW/architecture.md](docs/zh-TW/architecture.md)。

## 上版與發佈
打包流程、版本管理與發佈檢查清單請見 [docs/zh-TW/deployment.md](docs/zh-TW/deployment.md)。

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
