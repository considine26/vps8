#!/usr/bin/env python3
"""VPS8 DNS OpenAPI 交互式管理工具

通过键盘交互完成域名 DNS 记录的增删改查操作。
API 文档: https://dev.526768.xyz/doc/vps8-api.html
"""

import os
import sys

import questionary
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# ── 初始化 ──────────────────────────────────────────────────────
load_dotenv()
console = Console()

BASE_URL = "https://vps8.zz.cd/api/client/dnsopenapi"
API_KEY = os.getenv("VPS8_API_KEY", "")

SUPPORTED_TYPES = ["A", "AAAA", "MX", "CNAME", "TXT"]
DEFAULT_TTL = 600


# ── API 层 ──────────────────────────────────────────────────────
def _auth():
    """返回 HTTP Basic Auth 凭据"""
    return ("client", API_KEY)


def _headers():
    return {"Content-Type": "application/json"}


def _post(endpoint: str, payload: dict) -> dict:
    """统一 POST 请求，自动处理错误

    API 返回格式: {"result": ..., "error": null}
    出错时: {"result": null, "error": "错误信息"}
    """
    url = f"{BASE_URL}/{endpoint}"
    try:
        resp = requests.post(url, json=payload, auth=_auth(), headers=_headers(), timeout=15)
        if resp.status_code == 429:
            console.print("[bold red]⚠ 请求过于频繁，已触发速率限制，请稍后再试[/]")
            return {}
        resp.raise_for_status()
        data = resp.json()
        # 检查 API 层面的错误
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


def api_domain_list() -> list:
    """列出所有 DNS 区域"""
    data = _post("domain_list", {})
    if not data:
        return []
    # API 返回格式: {"result": [...], "error": null}
    result = data.get("result", [])
    if isinstance(result, list):
        return result
    return []


def api_record_list(domain: str) -> list:
    """列出域名记录"""
    data = _post("record_list", {"domain": domain})
    if not data:
        return []
    # API 返回格式: {"result": [...], "error": null}
    result = data.get("result", [])
    if isinstance(result, list):
        return result
    return []


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


# ── 选择域名 ──────────────────────────────────────────────────────
def select_domain() -> str | None:
    """从域名列表中选择一个域名，返回域名文本或 None"""
    console.print("\n[dim]正在获取域名列表...[/]")
    domains = api_domain_list()

    if not domains:
        console.print("[yellow]未找到任何域名，或 API 返回为空[/]")
        return None

    # 兼容不同返回格式：可能是字符串列表，也可能是字典列表
    choices = []
    for d in domains:
        if isinstance(d, str):
            choices.append(d)
        elif isinstance(d, dict):
            name = d.get("domain", d.get("name", d.get("id", str(d))))
            choices.append(name)

    if not choices:
        console.print("[yellow]域名列表解析为空[/]")
        return None

    if len(choices) == 1:
        console.print(f"[green]自动选择唯一域名: {choices[0]}[/]")
        return choices[0]

    return questionary.select("请选择域名:", choices=choices).ask()


# ── 功能模块 ──────────────────────────────────────────────────────
def action_list_domains():
    """📋 列出所有 DNS 区域"""
    console.print()
    domains = api_domain_list()

    if not domains:
        console.print("[yellow]未找到任何域名[/]")
        return

    table = Table(title="DNS 区域列表", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("域名", style="cyan bold")
    table.add_column("类型", style="magenta")
    table.add_column("来源", style="green")
    table.add_column("创建时间", style="yellow")
    table.add_column("到期时间", style="yellow")

    for i, d in enumerate(domains, 1):
        if isinstance(d, dict):
            domain_name = d.get("domain", "")
            platform = d.get("platform_type", "")
            source = d.get("source_service", "")
            created = d.get("created_at", "-")
            expires = d.get("expires_at", "-")
            table.add_row(str(i), domain_name, platform, source, created, expires)
        else:
            table.add_row(str(i), str(d), "", "", "", "")

    console.print(table)


def action_list_records():
    """📋 列出域名记录"""
    domain = select_domain()
    if not domain:
        return

    console.print(f"\n[dim]正在获取 {domain} 的记录...[/]")
    records = api_record_list(domain)

    if not records:
        console.print(f"[yellow]{domain} 暂无记录[/]")
        return

    table = Table(title=f"DNS 记录 — {domain}", show_lines=True)
    table.add_column("ID", style="dim", width=8)
    table.add_column("主机名", style="cyan bold")
    table.add_column("类型", style="magenta")
    table.add_column("值", style="green")
    table.add_column("TTL", style="yellow", justify="right")
    table.add_column("优先级", style="blue", justify="right")

    for r in records:
        if isinstance(r, dict):
            rid = r.get("id", "")
            host = r.get("host", "")
            rtype = r.get("type", "")
            value = r.get("value", "")
            ttl = r.get("ttl", "")
            priority = r.get("priority", "")
            table.add_row(str(rid), str(host), str(rtype), str(value), str(ttl), str(priority))
        else:
            table.add_row("", str(r), "", "", "", "")

    console.print(table)


def action_create_record():
    """➕ 创建 DNS 记录"""
    domain = select_domain()
    if not domain:
        return

    console.print(Panel(f"为 [cyan bold]{domain}[/] 创建新记录", title="创建记录"))

    host = questionary.text("主机名 (如 www, @, sub):", default="").ask()
    if host is None:
        return

    rtype = questionary.select("记录类型:", choices=SUPPORTED_TYPES).ask()
    if rtype is None:
        return

    value = questionary.text("记录值 (如 1.2.3.4):").ask()
    if value is None:
        return

    ttl_str = questionary.text("TTL (秒):", default=str(DEFAULT_TTL)).ask()
    if ttl_str is None:
        return
    try:
        ttl = int(ttl_str)
    except ValueError:
        console.print("[red]TTL 必须为整数，已使用默认值 600[/]")
        ttl = DEFAULT_TTL

    # 确认
    confirm = questionary.confirm(
        f"确认创建: {host}.{domain}  {rtype} → {value}  TTL={ttl} ?"
    ).ask()
    if not confirm:
        console.print("[dim]已取消[/]")
        return

    result = api_record_create(domain, host, rtype, value, ttl)
    if result:
        console.print(f"[bold green]✓ 创建成功[/]  {result}")


def action_update_record():
    """✏️ 更新 DNS 记录"""
    domain = select_domain()
    if not domain:
        return

    # 先列出记录方便选择
    console.print(f"\n[dim]正在获取 {domain} 的记录...[/]")
    records = api_record_list(domain)
    if not records:
        console.print(f"[yellow]{domain} 暂无记录可更新[/]")
        return

    # 展示记录
    table = Table(title=f"当前记录 — {domain}", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("ID", style="dim", width=8)
    table.add_column("主机名", style="cyan")
    table.add_column("类型", style="magenta")
    table.add_column("值", style="green")
    table.add_column("TTL", style="yellow")
    for i, r in enumerate(records, 1):
        if isinstance(r, dict):
            table.add_row(
                str(i),
                str(r.get("id", "")),
                str(r.get("host", "")),
                str(r.get("type", "")),
                str(r.get("value", "")),
                str(r.get("ttl", "")),
            )
    console.print(table)

    # 让用户输入要更新的记录 ID
    id_str = questionary.text("请输入要更新的记录 ID:").ask()
    if id_str is None:
        return
    try:
        record_id = int(id_str)
    except ValueError:
        console.print("[red]记录 ID 必须为整数[/]")
        return

    # 选择要更新的字段
    fields = questionary.checkbox(
        "选择要更新的字段:", choices=["value (记录值)", "ttl (TTL)"]
    ).ask()
    if not fields:
        console.print("[dim]已取消[/]")
        return

    new_value = None
    new_ttl = None

    if any("value" in f for f in fields):
        new_value = questionary.text("新的记录值:").ask()
        if new_value is None:
            return

    if any("ttl" in f for f in fields):
        ttl_str = questionary.text("新的 TTL:", default=str(DEFAULT_TTL)).ask()
        if ttl_str is None:
            return
        try:
            new_ttl = int(ttl_str)
        except ValueError:
            console.print("[red]TTL 必须为整数[/]")
            return

    # 确认
    parts = []
    if new_value is not None:
        parts.append(f"value={new_value}")
    if new_ttl is not None:
        parts.append(f"ttl={new_ttl}")
    confirm = questionary.confirm(
        f"确认更新记录 ID={record_id} ({', '.join(parts)}) ?"
    ).ask()
    if not confirm:
        console.print("[dim]已取消[/]")
        return

    result = api_record_update(domain, record_id, value=new_value, ttl=new_ttl)
    if result:
        console.print(f"[bold green]✓ 更新成功[/]  {result}")


def action_delete_record():
    """🗑️ 删除 DNS 记录"""
    domain = select_domain()
    if not domain:
        return

    # 先列出记录
    console.print(f"\n[dim]正在获取 {domain} 的记录...[/]")
    records = api_record_list(domain)
    if not records:
        console.print(f"[yellow]{domain} 暂无记录可删除[/]")
        return

    # 展示记录
    table = Table(title=f"当前记录 — {domain}", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("ID", style="dim", width=8)
    table.add_column("主机名", style="cyan")
    table.add_column("类型", style="magenta")
    table.add_column("值", style="green")
    for i, r in enumerate(records, 1):
        if isinstance(r, dict):
            table.add_row(
                str(i),
                str(r.get("id", "")),
                str(r.get("host", "")),
                str(r.get("type", "")),
                str(r.get("value", "")),
            )
    console.print(table)

    # 输入要删除的 ID
    id_str = questionary.text("请输入要删除的记录 ID:").ask()
    if id_str is None:
        return
    try:
        record_id = int(id_str)
    except ValueError:
        console.print("[red]记录 ID 必须为整数[/]")
        return

    confirm = questionary.confirm(
        f"[bold red]⚠ 此操作不可逆！[/] 确认删除记录 ID={record_id} ?"
    ).ask()
    if not confirm:
        console.print("[dim]已取消[/]")
        return

    result = api_record_delete(domain, record_id)
    if result:
        console.print(f"[bold green]✓ 删除成功[/]  {result}")


# ── 主菜单 ──────────────────────────────────────────────────────
def main():
    if not API_KEY:
        console.print("[bold red]✗ 未检测到 VPS8_API_KEY，请在 .env 文件中配置[/]")
        sys.exit(1)

    console.print(Panel(
        "[bold cyan]VPS8 DNS 管理工具[/]\n"
        "[dim]键盘交互 · 支持域名记录增删改查[/]",
        title="🌐 VPS8 DNS",
        border_style="cyan",
    ))

    actions = {
        "📋 列出所有域名": action_list_domains,
        "📋 列出域名记录": action_list_records,
        "➕ 创建 DNS 记录": action_create_record,
        "✏️  更新 DNS 记录": action_update_record,
        "🗑️  删除 DNS 记录": action_delete_record,
        "❌ 退出": None,
    }

    while True:
        choice = questionary.select(
            "请选择操作:",
            choices=list(actions.keys()),
        ).ask()

        if choice is None or choice == "❌ 退出":
            console.print("[dim]再见！[/]")
            break

        handler = actions[choice]
        if handler:
            try:
                handler()
            except KeyboardInterrupt:
                console.print("\n[dim]操作已中断[/]")
            except Exception as e:
                console.print(f"[bold red]✗ 运行出错: {e}[/]")


if __name__ == "__main__":
    main()
