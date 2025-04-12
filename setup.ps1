$WingetPrograms = @(
	"Neovim.Neovim",
	"wez.wezterm",
	"Microsoft.PowerToys",
	"OpenJS.NodeJS.LTS",
	"Microsoft.Git",
	"Python.Python.3.13",
	"LLVM.LLVM"
)	

$NeovimConfig = "git@github.com:elbiazo/kickstart.nvim.git"
$sym_config = "srv*C:\symbols*https://msdl.microsoft.com/download/symbols"
$MainFunction = {
	param(
		[switch] $CheckDepOnly
	)
	# Check Dep
	info("Checking Dependencies")
	
	if ($CheckDepOnly) {
		info("Only checking Dependencies bye!")
		return
	}

	# Clone nvim
	if (Get-Item-Exist("$PWD/nvim")) {
		if (Get-Yes-No "Remove existing nvim?") {
			Remove-Item -r -Force ./nvim
			git clone $NeovimConfig ./nvim
		}
		else {
			info("Ignoring nvim folder")
		}

	}
 else {
		git clone $NeovimConfig ./nvim
	}

	if ($IsWindows) {
		WindowsConfig
	}
 elseif ($IsLinux) {
		LinuxConfig
	}
 else {
		info("Unsupported OS")
	}
}
function LinuxConfig {

	if (!(Get-Command nvim -ErrorAction SilentlyContinue)) {
		info("Neovim not found, installing")
		sudo apt purge vim -y
		sudo add-apt-repository ppa:neovim-ppa/unstable
		sudo apt-get update
		sudo apt-get install neovim clangd unzip -y
	}
 else {
		info("Neovim found")
	}

	if (!(Get-Command tmux -ErrorAction SilentlyContinue)) {
		info("Neovim not found, installing")
		sudo apt-get update
		sudo apt-get install tmux
	}
 else {
		info("TMUX found")
	}

	$nvim_dst = Join-Path $env:HOME "/.config/nvim/" 
	$nvim_src = Join-Path $PWD "/nvim/"
	Set-Symlink $nvim_dst $nvim_src

	$tmux_dst = Join-Path $env:HOME ".tmux.conf"
	Set-Symlink $tmux_dst "$PWD/tmux/tmux.conf"
}

function WindowsConfig {
	foreach ($prog in $WingetPrograms) {
		Invoke-Expression ("winget install {0:}" -f $prog)
	}

	$nvim_dst = Join-Path $env:USERPROFILE "/AppData/Local/nvim/" 
	$nvim_src = Join-Path $PWD "/nvim/"
	Set-Symlink $nvim_dst $nvim_src

	Set-Symlink "$HOME/.wezterm.lua" "$PWD/wezterm/.wezterm.lua"
	Set-Symlink $profile "$PWD/pwsh/Microsoft.PowerShell_profile.ps1"

	# Setting Sym Server Config for Process Exploerer and Windbg
	Set-Env "_NT_SYMBOL_PATH" $sym_config
}



. $PSScriptRoot/util.ps1
& $MainFunction
