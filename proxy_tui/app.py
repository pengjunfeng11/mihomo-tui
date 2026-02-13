"""Mihomo proxy manager TUI."""

from __future__ import annotations

import asyncio

import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Input,
    Label,
    Static,
)

from . import api, config

# ── Helpers ──────────────────────────────────────────────────────────


def _is_info_node(name: str) -> bool:
    for kw in ("剩余流量", "距离下次重置", "套餐到期"):
        if kw in name:
            return True
    return False


def _delay_text(delay: int | None) -> str:
    if delay is None:
        return "timeout"
    return f"{delay}ms"


def _delay_style(delay: int | None) -> str:
    if delay is None:
        return "red"
    if delay < 200:
        return "green"
    if delay < 500:
        return "yellow"
    return "red"


async def _run_bash(cmd: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "bash", "-ic", cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode(errors="replace").strip() if stdout else ""


# ── Input modal ──────────────────────────────────────────────────────


class InputScreen(ModalScreen[str | None]):
    CSS = """
    InputScreen { align: center middle; }
    #input-dialog {
        width: 72; height: auto; padding: 1 2;
        background: $surface; border: solid $primary;
    }
    #input-dialog Label { margin-bottom: 1; }
    #input-dialog Input { width: 100%; }
    """
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, placeholder: str = "") -> None:
        super().__init__()
        self._title = title
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="input-dialog"):
            yield Label(self._title)
            yield Input(placeholder=self._placeholder, id="modal-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Main app ─────────────────────────────────────────────────────────


class ProxyTUI(App):
    TITLE = "Proxy TUI"
    CSS = """
    Screen { layout: vertical; }
    #status-bar {
        height: 1; padding: 0 1;
        background: $primary; color: $text;
    }
    #main-area { height: 1fr; }
    #group-list {
        width: 22; border-right: solid $surface-lighten-1; padding: 0;
    }
    #group-list Label { padding: 0 1; width: 100%; }
    #group-list Label:hover { background: $surface-lighten-2; }
    #group-list Label.selected { background: $accent; color: $text; }
    #node-table { height: 1fr; }
    #sub-panel {
        height: auto; max-height: 10; padding: 0 1;
        background: $surface; border-top: solid $surface-lighten-1;
        display: none;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("r", "refresh", "刷新"),
        Binding("t", "test_selected", "测速"),
        Binding("T", "test_all", "全测"),
        Binding("m", "cycle_mode", "模式"),
        Binding("o", "toggle_proxy", "开关"),
        Binding("p", "toggle_sys_proxy", "代理", show=False),
        Binding("n", "toggle_tun", "TUN", show=False),
        Binding("s", "toggle_sub", "订阅"),
        Binding("a", "add_sub", "添加", show=False),
        Binding("u", "update_sub", "更新", show=False),
        Binding("1", "switch_mode('rule')", show=False),
        Binding("2", "switch_mode('global')", show=False),
        Binding("3", "switch_mode('direct')", show=False),
    ]

    show_sub: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        self.http = httpx.AsyncClient()
        self.proxy_data: dict = {}
        self.groups: list[str] = []
        self.active_group: str = ""
        self.group_labels: dict[str, Label] = {}
        self.delays: dict[str, int | None] = {}
        self.mihomo_running: bool = False

    def compose(self) -> ComposeResult:
        yield Static(id="status-bar")
        with Horizontal(id="main-area"):
            yield VerticalScroll(id="group-list")
            with Vertical():
                yield DataTable(id="node-table")
        yield Static(id="sub-panel")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#node-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Node", "Type", "Delay", " ")
        self.load_data()

    # ── Status bar ───────────────────────────────────────────────────

    def _update_status(
        self,
        mode: str = "--",
        node: str = "--",
        port: int = 0,
        tun: bool = False,
        sys_proxy: bool = False,
    ) -> None:
        mc = {"rule": "green", "global": "yellow", "direct": "blue"}.get(mode, "white")
        parts = [
            f"[{mc}] {mode.upper()} [/]",
            f"[bold cyan]{node}[/]",
            f":{port}" if port else "",
        ]
        flags = []
        if tun:
            flags.append("[green]TUN[/]")
        if sys_proxy:
            flags.append("[green]SYS[/]")
        if flags:
            parts.append(" ".join(flags))
        if not self.mihomo_running:
            parts = ["[red bold] STOPPED [/]"]
        self.query_one("#status-bar", Static).update("  ".join(p for p in parts if p))

    # ── Data loading ─────────────────────────────────────────────────

    @work(exclusive=True, group="load")
    async def load_data(self) -> None:
        # 读取文件配置
        try:
            rt = config.load_runtime()
        except Exception:
            rt = {}
        mixed_port = int(rt.get("mixed-port", 0))
        tun_on = bool(rt.get("tun", {}).get("enable"))
        try:
            mixin = config.load_mixin()
            sys_proxy_on = bool(
                mixin.get("_custom", {}).get("system-proxy", {}).get("enable")
            )
        except Exception:
            sys_proxy_on = False

        # 尝试连接 API
        try:
            proxies_resp, configs = await asyncio.gather(
                api.get_proxies(self.http),
                api.get_configs(self.http),
            )
            self.mihomo_running = True
        except Exception:
            self.mihomo_running = False
            self._update_status()
            return

        self.proxy_data = proxies_resp.get("proxies", {})
        mode = configs.get("mode", "--")

        # 筛选 Selector 分组
        self.groups = [
            name
            for name, info in self.proxy_data.items()
            if info.get("type") == "Selector"
        ]
        if not self.groups:
            self.groups = [
                name for name, info in self.proxy_data.items() if info.get("all")
            ]

        # 渲染分组列表
        gc = self.query_one("#group-list", VerticalScroll)
        gc.remove_children()
        self.group_labels.clear()
        for g in self.groups:
            lbl = Label(g, classes="group-item")
            lbl.data_group = g  # type: ignore[attr-defined]
            self.group_labels[g] = lbl
            gc.mount(lbl)

        if self.active_group not in self.groups:
            self.active_group = self.groups[0] if self.groups else ""

        self._highlight_group(self.active_group)
        self._render_nodes()

        # 更新状态栏
        now = self.proxy_data.get(self.active_group, {}).get("now", "--")
        self._update_status(mode, now, mixed_port, tun_on, sys_proxy_on)

    def _highlight_group(self, group: str) -> None:
        for name, lbl in self.group_labels.items():
            lbl.add_class("selected") if name == group else lbl.remove_class(
                "selected"
            )

    def _render_nodes(self) -> None:
        table = self.query_one("#node-table", DataTable)

        prev_key: str | None = None
        try:
            if table.row_count > 0 and table.cursor_row >= 0:
                prev_key = list(table.rows.keys())[table.cursor_row].value
        except (IndexError, AttributeError):
            pass

        table.clear()
        info = self.proxy_data.get(self.active_group, {})
        now = info.get("now", "")
        nodes = info.get("all", [])

        row_index = 0
        restore_index = 0
        for node_name in nodes:
            if _is_info_node(node_name):
                continue
            ni = self.proxy_data.get(node_name, {})
            delay = self.delays.get(node_name)
            delay_str = _delay_text(delay) if delay is not None else ""
            cur = "✓" if node_name == now else ""
            table.add_row(node_name, ni.get("type", ""), delay_str, cur, key=node_name)
            if node_name == prev_key:
                restore_index = row_index
            row_index += 1

        if table.row_count > 0:
            table.move_cursor(row=restore_index)

    # ── Interaction ──────────────────────────────────────────────────

    def on_click(self, event) -> None:
        w = event.widget
        if hasattr(w, "data_group"):
            self.active_group = w.data_group  # type: ignore[attr-defined]
            self._highlight_group(self.active_group)
            self._render_nodes()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not event.row_key or not event.row_key.value or not self.active_group:
            return
        node_name = event.row_key.value
        try:
            await api.switch_proxy(self.http, self.active_group, node_name)
        except httpx.HTTPError as e:
            self.notify(f"切换失败: {e}", severity="error")
            return
        self.notify(f"→ {node_name}")
        self.load_data()

    # ── Actions ──────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self.delays.clear()
        self.load_data()

    @work(exclusive=True, group="proxy-toggle")
    async def action_toggle_proxy(self) -> None:
        if self.mihomo_running:
            self.notify("正在关闭...")
            await _run_bash("clashoff")
            self.notify("代理已关闭")
        else:
            self.notify("正在启动...")
            await _run_bash("clashon")
            self.notify("代理已启动")
        self.delays.clear()
        self.load_data()

    @work(exclusive=True, group="sys-proxy")
    async def action_toggle_sys_proxy(self) -> None:
        try:
            mixin = config.load_mixin()
            on = mixin.get("_custom", {}).get("system-proxy", {}).get("enable")
        except Exception:
            on = False
        if on:
            await _run_bash("clashproxy off")
            self.notify("系统代理已关闭")
        else:
            await _run_bash("clashproxy on")
            self.notify("系统代理已开启")
        self.load_data()

    @work(exclusive=True, group="tun")
    async def action_toggle_tun(self) -> None:
        try:
            rt = config.load_runtime()
            on = rt.get("tun", {}).get("enable")
        except Exception:
            on = False
        if on:
            self.notify("正在关闭 TUN...")
            output = await _run_bash("clashtun off")
        else:
            self.notify("正在开启 TUN (需要 sudo)...")
            output = await _run_bash("clashtun on")
        self.notify(output[:60] if output else "完成")
        self.delays.clear()
        self.load_data()

    @work(exclusive=True, group="test")
    async def action_test_selected(self) -> None:
        table = self.query_one("#node-table", DataTable)
        if table.cursor_row < 0:
            return
        try:
            node_name = list(table.rows.keys())[table.cursor_row].value
        except (IndexError, AttributeError):
            return
        if not node_name:
            return
        self.notify(f"测速: {node_name}...")
        delay = await api.test_delay(self.http, node_name)
        self.delays[node_name] = delay
        self.notify(f"{node_name}: {_delay_text(delay)}")
        self._render_nodes()

    @work(exclusive=True, group="test")
    async def action_test_all(self) -> None:
        info = self.proxy_data.get(self.active_group, {})
        nodes = [n for n in info.get("all", []) if not _is_info_node(n)]
        if not nodes:
            return
        total = len(nodes)
        self.notify(f"测速 {total} 个节点...")

        sem = asyncio.Semaphore(8)

        async def _test(name: str) -> None:
            async with sem:
                self.delays[name] = await api.test_delay(self.http, name)

        tasks = [asyncio.create_task(_test(n)) for n in nodes]
        for coro in asyncio.as_completed(tasks):
            await coro

        self._render_nodes()
        self.notify(f"已测试 {total} 个节点")

    @work(exclusive=True, group="mode")
    async def action_cycle_mode(self) -> None:
        modes = ["rule", "global", "direct"]
        try:
            cfgs = await api.get_configs(self.http)
            cur = cfgs.get("mode", "rule")
            idx = modes.index(cur)
        except (httpx.HTTPError, ValueError):
            idx = -1
        new_mode = modes[(idx + 1) % len(modes)]
        await self._set_mode(new_mode)

    async def action_switch_mode(self, mode: str) -> None:
        await self._set_mode(mode)

    async def _set_mode(self, mode: str) -> None:
        try:
            await api.patch_configs(self.http, {"mode": mode})
        except httpx.HTTPError as e:
            self.notify(f"模式切换失败: {e}", severity="error")
            return
        self.notify(f"模式 → {mode}")
        self.load_data()

    # ── Subscription ─────────────────────────────────────────────────

    def action_toggle_sub(self) -> None:
        self.show_sub = not self.show_sub
        panel = self.query_one("#sub-panel", Static)
        if self.show_sub:
            panel.styles.display = "block"
            self._refresh_sub_panel()
        else:
            panel.styles.display = "none"

    def _refresh_sub_panel(self) -> None:
        data = config.load_profiles()
        current = data.get("use", "")
        profiles = data.get("profiles", [])
        lines = [" [bold]订阅[/]  [dim]a:添加 u:更新[/]"]
        for p in profiles:
            pid = p.get("id", "")
            url = p.get("url", "")
            marker = "✓" if str(pid) == str(current) else " "
            short = url[:60] + "..." if len(url) > 60 else url
            lines.append(f"  {marker} [{pid}] {short}")
        if not profiles:
            lines.append("  暂无订阅")
        self.query_one("#sub-panel", Static).update("\n".join(lines))

    def action_add_sub(self) -> None:
        self.push_screen(
            InputScreen("输入订阅链接:", "https://..."), self._on_sub_url
        )

    @work(exclusive=True, group="sub")
    async def _on_sub_url(self, url: str | None) -> None:
        if not url:
            return
        self.notify("正在添加订阅...")
        output = await _run_bash(f"clashsub add '{url}'")
        self.notify("订阅已添加" if "已添加" in output else output[:80])
        if self.show_sub:
            self._refresh_sub_panel()

    @work(exclusive=True, group="sub")
    async def action_update_sub(self) -> None:
        self.notify("正在更新订阅...")
        output = await _run_bash("clashsub update")
        self.notify("订阅已更新" if "已" in output else output[:80])
        self.delays.clear()
        self.load_data()
        if self.show_sub:
            self._refresh_sub_panel()

    async def on_unmount(self) -> None:
        await self.http.aclose()


def main() -> None:
    ProxyTUI().run()


if __name__ == "__main__":
    main()
