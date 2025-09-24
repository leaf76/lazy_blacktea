#!/usr/bin/env python3
"""
錯誤處理統一化重構腳本

這個腳本將：
1. 統一所有錯誤處理調用為使用 error_handler
2. 添加適當的錯誤代碼
3. 保持功能一致性
4. 提供回滾機制
"""

import re
import shutil
from pathlib import Path


def backup_file(file_path: str) -> str:
    """創建檔案備份"""
    backup_path = f"{file_path}.error_handling_backup"
    shutil.copy2(file_path, backup_path)
    print(f"✅ 已創建備份: {backup_path}")
    return backup_path


def analyze_error_calls(content: str) -> dict:
    """分析錯誤處理調用"""
    patterns = {
        'show_error': r'self\.show_error\([\'"]([^\'\"]*)[\'"],\s*[\'"]([^\'\"]*)[\'\"]\)',
        'show_info': r'self\.show_info\([\'"]([^\'\"]*)[\'"],\s*[\'"]([^\'\"]*)[\'\"]\)',
        'show_warning': r'self\.show_warning\([\'"]([^\'\"]*)[\'"],\s*[\'"]([^\'\"]*)[\'\"]\)'
    }

    results = {}
    for call_type, pattern in patterns.items():
        matches = re.findall(pattern, content)
        results[call_type] = matches
        print(f"📊 找到 {len(matches)} 個 {call_type} 調用")

    return results


def generate_unified_replacements(analysis: dict) -> list:
    """生成統一化替換規則"""
    replacements = []

    # show_error 替換
    for title, message in analysis.get('show_error', []):
        old_pattern = f"self.show_error('{title}', '{message}')"

        # 根據內容選擇適當的錯誤代碼
        error_code = 'ErrorCode.UNKNOWN_ERROR'
        if 'device' in message.lower():
            error_code = 'ErrorCode.DEVICE_NOT_FOUND'
        elif 'file' in message.lower():
            error_code = 'ErrorCode.FILE_NOT_FOUND'
        elif 'command' in message.lower():
            error_code = 'ErrorCode.COMMAND_FAILED'
        elif 'config' in message.lower():
            error_code = 'ErrorCode.CONFIG_INVALID'

        new_pattern = f"self.error_handler.handle_error({error_code}, '{message}', title='{title}')"
        replacements.append((old_pattern, new_pattern))

    # show_info 替換
    for title, message in analysis.get('show_info', []):
        old_pattern = f"self.show_info('{title}', '{message}')"
        new_pattern = f"self.error_handler.show_info('{title}', '{message}')"
        replacements.append((old_pattern, new_pattern))

    # show_warning 替換
    for title, message in analysis.get('show_warning', []):
        old_pattern = f"self.show_warning('{title}', '{message}')"
        new_pattern = f"self.error_handler.show_warning('{title}', '{message}')"
        replacements.append((old_pattern, new_pattern))

    return replacements


def apply_replacements(content: str, replacements: list) -> str:
    """應用替換"""
    updated_content = content
    applied_count = 0

    for old, new in replacements:
        if old in updated_content:
            updated_content = updated_content.replace(old, new)
            applied_count += 1
            print(f"✅ 替換: {old[:50]}...")

    print(f"📊 總共應用了 {applied_count} 個替換")
    return updated_content


def refactor_error_handling(main_file: str):
    """重構錯誤處理"""
    print("🔧 開始錯誤處理統一化重構...")

    # 1. 備份原檔案
    backup_path = backup_file(main_file)

    # 2. 讀取檔案內容
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 3. 分析現有錯誤調用
    print("\n📊 分析現有錯誤處理調用...")
    analysis = analyze_error_calls(content)

    # 4. 生成替換規則
    print("\n🔄 生成統一化替換規則...")
    replacements = generate_unified_replacements(analysis)

    if not replacements:
        print("ℹ️  沒有找到需要統一化的調用，退出...")
        return

    print(f"📋 生成了 {len(replacements)} 個替換規則")

    # 5. 應用替換
    print("\n⚡ 應用統一化替換...")
    updated_content = apply_replacements(content, replacements)

    # 6. 檢查是否需要添加錯誤代碼導入
    if 'ErrorCode.UNKNOWN_ERROR' in updated_content and 'UNKNOWN_ERROR' not in content:
        # 添加到現有的ErrorCode導入
        error_import_pattern = r'from ui\.error_handler import ([^,\n]+)'
        match = re.search(error_import_pattern, updated_content)
        if match:
            current_imports = match.group(1)
            if 'ErrorCode' not in current_imports:
                new_imports = current_imports + ', ErrorCode'
                updated_content = re.sub(error_import_pattern, f'from ui.error_handler import {new_imports}', updated_content)
                print("✅ 已添加 ErrorCode 導入")

    # 7. 寫回檔案
    with open(main_file, 'w', encoding='utf-8') as f:
        f.write(updated_content)

    print(f"\n✅ 錯誤處理統一化重構完成！")
    print(f"📁 原檔案備份: {backup_path}")
    print(f"📄 已更新主檔案: {main_file}")


def create_validation_script():
    """創建驗證腳本"""
    validation_script = '''#!/usr/bin/env python3
"""驗證錯誤處理統一化是否成功"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import lazy_blacktea_pyqt
    from ui.error_handler import ErrorHandler, ErrorCode

    print("✅ 模組導入測試通過")
    print("✅ ErrorCode 可用")
    print("🎉 錯誤處理統一化成功！")

except Exception as e:
    print(f"❌ 錯誤處理統一化驗證失敗: {e}")
    sys.exit(1)
'''

    with open('validate_error_refactor.py', 'w', encoding='utf-8') as f:
        f.write(validation_script)

    print("✅ 已創建驗證腳本: validate_error_refactor.py")


if __name__ == "__main__":
    main_file = "lazy_blacktea_pyqt.py"

    if not Path(main_file).exists():
        print(f"❌ 找不到主檔案: {main_file}")
        sys.exit(1)

    try:
        refactor_error_handling(main_file)
        create_validation_script()

        print("\n" + "="*50)
        print("🎉 錯誤處理統一化重構完成！")
        print("="*50)
        print("下一步：")
        print("1. 運行 python3 validate_error_refactor.py 驗證")
        print("2. 測試應用程式功能")
        print("3. 如有問題，從備份檔案恢復")

    except Exception as e:
        print(f"❌ 重構過程中發生錯誤: {e}")
        sys.exit(1)