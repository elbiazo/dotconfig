$MainFunction = {
	# Moving wezterm config
	Set-Symlink ($HOME+"/.glaze-wm/config.yaml") ($PWD.ToString() + "/glazewm/config.yaml")
	Set-Symlink ($HOME+"/.wezterm.lua") ($PWD.ToString() + "/wezterm/.wezterm.lua")
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
			Remove-Item $dst
		}
	}

	New-Item -Path $dst -ItemType SymbolicLink -Value $src 
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

New-Alias -Name info -Value Write-Info

& $MainFunction
