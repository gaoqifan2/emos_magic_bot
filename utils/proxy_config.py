import os

from config import HTTP_PROXY_URL


def _build_proxies():
    proxy = HTTP_PROXY_URL or os.getenv("REQUESTS_PROXY_URL", "")
    if not proxy:
        return None
    return {
        "http": proxy,
        "https": proxy,
    }


proxies = _build_proxies()
