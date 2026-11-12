{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  git,
  cacert,
  nix-prefetch-git,
  original,
  originalCore,
  core,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "lazy-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/lazy-purifier"
    cp -r lazy_purifier pkgs lib-overlays native lua "$out/lib/lazy-purifier/"
    install -m755 bin/lazy-purifier "$out/bin/lazy-purifier"
    for file in realize release; do
      substituteInPlace "$out/lib/lazy-purifier/pkgs/build-lazy-project/$file.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    done
    wrapProgram "$out/bin/lazy-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          git
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default LAZY_PURIFIER_GH ${gh}/bin/gh \
      --set LAZY_PURIFIER_NVIM ${original}/bin/nvim \
      --set LAZY_PURIFIER_CORE ${core} \
      --set LAZY_PURIFIER_ORIGINAL_CORE ${originalCore} \
      --set LAZY_PURIFIER_PREFETCH_GIT ${nix-prefetch-git}/bin/nix-prefetch-git \
      --set LAZY_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set LAZY_PURIFIER_SDK "$out"
    makeWrapper "$out/bin/lazy-purifier" "$out/bin/nvim" --add-flags '--native'
  '';
  meta = {
    description = "Neovim and lazy.nvim with locked Nix-resolved plugins";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "lazy-purifier";
  };
}
