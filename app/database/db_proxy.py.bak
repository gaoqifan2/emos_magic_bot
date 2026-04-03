#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支持代理的数据库连接模块
通过 Clash 代理连接 MySQL 数据库
"""

import pymysql
import socks  # PySocks
import socket
from config import DB_CONFIG
from utils.http_client import http_client

# Clash 代理配置（默认 Clash 本地端口）
CLASH_PROXY_HOST = "127.0.0.1"
CLASH_PROXY_PORT = 7890  # Clash 默认 HTTP 代理端口

def get_db_connection_with_proxy():
    """通过 Clash 代理获取数据库连接"""
    try:
        # 保存原始 socket
        original_socket = socket.socket
        
        # 设置 SOCKS5 代理
        socks.set_default_proxy(socks.SOCKS5, CLASH_PROXY_HOST, CLASH_PROXY_PORT)
        socket.socket = socks.socksocket
        
        # 创建数据库连接
        connection = pymysql.connect(
            **DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=30
        )
        
        # 恢复原始 socket
        socket.socket = original_socket
        
        return connection
    except Exception as e:
        print(f"代理数据库连接失败: {e}")
        # 恢复原始 socket
        socket.socket = socket._socketobject if hasattr(socket, '_socketobject') else socket.socket
        return None

def get_db_connection_direct():
    """直接连接数据库（不使用代理）"""
    try:
        connection = pymysql.connect(
            **DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
        return connection
    except Exception as e:
        print(f"直接数据库连接失败: {e}")
        return None

def get_db_connection():
    """
    获取数据库连接
    优先尝试直接连接，失败则尝试代理连接
    """
    # 首先尝试直接连接
    print("尝试直接连接数据库...")
    conn = get_db_connection_direct()
    if conn:
        print("✅ 直接连接成功")
        return conn
    
    # 直接连接失败，尝试代理连接
    print("直接连接失败，尝试通过 Clash 代理连接...")
    conn = get_db_connection_with_proxy()
    if conn:
        print("✅ 代理连接成功")
        return conn
    
    print("❌ 所有连接方式都失败")
    return None

# 测试函数
if __name__ == "__main__":
    print("=" * 50)
    print("测试数据库连接")
    print("=" * 50)
    
    conn = get_db_connection()
    if conn:
        print("✅ 连接成功！")
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            print(f"查询结果: {result}")
        conn.close()
    else:
        print("❌ 连接失败！")
