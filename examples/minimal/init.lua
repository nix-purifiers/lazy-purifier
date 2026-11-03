local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.fn.system({"git", "clone", "--filter=blob:none", "https://github.com/folke/lazy.nvim.git", lazypath})
end
vim.opt.rtp:prepend(lazypath)
vim.g.answer = 42
require("lazy").setup({
  {"nvim-lua/popup.nvim", dependencies = {"nvim-lua/plenary.nvim"}},
}, { rocks = {enabled = false}, checker = {enabled = false} })
