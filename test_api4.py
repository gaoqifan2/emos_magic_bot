import requests
import time

api_url = "https://dev.emos.best/api/user"
token = "11_test-token"

headers = {"Authorization": f"Bearer {token}"}

try:
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试API: {api_url}")
    print(f"测试Token: {token}")
    
    response = requests.get(api_url, headers=headers, timeout=10)
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {response.text[:500]}...")  # 只显示前500个字符
    
    if response.status_code == 200:
        print("✅ 测试成功！")
    elif response.status_code == 502:
        print("❌ 测试API服务器返回502错误！")
    else:
        print(f"❌ 测试失败，状态码: {response.status_code}")
except Exception as e:
    print(f"❌ 测试失败: {e}")
