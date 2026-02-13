from pathlib import Path

import yaml

CLASHCTL_DIR = Path.home() / "clashctl"
RUNTIME_YAML = CLASHCTL_DIR / "resources" / "runtime.yaml"
MIXIN_YAML = CLASHCTL_DIR / "resources" / "mixin.yaml"
PROFILES_YAML = CLASHCTL_DIR / "resources" / "profiles.yaml"


def load_runtime() -> dict:
    with open(RUNTIME_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_secret() -> str:
    return str(load_runtime().get("secret", ""))


def get_external_controller() -> tuple[str, int]:
    raw = load_runtime().get("external-controller", "127.0.0.1:9090")
    host, _, port = raw.rpartition(":")
    if host == "0.0.0.0":
        host = "127.0.0.1"
    return host, int(port)


def get_mixed_port() -> int:
    return int(load_runtime().get("mixed-port", 7890))


def load_profiles() -> dict:
    if not PROFILES_YAML.exists():
        return {}
    with open(PROFILES_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_mixin() -> dict:
    if not MIXIN_YAML.exists():
        return {}
    with open(MIXIN_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
