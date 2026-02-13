#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/pengjunfeng11/mihomo-tui.git"
INSTALL_DIR="$HOME/mihomo-tui"
ALIAS_CMD="alias proxtui='cd ~/mihomo-tui && uv run proxy-tui'"

CLASHCTL_REPO="https://github.com/nelvko/clash-for-linux-install.git"
CLASHCTL_DIR="$HOME/clashctl"
GH_PROXY="https://gh-proxy.org"

# ── Helpers ──────────────────────────────────────────────────────────

info()  { printf "\033[1;34m[INFO]\033[0m  %s\n" "$*"; }
ok()    { printf "\033[1;32m[OK]\033[0m    %s\n" "$*"; }
warn()  { printf "\033[1;33m[WARN]\033[0m  %s\n" "$*"; }
err()   { printf "\033[1;31m[ERR]\033[0m   %s\n" "$*" >&2; }

check_cmd() {
    command -v "$1" &>/dev/null
}

detect_rc() {
    case "$(basename "$SHELL")" in
        zsh)  echo "$HOME/.zshrc" ;;
        *)    echo "$HOME/.bashrc" ;;
    esac
}

# ── Pre-checks ───────────────────────────────────────────────────────

info "Checking prerequisites..."

if check_cmd python3; then
    py_ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if python3 -c 'import sys; exit(0 if sys.version_info >= (3,10) else 1)'; then
        ok "Python $py_ver"
    else
        err "Python >= 3.10 required, found $py_ver"
        exit 1
    fi
else
    err "Python3 not found, please install Python >= 3.10"
    exit 1
fi

if check_cmd git; then
    ok "git"
else
    err "git not found, please install git"
    exit 1
fi

if check_cmd curl; then
    ok "curl"
else
    err "curl not found, please install curl"
    exit 1
fi

# ── Install clashctl ─────────────────────────────────────────────────

if [ -d "$CLASHCTL_DIR/bin" ] && [ -d "$CLASHCTL_DIR/scripts" ]; then
    ok "clashctl already installed"
else
    info "clashctl not found, installing..."
    TMPDIR=$(mktemp -d)
    # 尝试直连，失败则用加速
    if git clone --branch master --depth 1 --quiet "$CLASHCTL_REPO" "$TMPDIR" 2>/dev/null; then
        ok "Cloned clashctl"
    else
        warn "Direct clone failed, trying proxy..."
        git clone --branch master --depth 1 --quiet "${GH_PROXY}/${CLASHCTL_REPO}" "$TMPDIR"
        ok "Cloned clashctl via proxy"
    fi
    info "Running clashctl installer..."
    printf '\n'
    (cd "$TMPDIR" && bash install.sh)
    printf '\n'
    rm -rf "$TMPDIR"
    # 重新加载 shell 函数
    RC_FILE=$(detect_rc)
    # shellcheck disable=SC1090
    source "$RC_FILE" 2>/dev/null || true
    ok "clashctl installed"
fi

# ── Install uv ───────────────────────────────────────────────────────

if check_cmd uv; then
    ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"
else
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if check_cmd uv; then
        ok "uv installed"
    else
        err "uv installation failed"
        exit 1
    fi
fi

# ── Clone / Update mihomo-tui ────────────────────────────────────────

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating mihomo-tui..."
    git -C "$INSTALL_DIR" pull --rebase --quiet
    ok "Updated"
else
    if [ -d "$INSTALL_DIR" ]; then
        err "$INSTALL_DIR already exists but is not a git repo"
        err "Please remove it first: rm -rf $INSTALL_DIR"
        exit 1
    fi
    info "Cloning mihomo-tui..."
    git clone --quiet "$REPO" "$INSTALL_DIR"
    ok "Cloned to $INSTALL_DIR"
fi

# ── Install deps ─────────────────────────────────────────────────────

info "Installing dependencies..."
(cd "$INSTALL_DIR" && uv sync --quiet)
ok "Dependencies installed"

# ── Shell alias ──────────────────────────────────────────────────────

RC_FILE=$(detect_rc)

if grep -qF 'proxtui' "$RC_FILE" 2>/dev/null; then
    ok "Alias already in $RC_FILE"
else
    printf '\n# mihomo-tui\n%s\n' "$ALIAS_CMD" >> "$RC_FILE"
    ok "Alias added to $RC_FILE"
fi

# ── Done ─────────────────────────────────────────────────────────────

printf '\n'
ok "Installation complete! Run 'proxtui' to start."
printf '\n'

# 重启当前 shell 使 alias 立即生效
exec "$SHELL"
