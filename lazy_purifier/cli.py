import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .capture import capture
from .common import original_environment, run
from .runtime import execute, realize


def locate(project=None, lock=None, native=None):
    env = original_environment()
    chosen = project or os.environ.get("LAZY_PURIFIER_PROJECT")
    root = Path(
        chosen
        or Path(env.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        / env.get("NVIM_APPNAME", "nvim")
    ).resolve()
    companion = Path(
        lock or os.environ.get("LAZY_PURIFIER_LOCK", root / "lazy-purifier.lock.json")
    ).resolve()
    explicit = native or os.environ.get("LAZY_PURIFIER_NATIVE_LOCK")
    native_file = Path(explicit or root / "lazy-lock.json").resolve()
    return root, companion, native_file, bool(explicit)


def main_impl():
    args = sys.argv[1:]
    if args[:1] == ["--native"]:
        root, companion, native, explicit = locate()
        flags = args[1:]
        if not companion.exists():
            print(
                "lazy-purifier: no lockfile; using ordinary impure Neovim/plugin resolution",
                file=sys.stderr,
            )
            return subprocess.call(
                [os.environ["LAZY_PURIFIER_NVIM"], *flags], env=original_environment()
            )
        if any(
            value in ("--version", "-v", "--help", "-h", "--clean") for value in flags
        ):
            return subprocess.call(
                [os.environ["LAZY_PURIFIER_NVIM"], *flags], env=original_environment()
            )
        return execute(root, companion, native, flags, explicit=explicit)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["lock", "prefetch", "exec", "bundle", "publish"]
    )
    parser.add_argument("--project", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--native-lock", type=Path)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--tag", default="v0.1.0")
    opts, rest = parser.parse_known_args(args)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    root, companion, native, explicit = locate(
        opts.project, opts.lock, opts.native_lock
    )
    if opts.action == "lock":
        capture(root, companion, native, opts.update, explicit=explicit)
    elif opts.action == "prefetch":
        realize(root, companion, native)
    elif opts.action == "exec":
        if not rest:
            raise ValueError("Pass a command after --")
        if Path(rest[0]).name == "nvim":
            return execute(root, companion, native, rest[1:], explicit=explicit)
        realize(root, companion, native)
        env = original_environment()
        env.update(
            LAZY_PURIFIER_PROJECT=str(root),
            LAZY_PURIFIER_LOCK=str(companion),
            LAZY_PURIFIER_NATIVE_LOCK=str(native),
        )
        env["PATH"] = (
            str(Path(os.environ["LAZY_PURIFIER_SDK"]) / "bin")
            + os.pathsep
            + env["PATH"]
        )
        return subprocess.call(rest, env=env)
    else:
        realize(root, companion, native)
        expression = (
            "import "
            + json.dumps(
                os.environ["LAZY_PURIFIER_SDK"] + "/lib/lazy-purifier/nix/release.nix"
            )
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";nativeLockFile="
            + json.dumps(str(native))
            + ";}"
        )
        output = Path(
            run(
                [
                    "nix",
                    "build",
                    "--impure",
                    "--no-link",
                    "--print-out-paths",
                    "--expr",
                    expression,
                ]
            ).strip()
        )
        archive = output / "nvim-config.tar.gz"
        if opts.action == "bundle":
            print(archive)
        else:
            subprocess.run(
                [
                    os.environ["LAZY_PURIFIER_GH"],
                    "release",
                    "upload",
                    opts.tag,
                    str(archive),
                    "--clobber",
                ],
                cwd=root,
                check=True,
            )
    return 0


def main():
    try:
        raise SystemExit(main_impl())
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print("lazy-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
