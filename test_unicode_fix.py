#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试并修复 UnicodeEncodeError 问题
"""

import sys
import logging
from datetime import datetime, timezone, timedelta

# 北京时间 UTC+8
beijing_tz = timezone(timedelta(hours=8))

# 修复 stdout 编码
print(f"原始 stdout 编码: {sys.stdout.encoding}")
try:
    sys.stdout.reconfigure(encoding='utf-8')
    print(f"修复后 stdout 编码: {sys.stdout.encoding}")
except (AttributeError, OSError) as e:
    print(f"无法修复编码: {e}")

# 配置日志
log_filename = f"logs/test_unicode_{datetime.now(beijing_tz).strftime('%Y%m%d_%H%M%S')}.log"

# 确保 logs 目录存在
import os
os.makedirs('logs', exist_ok=True)

# 测试日志配置
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        console_handler,
        logging.FileHandler(log_filename, encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)
print(f"日志文件: {log_filename}")

# 测试中文日志
print("\n=== 测试中文输出 ===")
print("直接 print 输出: 你好，世界！")

print("\n=== 测试日志输出 ===")
try:
    logger.info("测试中文日志: 你好，世界！")
    print("✓ 日志输出成功")
except UnicodeEncodeError as e:
    print(f"✗ 日志输出失败: {e}")

# 测试 token 处理
print("\n=== 测试 token 处理 ===")
test_token = "1047_test_token_123"
try:
    logger.info(f"Token 长度: {len(test_token)}")
    print("✓ Token 处理成功")
except UnicodeEncodeError as e:
    print(f"✗ Token 处理失败: {e}")

# 测试 JSON 编码
print("\n=== 测试 JSON 编码 ===")
test_data = {"name": "测试服务商", "description": "这是一个测试服务商"}
import json
try:
    json_data = json.dumps(test_data, ensure_ascii=False).encode('utf-8')
    print(f"✓ JSON 编码成功，长度: {len(json_data)}")
    print(f"  编码后: {json_data[:50]}...")
except UnicodeEncodeError as e:
    print(f"✗ JSON 编码失败: {e}")

# 测试 HTTP 请求模拟
print("\n=== 测试 HTTP 请求模拟 ===")
try:
    import httpx
    
    # 模拟响应
    class MockResponse:
        def __init__(self):
            self.status_code = 200
            self.text = "{\"success\": true, \"message\": \"申请成功\"}"
    
    # 测试响应处理
    mock_response = MockResponse()
    logger.info(f"响应状态码: {mock_response.status_code}")
    logger.info(f"响应内容: {mock_response.text}")
    print("✓ 响应处理成功")
except Exception as e:
    print(f"✗ 响应处理失败: {e}")

print("\n=== 测试完成 ===")
