import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath('.'))

from utils.r2_client import r2_client
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

print("Testing R2 client...")
print(f"R2 client instance: {r2_client}")

if r2_client:
    print(f"R2 client client attribute: {r2_client.client}")
    print(f"R2 client bucket: {r2_client.bucket}")
    print(f"R2 client public URL: {r2_client.public_url}")
else:
    print("R2 client is None")

print("Test completed.")
