import os
import questionary
from rich.panel import Panel
from rich.table import Table
from .api import (
    api_domain_list, api_record_list, api_record_create, 
    api_record_update, api_record_delete,
    api_cert_list, api_cert_download, api_cert_renew
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

def _print_certs_table(domain: str, certs: list):
    """渲染证书列表表格"""
    if not certs:
        console.print(f"[yellow]⚠ {domain} 暂无证书信息[/]")
        return

    table = Table(title=f"证书信息 — {domain}", show_lines=True)
    table.add_column("ID", style="dim")
    table.add_column("域名", style="cyan")
    table.add_column("状态", style="bold green")
    table.add_column("剩余天数", style="magenta")
    table.add_column("生效时间", style="blue")
    table.add_column("到期时间", style="yellow")

    for c in certs:
        if isinstance(c, dict):
            # API 返回字段：cert_id, domain, status, days_left, not_before, not_after
            table.add_row(
                str(c.get("cert_id", "")),
                str(c.get("domain", "")),
                str(c.get("status", "")),
                str(c.get("days_left", "")),
                str(c.get("not_before", "")),
                str(c.get("not_after", "")),
            )
    console.print(table)

def action_manage_certs():
    """🔒 证书管理逻辑"""
    domain = select_domain()
    if not domain:
        return

    while True:
        clear_screen()
        with console.status(f"[dim]正在获取 {domain} 的证书...[/]", spinner="dots"):
            certs = api_cert_list(domain)
        
        _print_certs_table(domain, certs)

        choice = questionary.select(
            f"🔒 {domain} — 证书管理:",
            choices=[
                "📥 下载证书内容",
                "🔄 发起续签",
                "↩  返回上级",
            ],
        ).ask()

        if choice is None or choice == "↩  返回上级":
            break

        if choice == "📥 下载证书内容":
            types_to_download = [
                ("Fullchain", "fullchain"),
                ("Certificate", "cert"),
                ("Private Key", "privkey"),
                ("Bundle", "bundle"),
            ]
            
            confirm = questionary.confirm(f"确认要下载 {domain} 的所有证书文件 (Fullchain, Cert, Key, Bundle) 吗？").ask()
            if not confirm:
                continue

            # 确保目录存在: cert/<domain>/
            target_dir = os.path.join("cert", domain)
            os.makedirs(target_dir, exist_ok=True)
            
            success_count = 0
            with console.status(f"[bold cyan]正在批量下载 {domain} 的证书文件...[/]", spinner="dots"):
                for label, t_type in types_to_download:
                    res = api_cert_download(domain, t_type)
                    if res and res.get("result"):
                        raw_result = res.get("result")
                        
                        if isinstance(raw_result, dict):
                            content = raw_result.get("content", "")
                            filename = raw_result.get("filename", f"{domain}_{t_type}.pem")
                        else:
                            content = str(raw_result)
                            filename = f"{domain}_{t_type}.pem"
                        
                        if content:
                            full_path = os.path.join(target_dir, filename)
                            try:
                                with open(full_path, "w", encoding="utf-8") as f:
                                    f.write(content)
                                console.print(f"[green]✓[/] 已保存 {label}: [dim]{full_path}[/]")
                                success_count += 1
                            except Exception as e:
                                console.print(f"[red]✗[/] 保存 {label} 失败: {e}")
                    else:
                        console.print(f"[red]✗[/] 下载 {label} 失败")

            console.print(f"\n[bold green]批量下载完成！成功: {success_count}/{len(types_to_download)}[/]")
            console.print(f"[dim]文件已存放在: {os.path.abspath(target_dir)}[/]")
            _pause()

        elif choice == "🔄 发起续签":
            if questionary.confirm(f"确认要为 {domain} 发起续签吗?").ask():
                with console.status("[dim]正在发起续签请求...[/]", spinner="dots"):
                    res = api_cert_renew(domain)
                
                if res:
                    result_data = res.get("result", {})
                    if isinstance(result_data, dict) and result_data.get("message"):
                        msg = result_data.get("message")
                        console.print(Panel(msg, title="续签反馈", border_style="cyan"))
                    else:
                        console.print("[bold green]✓ 续签请求已提交[/]")
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
