# =============================================================================
# util.ps1 - Shared helper functions for dotfile setup
#
# Provides symlink management, user prompts, path/env helpers, and logging.
# Sourced by setup.ps1 before any other logic runs.
# =============================================================================

# --- Symlink Management ---

# Creates a symbolic link from $dst -> $src.
# If $dst already exists it is either backed up (.old) or removed, depending
# on the -backup switch.
function Set-Symlink([string]$dst, [string]$src, [switch]$backup) {
    info("Setting Symlink {0} <- {1}" -f $dst, $src)

    if (Get-ItemExist($dst)) {
        if ($backup) {
            info($dst + " exists, backing up to .old")
            Move-Item -Path $dst -Destination ($dst + ".old") -Force
        } else {
            info($dst + " exists, removing it")
            if ($IsWindows) {
                Remove-Item $dst -r -Force
            } else {
                # On Linux the trailing '/' must be stripped because a symlink
                # is a file, not a directory.
                Remove-Item -Force $dst.TrimEnd('/')
            }
        }
    }

    New-Item -Path $dst -ItemType SymbolicLink -Value $src -Force | Out-Null
}

# --- User Prompts ---

# Prompts the user with a yes/no question and returns $true for 'y'.
function Get-Yes-No([string]$msg) {
    if ((Read-Host $msg " [y/n]") -eq "y") {
        return $true
    } else {
        return $false
    }
}

# --- Path / Item Helpers ---

# Returns $true if the given path exists (file or directory).
function Get-ItemExist([string]$dst) {
    if (Get-Item $dst -ErrorAction SilentlyContinue) {
        return $true
    } else {
        return $false
    }
}

# Returns $true if the given command is available on the PATH.
function Get-Command-Exist([string]$cmd) {
    if (Get-Command -ErrorAction SilentlyContinue $cmd) {
        Write-Output $true
    } else {
        Write-Output $false
    }
}

# --- Logging ---

# Writes a prefixed informational message to stdout.
function Write-Info([string]$msg) {
    Write-Output ("[+] {0}" -f $msg)
}

# --- Environment Variables ---

# Sets a machine-level environment variable. Refuses to modify the PATH
# variable to prevent accidental corruption.
function Set-Env([string] $env_name, [string] $env_path) {
    if ($env_name -eq "Path") {
        Write-Error "Currently not supporting writing Path env variable"
        return $false
    }

    Write-Output "Setting $env_name"

    $cur_env = [Environment]::GetEnvironmentVariable($env_name)
    if ($null -eq $cur_env) {
        Write-Output ("{0} doesn't exist. Creating and setting to {1}" -f $env_name, $env_path)
        [Environment]::SetEnvironmentVariable($env_name, $env_path, [System.EnvironmentVariableTarget]::Machine)
    } else {
        Write-Output ("{0} already exists, set to {1}" -f $env_name, $cur_env)
    }
}

# --- Aliases ---
New-Alias -Name info -Value Write-Info