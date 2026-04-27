# VPS8 DNS 管理工具

通过键盘交互完成 VPS8 DNS 记录的增删改查操作。

## 功能

| 操作 | 说明 |
|------|------|
| 列出所有域名 | 查看账户下所有 DNS 区域 |
| 列出域名记录 | 查看指定域名的全部 DNS 记录 |
| 创建 DNS 记录 | 添加 A / AAAA / MX / CNAME / TXT 记录 |
| 更新 DNS 记录 | 修改已有记录的值或 TTL |
| 删除 DNS 记录 | 删除指定记录（需二次确认） |

## 环境准备

1. 安装 [uv](https://docs.astral.sh/uv/)
2. 在项目根目录创建 `.env` 文件：

```env
VPS8_API_KEY=你的API密钥
```

API 密钥获取：登录 VPS8 客户区域 → Account / Profile settings → API key。

## 快速开始

```bash
# 安装依赖
uv sync

# 运行
uv run vps8_dns.py
```

## 项目依赖

- **requests** — HTTP 请求
- **questionary** — 键盘交互选择
- **rich** — 终端美化输出
- **python-dotenv** — 读取 .env 变量

## API 参考

- Base URL: `https://vps8.zz.cd/api/client/dnsopenapi/*`
- 认证: HTTP Basic Auth (`client` / `YOUR_API_KEY`)
- 方法: 所有接口均为 POST
- 文档: https://dev.526768.xyz/doc/vps8-api.html

## 支持的记录类型

A · AAAA · MX · CNAME · TXT
