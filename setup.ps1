$WingetPrograms = @(
	"Neovim.Neovim",
	"wez.wezterm"
)	

$NeovimConfig = "git@github.com:elbiazo/kickstart.nvim.git"

$MainFunction = {
	param(
		[switch] $CheckDepOnly
	)
	# Check Dep
	info("Checking Dependencies")
	
	if ($CheckDepOnly)
	{
		info("Only checking Dependencies bye!")
		return
	}

	# Clone nvim
	if (Get-Item-Exist("$PWD/nvim"))
	{
		if (Get-Yes-No "Remove existing nvim?")
		{
			Remove-Item -r -Force ./nvim
			git clone $NeovimConfig ./nvim
		} else
		{
			info("Ignoring nvim folder")
		}

	} else
	{
		git clone $NeovimConfig ./nvim
	}

	if ($IsWindows)
	{
		WindowsConfig
	} elseif ($IsLinux)
	{
		LinuxConfig
	} else
	{
		info("Unsupported OS")
	}
}
function LinuxConfig
{

	if (!(Get-Command nvim -ErrorAction SilentlyContinue))
	{
		info("Neovim not found, installing")
		sudo apt purge vim -y
		sudo add-apt-repository ppa:neovim-ppa/unstable
		sudo apt-get update
		sudo apt-get install neovim clangd unzip -y
	} else
	{
		info("Neovim found")
	}

	if (!(Get-Command tmux -ErrorAction SilentlyContinue))
	{
		info("Neovim not found, installing")
		sudo apt-get update
		sudo apt-get install tmux
	} else
	{
		info("TMUX found")
	}

	$nvim_dst = Join-Path $env:HOME "/.config/nvim/" 
	$nvim_src = Join-Path $PWD "/nvim/"
	Set-Symlink $nvim_dst $nvim_src

	$tmux_dst = Join-Path $env:HOME ".tmux.conf"
	Set-Symlink $tmux_dst "$PWD/tmux/tmux.conf"
}

function WindowsConfig
{
	foreach ($prog in $WingetPrograms)
	{
		Invoke-Expression ("winget install {0:}" -f $prog)
	}

	$nvim_dst = Join-Path $env:USERPROFILE "/AppData/Local/nvim/" 
	$nvim_src = Join-Path $PWD "/nvim/"
	Set-Symlink $nvim_dst $nvim_src

	Set-Symlink "$HOME/.wezterm.lua" "$PWD/wezterm/.wezterm.lua"
	Set-Symlink $profile "$PWD/pwsh/Microsoft.PowerShell_profile.ps1"

	# Setting Sym Server Config for Process Exploerer and Windbg
	.\symsrv\set_sym_env.ps1
}

# This function will set the symlink if it doesn't exists. else it will save it
# with .old extension and set it with new one
function Set-Symlink([string]$dst, [string]$src, [switch]$backup)
{
	info("Setting Symlink {0:} <- {1:}" -f $dst, $src)

	# if path exists then try to save old one
	if (Get-Item-Exist($dst))
	{
		if ($backup)
		{
			info($dst + " exists so move it to .old")
			Move-Item -Path $dst -Destination ($dst + ".old") -Force
		} else
		{
			info($dst + " exists, removing it")
			if ($IsWindows)
			{
				Remove-Item $dst -r -Force
			} else
			{
				Remove-Item -f $dst # Remove-Item doesn't remove symlink in unix
			}
		}
	}

	New-Item -Path $dst -ItemType SymbolicLink -Value $src -Force
}

function Get-Yes-No([string]$msg)
{
	if ((Read-Host $msg " [y/n]") -eq "y")
	{
		return $true
	} else
	{
		return $false
	}
}

function Get-Item-Exist([string]$dst)
{
	if (Get-Item $dst -ErrorAction SilentlyContinue)
	{
		return $true
	} else
	{
		return $false
	}
}

function Write-Info([string]$msg)
{
	Write-Output ("[+] {0:}" -f $msg)
}

function Get-Command-Exist([string]$cmd)
{
	if (get-command -ErrorAction SilentlyContinue $cmd)
	{ Write-Output $true 
 } else
	{ Write-Output $false 
 }
}

New-Alias -Name info -Value Write-Info

& $MainFunction
