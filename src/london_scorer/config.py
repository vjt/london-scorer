from pathlib import Path
import yaml


def load_config(path="config/zones.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text())


def load_env(path=".env") -> dict:
    env = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env
