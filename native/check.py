import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from lazy_purifier.layout import configure, launch

root, state, core, manifest_file, data_file, binary = map(Path, sys.argv[1:7])
manifest = json.loads(manifest_file.read_text())
data = json.loads(data_file.read_text())
state.mkdir(parents=True, exist_ok=True)
native = state / "lazy-lock.json"
native.write_text(json.dumps(data["native"]))
env = configure(
    root,
    state,
    core,
    manifest["plugins"],
    native,
    data["selection"],
    True,
    explicit=True,
)
args = sys.argv[7:] or ["--headless"]
args += ["-c", "lua if vim.v.errmsg ~= '' then vim.cmd.cquit(1) end", "-c", "qa!"]
raise SystemExit(launch(binary, root, state, core, env, args))
