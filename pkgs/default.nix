{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.neovim-unwrapped;
  originalCore = pkgs.vimPlugins.lazy-nvim;
  extraLuaPackages = _: [ ];
  luaModules = scope.extraLuaPackages scope.original.lua.pkgs;
  luaModuleClosure = scope.original.lua.pkgs.luaLib.requiredLuaModules scope.luaModules;
  luaEnvironment =
    assert pkgs.lib.assertMsg (
      (builtins.all (module: (module.luaModule or null) == scope.original.lua) scope.luaModules)
      && builtins.all (
        module: module == scope.original.lua || (module.luaModule or null) == scope.original.lua
      ) scope.luaModuleClosure
    ) "lazy-purifier: supplied Lua modules must belong to Neovim's original Lua interpreter";
    scope.original.lua.withPackages (_: scope.luaModules);
  luaConfig = pkgs.lib.optionalAttrs (scope.luaModules != [ ]) {
    interpreter = toString scope.original.lua;
    environment = toString scope.luaEnvironment;
    path = scope.luaEnvironment.luaPath;
    cpath = scope.luaEnvironment.luaCpath;
    modules = map toString scope.luaModuleClosure;
  };
  core = scope.originalCore.overrideAttrs (old: {
    postPatch = (old.postPatch or "") + ''
      ${pkgs.python3}/bin/python3 ${../native/patch-lazy.py}
    '';
    postInstall = (old.postInstall or "") + ''
      install -m644 ${../lua/nix_purifier_lazy.lua} "$out/lua/nix_purifier_lazy.lua"
    '';
  });
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  sdkVersion = builtins.hashString "sha256" (
    builtins.toJSON (
      {
        nixpkgs = toString nixpkgsSrc;
        neovim = toString scope.original.src;
        lazy = toString scope.originalCore.src;
        patch = builtins.hashFile "sha256" ../native/patch-lazy.py;
        helper = builtins.hashFile "sha256" ../lua/nix_purifier_lazy.lua;
      }
      // pkgs.lib.optionalAttrs (scope.luaModules != [ ]) { lua = scope.luaConfig; }
    )
  );
  cli = scope.callPackage ./cli/default.nix { inherit nixpkgsSrc purifierSrc; };
  buildLazyProject = scope.callPackage ./build-lazy-project/default.nix { };
})
