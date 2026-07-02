# =============================================================================
# util.ps1 - Shared helper functions for dotfile setup
#
# Provides symlink management, user prompts, path/env helpers, and logging.
# Sourced by setup.ps1 before any other logic runs.
# =============================================================================

# --- Config Management ---

# Copies a config from $src to $dst.
# If $dst already exists the user is prompted before overwriting. When the user
# confirms, the existing config is backed up to "$dst.bak" (any previous backup
# is replaced) and then $src is copied into place. Answering 'n' leaves the
# existing config untouched.
function Set-Config([string]$dst, [string]$src) {
    # Normalise trailing slashes so directory copies land at the right path.
    $dst = $dst.TrimEnd('/', '\')
    $src = $src.TrimEnd('/', '\')

    info("Setting Config {0} <- {1}" -f $dst, $src)

    if (Get-ItemExist($dst)) {
        if (Get-Yes-No ("{0} already exists. Overwrite?" -f $dst)) {
            $bak = $dst + ".bak"
            info("Backing up {0} -> {1}" -f $dst, $bak)
            if (Get-ItemExist($bak)) {
                Remove-Item -Recurse -Force $bak
            }
            Move-Item -Path $dst -Destination $bak -Force
        } else {
            info("Keeping existing {0}, skipping" -f $dst)
            return
        }
    }

    # Ensure the parent directory exists before copying.
    $parent = Split-Path -Parent $dst
    if ($parent -and !(Test-Path $parent)) {
        New-Item -Path $parent -ItemType Directory -Force | Out-Null
    }

    Copy-Item -Path $src -Destination $dst -Recurse -Force
}

# --- User Prompts ---

# Prompts the user with a yes/no question and returns $true for 'y'.
function Get-Yes-No([string]$msg) {
    if ((Read-Host ($msg + " [y/n]")) -eq "y") {
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