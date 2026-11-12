{ lib }:
{
  src,
  lockFile ? src + "/lazy-purifier.lock.json",
  nativeLockFile ? src + "/lazy-lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  native =
    if builtins.pathExists nativeLockFile then
      builtins.fromJSON (builtins.readFile nativeLockFile)
    else
      null;
  component =
    s:
    builtins.isString s
    && builtins.match "[A-Za-z0-9_.+-]+" s != null
    && !(builtins.elem s [
      "."
      ".."
    ]);
  shape =
    (data.version or null) == 1
    && (data.purifier or null) == "lazy"
    && builtins.isString (data.sdk or null)
    && builtins.isAttrs (data.native or null)
    && builtins.isAttrs (data.selection or null)
    && builtins.isList entries
    && builtins.all (
      entry:
      builtins.isAttrs entry
      && component (entry.path or null)
      && builtins.isAttrs (entry.lazy or null)
      && (entry.lazy.name or null) == entry.path
      && builtins.isString (entry.lazy.branch or null)
      && builtins.isAttrs (entry.git or null)
      && builtins.isString (entry.git.url or null)
      && lib.hasPrefix "https://" entry.git.url
      && !(lib.hasInfix "?" entry.git.url)
      && !(lib.hasInfix "#" entry.git.url)
      && builtins.isString (entry.git.rev or null)
      && builtins.match "[0-9a-f]{40}" entry.git.rev != null
      && (entry.git.submodules or null) == false
      && (entry.git.leaveDotGit or null) == true
      && builtins.isAttrs (entry.git.commitObject or null)
      && builtins.isString (entry.git.commitObject.object or null)
      && (entry.git.commitObject.gitlinks or null) == [ ]
      && builtins.isString (entry.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" entry.hash != null
    ) entries;
  valid =
    shape
    && data.native == native
    && builtins.pathExists (src + "/init.lua")
    && builtins.length (lib.unique (map (entry: entry.path) entries)) == builtins.length entries
    &&
      builtins.sort builtins.lessThan (map (entry: entry.path) entries)
      == builtins.attrNames data.selection
    && builtins.all (
      entry:
      builtins.hasAttr entry.path data.native
      && builtins.isAttrs data.native.${entry.path}
      && (data.native.${entry.path}.commit or null) == entry.git.rev
      && (data.native.${entry.path}.branch or null) == entry.lazy.branch
      && builtins.isAttrs data.selection.${entry.path}
      && (data.selection.${entry.path}.url or null) == entry.git.url
    ) entries;
in
{
  purifier = "lazy";
  inherit entries data;
  problems = lib.optional (
    !valid
  ) "lazy.nvim lock is missing, malformed, or stale; run lazy-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
