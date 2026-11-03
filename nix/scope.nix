{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.neovim-unwrapped;
  originalCore = pkgs.vimPlugins.lazy-nvim;
  core = pkgs.vimPlugins.lazy-nvim.overrideAttrs (old: {
    postPatch = (old.postPatch or "") + ''
      ${pkgs.python3}/bin/python3 ${../native/patch-lazy.py}
    '';
    postInstall = (old.postInstall or "") + ''
      install -m644 ${../lua/nix_purifier_lazy.lua} "$out/lua/nix_purifier_lazy.lua"
    '';
  });
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  sdkVersion = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      neovim = toString pkgs.neovim-unwrapped.src;
      lazy = toString pkgs.vimPlugins.lazy-nvim.src;
      patch = builtins.hashFile "sha256" ../native/patch-lazy.py;
      helper = builtins.hashFile "sha256" ../lua/nix_purifier_lazy.lua;
    }
  );
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  buildLazyProject = scope.callPackage ./build-project.nix { };
})
