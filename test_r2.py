#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试R2客户端连接状态
"""

import logging
from utils.r2_client import r2_client

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("测试R2客户端连接状态")
    
    # 检查R2客户端是否初始化
    if not r2_client:
        logger.error("R2客户端未初始化")
    else:
        logger.info("R2客户端已初始化")
        
        # 检查内部client是否初始化
        if not hasattr(r2_client, 'client') or not r2_client.client:
            logger.error("R2客户端内部client未初始化")
        else:
            logger.info("R2客户端内部client已初始化")
            
            # 尝试上传一个测试文件
            try:
                test_data = b"test"
                url = r2_client.upload_file(test_data, "test.txt", "test")
                logger.info(f"测试文件上传成功: {url}")
            except Exception as e:
                logger.error(f"测试文件上传失败: {e}")

    logger.info("测试完成")
