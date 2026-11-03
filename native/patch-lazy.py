from pathlib import Path

changes = {
    "lua/lazy/manage/task/plugin.lua": (
        "  run = function(self)\n    vim.cmd([[silent! runtime plugin/rplugin.vim]])",
        '  run = function(self)\n    if vim.env.LAZY_PURIFIER_STATE and self.plugin.build ~= false and (self.plugin.build or get_build_file(self.plugin)) then require("nix_purifier_lazy").build(self.plugin) end\n    vim.cmd([[silent! runtime plugin/rplugin.vim]])',
    ),
    "lua/lazy/core/config.lua": (
        "function M.setup(opts)\n",
        'function M.setup(opts)\n  if vim.env.LAZY_PURIFIER_STATE then opts = require("nix_purifier_lazy").options(opts) end\n',
    ),
    "lua/lazy/core/plugin.lua": (
        '  vim.api.nvim_exec_autocmds("User", { pattern = "LazyPlugins", modeline = false })',
        '  if vim.env.LAZY_PURIFIER_STATE then require("nix_purifier_lazy").validate(Config) end\n  vim.api.nvim_exec_autocmds("User", { pattern = "LazyPlugins", modeline = false })',
    ),
    "lua/lazy/manage/init.lua": (
        "function M.run(ropts, opts)\n",
        'function M.run(ropts, opts)\n  if vim.env.LAZY_PURIFIER_STATE then require("nix_purifier_lazy").operation(ropts) end\n',
    ),
}
path = Path("lua/lazy/manage/task/plugin.lua")
source = path.read_text()
before = '  run = function(self)\n    local docs = self.plugin.dir .. "/doc"'
after = '  run = function(self)\n    if vim.env.LAZY_PURIFIER_STATE and self.plugin.name == "lazy.nvim" then return end\n    local docs = self.plugin.dir .. "/doc"'
assert source.count(before) == 1
path.write_text(source.replace(before, after))
for name, (before, after) in changes.items():
    path = Path(name)
    source = path.read_text()
    assert source.count(before) == 1, name
    path.write_text(source.replace(before, after))
