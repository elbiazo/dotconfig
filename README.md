# Dot Config

Contains .config for Windows, Linux, and macOS.

Instead of symlinking, configs are **copied** into place. If a config already
exists at the destination you are prompted (`y/n`); answering yes backs the
existing config up to `<config>.bak` before copying the new one.

It will configure the following

- Update pwsh config
- Neovim with kickstarter.nvim
- wezterm
- Add Env Path

On **macOS** only Neovim (vim), tmux, and zsh (`~/.zshrc`) are pulled and
configured for now. The zsh config enables colored output (`ls`, prompt,
completion, `grep`) and installs the `zsh-autosuggestions` and
`zsh-syntax-highlighting` plugins via Homebrew.

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
