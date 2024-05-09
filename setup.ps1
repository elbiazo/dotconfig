$WindowsPrograms = @(
	"Neovim.Neovim",
	"JanDeDobbeleer.OhMyPosh"
	# "glzr-io.glazewm"
	# "wez.wezterm"
)	


# / will be split and will be ORed
$CommonDependencies = @(
	"python3/python",
	"gcc/clang",
	"git",
	"cargo"
)

$WindowsDependencis = @(
	"winget",
	"win32yank"
)

$RustDependencies = @(
	"ripgrep/rg",
	"fd-find/fd"
)

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

	foreach ($prog in $WindowsPrograms) {
		Invoke-Expression ("winget install {0:}" -f $prog)
	}
	if (Get-Item-Exist("$PWD/nvim")) {
		if (Get-Yes-No "Remove existing nvim?") {
			rm -r -Force ./nvim
			git clone git@github.com:elbiazo/kickstart.nvim.git ./nvim
		} else {
			info("Ignoring nvim folder")
		}

	} else {
		git clone git@github.com:elbiazo/kickstart.nvim.git ./nvim
	}

	# Set-Symlink "$HOME/.glaze-wm/config.yaml" "$PWD/glazewm/config.yaml"
	# Set-Symlink "$HOME/.wezterm.lua" "$PWD/wezterm/.wezterm.lua"
	
	Set-Symlink "$PROFILE/../oh-my-posh/peru.omp.json" "$PWD/oh-my-posh/peru.omp.json"
	Set-Symlink $PROFILE "$PWD/pwsh/Microsoft.PowerShell_profile.ps1"

	$nvim_dst = Join-Path $env:USERPROFILE "/AppData/Local/nvim/" 
	$nvim_src = Join-Path $PWD "/nvim/"
	Set-Symlink $nvim_dst $nvim_src
}

function Invoke-Dep-Check() {

}

# This function will set the symlink if it doesn't exists. else it will save it
# with .old extension and set it with new one
function Set-Symlink([string]$dst, [string]$src, [switch]$backup) {
	info("Setting Symlink {0:} <- {1:}" -f $dst, $src)

	# if path exists then try to save old one
	if (Get-Item-Exist($dst)) {
		if ($backup){
			info($dst + " exists so move it to .old")
			Move-Item -Path $dst -Destination ($dst + ".old") -Force
		} else {
			info($dst + " exists, removing it")
			Remove-Item $dst -r -Force
		}
	}

	New-Item -Path $dst -ItemType SymbolicLink -Value $src -Force
}

function Get-Yes-No([string]$msg) {
	if ((Read-Host $msg " [y/n]") -eq "y") {
		return $true
	} else {
		return $false
	}
}

function Get-Item-Exist([string]$dst) {
	if (Get-Item $dst -ErrorAction SilentlyContinue) {
		return $true
	} else {
		return $false
	}
}

function Write-Info([string]$msg) {
	Write-Output ("[+] {0:}" -f $msg)
}

function Get-Command-Exist([string]$cmd) {
	if (get-command -ErrorAction SilentlyContinue $cmd) { echo $true } else { echo $false }
}

New-Alias -Name info -Value Write-Info


& $MainFunction
