#!/usr/bin/env python3
# 最小化测试httpx模块

print("测试httpx模块...")

try:
    import httpx
    print("✓ httpx 导入成功")
    
    # 测试同步请求
    response = httpx.get("https://httpbin.org/get", timeout=10)
    print(f"✓ 同步请求成功，状态码: {response.status_code}")
    
    print("\n测试完成，httpx模块正常工作！")
except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()