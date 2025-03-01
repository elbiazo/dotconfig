# Required for Wezterm Multiplexer to work
# Q: https://github.com/wezterm/wezterm/issues/5335
# A: https://wezfurlong.org/wezterm/shell-integration.html#osc-7-on-windows-with-powershell-with-starship
function prompt {
    $p = $executionContext.SessionState.Path.CurrentLocation
    $osc7 = ""
    if ($p.Provider.Name -eq "FileSystem") {
        $ansi_escape = [char]27
        $provider_path = $p.ProviderPath -Replace "\\", "/"
        $osc7 = "$ansi_escape]7;file://${env:COMPUTERNAME}/${provider_path}${ansi_escape}\"
    }
    "${osc7}PS $p$('>' * ($nestedPromptLevel + 1)) ";
}

function Enter-Dev {
    $vspath = &"${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe" -property installationpath
    Import-Module $vsPath/Common7/Tools/Microsoft.VisualStudio.DevShell.dll
    Enter-VsDevShell -VsInstallPath $vsPath -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64 -no_logo'
}

Set-Alias -Name dev -Value Enter-Dev
Set-Alias -Name vim -Value nvim
Set-Alias -Name gh -Value Get-Help
Set-Alias -Name ll -Value ls
Set-Alias -Name sl -Value ls -Force
