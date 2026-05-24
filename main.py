#!/usr/bin/env python3
import sys
import questionary
from rich.panel import Panel

from vps8_core.config import API_KEY
from vps8_core.ui import console, clear_screen, _pause, _pause_and_clear
from vps8_core.api import api_domain_list
from vps8_core.actions import action_list_domains, select_domain, _record_menu

def main():
    if not API_KEY:
        console.print("[bold red]✗ 未检测到 VPS8_API_KEY，请在 .env 文件中配置[/]")
        sys.exit(1)

    while True:
        clear_screen()
        console.print(Panel.fit(
            "[bold cyan]VPS8 DNS 管理工具[/]\n"
            "[dim]支持域名记录增删改查[/]",
            title="🌐 VPS8 DNS",
            border_style="cyan",
        ))

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
                _pause()
            except Exception as e:
                console.print(f"[bold red]✗ 运行出错: {e}[/]")
                _pause()

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
