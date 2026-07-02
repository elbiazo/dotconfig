# =============================================================================
# test.ps1 - Smoke tests for the pwsh utils and profile functions
#
# Sources util.ps1 and pwsh/profile.ps1, exercises their functions inside a
# scratch ./tmp directory, then removes ./tmp afterward. Interactive and
# system-modifying calls (Read-Host, Set-Env on PATH) are mocked or limited to
# their safe branch so the suite runs unattended.
#
# Usage: pwsh ./test.ps1
# =============================================================================

# Source the code under test
. $PSScriptRoot/util.ps1
. $PSScriptRoot/pwsh/profile.ps1

$script:Passed = 0
$script:Failed = 0

# Records a pass/fail line for a single assertion.
function Assert([bool]$cond, [string]$name) {
    if ($cond) {
        Write-Host "[PASS] $name" -ForegroundColor Green
        $script:Passed++
    } else {
        Write-Host "[FAIL] $name" -ForegroundColor Red
        $script:Failed++
    }
}

$tmp = Join-Path $PSScriptRoot "tmp"

try {
    # Fresh scratch directory
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    New-Item -ItemType Directory -Path $tmp | Out-Null

    # --- Get-ItemExist ---
    Assert (Get-ItemExist $tmp) "Get-ItemExist: true for existing path"
    Assert (-not (Get-ItemExist (Join-Path $tmp "missing"))) "Get-ItemExist: false for missing path"

    # --- Write-Info / info alias ---
    Assert ((Write-Info "hello") -eq "[+] hello") "Write-Info: prefixes [+]"
    Assert ((info "world") -eq "[+] world") "info: alias resolves to Write-Info"

    # --- Get-Command-Exist ---
    Assert ([bool](Get-Command-Exist "pwsh")) "Get-Command-Exist: true for pwsh"
    Assert (-not [bool](Get-Command-Exist "no-such-cmd-xyz-123")) "Get-Command-Exist: false for missing command"

    # --- Set-Env (safe branch: refuses to touch PATH) ---
    $r = Set-Env "Path" "should-be-ignored" 2>$null
    Assert ($r -eq $false) "Set-Env: refuses to modify PATH"

    # --- Get-Yes-No (Read-Host mocked) ---
    function Read-Host { param([string]$Prompt) return $script:MockRead }
    $script:MockRead = "y"
    Assert (Get-Yes-No "continue?") "Get-Yes-No: true when input is y"
    $script:MockRead = "n"
    Assert (-not (Get-Yes-No "continue?")) "Get-Yes-No: false when input is n"

    # --- Set-Config: fresh copy (no existing dst, no prompt) ---
    $src = Join-Path $tmp "src.txt"
    $dst = Join-Path $tmp "dst.txt"
    "content-v1" | Set-Content $src
    Set-Config $dst $src
    Assert (Test-Path $dst) "Set-Config: copies to a new destination"
    Assert ((Get-Content $dst) -eq "content-v1") "Set-Config: destination matches source"

    # --- Set-Config: overwrite with backup (Get-Yes-No mocked -> yes) ---
    function Get-Yes-No([string]$m) { return $true }
    "content-v2" | Set-Content $src
    Set-Config $dst $src
    Assert (Test-Path "$dst.bak") "Set-Config: backs existing dst up to .bak"
    Assert ((Get-Content "$dst.bak") -eq "content-v1") "Set-Config: .bak keeps the old content"
    Assert ((Get-Content $dst) -eq "content-v2") "Set-Config: dst updated to new content"

    # --- Set-Config: keep existing (Get-Yes-No mocked -> no) ---
    function Get-Yes-No([string]$m) { return $false }
    "content-v3" | Set-Content $src
    Set-Config $dst $src
    Assert ((Get-Content $dst) -eq "content-v2") "Set-Config: leaves dst untouched when declined"

    # --- Format-NumHex / hex alias (from profile.ps1) ---
    Assert ((Format-NumHex 255) -eq "0xff") "Format-NumHex: 255 -> 0xff"
    Assert ((Format-NumHex 0) -eq "0x0") "Format-NumHex: 0 -> 0x0"
    Assert ((Format-NumHex 4096) -eq "0x1000") "Format-NumHex: 4096 -> 0x1000"
    Assert ((hex 255) -eq "0xff") "hex: alias resolves to Format-NumHex"

    # --- Profile functions are defined (not executed: platform/interactive) ---
    foreach ($fn in "prompt", "Enter-Dev", "Enter-PreviewDev", "Update-Path", "Set-Path", "ll") {
        Assert ([bool](Get-Command $fn -ErrorAction SilentlyContinue)) "profile: $fn is defined"
    }

    # --- Set-Path add/remove (Process scope; Windows ';' PATH semantics) ---
    if ($IsWindows) {
        $savedPath = [Environment]::GetEnvironmentVariable('PATH', 'Process')
        try {
            Set-Path -AddPath 'C:\dotconfig\testpath' -Scope Process
            $after = [Environment]::GetEnvironmentVariable('PATH', 'Process') -split ';'
            Assert ($after -contains 'C:\dotconfig\testpath') "Set-Path: adds an entry (Process scope)"
            Set-Path -RemovePath 'C:\dotconfig\testpath' -Scope Process
            $after2 = [Environment]::GetEnvironmentVariable('PATH', 'Process') -split ';'
            Assert (-not ($after2 -contains 'C:\dotconfig\testpath')) "Set-Path: removes an entry (Process scope)"
        } finally {
            [Environment]::SetEnvironmentVariable('PATH', $savedPath, 'Process')
            $env:PATH = $savedPath
        }
    } else {
        Write-Host "[SKIP] Set-Path/Update-Path exercise (Windows-only ';' PATH semantics)" -ForegroundColor Yellow
    }
}
finally {
    # Always clean up the scratch directory.
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
}

Write-Host ""
Write-Host ("Results: {0} passed, {1} failed" -f $script:Passed, $script:Failed)
if ($script:Failed -gt 0) { exit 1 } else { exit 0 }
