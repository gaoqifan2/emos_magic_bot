#!/usr/bin/env python3
# 测试httpx模块的使用

import httpx
from datetime import datetime, timedelta, timezone

# 北京时间 UTC+8
beijing_tz = timezone(timedelta(hours=8))

print("测试httpx模块...")

# 测试基本的httpx使用
try:
    async def test_httpx():
        async with httpx.AsyncClient() as client:
            # 测试一个简单的GET请求
            response = await client.get("https://httpbin.org/get", timeout=10)
            print(f"HTTP响应状态码: {response.status_code}")
            print(f"响应内容: {response.json()}")
            print("✓ httpx 测试成功")
    
    import asyncio
    asyncio.run(test_httpx())
except Exception as e:
    print(f"✗ httpx 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n测试完成!")