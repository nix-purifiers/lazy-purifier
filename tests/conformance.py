import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)

with tempfile.TemporaryDirectory(prefix="lazy proof with spaces ") as temporary:
    temp = Path(temporary)
    root = temp / "configuration/nvim"
    shutil.copytree(repo / "examples/minimal", root)
    ambient = temp / "ambient-data/nvim/lazy/plenary.nvim/keep.txt"
    ambient.parent.mkdir(parents=True)
    ambient.write_text("existing checkout\n")
    env = dict(
        os.environ,
        LAZY_PURIFIER_PROJECT=str(root),
        XDG_CACHE_HOME=str(temp / "cache"),
        XDG_DATA_HOME=str(temp / "ambient-data"),
        XDG_STATE_HOME=str(temp / "ambient-state"),
        LUA_PATH="/nonexistent/poison/?.lua",
        LUA_CPATH="/nonexistent/poison/?.so",
    )

    def call(name, *args, success=True, extra=None, cwd=None):
        result = subprocess.run(
            [sdk / "bin" / name, *args],
            cwd=cwd or root,
            env=dict(env, **(extra or {})),
            text=True,
            capture_output=True,
            timeout=300,
        )
        assert (result.returncode == 0) == success, result
        return result

    result_file = temp / "result.json"
    lua = (
        "local p=require('plenary.path');assert(type(require('popup').create)=='function');vim.fn.writefile({vim.json.encode({answer=tonumber(p:new(tostring(vim.g.answer)).filename),source=debug.getinfo(p.new).source})},"
        + json.dumps(str(result_file))
        + ")"
    )

    def editor(extra=None, cwd=None):
        result_file.unlink(missing_ok=True)
        call(
            "nvim", "--headless", "-c", "lua " + lua, "-c", "qa!", extra=extra, cwd=cwd
        )
        data = json.loads(result_file.read_text())
        assert data["source"].startswith("@/nix/store/"), data
        return data["answer"]

    companion = root / "lazy-purifier.lock.json"
    native = root / "lazy-lock.json"
    before = companion.read_bytes(), native.read_bytes()
    init = root / "init.lua"
    original = init.read_text()
    for value in (42, 43, 42):
        init.write_text(
            original.replace("vim.g.answer = 42", "vim.g.answer = " + str(value))
        )
        assert editor() == value
    assert before == (companion.read_bytes(), native.read_bytes())
    assert ambient.read_text() == "existing checkout\n"
    subdir = root / "subdir"
    subdir.mkdir()
    assert editor(cwd=subdir) == 42
    profiles = list((temp / "cache/lazy-purifier").glob("*/*/environment-profile"))
    assert len(profiles) == 1
    profile = profiles[0]
    closure = subprocess.check_output(
        ["nix-store", "--query", "--requisites", str(profile.resolve())], text=True
    )
    assert str(sdk) in closure
    persistent = profile.parent / "editor/state/nvim/purifier-proof"
    persistent.parent.mkdir(parents=True, exist_ok=True)
    persistent.write_text("preserved editor state")
    assert editor() == 42
    assert persistent.read_text() == "preserved editor state"
    output = Path(json.loads(profile.read_text())["output"])
    manifest = json.loads((output / "manifest.json").read_text())
    assert not (Path(manifest["plugins"]).stat().st_mode & 0o222)
    init.write_text(
        original.replace(
            '"nvim-lua/popup.nvim"',
            '"nvim-lua/popup.nvim", url="https://github.com/fixture/wrong.git"',
        )
    )
    denied = call("nvim", "--headless", "-c", "qa!", success=False)
    assert "selection changed" in denied.stderr, denied
    init.write_text(original)
    denied = call(
        "nvim", "--headless", "-c", "Lazy! update", "-c", "qa!", success=False
    )
    assert "Nix-resolved" in denied.stderr, denied
    call(
        "nvim",
        "--headless",
        "-c",
        "Lazy! log",
        "-c",
        "lua require('lazy.help').update()",
        "-c",
        "qa!",
    )

    # Editor commands keep normal networking; no socket/git/curl blockers.
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"42")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        network = (
            "local r=vim.system({'"
            + sys.executable
            + "','-c',\"import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:"
            + str(server.server_port)
            + "/').read().decode())\"},{text=true}):wait();assert(r.code==0);vim.fn.writefile({vim.trim(r.stdout)},"
            + json.dumps(str(result_file))
            + ")"
        )
        call("nvim", "--headless", "-c", "lua " + network, "-c", "qa!")
        assert result_file.read_text().strip() == "42"
    finally:
        server.shutdown()
        server.server_close()
    external_companion, external_native = temp / "companion.json", temp / "native.json"
    companion.rename(external_companion)
    native.rename(external_native)
    external = {
        "LAZY_PURIFIER_LOCK": str(external_companion),
        "LAZY_PURIFIER_NATIVE_LOCK": str(external_native),
    }
    assert editor(extra=external) == 42
    archive = Path(
        call(
            "lazy-purifier",
            "bundle",
            "--lock",
            str(external_companion),
            "--native-lock",
            str(external_native),
        ).stdout.strip()
    )
    assert archive.is_file()
    # Actual native release, unmodified lazy.nvim, ordinary Neovim.
    consumer = temp / "consumer/nvim"
    consumer.mkdir(parents=True)
    with tarfile.open(archive) as released:
        released.extractall(consumer, filter="data")
    (consumer / "lazy-lock.json").write_bytes(external_native.read_bytes())
    native_data = temp / "consumer-data/nvim/lazy"
    native_data.mkdir(parents=True)
    for plugin in Path(manifest["plugins"]).iterdir():
        (native_data / plugin.name).symlink_to(plugin)
    expression = (
        "let f=builtins.getFlake "
        + json.dumps(str(repo))
        + ";p=import f.inputs.nixpkgs {};in p.vimPlugins.lazy-nvim"
    )
    original_core = Path(
        subprocess.check_output(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--no-link",
                "--print-out-paths",
            ],
            text=True,
        ).strip()
    )
    (native_data / "lazy.nvim").symlink_to(original_core)
    ordinary = dict(
        os.environ,
        XDG_CONFIG_HOME=str(consumer.parent),
        XDG_DATA_HOME=str(temp / "consumer-data"),
        XDG_CACHE_HOME=str(temp / "consumer-cache"),
        XDG_STATE_HOME=str(temp / "consumer-state"),
        NVIM_APPNAME="nvim",
        LAZY_PURIFIER_CORE=str(original_core),
    )
    ordinary.pop("LUA_PATH", None)
    ordinary.pop("LUA_CPATH", None)
    result_file.unlink(missing_ok=True)
    expression = (
        "let f=builtins.getFlake "
        + json.dumps(str(repo))
        + ";p=import f.inputs.nixpkgs {};in p.neovim-unwrapped"
    )
    native_sdk = Path(
        subprocess.check_output(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--no-link",
                "--print-out-paths",
            ],
            text=True,
        ).strip()
    )
    result = subprocess.run(
        [
            native_sdk / "bin/nvim",
            "--headless",
            "--cmd",
            "lua dofile("
            + json.dumps(str(sdk / "lib/lazy-purifier/native/bootstrap.lua"))
            + ")",
            "-u",
            consumer / "init.lua",
            "-c",
            "lua " + lua,
            "-c",
            "qa!",
        ],
        cwd=consumer,
        env=ordinary,
        text=True,
        capture_output=True,
    )
    assert (
        result.returncode == 0 and json.loads(result_file.read_text())["answer"] == 42
    ), result
    fake_gh = temp / "fake-gh"
    fake_gh.write_text(
        "#!/usr/bin/env python3\nimport pathlib,sys\np=pathlib.Path(sys.argv[4]);pathlib.Path(__file__).with_suffix('.uploaded').write_bytes(p.read_bytes())\n"
    )
    fake_gh.chmod(0o755)
    call(
        "lazy-purifier",
        "publish",
        "--lock",
        str(external_companion),
        "--native-lock",
        str(external_native),
        extra={"LAZY_PURIFIER_GH": str(fake_gh)},
    )
    assert fake_gh.with_suffix(".uploaded").read_bytes() == archive.read_bytes()
    call("nvim", "--version", extra=external)
    fallback = temp / "fallback"
    fallback.mkdir()
    fallback_env = {
        "LAZY_PURIFIER_PROJECT": str(fallback),
        "LAZY_PURIFIER_LOCK": str(fallback / "missing.json"),
    }
    assert (
        "ordinary impure"
        in call("nvim", "--version", extra=fallback_env, cwd=fallback).stderr
    )
    fake = temp / "fake-native"
    fake.write_text("#!/bin/sh\nprintf native-out\nprintf native-err >&2\nexit 7\n")
    fake.chmod(0o755)
    direct = dict(
        os.environ,
        PYTHONPATH=str(sdk / "lib/lazy-purifier"),
        LAZY_PURIFIER_NVIM=str(fake),
        LAZY_PURIFIER_PROJECT=str(fallback),
    )
    result = subprocess.run(
        ["python3", "-m", "lazy_purifier.cli", "--native"],
        cwd=fallback,
        env=direct,
        text=True,
        capture_output=True,
    )
    assert (
        result.returncode == 7
        and result.stdout == "native-out"
        and result.stderr.endswith("native-err")
    ), result
print(
    "Native lazy.nvim source edits, immutable plugins, selection guards, networking, source consumer, publication and fallback passed"
)
