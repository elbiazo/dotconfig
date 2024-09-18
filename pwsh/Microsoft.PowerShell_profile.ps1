# Required to make wezterm respect powershell dir
## Problem: https://github.com/wez/wezterm/issues/5335
## Solution: https://github.com/JanDeDobbeleer/oh-my-posh/issues/2515#issuecomment-1374322136
function Set-EnvVar
{
	$p = $executionContext.SessionState.Path.CurrentLocation
	$osc7 = ""
	if ($p.Provider.Name -eq "FileSystem")
	{
		$ansi_escape = [char]27
		$provider_path = $p.ProviderPath -Replace "\\", "/"
		$osc7 = "$ansi_escape]7;file://${env:COMPUTERNAME}/${provider_path}${ansi_escape}\"
	}
	$env:OSC7=$osc7
}
New-Alias -Name 'Set-PoshContext' -Value 'Set-EnvVar' -Scope Global -Force

oh-my-posh init pwsh --config "$profile\..\oh-my-posh\peru.omp.json" | Invoke-Expression

Set-Alias -Name vim -Value nvim
Set-Alias gh Get-Help

# TODO: Implement similar command in the future.
# Only thing missing on ll is to display owner and hidden maybe
Set-Alias -Name ll -Value ls
