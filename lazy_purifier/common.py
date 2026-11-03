import json
import os
import subprocess


def run(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    return result.stdout


def original_environment():
    env = dict(os.environ)
    saved = env.pop("LAZY_PURIFIER_ORIGINAL_ENV", None)
    if saved:
        for key, value in json.loads(saved).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
    for key in ("LAZY_PURIFIER_STATE", "LAZY_PURIFIER_FROZEN"):
        env.pop(key, None)
    return env


def load(root, companion, native):
    data = json.loads(companion.read_text())
    if data.get("version") != 1 or data.get("purifier") != "lazy":
        raise ValueError("Unsupported lazy.nvim purifier lock")
    if data["sdk"] != os.environ["LAZY_PURIFIER_SDK_VERSION"]:
        raise ValueError("Neovim/lazy.nvim SDK changed; update the lock")
    if json.loads(native.read_text()) != data["native"]:
        raise ValueError("Native lazy-lock.json changed; update the purifier lock")
    if not (root / "init.lua").is_file():
        raise ValueError("The configuration needs init.lua")
    return data
