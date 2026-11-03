local core = assert(vim.env.LAZY_PURIFIER_CORE)
vim.opt.rtp:prepend(core)
local function module(name, path)
  package.preload[name] = function(...)
    return assert(loadfile(path))(...)
  end
end
-- Keep the SDK's manager modules ahead of any bootstrap copy in the user's
-- runtimepath. Other Lua namespaces retain normal Neovim loading behavior.
for _, path in ipairs(vim.fn.glob(core .. "/lua/lazy/**/*.lua", false, true)) do
  local name = path:sub(#core + 6):gsub("%.lua$", ""):gsub("/init$", ""):gsub("/", ".")
  module(name, path)
end
local helper = core .. "/lua/nix_purifier_lazy.lua"
if vim.uv.fs_stat(helper) then
  module("nix_purifier_lazy", helper)
end
