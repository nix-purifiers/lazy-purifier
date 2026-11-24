{
  root,
  lockFile,
  nativeLockFile,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  scope =
    (import ../default.nix {
      inherit pkgs nixpkgsSrc;
      purifierSrc = /. + "@purifier@";
    }).overrideScope
      (
        _: _:
        let
          overrides = "@scopeOverrides@";
        in
        overrides
        // {
          luaConfig = import ../restore-lua-config.nix overrides.luaConfig;
        }
      );
in
(scope.buildLazyProject {
  src = /. + root;
  lockFile = /. + lockFile;
  nativeLockFile = /. + nativeLockFile;
}).release
