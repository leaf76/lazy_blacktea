# 上版與發佈

## 打包與發佈
- 使用 PyInstaller 規格檔（位於 `build-scripts/`）產生 macOS、Linux 安裝包。
- 平台腳本：
  - `build-scripts/build_macos.sh`
  - `build-scripts/build_linux.sh`

## 版本資訊維護
- `VERSION` 檔案（版本來源）。
- `config/constants.py::ApplicationConstants.APP_VERSION`（由 VERSION 讀取）。
- README `Current release` badge（手動同步或使用 `scripts/bump_version.py`）。
- `CHANGELOG.md` 作為版本發佈紀錄。

## 最新版本
最新版本：v0.0.51（2026-03-06）。近期重點：
- APK 安裝顯示傳輸進度並支援取消。
- APK 安裝時串流顯示 ADB push 進度。
- Logcat 串流/過濾改為非 UI thread，整體更順暢。
- Logcat 文字可選取，並修正預設檔覆寫行為。
- 裝置列表可從快取刷新細節，加快更新速度。
- WiFi/藍牙狀態值正規化以確保顯示一致。
- Terminal 取消與歷史操作更穩定。

## Application Updater 需求
- Desktop updater 會檢查 `leaf76/lazy_blacktea` 的 latest GitHub Release。
- 每個要讓 app 內建 updater 可安裝的 release，都必須上傳 `SHA256SUMS.txt` asset。
- `SHA256SUMS.txt` 必須包含每個 desktop artifact 的完整檔名與 SHA256 digest。
- 若 checksum manifest 缺失、平台 asset 缺失，或下載檔案 digest 不相符，updater 會阻擋 download/open action。
- 支援的 updater artifacts：
  - macOS：`LazyBlacktea-macos-arm64.dmg` 或 `LazyBlacktea-macos-x86_64.dmg`
  - Linux：`LazyBlacktea-x86_64.AppImage`，fallback `lazyblacktea-linux.tar.gz`

## Release/Deployment 檢查清單
1. 執行 `uv run python tests/run_tests.py`。
2. 用 `scripts/bump_version.py` 更新版本（同步 `VERSION` 與 constants）。
3. 需要時重建 native 模組：`cd native_lbb && cargo build --release`。
4. 透過 `build-scripts/build_macos.sh`、`build-scripts/build_linux.sh` 產出安裝包。
5. 對所有 desktop artifacts 產出 `SHA256SUMS.txt`，並先在本機驗證 digest。
6. 於目標 OS 驗證產物，並在 GitHub Release 附上 `CHANGELOG.md` 摘要與 `SHA256SUMS.txt`。
