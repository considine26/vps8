import questionary
from rich.panel import Panel
from rich.table import Table
from .api import (
    api_domain_list, api_record_list, api_record_create, 
    api_record_update, api_record_delete
)
from .ui import console, clear_screen, _pause, _print_records_table
from .config import SUPPORTED_TYPES, DEFAULT_TTL

def select_domain() -> str | None:
    """从域名列表中选择一个域名"""
    domains = api_domain_list()
    if not domains:
        console.print("[yellow]未找到任何域名，或 API 返回为空[/]")
        return None

    def _sort_key(d):
        if isinstance(d, dict):
            src = d.get("source_service", "")
            return 0 if src == "domain" else (1 if src == "dns" else 2)
        return 2

    domains.sort(key=_sort_key)

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
    idx = choices.index(selected)
    return choice_domains[idx]

def action_list_domains():
    """📋 列出所有 DNS 区域"""
    console.print()
    domains = api_domain_list(refresh=True)

    if not domains:
        console.print("[yellow]未找到任何域名[/]")
        _pause()
        return

    def _sort_key(d):
        if isinstance(d, dict):
            src = d.get("source_service", "")
            return 0 if src == "domain" else (1 if src == "dns" else 2)
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

    while True:
        choice = questionary.select(
            "操作:",
            choices=["💾 导出MD文档", "↩  返回上级"],
        ).ask()

        if choice is None or choice == "↩  返回上级":
            break

        if choice == "💾 导出MD文档":
            filename = questionary.text("请输入导出文件名 (含 .md):", default="domains.md").ask()
            if filename:
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write("# DNS 区域列表\n\n")
                        f.write("| # | 域名 | 类型 | 来源 | 创建时间 | 到期时间 |\n")
                        f.write("|---|---|---|---|---|---|\n")
                        for i, d in enumerate(domains, 1):
                            if isinstance(d, dict):
                                domain_name = d.get("domain", "")
                                platform = d.get("platform_type", "")
                                source = d.get("source_service", "")
                                created = d.get("created_at", "-")
                                expires = d.get("expires_at", "-")
                                f.write(f"| {i} | {domain_name} | {platform} | {source} | {created} | {expires} |\n")
                            else:
                                f.write(f"| {i} | {d} | | | | |\n")
                    console.print(f"[bold green]✓ 成功导出到 {filename}[/]")
                except Exception as e:
                    console.print(f"[bold red]✗ 导出失败: {e}[/]")
                _pause()

def _do_create(domain: str, records: list) -> bool:
    """➕ 创建 DNS 记录"""
    console.print(Panel.fit(f"为 [cyan bold]{domain}[/] 创建新记录", title="创建记录"))
    host = questionary.text("主机名 (如 www, @, sub):", default="").ask()
    if host is None: return None
    rtype = questionary.select("记录类型:", choices=SUPPORTED_TYPES).ask()
    if rtype is None: return None
    value = questionary.text("记录值 (如 1.2.3.4):").ask()
    if value is None: return None
    ttl_str = questionary.text("TTL (秒):", default=str(DEFAULT_TTL)).ask()
    if ttl_str is None: return None
    try:
        ttl = int(ttl_str)
    except ValueError:
        console.print("[red]TTL 必须为整数，已使用默认值 600[/]")
        ttl = DEFAULT_TTL

    confirm = questionary.confirm(f"确认创建: {host}.{domain}  {rtype} → {value}  TTL={ttl} ?").ask()
    if not confirm:
        console.print("[dim]已取消[/]")
        return None

    result = api_record_create(domain, host, rtype, value, ttl)
    return True if result else False

def _do_update(domain: str, records: list) -> bool:
    """✏️ 更新 DNS 记录"""
    if not records:
        console.print(f"[yellow]{domain} 暂无记录可更新[/]")
        return False

    id_str = questionary.text("请输入要更新的记录 ID:").ask()
    if id_str is None: return None
    try:
        record_id = int(id_str)
    except ValueError:
        console.print("[red]记录 ID 必须为整数[/]")
        return False

    target = next((r for r in records if isinstance(r, dict) and str(r.get("id")) == str(record_id)), None)
    if not target:
        console.print(f"[yellow]未找到 ID={record_id} 的记录[/]")
        return False

    console.print(f"  当前: [cyan]{target.get('host')}[/]  [magenta]{target.get('type')}[/] → [green]{target.get('value')}[/]  TTL={target.get('ttl')}")

    fields = questionary.checkbox("选择要更新的字段:", choices=["value (记录值)", "ttl (TTL)"]).ask()
    if not fields:
        console.print("[dim]已取消[/]")
        return None

    new_value, new_ttl = None, None
    if any("value" in f for f in fields):
        new_value = questionary.text("新的记录值:").ask()
        if new_value is None: return None
    if any("ttl" in f for f in fields):
        ttl_str = questionary.text("新的 TTL:", default=str(target.get("ttl", DEFAULT_TTL))).ask()
        if ttl_str is None: return None
        try:
            new_ttl = int(ttl_str)
        except ValueError:
            console.print("[red]TTL 必须为整数[/]")
            return False

    confirm = questionary.confirm(f"确认更新记录 ID={record_id} ?").ask()
    if not confirm:
        console.print("[dim]已取消[/]")
        return None

    result = api_record_update(domain, record_id, value=new_value, ttl=new_ttl)
    if result:
        console.print("[bold green]✓ 更新成功[/]")
        if new_value is not None: target["value"] = new_value
        if new_ttl is not None: target["ttl"] = new_ttl
        return True
    return False

def _do_delete(domain: str, records: list) -> bool:
    """🗑️ 删除 DNS 记录"""
    if not records:
        console.print(f"[yellow]{domain} 暂无记录可删除[/]")
        return False

    id_str = questionary.text("请输入要删除的记录 ID:").ask()
    if id_str is None: return None
    try:
        record_id = int(id_str)
    except ValueError:
        console.print("[red]记录 ID 必须为整数[/]")
        return False

    target = next((r for r in records if isinstance(r, dict) and str(r.get("id")) == str(record_id)), None)
    if not target:
        console.print(f"[yellow]未找到 ID={record_id} 的记录[/]")
        return False

    console.print(f"  将删除: [cyan]{target.get('host')}[/]  [magenta]{target.get('type')}[/] → [green]{target.get('value')}[/]  TTL={target.get('ttl')}")
    confirm = questionary.confirm(f"[bold red]⚠ 此操作不可逆！[/] 确认删除记录 ID={record_id} ?").ask()
    if not confirm:
        console.print("[dim]已取消[/]")
        return None

    result = api_record_delete(domain, record_id)
    if result:
        console.print("[bold green]✓ 删除成功[/]")
        records.remove(target)
        return True
    return False

def _record_menu(domain: str):
    """域名记录子菜单"""
    clear_screen()
    with console.status(f"[dim]正在获取 {domain} 的记录...[/]", spinner="dots"):
        records = api_record_list(domain)

    while True:
        clear_screen()
        console.print()
        _print_records_table(domain, records)

        choice = questionary.select(
            f"📡 {domain} — 操作:",
            choices=["➕ 创建 DNS", "✏️ 更新 DNS", "🗑️ 删除 DNS", "🔄 重新获取", "↩  返回上级"],
        ).ask()

        if choice is None or choice == "↩  返回上级":
            break

        if choice == "🔄 重新获取":
            with console.status(f"[dim]重新获取 {domain} 的记录...[/]", spinner="dots"):
                records = api_record_list(domain)
            continue

        try:
            res = None
            if choice == "➕ 创建 DNS":
                res = _do_create(domain, records)
                if res is True:
                    with console.status(f"[dim]正在自动重新获取 {domain} 的记录...[/]", spinner="dots"):
                        records = api_record_list(domain)
            elif choice == "✏️ 更新 DNS":
                res = _do_update(domain, records)
            elif choice == "🗑️ 删除 DNS":
                res = _do_delete(domain, records)
            
            if res is not None:
                _pause()
        except KeyboardInterrupt:
            console.print("\n[dim]操作已中断[/]")
            _pause()
        except Exception as e:
            console.print(f"[bold red]✗ 运行出错: {e}[/]")
            _pause()
