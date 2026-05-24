import os
import requests
import json
import time
from .config import BASE_URL, API_KEY
from .ui import console

CACHE_FILE = ".vps8_cache.json"

# ── 域名缓存 ───────────────────────────────────────────────────
_domain_cache: dict | None = None

def _load_cache():
    """从文件加载缓存"""
    global _domain_cache
    if _domain_cache is not None:
        return _domain_cache
    
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _domain_cache = json.load(f)
        except Exception:
            _domain_cache = {"data": [], "updated_at": 0}
    else:
        _domain_cache = {"data": [], "updated_at": 0}
    return _domain_cache

def _save_cache(data):
    """保存缓存到文件"""
    global _domain_cache
    _domain_cache = {
        "data": data,
        "updated_at": int(time.time())
    }
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_domain_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        console.print(f"[dim red]保存本地缓存失败: {e}[/]")

def get_cache_info():
    """获取缓存状态信息"""
    cache = _load_cache()
    updated_at = cache.get("updated_at", 0)
    if updated_at == 0:
        return "从未更新"
    
    # 转换为易读格式
    struct_time = time.localtime(updated_at)
    return time.strftime("%Y-%m-%d %H:%M:%S", struct_time)

def clear_local_cache():
    """清空本地缓存文件"""
    global _domain_cache
    _domain_cache = {"data": [], "updated_at": 0}
    if os.path.exists(CACHE_FILE):
        try:
            os.remove(CACHE_FILE)
            return True
        except Exception as e:
            console.print(f"[red]删除缓存文件失败: {e}[/]")
    return False

def api_domain_list(refresh: bool = False) -> list:
    """获取域名列表（优先从本地文件缓存获取）"""
    cache = _load_cache()
    
    # 如果不是强制刷新，且缓存中有数据，则直接返回
    if not refresh and cache.get("data"):
        return cache["data"]

    # 否则请求 API
    with console.status("[dim]正在同步云端域名列表...[/]", spinner="dots"):
        data = _post("domain_list", {})
    
    if data:
        result = data.get("result", [])
        domains = result if isinstance(result, list) else []
        _save_cache(domains)
        return domains
    
    return cache.get("data", [])

def _auth():
    """返回 HTTP Basic Auth 凭据"""
    return ("client", API_KEY)

def _headers():
    return {"Content-Type": "application/json"}

def _post(endpoint: str, payload: dict, silent: bool = False) -> dict:
    """统一 POST 请求，自动处理错误"""
    url = f"{BASE_URL}/{endpoint}"
    try:
        resp = requests.post(url, json=payload, auth=_auth(), headers=_headers(), timeout=15)
        if resp.status_code == 429:
            if not silent:
                console.print("[bold red]⚠ 请求过于频繁，已触发速率限制，请稍后再试[/]")
            return {}
        resp.raise_for_status()
        data = resp.json()
        error = data.get("error")
        if error:
            if not silent:
                if isinstance(error, dict):
                    msg = error.get("message", "未知错误")
                    code = error.get("code", "")
                    console.print(f"[bold red]✗ API 错误: {msg}[/] [dim]({code})[/]")
                else:
                    console.print(f"[bold red]✗ API 错误: {error}[/]")
            return {}
        return data
    except requests.exceptions.HTTPError as e:
        if not silent:
            console.print(f"[bold red]✗ HTTP 错误: {e}[/]")
        return {}
    except requests.exceptions.ConnectionError:
        if not silent:
            console.print("[bold red]✗ 无法连接到 API 服务器，请检查网络[/]")
        return {}
    except requests.exceptions.Timeout:
        if not silent:
            console.print("[bold red]✗ 请求超时[/]")
        return {}
    except Exception as e:
        if not silent:
            console.print(f"[bold red]✗ 未知错误: {e}[/]")
        return {}

def api_record_list(domain: str) -> list:
    """列出域名记录"""
    data = _post("record_list", {"domain": domain})
    if not data:
        return []
    result = data.get("result", [])
    return result if isinstance(result, list) else []

def api_record_create(domain: str, host: str, rtype: str, value: str, ttl: int) -> dict:
    """创建 DNS 记录"""
    return _post("record_create", {
        "domain": domain,
        "host": host,
        "type": rtype,
        "value": value,
        "ttl": ttl,
    })

def api_record_update(domain: str, record_id: int, value: str = None, ttl: int = None) -> dict:
    """更新 DNS 记录"""
    payload = {"domain": domain, "id": record_id}
    if value is not None:
        payload["value"] = value
    if ttl is not None:
        payload["ttl"] = ttl
    return _post("record_update", payload)

def api_record_delete(domain: str, record_id: int) -> dict:
    """删除 DNS 记录"""
    return _post("record_delete", {"domain": domain, "id": record_id})

# ── 证书中心 API ────────────────────────────────────────────────
CERT_BASE_URL = "https://vps8.zz.cd/api/client/certcenter"

def _cert_post(endpoint: str, payload: dict, silent: bool = False) -> dict:
    """证书中心专用 POST 请求"""
    url = f"{CERT_BASE_URL}/{endpoint}"
    # 证书中心 API 似乎接受 Form Data 或 JSON，根据 curl 示例，这里尝试 Form Data 或兼容处理
    # 之前的 _post 是处理 JSON 的，如果该 API 支持 JSON，则复用逻辑
    # 观察 curl 示例: -d 'domain=example.com' 是 Form Data
    try:
        resp = requests.post(url, data=payload, auth=_auth(), timeout=15)
        if resp.status_code == 429:
            if not silent:
                console.print("[bold red]⚠ 请求过于频繁，请稍后再试[/]")
            return {}
        resp.raise_for_status()
        data = resp.json()
        error = data.get("error")
        if error:
            if not silent:
                if isinstance(error, dict):
                    msg = error.get("message", "未知错误")
                    code = error.get("code", "")
                    console.print(f"[bold red]✗ API 错误: {msg}[/] [dim]({code})[/]")
                else:
                    console.print(f"[bold red]✗ API 错误: {error}[/]")
            return {}
        return data
    except Exception as e:
        if not silent:
            console.print(f"[bold red]✗ 请求出错: {e}[/]")
        return {}

def api_cert_list(domain: str) -> list:
    """列出域名证书"""
    # 证书列表查询通常会遇到“未找到”的情况，这里使用 silent 模式
    data = _cert_post("list", {"domain": domain}, silent=True)
    if not data:
        return []
    result = data.get("result")
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return [result]
    return []

def api_cert_download(domain: str, cert_type: str = "fullchain") -> dict:
    """下载证书/私钥内容"""
    return _cert_post("download", {"domain": domain, "type": cert_type})

def api_cert_renew(domain: str) -> dict:
    """发起续签"""
    return _cert_post("renew", {"domain": domain})
