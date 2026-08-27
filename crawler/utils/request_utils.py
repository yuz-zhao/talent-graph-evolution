"""
HTTP 请求工具 — 封装 requests，内置重试、超时、限速、异常处理
"""

import time
import requests
from config.settings import USER_AGENT, REQUEST_TIMEOUT, MAX_RETRIES, REQUEST_DELAY


def build_headers(extra: dict = None) -> dict:
    """构建请求头，User-Agent 必带"""
    headers = {"User-Agent": USER_AGENT}
    if extra:
        headers.update(extra)
    return headers


def safe_get(url: str, params: dict = None, headers: dict = None,
             timeout: int = REQUEST_TIMEOUT, max_retries: int = MAX_RETRIES,
             delay: float = REQUEST_DELAY) -> requests.Response or None:
    """
    GET 请求，失败自动重试。

    Args:
        url:         请求地址
        params:      URL 参数
        headers:     自定义请求头
        timeout:     超时秒数
        max_retries: 最大重试次数
        delay:       重试前等待秒数

    Returns:
        Response 对象，全部失败返回 None
    """
    req_headers = build_headers(headers)
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, headers=req_headers, timeout=timeout)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                print(f"  [限流] 等待 {wait}s")
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                print(f"  [HTTP {resp.status_code}] 第 {attempt}/{max_retries} 次重试")
                if attempt < max_retries:
                    time.sleep(delay * attempt)
                continue
            return resp
        except requests.exceptions.Timeout:
            print(f"  [超时] 第 {attempt}/{max_retries} 次重试")
        except requests.exceptions.ConnectionError:
            print(f"  [连接错误] 第 {attempt}/{max_retries} 次重试")
        except requests.exceptions.RequestException as e:
            print(f"  [异常] {e}")
            return None
        if attempt < max_retries:
            time.sleep(delay)
    print(f"  [失败] 已重试 {max_retries} 次，放弃")
    return None


def safe_post(url: str, json_data: dict = None, headers: dict = None,
              timeout: int = REQUEST_TIMEOUT, max_retries: int = MAX_RETRIES,
              delay: float = REQUEST_DELAY) -> requests.Response or None:
    """POST 请求，失败自动重试"""
    req_headers = build_headers(headers)
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=json_data, headers=req_headers, timeout=timeout)
            if resp.status_code >= 400:
                if attempt < max_retries:
                    time.sleep(delay * attempt)
                continue
            return resp
        except requests.exceptions.RequestException:
            if attempt < max_retries:
                time.sleep(delay)
    return None
