{
  lib,
  runCommand,
  fetchurl,
  fetchgit,
  writeText,
  python3,
  purifier,
  sdkVersion,
  original,
  git,
  ...
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  tree = purifier.tree (
    {
      name = "lazy-locked-git-sources";
      entries = checked.entries;
      inherit
        runCommand
        fetchurl
        fetchgit
        writeText
        python3
        ;
    }
    // fetchers
  );
  plugins =
    runCommand "lazy-native-plugin-environment"
      {
        nativeBuildInputs = [
          original
          git
        ];
      }
      ''
        mkdir -p "$out"
        ${lib.concatMapStringsSep "\n" (entry: ''
          name=${lib.escapeShellArg entry.path}
          branch=${lib.escapeShellArg entry.lazy.branch}
          plugin="$out/$name"
          mkdir -p "$plugin"
          cp -pr ${lib.escapeShellArg "${tree}/${entry.path}/."} "$plugin/"
          chmod -R u+w "$plugin"
          git check-ref-format "refs/heads/$branch"
          mkdir -p "$(dirname "$plugin/.git/refs/heads/$branch")" "$(dirname "$plugin/.git/refs/remotes/origin/$branch")"
          printf '%s\n' ${lib.escapeShellArg entry.git.rev} > "$plugin/.git/refs/heads/$branch"
          printf '%s\n' ${lib.escapeShellArg entry.git.rev} > "$plugin/.git/refs/remotes/origin/$branch"
          printf 'ref: refs/heads/%s\n' "$branch" > "$plugin/.git/HEAD"
          printf 'ref: refs/remotes/origin/%s\n' "$branch" > "$plugin/.git/refs/remotes/origin/HEAD"
          git -C "$plugin" config remote.origin.url ${lib.escapeShellArg entry.git.url}
          if test -d "$plugin/doc"; then
            nvim --headless -u NONE -i NONE -c "helptags $plugin/doc" -c 'qa!'
          fi
        '') checked.entries}
      '';
  manifest = writeText "lazy-environment.json" (
    builtins.toJSON {
      inherit tree plugins;
      sdk = sdkVersion;
    }
  );
  output = runCommand "lazy-locked-environment" { passthru = { inherit plugins; }; } ''
    mkdir -p "$out"
    ln -s ${manifest} "$out/manifest.json"
  '';
in
assert lib.assertMsg (
  checked.data.sdk == sdkVersion
) "Neovim/lazy.nvim SDK changed; update the lock";
{
  inherit output tree plugins;
}
