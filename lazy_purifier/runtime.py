import hashlib
import json
import os
from pathlib import Path
import tempfile

from .common import load, run
from .layout import configure, launch


def realize(root, companion, native):
    data = load(root, companion, native)
    sdk = os.environ["LAZY_PURIFIER_SDK"]
    generation = hashlib.sha256(companion.read_bytes() + sdk.encode()).hexdigest()[:20]
    key = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    home = Path(
        os.environ.get(
            "LAZY_PURIFIER_CACHE_HOME",
            os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")),
        )
    )
    state = home / "lazy-purifier" / key / generation
    state.mkdir(parents=True, exist_ok=True)
    profile = state / "environment-profile"
    if not profile.exists():
        expression = (
            "import "
            + json.dumps(sdk + "/lib/lazy-purifier/pkgs/build-lazy-project/realize.nix")
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";nativeLockFile="
            + json.dumps(str(native))
            + ";sdk="
            + json.dumps(sdk)
            + ";}"
        )
        run(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--out-link",
                str(profile),
            ]
        )
    output = Path(json.loads(profile.read_text())["output"])
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest["sdk"] != data["sdk"]:
        raise ValueError("Prepared lazy.nvim SDK differs from the lock")
    return state, home, data, manifest


def execute(
    root, companion, native, args, verify=False, explicit=False, source_native=None
):
    state, home, data, manifest = realize(root, companion, native)
    with tempfile.TemporaryDirectory(prefix="invocation-", dir=state) as temporary:
        invocation = Path(temporary)
        private_lock = invocation / "lazy-lock.json"
        private_lock.write_bytes(native.read_bytes())
        env = configure(
            root,
            invocation,
            os.environ["LAZY_PURIFIER_CORE"],
            manifest["plugins"],
            private_lock,
            data["selection"],
            True,
            source_native=source_native or native,
            explicit=explicit,
            persistent=state / "editor",
        )
        env["LAZY_PURIFIER_CACHE_HOME"] = str(home)
        env["LAZY_PURIFIER_PROJECT"] = str(root)
        env["LAZY_PURIFIER_LOCK"] = str(companion)
        env["LAZY_PURIFIER_NATIVE_LOCK"] = str(native)
        finalizer = None
        if verify:
            finalizer = Path(__file__).parent.parent / "native/snapshot.lua"
            env["LAZY_PURIFIER_SNAPSHOT"] = str(invocation / "snapshot.json")
            env.pop("LAZY_PURIFIER_UPDATE", None)
        return launch(
            os.environ["LAZY_PURIFIER_NVIM"],
            root,
            invocation,
            os.environ["LAZY_PURIFIER_CORE"],
            env,
            args,
            finalizer=finalizer,
        )
