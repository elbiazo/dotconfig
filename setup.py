#!/usr/bin/env python3
"""Test and install dotfiles, run either step separately, or uninstall configs."""

import sys

if sys.version_info < (3, 11):
    sys.exit("Python 3.11 or newer is required to read config.toml.")

import argparse
import os
import platform
import shlex
import shutil
import stat
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANAGERS = {"windows": "winget", "linux": "apt", "mac": "brew"}
WINGET_NOT_FOUND = 0x8A150014
ZSH_BLOCK_START = b"# >>> dotconfig zsh >>>"
ZSH_BLOCK_END = b"# <<< dotconfig zsh <<<"


class SetupError(Exception):
    pass


@dataclass(frozen=True)
class App:
    package: str
    commands: tuple[str, ...] = ()
    ppa: str | None = None


@dataclass(frozen=True)
class Settings:
    repository: str
    apps: tuple[App, ...]
    npm: tuple[str, ...] = ()


def info(message: str) -> None:
    print(f"[+] {message}", flush=True)


def confirm(message: str) -> bool:
    try:
        return input(f"{message} [y/n] ").strip().lower() == "y"
    except EOFError as error:
        raise SetupError("No response received; setup stopped.") from error


def current_platform() -> str:
    name = platform.system()
    platforms = {"Windows": "windows", "Linux": "linux", "Darwin": "mac"}
    if name not in platforms:
        raise SetupError(f"Unsupported OS: {name}")
    return platforms[name]


def nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SetupError(f"{label} must be a nonempty string in config.toml.")
    return value


def string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SetupError(f"{label} must be an array of strings in config.toml.")
    return tuple(nonempty_string(item, label) for item in value)


def load_settings(system: str, path: Path | None = None) -> Settings:
    with (path or ROOT / "config.toml").open("rb") as stream:
        data = tomllib.load(stream)

    neovim = data.get("neovim")
    if not isinstance(neovim, dict):
        raise SetupError("config.toml must define [neovim].")
    repository = nonempty_string(neovim.get("repository"), "neovim.repository")
    section = data.get(system)
    if not isinstance(section, dict):
        raise SetupError(f"config.toml must define [{system}].")

    manager = MANAGERS[system]
    allowed_keys = {manager, "npm"} if system == "windows" else {manager}
    if section.keys() - allowed_keys:
        raise SetupError(f"Unknown settings in [{system}]: {section.keys() - allowed_keys}")
    entries = section.get(manager)
    if not isinstance(entries, list):
        raise SetupError(f"{system}.{manager} must be an array of app tables.")

    apps = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SetupError(f"Each {system}.{manager} app must be a table.")
        allowed_fields = {"package", "commands"}
        if system == "linux":
            allowed_fields.add("ppa")
        if entry.keys() - allowed_fields:
            raise SetupError(f"Unknown app fields: {entry.keys() - allowed_fields}")
        package = nonempty_string(entry.get("package"), f"{system}.{manager}.package")
        if package.startswith("-") or any(char.isspace() for char in package):
            raise SetupError(f"Invalid package name: {package!r}")
        commands = string_list(entry.get("commands", []), f"{package}.commands")
        ppa = entry.get("ppa")
        if ppa is not None:
            ppa = nonempty_string(ppa, f"{package}.ppa")
            if not ppa.startswith("ppa:"):
                raise SetupError(f"{package}.ppa must start with 'ppa:'.")
        apps.append(App(package, commands, ppa))

    npm = string_list(section.get("npm", []), f"{system}.npm")
    if any(
        package.startswith("-") or any(char.isspace() for char in package)
        for package in npm
    ):
        raise SetupError("Invalid npm package name in config.toml.")
    return Settings(repository, tuple(apps), npm)


def require_command(command: str) -> str:
    executable = shutil.which(command)
    if not executable:
        raise SetupError(
            f"{command} is required but is not on PATH. Install it and rerun setup."
        )
    return executable


def run(
    command: list[str], *, capture: bool = False, allowed: tuple[int, ...] = (0,),
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    executable = require_command(command[0])
    if not capture:
        info(f"Running {shlex.join(command)}")
    result = subprocess.run(
        [executable, *command[1:]],
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        check=False,
        cwd=cwd,
    )
    if result.returncode not in allowed:
        detail = f"\n{result.stdout.strip()}" if result.stdout else ""
        raise SetupError(f"Command failed ({result.returncode}): {shlex.join(command)}{detail}")
    return result


def run_tests() -> None:
    if not any((ROOT / "common/tests").glob("test*.py")):
        raise SetupError("No tests found in common/tests; refusing to continue.")
    run(
        [
            sys.executable, "-B", "-m", "unittest", "discover",
            "-s", "common/tests", "-v",
        ],
        cwd=ROOT,
    )


def run_as_root(command: list[str]) -> None:
    run(command if os.geteuid() == 0 else ["sudo", *command])


def app_installed(app: App, manager: str) -> bool:
    if manager != "winget" and app.commands:
        return all(shutil.which(command) for command in app.commands)
    if manager == "apt":
        result = run(
            ["dpkg-query", "-W", "-f=${Status}", app.package],
            capture=True,
            allowed=(0, 1),
        )
        return result.returncode == 0 and result.stdout == "install ok installed"
    if manager == "brew":
        return run(
            ["brew", "list", "--formula", app.package], capture=True, allowed=(0, 1)
        ).returncode == 0
    return run(
        [
            "winget", "list", "--id", app.package, "--exact",
            "--accept-source-agreements", "--disable-interactivity",
        ],
        capture=True,
        allowed=(0, WINGET_NOT_FOUND),
    ).returncode == 0


def refresh_windows_path() -> None:
    import winreg

    paths = [os.environ.get("PATH", "")]
    for hive, key in (
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
        (winreg.HKEY_CURRENT_USER, "Environment"),
    ):
        try:
            with winreg.OpenKey(hive, key) as registry:
                value, _ = winreg.QueryValueEx(registry, "Path")
        except FileNotFoundError:
            continue  # A user environment does not necessarily define PATH.
        paths.append(os.path.expandvars(value))
    os.environ["PATH"] = ";".join(paths)


def install_apps(system: str, settings: Settings) -> None:
    manager = MANAGERS[system]
    require_command("apt-get" if manager == "apt" else manager)
    missing = [app for app in settings.apps if not app_installed(app, manager)]

    if system == "linux" and missing:
        ppas = list(dict.fromkeys(app.ppa for app in missing if app.ppa))
        if ppas:
            if platform.freedesktop_os_release().get("ID") != "ubuntu":
                raise SetupError("The configured Neovim PPA requires Ubuntu.")
            if not shutil.which("add-apt-repository"):
                run_as_root(["apt-get", "update"])
                run_as_root(["apt-get", "install", "-y", "software-properties-common"])
            for ppa in ppas:
                run_as_root(["add-apt-repository", "-y", ppa])
        run_as_root(["apt-get", "update"])
        run_as_root(["apt-get", "install", "-y", *(app.package for app in missing)])
    elif system == "mac" and missing:
        run(["brew", "install", *(app.package for app in missing)])
    elif system == "windows":
        for app in missing:
            run([
                "winget", "install", "--id", app.package, "--exact",
                "--accept-source-agreements", "--accept-package-agreements",
                "--disable-interactivity",
            ])
        refresh_windows_path()
        if settings.npm:
            run(["npm", "install", "-g", *settings.npm])


def windows_documents() -> Path:
    import winreg

    key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as registry:
        documents, _ = winreg.QueryValueEx(registry, "Personal")
    return Path(os.path.expandvars(documents))


def absolute_env_path(name: str, default: Path | None = None) -> Path:
    value = os.environ.get(name)
    path = Path(value) if value else default
    if path is None or not path.is_absolute():
        raise SetupError(f"{name} must be set to an absolute path.")
    return path


def config_paths(system: str) -> list[tuple[Path, Path]]:
    home = Path.home()
    if system == "windows":
        nvim = absolute_env_path("LOCALAPPDATA") / "nvim"
    else:
        nvim = absolute_env_path("XDG_CONFIG_HOME", home / ".config") / "nvim"
    configs = [
        (ROOT / "common/nvim", nvim),
        (ROOT / "common/tmux/tmux.conf", home / ".tmux.conf"),
    ]
    if system == "windows":
        configs.append((
            ROOT / "windows/pwsh/profile.ps1",
            windows_documents() / "PowerShell/profile.ps1",
        ))
    return configs


def exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def validate_destination(path: Path) -> None:
    # Resolve the parent, not the final symlink: removing a link must not touch its target.
    target = path.parent.resolve() / path.name
    root = ROOT.resolve()
    if (
        target == Path.home().resolve()
        or target == root
        or root in target.parents
        or target in root.parents
    ):
        raise SetupError(f"Refusing to replace or remove a home/repository path: {path}")


def remove_path(path: Path) -> None:
    def retry_readonly(function, filename, error_info):
        error = error_info[1]
        if (
            os.name != "nt"
            or not isinstance(error, PermissionError)
            or os.path.islink(filename)
        ):
            raise error
        os.chmod(filename, stat.S_IWRITE)
        function(filename)

    if path.is_symlink() or not path.is_dir():
        try:
            path.unlink()
        except PermissionError:
            retry_readonly(os.unlink, str(path), sys.exc_info())
    else:
        shutil.rmtree(path, onerror=retry_readonly)


def set_config(src: Path, dst: Path) -> None:
    validate_destination(dst)
    if not src.exists():
        raise SetupError(f"Config source not found: {src}")
    present = exists(dst)
    question = f"{dst} already exists. Overwrite?" if present else f"Copy config to {dst}?"
    if not confirm(question):
        info(f"Skipping {dst}")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    backup = dst.with_name(dst.name + ".bak")
    # Finish copying before touching the user's config or its previous backup.
    with tempfile.TemporaryDirectory(prefix=".dotconfig-", dir=dst.parent) as temporary:
        staged = Path(temporary) / "config"
        if src.is_dir():
            shutil.copytree(src, staged, symlinks=True)
        else:
            shutil.copy2(src, staged)
        if present:
            if exists(backup):
                remove_path(backup)
            dst.rename(backup)
            info(f"Backed up {dst} -> {backup}")
        try:
            staged.rename(dst)
        except OSError:
            if present:
                backup.rename(dst)
            raise
    info(f"Copied {src} -> {dst}")


def uninstall_config(dst: Path) -> None:
    validate_destination(dst)
    backup = dst.with_name(dst.name + ".bak")
    if exists(backup):
        if not confirm(f"Restore {backup} to {dst}, replacing the current config?"):
            info(f"Keeping {dst} and its backup")
            return
        with tempfile.TemporaryDirectory(prefix=".dotconfig-", dir=dst.parent) as temporary:
            previous = Path(temporary) / "config"
            if exists(dst):
                dst.rename(previous)
            try:
                backup.rename(dst)
            except OSError:
                if exists(previous):
                    previous.rename(dst)
                raise
        info(f"Restored {dst}")
    elif exists(dst):
        if confirm(f"Remove {dst}? No .bak backup exists."):
            remove_path(dst)
            info(f"Removed {dst}")
        else:
            info(f"Keeping {dst}")
    else:
        info(f"No config or backup at {dst}, skipping")


def zshrc_path() -> Path:
    path = absolute_env_path("ZDOTDIR", Path.home()) / ".zshrc"
    validate_destination(path)
    if exists(path) and not path.is_file():
        raise SetupError(f"Expected a regular zsh config file at {path}.")
    # Unlike copied configs, a sourced rc file is edited through an existing symlink.
    validate_destination(path.resolve())
    return path


def zsh_block_range(content: bytes) -> tuple[int, int] | None:
    starts = []
    ends = []
    offset = 0
    for line in content.splitlines(keepends=True):
        marker = line.rstrip(b"\r\n")
        if marker == ZSH_BLOCK_START:
            starts.append(offset)
        elif marker == ZSH_BLOCK_END:
            ends.append(offset + len(line))
        offset += len(line)
    if not starts and not ends:
        return None
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise SetupError(
            "Malformed or duplicate dotconfig zsh markers; fix them before rerunning setup."
        )
    start = starts[0]
    # The leading separator is part of the block we append, not the user's content.
    if start and content[start - 1:start] == b"\n":
        start -= 1
    return start, ends[0]


def configure_zsh(system: str, *, uninstall: bool = False) -> None:
    path = zshrc_path()
    target = path.resolve()
    original = target.read_bytes() if target.exists() else None
    content = original or b""
    bounds = zsh_block_range(content)

    if uninstall:
        if bounds is None:
            info(f"No dotconfig source block in {path}, skipping")
            return
        if not confirm(f"Remove only the dotconfig source block from {path}?"):
            info(f"Keeping {path} unchanged")
            return
        before, after = content[:bounds[0]], content[bounds[1]:]
        if before and after and not before.endswith(b"\n") and not after.startswith(b"\n"):
            before += b"\n"
        updated = before + after
    else:
        sources = [ROOT / "common/zsh/zshrc", ROOT / system / "zsh/zshrc"]
        for source in sources:
            if not source.is_file():
                raise SetupError(f"Zsh config source not found: {source}")
        block = b"\n" + ZSH_BLOCK_START + b"\n"
        for source in sources:
            block += os.fsencode(f"source {shlex.quote(str(source))}\n")
        block += ZSH_BLOCK_END + b"\n"
        if bounds is None:
            updated = content + block
        else:
            if content[bounds[0]:bounds[1]] == block:
                info(f"Dotconfig sources already configured in {path}, skipping")
                return
            updated = content[:bounds[0]] + block + content[bounds[1]:]

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".dotconfig-", dir=target.parent) as temporary:
        staged = Path(temporary) / "zshrc"
        staged.write_bytes(updated)
        current = target.read_bytes() if target.exists() else None
        if path.resolve() != target or current != original:
            raise SetupError(f"{path} changed during setup; rerun to keep those edits.")
        if original is not None:
            shutil.copymode(target, staged)
        staged.replace(target)
    info(f"Updated {path}")


def prepare_neovim(repository: str, system: str) -> None:
    source = ROOT / "common/nvim"
    present = exists(source)
    if present and not confirm("Replace the existing Neovim checkout?"):
        info("Keeping existing Neovim checkout")
        return
    source.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".nvim-", dir=source.parent) as temporary:
        checkout = Path(temporary) / "nvim"
        run(["git", "clone", "--", repository, str(checkout)])
        if present:
            remove_path(source)
            if system == "windows":
                cache = absolute_env_path("LOCALAPPDATA") / "nvim-data"
                if exists(cache):
                    remove_path(cache)
        checkout.rename(source)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Without an option, run tests first and install only if they pass.",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--test", action="store_true", help="run tests only")
    action.add_argument(
        "--install", action="store_true",
        help="install apps and configure dotfiles without running tests",
    )
    action.add_argument(
        "--uninstall",
        action="store_true",
        help="restore/remove copied configs and remove the zsh source block; keep apps and checkout",
    )
    args = parser.parse_args(argv)
    try:
        if not args.install and not args.uninstall:
            run_tests()
            if args.test:
                return 0
        system = current_platform()
        configs = config_paths(system)
        for _, destination in configs:
            validate_destination(destination)
        if system in ("linux", "mac"):
            zshrc_path()
        if args.uninstall:
            info("Config-only uninstall; installed apps and common/nvim will be kept.")
            for _, destination in configs:
                uninstall_config(destination)
            if system in ("linux", "mac"):
                configure_zsh(system, uninstall=True)
        else:
            settings = load_settings(system)
            if system != "windows":
                require_command("git")
            info(f"Installing apps from config.toml [{system}]")
            install_apps(system, settings)
            require_command("git")
            prepare_neovim(settings.repository, system)
            for source, destination in configs:
                set_config(source, destination)
            if system in ("linux", "mac"):
                configure_zsh(system)
    except (SetupError, OSError, tomllib.TOMLDecodeError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[!] Setup cancelled.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
