"""Exercise original LuaJIT module suppliers through capture and native launches."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tarfile

repo = Path(__file__).resolve().parent.parent
expression = (
    "let f=builtins.getFlake " + json.dumps(str(repo)) + ";"
    "p=import f.inputs.nixpkgs {overlays=[f.overlays.default];};"
    "s=p.lazy-purifier.overrideScope (_: _: {extraLuaPackages = p: [p.luafilesystem];});"
    "in s.cli"
)
sdk = Path(subprocess.check_output(
    ["nix", "build", "--impure", "--expr", expression, "--no-link", "--print-out-paths"], text=True
).strip())
for package in ["p.lua5_4.pkgs.luafilesystem", "p.hello"]:
    rejected_expression = expression.replace(
        "extraLuaPackages = p: [p.luafilesystem]", "extraLuaPackages = _: [" + package + "]"
    ).replace("in s.cli", "in s.cli.drvPath")
    rejected = subprocess.run(["nix", "eval", "--impure", "--expr", rejected_expression,
                               "--option", "allow-import-from-derivation", "false"],
                              capture_output=True, text=True)
    assert rejected.returncode != 0 and "original Lua interpreter" in rejected.stderr, rejected.stderr
with tempfile.TemporaryDirectory(prefix="lazy native lua ") as temporary:
    root = Path(temporary) / "nvim"
    shutil.copytree(repo / "examples/minimal", root)
    companion = root / "lazy-purifier.lock.json"
    companion.unlink()
    init = root / "init.lua"
    init.write_text(init.read_text() + """
local lfs = require('lfs')
assert(debug.getinfo(lfs.attributes).what == 'C')
assert(lfs.attributes(lfs.currentdir(), 'mode') == 'directory')
local paths = {}
for line in io.lines('/proc/self/maps') do
  local path = line:match('(/nix/store/[^ ]+/lfs%.so)$')
  if path then paths[path] = true end
end
local expected = (vim.uv or vim.loop).fs_realpath((vim.env.LUA_CPATH:gsub('%?', 'lfs')))
assert(expected and paths[expected], 'selected native LuaRocks C module was not loaded')
""")
    poison = Path(temporary) / "poison"
    poison.mkdir()
    (poison / "lfs.lua").write_text("error('ambient module must not load')\n")
    env = dict(os.environ, LAZY_PURIFIER_PROJECT=str(root),
               XDG_CACHE_HOME=str(Path(temporary) / "cache"),
               LUA_PATH=str(poison / "?.lua"), LUA_CPATH=str(poison / "?.so"))

    def call(tool, *args):
        result = subprocess.run([sdk / "bin" / tool, *args], cwd=root,
                                env=env, text=True, capture_output=True, timeout=600)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result

    call("lazy-purifier", "lock")
    data = json.loads(companion.read_text())
    assert len(data["entries"]) == 2
    assert data["native"] == json.loads((root / "lazy-lock.json").read_text())
    before = companion.read_bytes()
    call("lazy-purifier", "prefetch")
    call("nvim", "--headless", "-c", "lua assert(require('lfs').currentdir())", "-c", "qa!")
    build_expression = expression.replace("in s.cli", "in (s.buildLazyProject { src=/. + "
        + json.dumps(str(root)) + "; }).packages.project")
    built = Path(subprocess.check_output(["nix", "build", "--impure", "--expr", build_expression,
                                         "--no-link", "--print-out-paths"], text=True).strip())
    archive = Path(call("lazy-purifier", "bundle").stdout.strip())
    assert archive.is_file()
    with tarfile.open(archive) as bundle:
        for name in ["init.lua", "lazy-lock.json", "lazy-purifier.lock.json"]:
            assert bundle.extractfile("./" + name).read() == (root / name).read_bytes()
            assert (built / name).read_bytes() == (root / name).read_bytes()
    call("lazy-purifier", "lock")
    assert companion.read_bytes() == before
    default_sdk = Path(subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip())
    rejected = subprocess.run([default_sdk / "bin/nvim", "--headless", "-c", "qa!"],
                              cwd=root, env=env, capture_output=True, text=True)
    assert rejected.returncode != 0 and "SDK changed" in rejected.stderr, rejected.stderr
    if os.environ.get("LAZY_NATIVE_LUA_FIXTURE_OUT"):
        shutil.copytree(root, os.environ["LAZY_NATIVE_LUA_FIXTURE_OUT"], dirs_exist_ok=True)
    if os.environ.get("LAZY_NATIVE_LUA_RECEIPT"):
        Path(os.environ["LAZY_NATIVE_LUA_RECEIPT"]).write_text(json.dumps({
            "sdk": str(sdk), "builder": str(built), "archive": str(archive),
            "capturedSdk": data["sdk"], "pluginCount": len(data["entries"]),
            "companionSha256": hashlib.sha256(before).hexdigest(),
            "nativeLockSha256": hashlib.sha256((root / "lazy-lock.json").read_bytes()).hexdigest(),
            "nativeModuleOrigin": "actual selected C extension mapped by native Neovim",
            "controls": ["wrong-interpreter", "non-module", "ambient-shadow", "unconfigured-sdk"],
            "sourceAndArchiveJoins": True,
        }, indent=2) + "\n")
print("native Lua module capture/prefetch/launch, ambient shadow rejection and stable locks PASS")
