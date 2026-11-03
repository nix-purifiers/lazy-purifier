import json
import os
from pathlib import Path
import subprocess


def configure(
    root,
    state,
    core,
    plugins,
    lockfile,
    expected,
    frozen,
    source_native=None,
    explicit=False,
    persistent=None,
):
    state.mkdir(parents=True, exist_ok=True)
    storage = persistent or state
    env = dict(os.environ)
    names = (
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
        "XDG_STATE_HOME",
        "NVIM_APPNAME",
        "LUA_PATH",
        "LUA_CPATH",
    )
    if "LAZY_PURIFIER_ORIGINAL_ENV" not in env:
        env["LAZY_PURIFIER_ORIGINAL_ENV"] = json.dumps({n: env.get(n) for n in names})
    env.update(
        XDG_CONFIG_HOME=str(root.parent),
        NVIM_APPNAME=root.name,
        XDG_DATA_HOME=str(storage / "data"),
        XDG_CACHE_HOME=str(storage / "cache"),
        XDG_STATE_HOME=str(storage / "state"),
    )
    env.pop("LUA_PATH", None)
    env.pop("LUA_CPATH", None)
    bootstrap = storage / "data" / root.name / "lazy/lazy.nvim"
    bootstrap.parent.mkdir(parents=True, exist_ok=True)
    if bootstrap.exists() or bootstrap.is_symlink():
        if bootstrap.resolve() != Path(core).resolve():
            raise ValueError("Private lazy.nvim bootstrap differs from the Nix SDK")
    else:
        bootstrap.symlink_to(core, target_is_directory=True)
    context = dict(
        sourceNative=str(source_native or root / "lazy-lock.json"),
        sourceExplicit=explicit,
        plugins=str(plugins),
        lockfile=str(lockfile),
        status=str(state / "status.json"),
        frozen=frozen,
        expected=expected,
    )
    context_file = state / "context.json"
    context_file.write_text(json.dumps(context))
    env["LAZY_PURIFIER_STATE"] = str(context_file)
    if frozen:
        env["LAZY_PURIFIER_FROZEN"] = "1"
    else:
        env.pop("LAZY_PURIFIER_FROZEN", None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    count = int(env.get("GIT_CONFIG_COUNT", "0"))
    if frozen:
        for path in Path(plugins).iterdir():
            env["GIT_CONFIG_KEY_" + str(count)] = "safe.directory"
            env["GIT_CONFIG_VALUE_" + str(count)] = str(path.resolve())
            count += 1
    env["GIT_CONFIG_COUNT"] = str(count)
    return env


def launch(binary, root, state, core, env, args, finalizer=None):
    status = state / "status.json"
    status.unlink(missing_ok=True)
    env["LAZY_PURIFIER_CORE"] = str(core)
    bootstrap = Path(__file__).parent.parent / "native/bootstrap.lua"
    command = [
        str(binary),
        "--cmd",
        "lua dofile(" + json.dumps(str(bootstrap), ensure_ascii=False) + ")",
        "-u",
        str(root / "init.lua"),
    ]
    if finalizer:
        command += [
            "--headless",
            "-c",
            "lua dofile(" + json.dumps(str(finalizer), ensure_ascii=False) + ")",
            "-c",
            "qa!",
        ]
    else:
        command += args
    result = subprocess.call(command, env=env)
    if not status.exists():
        return result or 1
    report = json.loads(status.read_text())
    return result if report.get("valid") else result or 1
