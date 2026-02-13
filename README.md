# Proxy TUI

Terminal UI for managing [mihomo](https://github.com/MetaCubeX/mihomo) proxy on Linux.

基于 [textual](https://github.com/Textualize/textual) 构建的终端代理管理工具，配合 [clashctl](https://github.com/nelvko/clash-for-linux-install) 使用，在终端内完成节点切换、测速、订阅管理等全部操作。

![proxy-tui](https://img.shields.io/badge/python-3.10+-blue) ![license](https://img.shields.io/badge/license-MIT-green)

## Features

- **节点管理** — 按分组浏览节点，Enter 一键切换，实时显示当前选中
- **延迟测速** — 单节点测速 / 全组并发测速，结果直接展示在列表中
- **模式切换** — Rule / Global / Direct 三种模式循环切换
- **代理开关** — 启动 / 停止 mihomo 内核
- **系统代理** — 开启 / 关闭 shell 环境变量代理
- **TUN 模式** — 开启 / 关闭透明代理（需 sudo）
- **订阅管理** — 查看订阅列表、添加新订阅、更新已有订阅

## Prerequisites

- Linux
- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (推荐) 或 pip
- [clashctl](https://github.com/nelvko/clash-for-linux-install) 已安装并配置完成
  - mihomo 内核位于 `~/clashctl/bin/mihomo`
  - 配置文件位于 `~/clashctl/resources/`
  - shell 命令已加载（`clashon`, `clashoff`, `clashsub` 等）

## Install

```bash
git clone https://github.com/<your-username>/proxy-tui.git ~/proxy-tui
cd ~/proxy-tui
uv sync
```

添加快捷命令到 shell 配置（`.bashrc` / `.zshrc`）：

```bash
alias proxtui='cd ~/proxy-tui && uv run proxy-tui'
```

## Usage

```bash
proxtui
```

### Keybindings

| Key | Action |
|-----|--------|
| `Enter` | 切换到选中节点 |
| `t` | 测速当前节点 |
| `T` | 测速全部节点 |
| `m` | 切换模式 (rule → global → direct) |
| `1` `2` `3` | 直接切换 rule / global / direct |
| `o` | 启动 / 停止代理 |
| `p` | 开关系统代理 |
| `n` | 开关 TUN 模式 |
| `s` | 显示 / 隐藏订阅面板 |
| `a` | 添加订阅 |
| `u` | 更新订阅 |
| `r` | 刷新数据 |
| `q` | 退出 |

### Status Bar

顶部状态栏显示：

```
 RULE  🇯🇵Japan 01  :7890  TUN  SYS
```

- 当前模式（彩色标识）
- 当前使用的节点
- 代理端口
- TUN / SYS 标记（启用时显示绿色）

## Project Structure

```
proxy-tui/
├── pyproject.toml          # 项目配置 & 依赖
├── proxy_tui/
│   ├── __init__.py
│   ├── __main__.py         # python -m proxy_tui 入口
│   ├── app.py              # TUI 主界面
│   ├── api.py              # mihomo RESTful API 客户端
│   └── config.py           # 配置文件读取
├── LICENSE
└── README.md
```

## Configuration

本工具从 clashctl 的配置文件中读取连接信息：

| File | Purpose |
|------|---------|
| `~/clashctl/resources/runtime.yaml` | API 地址、端口、secret、TUN 状态 |
| `~/clashctl/resources/mixin.yaml` | 系统代理开关状态 |
| `~/clashctl/resources/profiles.yaml` | 订阅列表 |

如果你的 clashctl 安装在其他路径，修改 `proxy_tui/config.py` 中的 `CLASHCTL_DIR` 即可。

## License

[MIT](LICENSE)
