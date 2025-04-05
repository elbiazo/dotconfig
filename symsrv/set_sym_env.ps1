
# Set Symbol Server for tools like procexp64.exe windbg, vs, etc
# run it as admin shell or use sudo

$sym_config = "srv*C:\symbols*https://msdl.microsoft.com/download/symbols"

Write-Output "Setting _NT_SYMBOL_PATH"
$cur_env = [Environment]::GetEnvironmentVariable("_NT_SYMBOL_PATH")
if ($null -eq $cur_env) {
	Write-Output ("_NT_SYMBOL_PATH doesn't exist. Creating env and setting it to {0}" -f $sym_config)
	[Environment]::SetEnvironmentVariable("_NT_SYMBOL_PATH", $sym_config, [System.EnvironmentVariableTarget]::Machine)
} else {
	Write-Output ("_NT_SYMBOL_PATH already exists and is it set to {0}" -f $cur_env)
}
