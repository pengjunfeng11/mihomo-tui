#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/pengjunfeng11/mihomo-tui.git"
INSTALL_DIR="$HOME/mihomo-tui"
ALIAS_CMD="alias proxtui='cd ~/mihomo-tui && uv run proxy-tui'"

# ── Helpers ──────────────────────────────────────────────────────────

info()  { printf "\033[1;34m[INFO]\033[0m  %s\n" "$*"; }
ok()    { printf "\033[1;32m[OK]\033[0m    %s\n" "$*"; }
err()   { printf "\033[1;31m[ERR]\033[0m   %s\n" "$*" >&2; }

check_cmd() {
    command -v "$1" &>/dev/null
}

# ── Detect shell config ─────────────────────────────────────────────

detect_rc() {
    case "$(basename "$SHELL")" in
        zsh)  echo "$HOME/.zshrc" ;;
        *)    echo "$HOME/.bashrc" ;;
    esac
}

# ── Pre-checks ───────────────────────────────────────────────────────

info "Checking prerequisites..."

# Python >= 3.10
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

# git
if check_cmd git; then
    ok "git"
else
    err "git not found, please install git"
    exit 1
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

# ── Clone / Update ───────────────────────────────────────────────────

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing installation..."
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
ok "Installation complete!"
printf '\n'
info "Prerequisite: clashctl must be installed"
info "  → https://github.com/nelvko/clash-for-linux-install"
printf '\n'

# 重启当前 shell 使 alias 立即生效
exec "$SHELL"
