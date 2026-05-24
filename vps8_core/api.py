import requests
from .config import BASE_URL, API_KEY
from .ui import console

# ── 域名缓存 ───────────────────────────────────────────────────
_domain_cache: list | None = None

def _auth():
    """返回 HTTP Basic Auth 凭据"""
    return ("client", API_KEY)

def _headers():
    return {"Content-Type": "application/json"}

def _post(endpoint: str, payload: dict) -> dict:
    """统一 POST 请求，自动处理错误"""
    url = f"{BASE_URL}/{endpoint}"
    try:
        resp = requests.post(url, json=payload, auth=_auth(), headers=_headers(), timeout=15)
        if resp.status_code == 429:
            console.print("[bold red]⚠ 请求过于频繁，已触发速率限制，请稍后再试[/]")
            return {}
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            console.print(f"[bold red]✗ API 错误: {data['error']}[/]")
            return {}
        return data
    except requests.exceptions.HTTPError as e:
        console.print(f"[bold red]✗ HTTP 错误: {e}[/]")
        return {}
    except requests.exceptions.ConnectionError:
        console.print("[bold red]✗ 无法连接到 API 服务器，请检查网络[/]")
        return {}
    except requests.exceptions.Timeout:
        console.print("[bold red]✗ 请求超时[/]")
        return {}
    except Exception as e:
        console.print(f"[bold red]✗ 未知错误: {e}[/]")
        return {}

def api_domain_list(refresh: bool = False) -> list:
    """获取域名列表（带缓存）"""
    global _domain_cache
    if _domain_cache is None or refresh:
        with console.status("[dim]正在获取域名列表...[/]", spinner="dots"):
            data = _post("domain_list", {})
        if data:
            result = data.get("result", [])
            _domain_cache = result if isinstance(result, list) else []
        else:
            _domain_cache = []
    return _domain_cache

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
