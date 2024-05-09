# Dot Config

Contains .config for Windows for now. Hopefully Linux in the future

It will configure following

- Powershell with Oh My Posh to make it look not shit
- Neovim with kickstarter.nvim
- Windows Terminal with better splitting keybind that respects current directory when splitting

It did use to support following but it have been disabled

- glazevm
- wezterm

## Requirements

- Powershell. Yes it requires powershell on Linux as well :^)
- Git
- Python
- C Compiler (e.g. clang or gcc. Need for Vim building tree-sitter)
- nodejs (For pyright and neovim copilot)

### Windows Requirements

- Winget
- Chocolatey Package manager

## Setup

From **administrator** shell install nodejs using choco

```pwsh
choco install nodejs-lts
```

Then

To setup entire environment, type `pwsh ./setup.ps1`

## Font

### Windows Oh My Posh

[doc](https://ohmyposh.dev/docs/installation/fonts)

```pwsh
oh-my-posh font install
```

## Vim

### LSP via Mason Plugin
from vim you can check what LSP you have by typing `:Mason` and You can also install LSP
for different Language by `:MasonInstall rust-analyzer`

### Copilot

Require node to be installed. To setup type `:Copilot setup`
