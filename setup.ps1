# =============================================================================
# setup.ps1 - Dotfiles bootstrap script
#
# Installs programs, clones the Neovim config, and symlinks dotfiles into place.
# Supports both Windows (via winget) and Linux (via apt).
#
# Usage: pwsh ./setup.ps1
# =============================================================================

# --- Programs to install via winget on Windows ---
$WingetPrograms = @(
    "Neovim.Neovim",
    "wez.wezterm",
    "Microsoft.PowerToys",
    "OpenJS.NodeJS.LTS",
    "Microsoft.Git",
    "Python.Python.3.13",
    "LLVM.LLVM",
    "Microsoft.VisualStudioCode"
)

# --- Configuration variables ---
$NeovimConfig = "git@github.com:elbiazo/kickstart.nvim.git"
$sym_config = "srv*C:\symbols*https://msdl.microsoft.com/download/symbols"

# --- Main entry point (script block) ---
$MainFunction = {
    param(
        [switch] $CheckDepOnly
    )

    info("Checking Dependencies")

    if ($CheckDepOnly) {
        info("Only checking Dependencies bye!")
        return
    }

    # Clone or refresh the Neovim config repo
    if (Get-ItemExist("$PWD/nvim")) {
        if (Get-Yes-No "Remove existing nvim?") {
            # Remove cached nvim data to avoid conflicts with a fresh clone
            if ($IsWindows) {
                Remove-Item -r -Force $env:LOCALAPPDATA/nvim-data
            }

            Remove-Item -r -Force ./nvim
            git clone $NeovimConfig ./nvim
        } else {
            info("Ignoring nvim folder")
        }
    } else {
        git clone $NeovimConfig ./nvim
    }

    # Dispatch to the platform-specific configuration
    if ($IsWindows) {
        WindowsConfig
    } elseif ($IsLinux) {
        LinuxConfig
    } else {
        info("Unsupported OS")
    }
}

# --- Linux-specific setup ---
function LinuxConfig {
    # Install Neovim from unstable PPA if not present
    if (!(Get-Command nvim -ErrorAction SilentlyContinue)) {
        info("Neovim not found, installing")
        sudo apt purge vim -y
        sudo add-apt-repository ppa:neovim-ppa/unstable
        sudo apt-get update
        sudo apt-get install neovim clangd unzip curl -y
    } else {
        info("Neovim found")
    }

    # Install tmux if not present
    if (!(Get-Command tmux -ErrorAction SilentlyContinue)) {
        info("tmux not found, installing")
        sudo apt-get update
        sudo apt-get install tmux -y
    } else {
        info("tmux found")
    }

    # Install build-essential (gcc, make, etc.) for tree-sitter compilation
    if (!(Get-Command make -ErrorAction SilentlyContinue)) {
        info("build-essential not found, installing")
        sudo apt-get update
        sudo apt-get install build-essential -y
    } else {
        info("build-essential found")
    }

    # Symlink Neovim config
    $nvim_dst = Join-Path $env:HOME "/.config/nvim/"
    $nvim_src = Join-Path $PWD "/nvim/"
    Set-Symlink $nvim_dst $nvim_src

    # Symlink tmux config
    $tmux_dst = Join-Path $env:HOME ".tmux.conf"
    Set-Symlink $tmux_dst "$PWD/tmux/tmux.conf"
}

# --- Windows-specific setup ---
function WindowsConfig {
    # Install all programs via winget
    foreach ($prog in $WingetPrograms) {
        Invoke-Expression ("winget install {0}" -f $prog)
    }

    # tree-sitter-cli is required for Neovim's tree-sitter grammar compilation
    npm install -g tree-sitter-cli

    # Symlink Neovim config
    $nvim_dst = Join-Path $env:USERPROFILE "/AppData/Local/nvim/"
    $nvim_src = Join-Path $PWD "/nvim/"
    Set-Symlink $nvim_dst $nvim_src

    # Symlink WezTerm config
    Set-Symlink "$HOME/.wezterm.lua" "$PWD/wezterm/.wezterm.lua"

    # Symlink PowerShell profile
    Set-Symlink $profile "$PWD/pwsh/Microsoft.PowerShell_profile.ps1"

    # Optional: symbol server for Process Explorer / WinDbg
    # Set-Env "_NT_SYMBOL_PATH" $sym_config

    # Optional: GlazeWM config path override
    # Set-Env "GLAZEWM_CONFIG_PATH" $PSScriptRoot/glazewm/config.yaml
}

# Source helpers then run
. $PSScriptRoot/util.ps1
& $MainFunction
