# Required for Wezterm Multiplexer to work
# Q: https://github.com/wezterm/wezterm/issues/5335
# A: https://wezfurlong.org/wezterm/shell-integration.html#osc-7-on-windows-with-powershell-with-starship
function prompt {
    $osc7 = ""
    $p = $executionContext.SessionState.Path.CurrentLocation

    # Need to change \\ to / for WezTerm multiplexer. Doing this to vscode will break split term because it won't be able to found CWD
    if($env:TERM_PROGRAM -eq "WezTerm"){
        if ($p.Provider.Name -eq "FileSystem") {
            $ansi_escape = [char]27
            $provider_path = $p.ProviderPath -Replace "\\", "/"
            $osc7 = "$ansi_escape]7;file://${env:COMPUTERNAME}/${provider_path}${ansi_escape}\"
        }
    }

    "${osc7}$p$('>' * ($nestedPromptLevel + 1)) ";
}

function Enter-Dev {
    $vspath = &"${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe" -property installationpath
    Import-Module $vsPath/Common7/Tools/Microsoft.VisualStudio.DevShell.dll
    Enter-VsDevShell -VsInstallPath $vsPath -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64 -no_logo'
}
function Enter-PreviewDev {
    $vspath = &"${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe" -property installationpath
    $vspath = Split-Path $vspath
    $vspath += "/Preview"
    Import-Module $vsPath/Common7/Tools/Microsoft.VisualStudio.DevShell.dll
    Enter-VsDevShell -VsInstallPath $vsPath -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64 -no_logo'
}

function Update-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") +
                ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
}

function Format-NumHex{
    param(
        [Parameter(Mandatory=$true, Position=0)]
        [int]$num
     )
    '0x{0:x}' -f $num
}

Function Set-Path {
    param (
        [string]$AddPath,
        [string]$RemovePath,
        [ValidateSet('Process', 'User', 'Machine')]
        [string]$Scope = 'Process'
    )
    $regexPaths = @()
    if ($PSBoundParameters.Keys -contains 'AddPath') {
        $regexPaths += [regex]::Escape($AddPath)
    }

    if ($PSBoundParameters.Keys -contains 'RemovePath') {
        $regexPaths += [regex]::Escape($RemovePath)
    }
    
    $arrPath = [System.Environment]::GetEnvironmentVariable('PATH', $Scope) -split ';'
    foreach ($path in $regexPaths) {
        $arrPath = $arrPath | Where-Object { $_ -notMatch "^$path\\?" }
    }
    $value = ($arrPath + $addPath) -join ';'
    [System.Environment]::SetEnvironmentVariable('PATH', $value, $Scope)
}

Set-Alias -Name dev -Value Enter-Dev
Set-Alias -Name pdev -Value Enter-PreviewDev
Set-Alias -Name gh -Value Get-Help
Set-Alias -Name ll -Value ls
Set-Alias -Name sl -Value ls -Force
Set-Alias -Name vim -Value nvim
Set-Alias -Name hex -Value Format-NumHex
Set-Alias -Name count -Value Measure-Object
