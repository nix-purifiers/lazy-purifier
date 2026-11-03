local M = {}
local function state()
  return vim.json.decode(table.concat(vim.fn.readfile(vim.env.LAZY_PURIFIER_STATE), "\n"))
end
local function write(file, data)
  vim.fn.writefile({vim.json.encode(data)}, file)
end
local function deny(data, message)
  write(data.status, {valid=false, error=message})
  error(message)
end
function M.options(opts)
  local data = state()
  opts = opts or {}
  if opts.lockfile and not data.sourceExplicit and vim.fn.fnamemodify(opts.lockfile, ":p") ~= data.sourceNative then
    deny(data, "Custom lazy lockfile: pass --native-lock explicitly")
  end
  opts.root = data.plugins
  opts.lockfile = data.lockfile
  opts.install = vim.tbl_extend("force", opts.install or {}, {missing=not data.frozen})
  opts.rocks = vim.tbl_extend("force", opts.rocks or {}, {enabled=false})
  opts.checker = vim.tbl_extend("force", opts.checker or {}, {enabled=false})
  return opts
end
function M.validate(config)
  local data = state()
  local actual = vim.empty_dict()
  for name, plugin in pairs(config.plugins) do
    if name ~= "lazy.nvim" then
      if not name:match("^[A-Za-z0-9_.+-]+$") or name == "." or name == ".." then deny(data, "Unsupported plugin name") end
      if plugin._.is_local then deny(data, "Local plugins need a source provider: " .. name) end
      if plugin.build then deny(data, "Plugin build hooks need a provider: " .. name) end
      if type(plugin.url) ~= "string" or not plugin.url:match("^https://") then deny(data, "Use public HTTPS Git plugins: " .. name) end
      local version = plugin.version
      if version == nil then version = config.options.defaults.version end
      actual[name] = {url=plugin.url, branch=plugin.branch or vim.NIL,
        commit=plugin.commit or vim.NIL, tag=plugin.tag or vim.NIL,
        version=version == nil and vim.NIL or version, submodules=plugin.submodules ~= false}
    end
  end
  if data.frozen and not vim.deep_equal(actual, data.expected) then
    deny(data, "Lazy plugin selection changed; update the purifier lock")
  end
  write(data.status, {valid=true, selection=actual})
end
function M.operation(opts)
  local data=state()
  if data.frozen then
    for _, step in ipairs(opts.pipeline or {}) do
      local name = type(step) == "table" and step[1] or step
      local readonly = name == "git.log" or (name == "git.origin" and type(step) == "table" and step.check == true)
      if not readonly then deny(data, "Lazy plugins are Nix-resolved; update the purifier lock") end
    end
  end
end
function M.build(plugin)
  deny(state(), "Plugin build hooks need a provider: " .. plugin.name)
end
return M
