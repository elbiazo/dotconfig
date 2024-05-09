Set-Alias gh Get-Help
oh-my-posh init pwsh --config "$profile\..\oh-my-posh\peru.omp.json" | Invoke-Expression

Set-Alias -Name vim -Value nvim

# TODO: Implement similar command in the future.
# Only thing missing on ll is to display owner and hidden maybe
Set-Alias -Name ll -Value ls
