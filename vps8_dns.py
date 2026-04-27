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

# ── 域名缓存 ───────────────────────────────────────────────────
_domain_cache: list | None = None


def api_domain_list(refresh: bool = False) -> list:
    """获取域名列表（带缓存，避免重复请求）

    Args:
        refresh: 强制刷新缓存
    """
    global _domain_cache
    if _domain_cache is None or refresh:
        data = _post("domain_list", {})
        if data:
            result = data.get("result", [])
            _domain_cache = result if isinstance(result, list) else []
        else:
            _domain_cache = []
    return _domain_cache


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
    domains = api_domain_list()

    if not domains:
        console.print("[yellow]未找到任何域名，或 API 返回为空[/]")
        return None

    # 按 source_service 排序: domain 在前, dns 在后
    def _sort_key(d):
        if isinstance(d, dict):
            src = d.get("source_service", "")
            if src == "domain":
                return 0
            elif src == "dns":
                return 1
            return 2
        return 2

    domains.sort(key=_sort_key)

    # 构建选项：来源标签 + 域名
    choices = []
    choice_domains = []
    for d in domains:
        if isinstance(d, str):
            choices.append(d)
            choice_domains.append(d)
        elif isinstance(d, dict):
            name = d.get("domain", "")
            src = d.get("source_service", "")
            tag = {"domain": "📦", "dns": "🔗"}.get(src, "❓")
            choices.append(f"{tag} {name}  ({src})")
            choice_domains.append(name)

    if not choices:
        console.print("[yellow]域名列表解析为空[/]")
        return None

    if len(choices) == 1:
        console.print(f"[green]自动选择唯一域名: {choice_domains[0]}[/]")
        return choice_domains[0]

    selected = questionary.select("请选择域名:", choices=choices).ask()
    if selected is None:
        return None
    # 从选中项提取纯域名（去掉标签前缀）
    idx = choices.index(selected)
    return choice_domains[idx]


# ── 功能模块 ──────────────────────────────────────────────────────
def action_list_domains():
    """📋 列出所有 DNS 区域（domain 来源优先，dns 来源在后）"""
    console.print()
    domains = api_domain_list(refresh=True)

    if not domains:
        console.print("[yellow]未找到任何域名[/]")
        return

    # 按 source_service 排序: domain 在前, dns 在后
    def _sort_key(d):
        if isinstance(d, dict):
            src = d.get("source_service", "")
            # domain → 0 (优先), dns → 1, 其他 → 2
            if src == "domain":
                return 0
            elif src == "dns":
                return 1
            return 2
        return 2

    domains.sort(key=_sort_key)

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


def _print_records_table(domain: str, records: list):
    """渲染 DNS 记录表格（纯展示，不请求 API）"""
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
            table.add_row(
                str(r.get("id", "")),
                str(r.get("host", "")),
                str(r.get("type", "")),
                str(r.get("value", "")),
                str(r.get("ttl", "")),
                str(r.get("priority", "")),
            )

    console.print(table)



def _do_create(domain: str, records: list) -> bool:
    """➕ 创建 DNS 记录，成功后更新本地 records 列表，返回是否有变更"""
    console.print(Panel(f"为 [cyan bold]{domain}[/] 创建新记录", title="创建记录"))

    host = questionary.text("主机名 (如 www, @, sub):", default="").ask()
    if host is None:
        return False

    rtype = questionary.select("记录类型:", choices=SUPPORTED_TYPES).ask()
    if rtype is None:
        return False

    value = questionary.text("记录值 (如 1.2.3.4):").ask()
    if value is None:
        return False

    ttl_str = questionary.text("TTL (秒):", default=str(DEFAULT_TTL)).ask()
    if ttl_str is None:
        return False
    try:
        ttl = int(ttl_str)
    except ValueError:
        console.print("[red]TTL 必须为整数，已使用默认值 600[/]")
        ttl = DEFAULT_TTL

    confirm = questionary.confirm(
        f"确认创建: {host}.{domain}  {rtype} → {value}  TTL={ttl} ?"
    ).ask()
    if not confirm:
        console.print("[dim]已取消[/]")
        return False

    result = api_record_create(domain, host, rtype, value, ttl)
    if not result:
        return False

    console.print("[bold green]✓ 创建成功[/]")
    # 从 API 返回中提取新记录，加入本地列表
    new_record = result.get("result")
    if isinstance(new_record, dict):
        records.append(new_record)
    else:
        # API 未返回完整记录，用用户输入构造一条
        records.append({
            "id": new_record if new_record else "?",
            "host": host,
            "type": rtype,
            "value": value,
            "ttl": ttl,
            "priority": 0,
        })
    return True


def _do_update(domain: str, records: list) -> bool:
    """✏️ 更新 DNS 记录，成功后更新本地 records 列表，返回是否有变更"""
    if not records:
        console.print(f"[yellow]{domain} 暂无记录可更新[/]")
        return False

    id_str = questionary.text("请输入要更新的记录 ID:").ask()
    if id_str is None:
        return False
    try:
        record_id = int(id_str)
    except ValueError:
        console.print("[red]记录 ID 必须为整数[/]")
        return False

    # 在本地列表中查找
    target = None
    for r in records:
        if isinstance(r, dict) and str(r.get("id", "")) == str(record_id):
            target = r
            break
    if not target:
        console.print(f"[yellow]未找到 ID={record_id} 的记录[/]")
        return False

    # 显示当前记录
    console.print(f"  当前: [cyan]{target.get('host')}[/]  [magenta]{target.get('type')}[/] → [green]{target.get('value')}[/]  TTL={target.get('ttl')}")

    fields = questionary.checkbox(
        "选择要更新的字段:", choices=["value (记录值)", "ttl (TTL)"]
    ).ask()
    if not fields:
        console.print("[dim]已取消[/]")
        return False

    new_value = None
    new_ttl = None

    if any("value" in f for f in fields):
        new_value = questionary.text("新的记录值:").ask()
        if new_value is None:
            return False

    if any("ttl" in f for f in fields):
        ttl_str = questionary.text("新的 TTL:", default=str(target.get("ttl", DEFAULT_TTL))).ask()
        if ttl_str is None:
            return False
        try:
            new_ttl = int(ttl_str)
        except ValueError:
            console.print("[red]TTL 必须为整数[/]")
            return False

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
        return False

    result = api_record_update(domain, record_id, value=new_value, ttl=new_ttl)
    if not result:
        return False

    console.print("[bold green]✓ 更新成功[/]")
    # 更新本地列表
    if new_value is not None:
        target["value"] = new_value
    if new_ttl is not None:
        target["ttl"] = new_ttl
    return True


def _do_delete(domain: str, records: list) -> bool:
    """🗑️ 删除 DNS 记录，成功后更新本地 records 列表，返回是否有变更"""
    if not records:
        console.print(f"[yellow]{domain} 暂无记录可删除[/]")
        return False

    id_str = questionary.text("请输入要删除的记录 ID:").ask()
    if id_str is None:
        return False
    try:
        record_id = int(id_str)
    except ValueError:
        console.print("[red]记录 ID 必须为整数[/]")
        return False

    # 在本地列表中查找
    target = None
    for r in records:
        if isinstance(r, dict) and str(r.get("id", "")) == str(record_id):
            target = r
            break
    if not target:
        console.print(f"[yellow]未找到 ID={record_id} 的记录[/]")
        return False

    # 显示要删除的记录
    console.print(f"  将删除: [cyan]{target.get('host')}[/]  [magenta]{target.get('type')}[/] → [green]{target.get('value')}[/]  TTL={target.get('ttl')}")

    confirm = questionary.confirm(
        f"[bold red]⚠ 此操作不可逆！[/] 确认删除记录 ID={record_id} ?"
    ).ask()
    if not confirm:
        console.print("[dim]已取消[/]")
        return False

    result = api_record_delete(domain, record_id)
    if not result:
        return False

    console.print("[bold green]✓ 删除成功[/]")
    # 从本地列表移除
    records.remove(target)
    return True


# ── 主菜单 ──────────────────────────────────────────────────────
def _pause_and_clear():
    """操作结束后等待用户确认，然后清屏"""
    questionary.select("按回车返回...", choices=["↩ 返回"]).ask()
    os.system("cls" if os.name == "nt" else "clear")


def _record_menu(domain: str):
    """域名记录子菜单 — 本地缓存记录列表，增删改后动态刷新"""
    # 首次进入时获取一次记录
    console.print(f"\n[dim]正在获取 {domain} 的记录...[/]")
    records = api_record_list(domain)

    while True:
        # 每次循环先刷新显示记录列表
        console.print()
        _print_records_table(domain, records)

        # 记录列表下方显示操作选项
        choice = questionary.select(
            f"📡 {domain} — 操作:",
            choices=[
                "➕ 创建 DNS",
                "✏️  更新 DNS",
                "🗑️  删除 DNS",
                "🔄 重新获取",
                "↩ 返回上级",
            ],
        ).ask()

        if choice is None or choice == "↩ 返回上级":
            break

        if choice == "🔄 重新获取":
            console.print(f"\n[dim]重新获取 {domain} 的记录...[/]")
            records = api_record_list(domain)
            continue

        try:
            if choice == "➕ 创建 DNS":
                changed = _do_create(domain, records)
            elif choice == "✏️  更新 DNS":
                changed = _do_update(domain, records)
            elif choice == "🗑️  删除 DNS":
                changed = _do_delete(domain, records)
            else:
                changed = False
        except KeyboardInterrupt:
            console.print("\n[dim]操作已中断[/]")
            continue
        except Exception as e:
            console.print(f"[bold red]✗ 运行出错: {e}[/]")
            continue

        # 操作完成后清屏，循环回到顶部重新渲染列表
        os.system("cls" if os.name == "nt" else "clear")


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

    while True:
        choice = questionary.select(
            "请选择操作:",
            choices=[
                "📋 查看域名",
                "📡 域名记录",
                "🔄 刷新缓存",
                "❌ 退出脚本",
            ],
        ).ask()

        if choice is None or choice == "❌ 退出脚本":
            console.print("[dim]再见！[/]")
            break

        if choice == "📋 查看域名":
            try:
                action_list_domains()
            except KeyboardInterrupt:
                console.print("\n[dim]操作已中断[/]")
            except Exception as e:
                console.print(f"[bold red]✗ 运行出错: {e}[/]")
            _pause_and_clear()

        elif choice == "📡 域名记录":
            domain = select_domain()
            if domain:
                _record_menu(domain)

        elif choice == "🔄 刷新缓存":
            api_domain_list(refresh=True)
            console.print("[green]✓ 域名缓存已刷新[/]")
            _pause_and_clear()


if __name__ == "__main__":
    main()
