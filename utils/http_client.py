#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP客户端工具模块
提供全局的HTTP客户端实例，使用连接池提高性能
"""

import httpx
from typing import Optional, Dict, Any

class HTTPClient:
    """HTTP客户端管理类"""
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
    
    async def init_client(self):
        """初始化HTTP客户端"""
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=5.0,      # 连接超时
                    read=10.0,        # 读取超时
                    write=5.0,        # 写入超时
                    pool=30.0         # 池超时
                ),
                limits=httpx.Limits(
                    max_connections=100,    # 最大连接数
                    max_keepalive_connections=20,  # 最大保持连接数
                    keepalive_expiry=30.0   # 保持连接过期时间
                ),
                follow_redirects=True,  # 跟随重定向
                http2=False,  # 禁用HTTP/2，避免需要h2包
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
    
    async def close(self):
        """关闭HTTP客户端"""
        if self.client and not self.client.is_closed:
            await self.client.aclose()
            self.client = None
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """发送GET请求"""
        await self.init_client()
        return await self.client.get(url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """发送POST请求"""
        await self.init_client()
        return await self.client.post(url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> httpx.Response:
        """发送PUT请求"""
        await self.init_client()
        return await self.client.put(url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """发送DELETE请求"""
        await self.init_client()
        return await self.client.delete(url, **kwargs)

# 创建全局HTTP客户端实例
http_client = HTTPClient()
