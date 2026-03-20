#!/usr/bin/env python3
"""
测试抽奖中奖列表API
使用方法：python test_lottery_win.py <lottery_id>
"""

import sys
import httpx
import json

# 生产环境API地址
API_BASE_URL = "https://emos.best/api"

# 测试token（需要替换为有效的token）
TEST_TOKEN = "1047_ow2NHeo3HyzDSxvl"

def test_lottery_win(lottery_id):
    """测试抽奖中奖列表API"""
    url = f"{API_BASE_URL}/lottery/win?lottery_id={lottery_id}"
    headers = {
        "Authorization": f"Bearer {TEST_TOKEN}"
    }
    
    print(f"测试API: {url}")
    print(f"请求头: {headers}")
    
    try:
        # 发送请求
        response = httpx.get(url, headers=headers, timeout=10)
        
        print(f"\n响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        # 尝试解析JSON响应
        try:
            data = response.json()
            print(f"\n响应内容 (JSON):")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(f"\n响应内容 (原始):")
            print(response.text)
            
    except Exception as e:
        print(f"\n请求失败: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使用方法: python test_lottery_win.py <lottery_id>")
        print("示例: python test_lottery_win.py G2yRK3v56w15")
        sys.exit(1)
    
    lottery_id = sys.argv[1]
    test_lottery_win(lottery_id)
