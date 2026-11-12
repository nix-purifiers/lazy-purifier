{
  lib,
  runCommand,
  writeText,
  python3,
  fetchurl,
  fetchgit,
  purifier,
  sdkVersion,
  original,
  core,
  git,
  gnutar,
  gzip,
  ...
}@scope:
{
  src,
  lockFile ? src + "/lazy-purifier.lock.json",
  nativeLockFile ? src + "/lazy-lock.json",
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
  nvimArgs ? [ "--headless" ],
}:
let
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } {
      inherit src lockFile nativeLockFile;
    }
  );
  prepared = import ./environment.nix scope { inherit lock fetchers; };
  source = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        "result"
        "__pycache__"
      ]);
  };
  data = writeText "lazy-lock-data.json" (builtins.toJSON lock.data);
  driver = lib.fileset.toSource {
    root = ../..;
    fileset = lib.fileset.unions [
      ../../lazy_purifier/layout.py
      ../../native/bootstrap.lua
      ../../native/check.py
    ];
  };
  project = runCommand "lazy-configuration" { nativeBuildInputs = [ git ]; } ''
    cp -pr ${source} source
    chmod -R u+w source
    ${python3}/bin/python3 ${driver}/native/check.py "$PWD/source" "$TMPDIR/state" ${core} \
      ${prepared.output}/manifest.json ${data} ${original}/bin/nvim ${lib.escapeShellArgs nvimArgs}
    mkdir -p "$out"
    cp -pr ${source}/. "$out/"
    ${lib.optionalString doCheck checkCommand}
  '';
  release =
    runCommand "lazy-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        test -d ${project}
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/nvim-config.tar.gz" -C ${source} .
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
