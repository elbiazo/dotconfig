# Oh My Posh

## Powershell Split

To get split respect current working directory you need to add pwd to the oh-my-posh theme
```
"pwd": "osc99",
```

And add this to Windows Terminal Settings

```
{
    "command": 
    {
        "action": "splitPane",
        "split": "down",
        "splitMode": "duplicate"
    },
    "keys": "alt+s"
},
{
    "command": 
    {
        "action": "splitPane",
        "split": "right",
        "splitMode": "duplicate"
    },
    "keys": "alt+v"
},
```
