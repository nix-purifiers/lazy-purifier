{
  description = "Locked, Nix-resolved Neovim plugins for lazy.nvim";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        lazy-purifier = import ./pkgs/default.nix {
          pkgs = final;
          nixpkgsSrc = nixpkgs;
          purifierSrc = purifier;
        };
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).lazy-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/lazy-purifier";
          meta.description = "Lock native lazy.nvim plugins";
        };
      });
      lib.lazy-purifier = (nixpkgs.lib.extend (import ./lib-overlays/default)).lazy-purifier;
      checks = forAll (
        system:
        let
          p = pkgsFor system;
          b = p.lazy-purifier.buildLazyProject {
            src = ./examples/minimal;
            doCheck = true;
            nvimArgs = [
              "--headless"
              "-c"
              "lua assert(type(require('popup').create)=='function');assert(tonumber(require('plenary.path'):new(tostring(vim.g.answer)).filename)==42)"
            ];
          };
        in
        {
          inherit (b.packages) environment project;
          release = b.release;
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
