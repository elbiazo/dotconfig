# Dot Config

Contains .config for Windows for now.

It will configure following

- Update pwsh config
- Neovim with kickstarter.nvim
- wezterm
- Add Env Path

## Requirements

- Powershell. Yes it requires powershell on Linux as well :^)
- Git
- Python
- C Compiler (e.g. clang or gcc. Need for Vim building tree-sitter)
- nodejs (For pyright and neovim copilot)

### Windows Requirements

- Winget

## Setup

To setup entire environment, type `pwsh ./setup.ps1`

## Vim

### LSP via Mason Plugin
from vim you can check what LSP you have by typing `:Mason` and You can also install LSP
for different Language by `:MasonInstall rust-analyzer`

### Copilot

**Currently Disabled**.Require node to be installed. To setup type `:Copilot setup`
