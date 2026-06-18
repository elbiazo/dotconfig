# =============================================================================
# Microsoft.PowerShell_profile.ps1 - PowerShell user profile
#
# Custom prompt (with WezTerm OSC 7 support), Visual Studio dev shell helpers,
# PATH utilities, and convenience aliases.
# =============================================================================

# --- Custom Prompt ---

# Keeps terminal splitters and multiplexers in sync with PowerShell's CWD.
# PowerShell tracks its provider location separately from the process CWD, so
# keep both aligned for tools that inspect the shell process.
function prompt {
    $p = $executionContext.SessionState.Path.CurrentLocation

    if ($p.Provider.Name -eq "FileSystem") {
        # Without this, zellij new-pane cwd won't work
        [System.Environment]::CurrentDirectory = $p.ProviderPath
    }

    "$p$('>' * ($nestedPromptLevel + 1)) ";
}

# --- Visual Studio Developer Shell ---

# Enters the VS Developer Shell for the selected (or sole) VS installation.
# When multiple installations exist, the user is prompted to choose one.
function Enter-Dev {
    $vspath = &"${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe" -property installationpath

    if ($vspath -is [array]) {
        Write-Output "Multiple Visual Studio installations found."
        for ($i = 0; $i -lt $vspath.Length; $i++) {
            Write-Output "[$i]: $($vspath[$i])"
        }
        $vs_selection = Read-Host "Enter the number of the installation to use: "

        if ($vs_selection -lt 0 -or $vs_selection -ge $vspath.Length) {
            Write-Error "Invalid selection. Exiting."
            return
        }
        else {
            $vspath = $vspath[$vs_selection]
        }
    }

    Import-Module $vsPath/Common7/Tools/Microsoft.VisualStudio.DevShell.dll
    Write-Host "Entering Visual Studio Developer Shell at: $vsPath"
    Enter-VsDevShell -VsInstallPath $vsPath -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64 -no_logo'
}

# Enters the VS Developer Shell for the Preview installation specifically.
function Enter-PreviewDev {
    $vspath = &"${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe" -property installationpath
    $vspath = Split-Path $vspath
    $vspath += "/Preview"
    Import-Module $vsPath/Common7/Tools/Microsoft.VisualStudio.DevShell.dll
    Enter-VsDevShell -VsInstallPath $vsPath -SkipAutomaticLocation -DevCmdArguments '-arch=x64 -host_arch=x64 -no_logo'
}

# --- PATH Utilities ---

# Reloads the PATH from Machine + User scopes into the current process.
function Update-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") +
    ";" +
    [System.Environment]::GetEnvironmentVariable("Path", "User")
}

# Adds and/or removes entries from the PATH at the given scope.
function Set-Path {
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

# --- Formatting Helpers ---

# Converts an integer to a hex string (e.g. 255 -> "0xff").
function Format-NumHex {
    param(
        [Parameter(Mandatory = $true, Position = 0)]
        [int]$num
    )
    '0x{0:x}' -f $num
}

function ll { ls.exe -la --color=auto @args }

# --- Aliases ---
Set-Alias -Name dev   -Value Enter-Dev
Set-Alias -Name pdev  -Value Enter-PreviewDev
Set-Alias -Name ghp    -Value Get-Help
Set-Alias -Name sl    -Value ls.exe -Force
Set-Alias -Name vim   -Value nvim
Set-Alias -Name hex   -Value Format-NumHex
Set-Alias -Name count -Value Measure-Object
