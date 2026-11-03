local state = vim.json.decode(table.concat(vim.fn.readfile(vim.env.LAZY_PURIFIER_STATE), "\n"))
local config = require("lazy.core.config")
local function snapshot()
  assert(vim.v.errmsg == "", "Neovim configuration failed: " .. vim.v.errmsg)
  if vim.env.LAZY_PURIFIER_UPDATE == "1" then
    require("lazy.manage").update({wait=true, show=false})
  end
  local plugins = vim.empty_dict()
  for name, plugin in pairs(config.plugins) do
    if name ~= "lazy.nvim" then
      assert(plugin._.installed, "Plugin was not installed: " .. name)
      assert(not require("lazy.core.plugin").has_errors(plugin), "Native plugin task failed: " .. name)
      plugins[name] = {url=plugin.url, dir=plugin.dir}
    end
  end
  if not state.frozen then require("lazy.manage.lock").update() end
  local report = vim.json.decode(table.concat(vim.fn.readfile(state.status), "\n"))
  assert(report.valid, report.error)
  local native = vim.json.decode(table.concat(vim.fn.readfile(config.options.lockfile), "\n"))
  vim.fn.writefile({vim.json.encode({plugins=plugins, selection=report.selection, native=native})}, vim.env.LAZY_PURIFIER_SNAPSHOT)
end
local ok, err = pcall(snapshot)
if not ok then
  vim.fn.writefile({vim.json.encode({valid=false, error=tostring(err)})}, state.status)
  vim.api.nvim_err_writeln(tostring(err))
end
