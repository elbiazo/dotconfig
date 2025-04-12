# This function will set the symlink if it doesn't exists. else it will save it
# with .old extension and set it with new one
function Set-Symlink([string]$dst, [string]$src, [switch]$backup) {
    info("Setting Symlink {0:} <- {1:}" -f $dst, $src)

    # if path exists then try to save old one
    if (Get-Item-Exist($dst)) {
        if ($backup) {
            info($dst + " exists so move it to .old")
            Move-Item -Path $dst -Destination ($dst + ".old") -Force
        }
        else {
            info($dst + " exists, removing it")
            if ($IsWindows) {
                Remove-Item $dst -r -Force
            }
            else {
                Remove-Item -f $dst # Remove-Item doesn't remove symlink in unix
            }
        }
    }

    New-Item -Path $dst -ItemType SymbolicLink -Value $src -Force
}

function Get-Yes-No([string]$msg) {
    if ((Read-Host $msg " [y/n]") -eq "y") {
        return $true
    }
    else {
        return $false
    }
}

function Get-Item-Exist([string]$dst) {
    if (Get-Item $dst -ErrorAction SilentlyContinue) {
        return $true
    }
    else {
        return $false
    }
}

function Write-Info([string]$msg) {
    Write-Output ("[+] {0:}" -f $msg)
}

function Get-Command-Exist([string]$cmd) {
    if (get-command -ErrorAction SilentlyContinue $cmd) {
        Write-Output $true 
    }
    else {
        Write-Output $false 
    }
}
function Set-Env([string] $env_name, [string] $env_path) {
    if ($env_name -eq "Path") {
        Write-Error "Currently not supporting writing Path env variable"
        return $false
    }

    Write-Output "Setting $env_name"

    $cur_env = [Environment]::GetEnvironmentVariable($env_name)
    if ($null -eq $cur_env) {
        Write-Output ("{0} doesn't exist. Creating env and setting it to {1}" -f $env_name, $env_path)
        [Environment]::SetEnvironmentVariable($env_name, $env_path, [System.EnvironmentVariableTarget]::Machine)
    }
    else {
        Write-Output ("{0} already exists and is it set to {1}" -f $env_name , $cur_env)
    }
}

New-Alias -Name info -Value Write-Info