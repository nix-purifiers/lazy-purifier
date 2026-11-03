import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlsplit

from .common import original_environment, run
from .layout import configure, launch


def capture(root, companion, native, update=False, explicit=False):
    if companion.exists() and not update:
        from .runtime import execute

        if execute(root, companion, native, [], verify=True, explicit=explicit):
            raise ValueError("Locked lazy.nvim configuration failed verification")
        return
    if not (root / "init.lua").is_file():
        raise ValueError("The configuration needs init.lua")
    with tempfile.TemporaryDirectory(prefix="lazy-capture-") as temporary:
        state = Path(temporary)
        private_lock = state / "lazy-lock.json"
        if native.exists():
            private_lock.write_bytes(native.read_bytes())
        env = configure(
            root,
            state,
            os.environ["LAZY_PURIFIER_CORE"],
            state / "plugins",
            private_lock,
            {},
            False,
            source_native=native,
            explicit=explicit,
        )
        # Capture uses ordinary native Git resolution in a private cache.
        for key, value in original_environment().items():
            if key.startswith("GIT_CONFIG_"):
                env[key] = value
        env["LAZY_PURIFIER_UPDATE"] = "1" if update else "0"
        result_file = state / "snapshot.json"
        env["LAZY_PURIFIER_SNAPSHOT"] = str(result_file)
        finalizer = Path(__file__).parent.parent / "native/snapshot.lua"
        if (
            launch(
                os.environ["LAZY_PURIFIER_NVIM"],
                root,
                state,
                os.environ["LAZY_PURIFIER_CORE"],
                env,
                [],
                finalizer=finalizer,
            )
            or not result_file.exists()
        ):
            raise ValueError("Native lazy.nvim resolution failed")
        snapshot = json.loads(result_file.read_text())
        entries = []
        for name, plugin in sorted(snapshot["plugins"].items()):
            url = urlsplit(plugin["url"])
            if (
                url.scheme != "https"
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError("Use public HTTPS Git plugins")
            revision = snapshot["native"][name]["commit"]
            source = Path(plugin["dir"])
            commit = subprocess.check_output(
                ["git", "-C", str(source), "cat-file", "commit", revision]
            )
            tree = subprocess.check_output(
                ["git", "-C", str(source), "ls-tree", "-r", revision], text=True
            )
            if any(line.startswith("160000 ") for line in tree.splitlines()):
                raise ValueError("Git submodules need a plugin provider")
            fetched = json.loads(
                run(
                    [
                        os.environ["LAZY_PURIFIER_PREFETCH_GIT"],
                        "--url",
                        plugin["url"],
                        "--rev",
                        revision,
                    ],
                    env=original_environment(),
                )
            )
            entries.append(
                dict(
                    path=name,
                    hash=fetched["hash"],
                    git=dict(
                        url=plugin["url"],
                        rev=revision,
                        submodules=False,
                        leaveDotGit=True,
                        commitObject=dict(
                            object=base64.b64encode(commit).decode(), gitlinks=[]
                        ),
                    ),
                    lazy=dict(name=name, branch=snapshot["native"][name]["branch"]),
                )
            )
        data = dict(
            version=1,
            purifier="lazy",
            sdk=os.environ["LAZY_PURIFIER_SDK_VERSION"],
            entries=entries,
            selection=snapshot["selection"],
            native=snapshot["native"],
        )
        candidate = state / "lazy-purifier.lock.json"
        candidate.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
        # A fresh process must load the actual Nix-delivered plugins before
        # either of the user's lockfiles is replaced.
        from .runtime import execute

        if execute(
            root,
            candidate,
            private_lock,
            [],
            verify=True,
            explicit=explicit,
            source_native=native,
        ):
            raise ValueError("Nix-delivered lazy.nvim plugins failed verification")
        for target, payload in (
            (native, private_lock.read_bytes()),
            (companion, candidate.read_bytes()),
        ):
            target.parent.mkdir(parents=True, exist_ok=True)
            staged = target.with_name(target.name + ".tmp")
            staged.write_bytes(payload)
            staged.replace(target)
