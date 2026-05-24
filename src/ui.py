import os
import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def _pause():
    questionary.select("按回车继续...", choices=["↩ 继续"]).ask()

def _pause_and_clear():
    """操作结束后等待用户确认，然后清屏"""
    _pause()
    clear_screen()

def _print_records_table(domain: str, records: list):
    """渲染 DNS 记录表格"""
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
