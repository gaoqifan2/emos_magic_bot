#!/usr/bin/env python3
"""
修复 Python 3.13+ 事件循环兼容性问题的完整脚本
"""

import re

# 读取文件
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 修复模块级别的事件循环代码（第32-45行）
old_module_code = '''# Fix for Python 3.13+ event loop issue
if sys.version_info >= (3, 13):
    try:
        import signal
        loop = asyncio.get_event_loop()
        # 禁用信号处理
        loop.add_signal_handler = lambda sig, handler: None
    except:
        pass'''

new_module_code = '''# Fix for Python 3.13+ event loop issue
if sys.version_info >= (3, 13):
    try:
        import signal
        # Python 3.13+ 兼容性修复
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        # 禁用信号处理
        loop.add_signal_handler = lambda sig, handler: None
    except:
        pass'''

if old_module_code in content:
    content = content.replace(old_module_code, new_module_code)
    print("✅ 修复了模块级别的事件循环代码")
else:
    print("⚠️ 模块级别代码可能已经修复或格式不同")

# 2. 在 main() 函数中添加事件循环创建（在 application.run_polling 之前）
old_main_code = '''    logger.info(f"机器@{Config.BOT_USERNAME} 启动成功")
    
    # 启动机器

    application.run_polling(allowed_updates=Update.ALL_TYPES)'''

new_main_code = '''    logger.info(f"机器@{Config.BOT_USERNAME} 启动成功")
    
    # 启动机器
    # Python 3.13+ 兼容性：确保有事件循环
    if sys.version_info >= (3, 13):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)'''

if old_main_code in content:
    content = content.replace(old_main_code, new_main_code)
    print("✅ 在 main() 函数中添加了事件循环创建")
else:
    print("⚠️ main() 函数代码可能已经修复或格式不同")

# 写入文件
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n🎉 修复完成！")
print("请上传修复后的 main.py 到VPS并重启服务")
