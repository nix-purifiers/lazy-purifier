"""Exercise native resolution and verify atomic lock publication."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)

with tempfile.TemporaryDirectory(prefix="lazy capture ") as temporary:
    temp = Path(temporary)
    root = temp / "nvim"
    shutil.copytree(repo / "examples/minimal", root)
    native = root / "lazy-lock.json"
    companion = root / "lazy-purifier.lock.json"
    companion.unlink()
    env = dict(
        os.environ, XDG_CACHE_HOME=str(temp / "cache"), LAZY_PURIFIER_PROJECT=str(root)
    )

    def capture(*args, success=True):
        result = subprocess.run(
            [sdk / "bin/lazy-purifier", "lock", *args],
            env=env,
            text=True,
            capture_output=True,
            timeout=600,
        )
        assert (result.returncode == 0) == success, result
        return result

    capture()
    data = json.loads(companion.read_text())
    assert set(data["native"]) == {"popup.nvim", "plenary.nvim"}
    assert len(data["entries"]) == 2
    assert data["native"] == json.loads(native.read_text())
    before = native.read_bytes(), companion.read_bytes()
    capture()
    assert before == (native.read_bytes(), companion.read_bytes())
    # Neovim normally exits zero after startup Lua errors. The Nix builder
    # must turn a failed native assertion into a failed derivation.
    expression = (
        "let f=builtins.getFlake "
        + json.dumps(str(repo))
        + ";p=import f.inputs.nixpkgs {overlays=[f.overlays.default];};"
        + "b=p.lazy-purifier.buildLazyProject {src=/. + "
        + json.dumps(str(root))
        + ';nvimArgs=["--headless" "-c" "lua assert(vim.g.answer==99)"];};'
        + "in b.packages.project"
    )
    rejected = subprocess.run(
        ["nix", "build", "--impure", "--no-link", "--expr", expression],
        text=True,
        capture_output=True,
    )
    assert rejected.returncode != 0 and "assertion failed" in rejected.stderr, rejected
    init = root / "init.lua"
    original = init.read_text()
    init.write_text('error("purifier startup proof")\n' + original)
    default_expression = expression.replace(
        ';nvimArgs=["--headless" "-c" "lua assert(vim.g.answer==99)"];', ";"
    )
    rejected = subprocess.run(
        ["nix", "build", "--impure", "--no-link", "--expr", default_expression],
        text=True,
        capture_output=True,
    )
    assert rejected.returncode != 0 and "purifier startup proof" in rejected.stderr, (
        rejected
    )
    init.write_text(original.replace("vim.g.answer = 42", "vim.g.answer = 43"))
    capture()
    assert before == (native.read_bytes(), companion.read_bytes())
    init.write_text(
        original.replace(
            '"nvim-lua/popup.nvim"',
            '"nvim-lua/popup.nvim", build=function() error("must not run") end',
        )
    )
    denied = capture("--update", success=False)
    assert "build" in denied.stderr.lower(), denied
    assert before == (native.read_bytes(), companion.read_bytes())
    init.write_text('require("lazy").setup({})\n')
    capture("--update")
    data = json.loads(companion.read_text())
    assert data["selection"] == {} and data["native"] == {} and data["entries"] == []
    capture()

print(
    "Native lazy.nvim capture, stable locks, build-hook rejection and empty profile passed"
)
