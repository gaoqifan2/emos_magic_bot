import requests

api_url = "https://dev.emos.best/api/user"
token = "11_test-token"

headers = {"Authorization": f"Bearer {token}"}

try:
    response = requests.get(api_url, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
