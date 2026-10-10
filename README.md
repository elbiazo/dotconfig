# Dot Config

Dotfiles for Windows, Linux, and macOS. One Python installer reads platform app
dependencies from `config.toml`; no shell or PowerShell setup script is needed.

## Layout

```text
setup.py                  Cross-platform test/install/uninstall entry point
config.toml               Windows, Linux, and macOS app dependencies
windows/pwsh/profile.ps1   Windows PowerShell profile
linux/zsh/zshrc            Linux zsh options and plugins
mac/zsh/zshrc              macOS zsh options and plugins
common/zsh/zshrc           Shared zsh aliases, prompt, and completion
common/tests/             Shared Python tests
common/tmux/tmux.conf      Shared tmux/psmux config
common/nvim/              Shared Neovim checkout (gitignored)
```

Files shared by two or more platforms belong in `common/`; platform-specific
files belong in `windows/`, `linux/`, or `mac/`.

## Requirements

- **All platforms:** Python **3.11+**. TOML support comes from the standard
  library, so there are no Python packages to install.
- **Windows:** winget (Windows App Installer). The copied profile is for
  PowerShell 7; PowerShell is not required to run the installer.
- **macOS:** Git, [Homebrew](https://brew.sh), and Xcode Command Line Tools for
  compiling Neovim tree-sitter grammars.
- **Linux:** Git, Ubuntu with apt, and sudo when not running as root. The
  default Neovim package uses `ppa:neovim-ppa/unstable`, which requires Ubuntu.
  Other apt-based distributions need their own package/PPA choices in
  `config.toml`; other package managers are not supported.
- GitHub SSH access is needed to clone the configured Neovim repository.
- Node.js is needed for Neovim tooling such as pyright and Copilot; it is
  installed automatically on Windows.

## Setup

```sh
# macOS / Linux: test first, then install
python3 setup.py
```

```powershell
# Windows (Python launcher): test first, then install
py -3 setup.py
```

Source paths are relative to `setup.py`, not the working directory, so invoking
it by absolute path also works.

| Command | Behavior |
| --- | --- |
| `python3 setup.py` | Run tests, then install only if they pass. |
| `python3 setup.py --test` | Run the tests only; do not install or configure anything. |
| `python3 setup.py --install` | Install apps and configure dotfiles without running tests. |
| `python3 setup.py --uninstall` | Undo config changes without running tests or removing apps. |

On Windows, replace `python3` with `py -3`. The three flags are mutually
exclusive. A failed test run stops the default setup before any package
installation or config changes. The test runner uses the same Python interpreter
as setup and runs from the repository root.

The install step installs missing apps, clones Neovim into `common/nvim/`, and
**copies** the Neovim, tmux, and Windows PowerShell configs into place. Every
copy prompts for confirmation (`y/n`).
Replacing an existing config moves it to `<config>.bak`, replacing the previous
backup. Declining leaves the config and its backup unchanged. On Linux and
macOS, zsh is configured by appending source lines instead of copying `.zshrc`.

Setup also prompts before replacing an existing Neovim checkout; declining
reuses it. A replacement is cloned successfully before the old checkout is
removed. On Windows, replacing the checkout also clears `nvim-data` as before.
If upgrading from the original layout, move `nvim/` to `common/nvim/` to retain
your checkout.

| Platform | Default apps | Config destinations |
| --- | --- | --- |
| Windows | Neovim, PowerToys, Node.js LTS, Git, VS Code, psmux, coreutils; tree-sitter CLI via npm | `%LOCALAPPDATA%/nvim`, `~/.tmux.conf`, the Windows Documents folder's `PowerShell/profile.ps1` |
| Linux | Neovim, tmux, clangd, unzip, curl, build-essential, zsh, zsh-autosuggestions, zsh-syntax-highlighting | `$XDG_CONFIG_HOME/nvim` (default `~/.config/nvim`), `~/.tmux.conf`, a source block in `.zshrc` |
| macOS | Neovim, tmux, tree-sitter CLI, zsh-autosuggestions, zsh-syntax-highlighting | `$XDG_CONFIG_HOME/nvim` (default `~/.config/nvim`), `~/.tmux.conf`, a source block in `.zshrc` |

Windows Documents redirection (including OneDrive) is respected.

## Zsh on Linux and macOS

Setup automatically appends a marked block to your existing `~/.zshrc`, or
creates that file if missing, without asking for confirmation. An exported
`ZDOTDIR` selects `$ZDOTDIR/.zshrc` instead.
Your existing settings remain in place, and an existing `.zshrc.bak` is not
changed. The block sources the shared options first, then the current platform:

```zsh
# >>> dotconfig zsh >>>
source /absolute/path/to/dotconfig/common/zsh/zshrc
source /absolute/path/to/dotconfig/linux/zsh/zshrc
# <<< dotconfig zsh <<<
```

On macOS the second line sources `mac/zsh/zshrc`. Paths are shell-quoted when
needed. Running setup again skips an identical block without prompting or
adding duplicates. If the repository moved or the platform changed, setup
automatically updates just the block. Duplicate or incomplete markers are reported
as errors rather than guessing which content to replace.

An existing `.zshrc` symlink is kept and its target is edited. Dangling links
and links back into this repository are rejected to avoid broken or recursive
configuration.

Shared settings provide aliases, a colored prompt, and completion. Linux adds
GNU `ls` colors and apt-installed zsh plugins; macOS adds BSD `ls` colors, the
VS Code CLI path, and Homebrew plugins. These settings run after your existing
settings, so shared alias/prompt definitions take precedence. Settings from
older, copied `.zshrc` files are not automatically removed.

Keep the repository at the sourced location; edits to these config files take
effect in the next zsh session without rerunning setup. Run `zsh` to try it.
Setup installs zsh on Linux but does **not** change your login shell.

## `config.toml` reference

Edit `config.toml` beside `setup.py`. The installer reads `[neovim]` and the
section for the current OS: `[windows]`, `[linux]`, or `[mac]`. Section and field
names are case-sensitive. Sections for other operating systems are not required
or schema-checked during that run, but the entire file must be valid TOML.

### Sections and fields

These are all supported section-level fields:

| Field | TOML type | Required / default | Purpose |
| --- | --- | --- | --- |
| `neovim.repository` | String | Required on every install; no implicit default | Git repository URL or path to clone into `common/nvim/`. SSH and HTTPS URLs are supported; SSH URLs require working SSH access. |
| `windows.winget` | Array of app tables | Required on Windows; `[]` is allowed | Apps to check/install using exact WinGet package IDs. |
| `windows.npm` | Array of strings | Optional; defaults to `[]` | npm package names/specifiers to install globally on Windows. Unlike the other arrays, entries are strings, not app tables. |
| `linux.apt` | Array of app tables | Required on Linux; `[]` is allowed | Packages to check/install using apt. App entries may specify an Ubuntu PPA. |
| `mac.brew` | Array of app tables | Required on macOS; `[]` is allowed | Homebrew formulae to check/install. The section is named `mac`, not `macos`. |

The checked-in file supplies the default app lists and Neovim repository;
the installer does not substitute built-in app lists for omitted fields.
Use an empty manager array to request no packages from that manager, although
the manager must still be available. Config setup still runs. Omitting an app
or emptying an array does **not** uninstall previously installed packages.

### App-table fields

Each entry in `windows.winget`, `linux.apt`, or `mac.brew` supports the fields
below. `windows.npm` does not use these tables.

| Field | TOML type | Required / default | Behavior |
| --- | --- | --- | --- |
| `package` | String | Required | WinGet package ID, apt package name, or Homebrew formula name passed to the package manager. |
| `commands` | Array of strings | Optional; defaults to `[]` | For apt/Homebrew, skip installation only if **all** listed executables can be found on PATH. With no entries, query the package manager instead. Accepted for WinGet entries but ignored: WinGet always checks the exact package ID. |
| `ppa` | String | Optional; omitted means no PPA | **Linux apt entries only.** Must start with `ppa:`, such as `ppa:neovim-ppa/unstable`. Add this PPA only if the associated app is missing. PPA installation requires Ubuntu. |

All string values must be nonempty. `package` values and `windows.npm` entries
must not contain whitespace or start with `-`. Each `commands` entry is an
executable to look up, not a shell command to execute; arguments and version
checks are not supported. For example, `commands = ["make", "cc"]` requests
installation if either executable is missing. `commands = []` has the same
behavior as omitting `commands`.

When a missing app needs a PPA, setup installs `software-properties-common`
if `add-apt-repository` is unavailable. On other apt-based distributions, omit
the `ppa` field and choose packages available in that distribution's repositories.

Windows npm packages are passed to `npm install -g` on **every install run**,
after WinGet finishes and the process PATH is refreshed; they do not have an
installed-package check. npm must already be available or be installed through
`windows.winget`, for example with `OpenJS.NodeJS.LTS`. Omitting `windows.npm`
or setting it to `[]` skips this step.

Unknown keys inside the active OS section or its app tables are rejected.
There are no additional fields for install arguments, dependency graphs, pip
packages, or shell hooks. Config destinations and zsh source files are not
configured through TOML.

### Example using every supported field

This illustrates the schema, not the complete default app list:

```toml
[neovim]
repository = "git@github.com:elbiazo/kickstart.nvim.git"

[windows]
winget = [
    { package = "Microsoft.Git" },
    { package = "OpenJS.NodeJS.LTS" },
    { package = "Neovim.Neovim" },
]
npm = ["tree-sitter-cli"]

[linux]
apt = [
    { package = "neovim", commands = ["nvim"], ppa = "ppa:neovim-ppa/unstable" },
    { package = "build-essential", commands = ["make", "cc"] },
    { package = "ripgrep", commands = ["rg"] },
    { package = "zsh-autosuggestions" },
]

[mac]
brew = [
    { package = "neovim", commands = ["nvim"] },
    { package = "zsh-autosuggestions" },
]
```

Add app tables to the relevant array to install more apps. TOML's
array-of-tables syntax, such as `[[linux.apt]]` with `package`, `commands`, and
`ppa` on separate lines, is also supported; use one style per array.

## Uninstall configs

```sh
python3 setup.py --uninstall
```

```powershell
py -3 setup.py --uninstall
```

Uninstall visits the config destinations for the current platform and asks
before each change. For copied configs, it restores the latest `<config>.bak`
if one exists, otherwise it offers to remove the config. Missing configs are
skipped, and declining keeps both the config and backup. Restoring a backup
consumes that `.bak` file. Review the paths in the prompts, especially if you
have replaced configs manually.

For zsh, uninstall removes **only the marked source block**, leaving all other
`.zshrc` content (including later additions) and `.zshrc.bak` untouched. An empty
`.zshrc` is kept. Files without a managed block are left alone.

**Installed apps, package repositories, Neovim caches, and `common/nvim/` are
left alone.** Uninstall does not require Git, package managers, or `config.toml`.

## Tests

```sh
python3 setup.py --test
```

On Windows, use `py -3 setup.py --test`. This is the same suite run automatically
before the default setup. To invoke unittest directly:

```sh
python3 -m unittest discover -s common/tests -v
```

Tests use temporary configs and mocked package managers; they do not install
apps or change your home directory. PowerShell profile checks run only when
`pwsh` is available.
Live zsh checks run when zsh is available; the Linux plugin startup check also
requires the two apt-installed plugins.

## Vim

### LSP via Mason Plugin

Use `:Mason` to inspect language servers and `:MasonInstall rust-analyzer` to
install one.

### Copilot

Currently disabled. Requires Node.js; configure it with `:Copilot setup`.
