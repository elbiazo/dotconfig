import contextlib
import io
import ntpath
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import MagicMock, call, patch

import setup


REPO = setup.ROOT


class TemporarySetup(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dotconfig-test-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "repo with spaces"
        self.home = self.base / "home"
        self.home.mkdir()
        self.root.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(setup, "ROOT", self.root).start()
        patch.object(Path, "home", return_value=self.home).start()
        patch.dict(os.environ, {
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "LOCALAPPDATA": str(self.home / "AppData/Local"),
            "XDG_CONFIG_HOME": "",
            "ZDOTDIR": "",
        }).start()
        self.prompt = patch("builtins.input", return_value="y").start()
        self.output = io.StringIO()
        patch("sys.stdout", self.output).start()
        self.write(self.root / "common/nvim/init.lua", "Neovim config")
        self.write(self.root / "common/tmux/tmux.conf", "tmux config")
        self.write(self.root / "common/zsh/zshrc", "shared zsh config")
        self.write(self.root / "linux/zsh/zshrc", "Linux zsh config")
        self.write(self.root / "mac/zsh/zshrc", "zsh config")
        self.write(self.root / "windows/pwsh/profile.ps1", "PowerShell profile")
        shutil.copy2(REPO / "config.toml", self.root / "config.toml")

    @staticmethod
    def write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


class SettingsTests(TemporarySetup):
    def test_all_platforms_load_their_own_app_lists(self):
        windows = setup.load_settings("windows")
        linux = setup.load_settings("linux")
        mac = setup.load_settings("mac")
        self.assertIn(setup.App("Microsoft.Git"), windows.apps)
        self.assertEqual(windows.npm, ("tree-sitter-cli",))
        self.assertEqual(linux.apps[0].ppa, "ppa:neovim-ppa/unstable")
        self.assertIn(setup.App("build-essential", ("make", "cc")), linux.apps)
        self.assertIn(setup.App("zsh", ("zsh",)), linux.apps)
        self.assertIn(setup.App("zsh-autosuggestions"), linux.apps)
        self.assertIn(setup.App("zsh-syntax-highlighting"), linux.apps)
        self.assertIn(setup.App("zsh-autosuggestions"), mac.apps)
        self.assertEqual(mac.npm, ())

    def test_app_changes_are_loaded_from_toml(self):
        path = self.write(self.base / "custom.toml", """
[neovim]
repository = "https://example.invalid/nvim.git"
[linux]
apt = [{package = "ripgrep", commands = ["rg"]}, {package = "fonts-firacode"}]
""")
        config = setup.load_settings("linux", path)
        self.assertEqual(config.repository, "https://example.invalid/nvim.git")
        self.assertEqual(config.apps, (
            setup.App("ripgrep", ("rg",)), setup.App("fonts-firacode"),
        ))

    def test_invalid_app_definitions_are_rejected(self):
        entries = [
            '["tmux"]',
            '[{package = ""}]',
            '[{package = "--remove"}]',
            '[{package = "two packages"}]',
            '[{package = "tmux", commands = "tmux"}]',
            '[{package = "tmux", commands = [1]}]',
            '[{package = "tmux", ppa = "not-a-ppa"}]',
            '[{package = "tmux", command = "tmux"}]',
        ]
        for entries_toml in entries:
            with self.subTest(entries=entries_toml):
                path = self.write(self.base / "bad.toml", (
                    '[neovim]\nrepository = "repo"\n[linux]\napt = ' + entries_toml
                ))
                with self.assertRaises(setup.SetupError):
                    setup.load_settings("linux", path)

    def test_missing_sections_and_wrong_managers_are_rejected(self):
        for contents in (
            "",
            '[neovim]\nrepository = "repo"',
            '[neovim]\nrepository = "repo"\n[linux]\nbrew = []',
            '[neovim]\nrepository = "repo"\n[linux]\napt = "tmux"',
        ):
            with self.subTest(contents=contents):
                path = self.write(self.base / "bad.toml", contents)
                with self.assertRaises(setup.SetupError):
                    setup.load_settings("linux", path)

    def test_malformed_toml_is_not_ignored(self):
        path = self.write(self.base / "bad.toml", "[linux")
        with self.assertRaises(tomllib.TOMLDecodeError):
            setup.load_settings("linux", path)

    def test_invalid_npm_package_is_rejected(self):
        path = self.write(self.base / "bad.toml", """
[neovim]
repository = "repo"
[windows]
winget = []
npm = ["--other-option"]
""")
        with self.assertRaisesRegex(setup.SetupError, "Invalid npm"):
            setup.load_settings("windows", path)


class ConfigTests(TemporarySetup):
    def setUp(self):
        super().setUp()
        self.source = self.write(self.root / "source [config]", "v1")
        self.destination = self.home / "nested dir/config [name]"
        self.backup = self.destination.with_name(self.destination.name + ".bak")

    def test_fresh_copy_and_declining_copy(self):
        setup.set_config(self.source, self.destination)
        self.assertEqual(self.destination.read_text(), "v1")
        self.assertFalse(self.destination.is_symlink())
        self.assertFalse(self.backup.exists())
        self.prompt.return_value = "n"
        setup.set_config(self.source, self.home / "skipped")
        self.assertFalse((self.home / "skipped").exists())

    def test_overwrite_and_repeated_backup(self):
        setup.set_config(self.source, self.destination)
        for new, old in (("v2", "v1"), ("v3", "v2")):
            self.source.write_text(new)
            setup.set_config(self.source, self.destination)
            self.assertEqual(self.destination.read_text(), new)
            self.assertEqual(self.backup.read_text(), old)
        self.prompt.return_value = "n"
        setup.set_config(self.source, self.destination)
        self.assertEqual(self.destination.read_text(), "v3")
        self.assertEqual(self.backup.read_text(), "v2")

    def test_directory_copies_do_not_merge_or_nest(self):
        directory = self.root / "directory"
        self.write(directory / ".hidden", "hidden")
        self.write(directory / "subdir/config", "nested")
        self.write(self.destination / "stale", "old")
        setup.set_config(directory, self.destination)
        self.assertEqual((self.destination / ".hidden").read_text(), "hidden")
        self.assertEqual((self.destination / "subdir/config").read_text(), "nested")
        self.assertFalse((self.destination / "stale").exists())
        self.assertTrue((self.backup / "stale").exists())
        setup.set_config(directory, self.destination)
        self.assertFalse((self.backup / "stale").exists())
        self.assertTrue((self.backup / ".hidden").exists())

    def test_missing_source_and_copy_failure_preserve_existing_files(self):
        self.write(self.destination, "original")
        self.write(self.backup, "older")
        with self.assertRaisesRegex(setup.SetupError, "source not found"):
            setup.set_config(self.root / "missing", self.destination)
        with patch("setup.shutil.copy2", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                setup.set_config(self.source, self.destination)
        self.assertEqual(self.destination.read_text(), "original")
        self.assertEqual(self.backup.read_text(), "older")
        self.assertFalse(list(self.destination.parent.glob(".dotconfig-*")))

    def test_failed_replacement_restores_destination(self):
        self.write(self.destination, "original")
        rename = Path.rename

        def fail_staged(path, destination):
            if path.parent.name.startswith(".dotconfig-"):
                raise OSError("rename failed")
            return rename(path, destination)

        with patch.object(Path, "rename", fail_staged):
            with self.assertRaisesRegex(OSError, "rename failed"):
                setup.set_config(self.source, self.destination)
        self.assertEqual(self.destination.read_text(), "original")

    def test_readonly_file_removal_is_retried_on_windows(self):
        with patch("setup.os.name", "nt"), patch(
            "setup.os.unlink", side_effect=[PermissionError("read-only"), None]
        ) as unlink, patch("setup.os.chmod") as chmod:
            setup.remove_path(self.source)
        self.assertEqual(unlink.call_count, 2)
        chmod.assert_called_once_with(str(self.source), stat.S_IWRITE)

    def test_eof_is_an_error_and_does_not_change_config(self):
        self.write(self.destination, "original")
        self.prompt.side_effect = EOFError
        with self.assertRaisesRegex(setup.SetupError, "No response received"):
            setup.set_config(self.source, self.destination)
        self.assertEqual(self.destination.read_text(), "original")
        self.assertFalse(self.backup.exists())

    def test_home_repository_and_ancestors_are_protected(self):
        for destination in (
            self.home, self.root, self.root / "common/nvim", self.base, self.base.anchor,
        ):
            with self.subTest(destination=destination):
                with self.assertRaisesRegex(setup.SetupError, "Refusing"):
                    setup.uninstall_config(Path(destination))

    @unittest.skipIf(os.name == "nt", "Windows symlinks can require elevation")
    def test_dangling_symlink_is_backed_up_without_following_it(self):
        target = self.home / "missing"
        self.destination.parent.mkdir()
        self.destination.symlink_to(target)
        setup.set_config(self.source, self.destination)
        self.assertEqual(self.destination.read_text(), "v1")
        self.assertTrue(self.backup.is_symlink())
        self.assertFalse(target.exists())
        setup.uninstall_config(self.destination)
        self.assertTrue(self.destination.is_symlink())
        self.assertFalse(self.backup.is_symlink())
        self.assertFalse(target.exists())


class UninstallTests(TemporarySetup):
    def test_restores_file_and_directory_backups(self):
        for directory in (False, True):
            with self.subTest(directory=directory):
                destination = self.home / f"config-{directory}"
                backup = destination.with_name(destination.name + ".bak")
                if directory:
                    self.write(destination / "current", "current")
                    self.write(backup / ".original", "original")
                else:
                    self.write(destination, "current")
                    self.write(backup, "original")
                setup.uninstall_config(destination)
                restored = destination / ".original" if directory else destination
                self.assertEqual(restored.read_text(), "original")
                self.assertFalse(backup.exists())
                if directory:
                    self.assertFalse((destination / "current").exists())

    def test_removes_configs_without_backups(self):
        file = self.write(self.home / ".tmux.conf", "tmux")
        directory = self.home / ".config/nvim"
        self.write(directory / "init.lua", "config")
        setup.uninstall_config(file)
        setup.uninstall_config(directory)
        self.assertFalse(file.exists())
        self.assertFalse(directory.exists())
        self.assertTrue((self.root / "common/nvim/init.lua").exists())

    def test_declining_preserves_config_and_backup(self):
        self.prompt.return_value = "n"
        destination = self.write(self.home / "config", "current")
        setup.uninstall_config(destination)
        backup = self.write(self.home / "config.bak", "original")
        setup.uninstall_config(destination)
        self.assertEqual(destination.read_text(), "current")
        self.assertEqual(backup.read_text(), "original")

    def test_restores_orphan_backup_and_skips_missing_config(self):
        destination = self.home / "config"
        self.write(self.home / "config.bak", "original")
        setup.uninstall_config(destination)
        self.assertEqual(destination.read_text(), "original")
        self.prompt.reset_mock()
        setup.uninstall_config(self.home / "absent")
        self.prompt.assert_not_called()

    def test_restore_failure_keeps_both_versions(self):
        destination = self.write(self.home / "config", "current")
        backup = self.write(self.home / "config.bak", "original")
        rename = Path.rename

        def fail_backup(path, target):
            if path == backup:
                raise OSError("restore failed")
            return rename(path, target)

        with patch.object(Path, "rename", fail_backup):
            with self.assertRaisesRegex(OSError, "restore failed"):
                setup.uninstall_config(destination)
        self.assertEqual(destination.read_text(), "current")
        self.assertEqual(backup.read_text(), "original")

    @unittest.skipIf(os.name == "nt", "Windows symlinks can require elevation")
    def test_removing_symlink_never_removes_target(self):
        target = self.home / "other"
        self.write(target / "keep", "keep")
        link = self.home / "config"
        link.symlink_to(target, target_is_directory=True)
        setup.uninstall_config(link)
        self.assertFalse(link.is_symlink())
        self.assertEqual((target / "keep").read_text(), "keep")

    @unittest.skipIf(os.name == "nt", "Windows symlinks can require elevation")
    def test_failed_symlink_removal_does_not_change_target_permissions(self):
        target = self.write(self.home / "target", "keep")
        link = self.home / "link"
        link.symlink_to(target)
        with patch("setup.os.name", "nt"), patch(
            "setup.os.unlink", side_effect=PermissionError("access denied")
        ), patch("setup.os.chmod") as chmod:
            with self.assertRaises(PermissionError):
                setup.remove_path(link)
        chmod.assert_not_called()
        self.assertEqual(target.read_text(), "keep")


class PackageTests(TemporarySetup):
    def setUp(self):
        super().setUp()
        self.commands = {"git", "apt-get", "brew", "winget", "npm", "sudo", "dpkg-query"}
        self.which = patch("setup.shutil.which", side_effect=lambda name: name if name in self.commands else None).start()
        self.run = patch("setup.run", return_value=subprocess.CompletedProcess([], 0, "")).start()
        patch("setup.os.geteuid", return_value=1000, create=True).start()
        patch("setup.platform.freedesktop_os_release", return_value={"ID": "ubuntu"}).start()
        self.refresh_path = patch("setup.refresh_windows_path").start()
        self.plugin_queries = [
            call(["dpkg-query", "-W", "-f=${Status}", package], capture=True, allowed=(0, 1))
            for package in ("zsh-autosuggestions", "zsh-syntax-highlighting")
        ]

    def test_linux_installs_only_missing_commands_and_prepares_ppa(self):
        self.commands.add("curl")
        setup.install_apps("linux", setup.load_settings("linux"))
        self.assertEqual(self.run.call_args_list, self.plugin_queries + [
            call(["sudo", "apt-get", "update"]),
            call(["sudo", "apt-get", "install", "-y", "software-properties-common"]),
            call(["sudo", "add-apt-repository", "-y", "ppa:neovim-ppa/unstable"]),
            call(["sudo", "apt-get", "update"]),
            call([
                "sudo", "apt-get", "install", "-y", "neovim", "tmux", "clangd",
                "unzip", "build-essential", "zsh", "zsh-autosuggestions",
                "zsh-syntax-highlighting",
            ]),
        ])

    def test_apt_query_supports_packages_without_commands(self):
        app = setup.App("fonts-firacode")
        self.run.return_value = subprocess.CompletedProcess([], 0, "install ok installed")
        self.assertTrue(setup.app_installed(app, "apt"))
        self.run.assert_called_with(
            ["dpkg-query", "-W", "-f=${Status}", "fonts-firacode"],
            capture=True, allowed=(0, 1),
        )
        self.run.return_value = subprocess.CompletedProcess([], 0, "deinstall ok config-files")
        self.assertFalse(setup.app_installed(app, "apt"))

    def test_linux_requires_every_command_and_skips_ppa_for_existing_nvim(self):
        self.commands.update({"nvim", "tmux", "clangd", "unzip", "curl", "make", "zsh"})
        self.run.return_value = subprocess.CompletedProcess([], 0, "install ok installed")
        setup.install_apps("linux", setup.load_settings("linux"))
        self.assertEqual(self.run.call_args_list, self.plugin_queries + [
            call(["sudo", "apt-get", "update"]),
            call(["sudo", "apt-get", "install", "-y", "build-essential"]),
        ])
        self.run.reset_mock()
        self.commands.add("cc")
        setup.install_apps("linux", setup.load_settings("linux"))
        self.assertEqual(self.run.call_args_list, self.plugin_queries)

    def test_ppa_is_rejected_on_non_ubuntu_before_changes(self):
        with patch("setup.platform.freedesktop_os_release", return_value={"ID": "debian"}):
            with self.assertRaisesRegex(setup.SetupError, "requires Ubuntu"):
                setup.install_apps("linux", setup.load_settings("linux"))
        self.assertEqual(self.run.call_args_list, self.plugin_queries)

    def test_root_does_not_use_sudo(self):
        with patch("setup.os.geteuid", return_value=0):
            setup.run_as_root(["apt-get", "update"])
        self.run.assert_called_once_with(["apt-get", "update"])

    def test_macos_checks_formulae_and_batches_missing_apps(self):
        self.commands.add("nvim")
        self.run.return_value = subprocess.CompletedProcess([], 1, "")
        setup.install_apps("mac", setup.load_settings("mac"))
        self.assertEqual(self.run.call_args_list, [
            call(["brew", "list", "--formula", "zsh-autosuggestions"], capture=True, allowed=(0, 1)),
            call(["brew", "list", "--formula", "zsh-syntax-highlighting"], capture=True, allowed=(0, 1)),
            call(["brew", "install", "tmux", "tree-sitter-cli", "zsh-autosuggestions", "zsh-syntax-highlighting"]),
        ])

    def test_macos_skips_installed_tools_and_plugins(self):
        self.commands.update({"nvim", "tmux", "tree-sitter"})
        setup.install_apps("mac", setup.load_settings("mac"))
        self.assertEqual(self.run.call_count, 2)
        self.assertTrue(all(item.args[0][1] == "list" for item in self.run.call_args_list))

    def test_windows_uses_toml_ids_and_npm_after_path_refresh(self):
        settings = setup.Settings("repo", (setup.App("Installed.App"), setup.App("New.App")), ("test-cli",))
        self.run.side_effect = [
            subprocess.CompletedProcess([], 0, "installed"),
            subprocess.CompletedProcess([], setup.WINGET_NOT_FOUND, "not found"),
            subprocess.CompletedProcess([], 0, ""),
            subprocess.CompletedProcess([], 0, ""),
        ]
        setup.install_apps("windows", settings)
        self.assertEqual(self.run.call_args_list[-2:], [
            call(["winget", "install", "--id", "New.App", "--exact",
                  "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"]),
            call(["npm", "install", "-g", "test-cli"]),
        ])
        self.refresh_path.assert_called_once()

    def test_missing_managers_are_errors(self):
        self.commands.clear()
        for system in setup.MANAGERS:
            with self.subTest(system=system):
                with self.assertRaisesRegex(setup.SetupError, "required"):
                    setup.install_apps(system, setup.load_settings(system))
        self.run.assert_not_called()


class CommandTests(unittest.TestCase):
    def test_commands_use_argument_lists_and_report_failures(self):
        with patch("setup.shutil.which", return_value="/mock/tool"), patch(
            "setup.subprocess.run", return_value=subprocess.CompletedProcess([], 7, "failure details")
        ) as command:
            with self.assertRaisesRegex(setup.SetupError, "failure details"):
                setup.run(["tool", "path with spaces"], capture=True)
            self.assertEqual(command.call_args.args[0], ["/mock/tool", "path with spaces"])
            self.assertFalse(command.call_args.kwargs.get("shell", False))

    def test_winget_query_failures_are_not_treated_as_missing_apps(self):
        for status in (0, setup.WINGET_NOT_FOUND, 0x8A150045):
            with self.subTest(status=status), patch(
                "setup.shutil.which", return_value="winget"
            ), patch("setup.subprocess.run", return_value=subprocess.CompletedProcess([], status, "query result")):
                if status == 0x8A150045:
                    with self.assertRaises(setup.SetupError):
                        setup.app_installed(setup.App("Some.App"), "winget")
                else:
                    self.assertEqual(setup.app_installed(setup.App("Some.App"), "winget"), status == 0)


class PlatformTests(TemporarySetup):
    def test_platform_detection(self):
        for actual, expected in (("Linux", "linux"), ("Darwin", "mac"), ("Windows", "windows")):
            with patch("setup.platform.system", return_value=actual):
                self.assertEqual(setup.current_platform(), expected)
        with patch("setup.platform.system", return_value="FreeBSD"):
            with self.assertRaisesRegex(setup.SetupError, "Unsupported OS"):
                setup.current_platform()

    def test_platform_destinations_and_xdg(self):
        linux = setup.config_paths("linux")
        self.assertEqual([dst for _, dst in linux], [self.home / ".config/nvim", self.home / ".tmux.conf"])
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.home / "custom config")}):
            mac = setup.config_paths("mac")
        self.assertEqual(mac[0][1], self.home / "custom config/nvim")
        self.assertEqual(len(mac), 2)
        self.assertEqual(setup.zshrc_path(), self.home / ".zshrc")
        documents = self.home / "OneDrive Documents"
        with patch("setup.windows_documents", return_value=documents):
            windows = setup.config_paths("windows")
        self.assertEqual(windows[0][1], self.home / "AppData/Local/nvim")
        self.assertEqual(windows[-1][1], documents / "PowerShell/profile.ps1")

    def test_relative_config_directory_is_rejected(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative"}):
            with self.assertRaisesRegex(setup.SetupError, "absolute path"):
                setup.config_paths("linux")

    def test_windows_registry_paths_are_expanded(self):
        registry = MagicMock()
        registry.QueryValueEx.return_value = ("%USERPROFILE%/OneDrive/Documents", 2)
        with patch.dict(sys.modules, {"winreg": registry}), patch(
            "setup.os.path.expandvars", ntpath.expandvars
        ):
            self.assertEqual(setup.windows_documents(), self.home / "OneDrive/Documents")
            registry.QueryValueEx.side_effect = [
                ("%USERPROFILE%/MachineBin", 2), ("%USERPROFILE%/UserBin", 2),
            ]
            original = os.environ["PATH"]
            setup.refresh_windows_path()
        self.assertEqual(os.environ["PATH"], f"{original};{self.home}/MachineBin;{self.home}/UserBin")

    def test_missing_user_path_keeps_machine_and_process_paths(self):
        registry = MagicMock()
        registry.QueryValueEx.side_effect = [("machine-bin", 1), FileNotFoundError()]
        original = os.environ["PATH"]
        with patch.dict(sys.modules, {"winreg": registry}):
            setup.refresh_windows_path()
        self.assertEqual(os.environ["PATH"], f"{original};machine-bin")


class NeovimTests(TemporarySetup):
    @unittest.skipUnless(shutil.which("git"), "Local clone checks require Git")
    def test_real_local_clone_and_failed_clone_preservation(self):
        run = setup.run
        with patch("setup.run", side_effect=lambda args: run(args, capture=True)):
            with self.assertRaisesRegex(setup.SetupError, "Command failed"):
                setup.prepare_neovim(str(self.base / "missing repository"), "linux")
            self.assertEqual(
                (self.root / "common/nvim/init.lua").read_text(), "Neovim config"
            )
            remote = self.base / "local repository"
            subprocess.run(
                ["git", "init", "--bare", str(remote)],
                capture_output=True, check=True,
            )
            setup.prepare_neovim(str(remote), "linux")
        self.assertTrue((self.root / "common/nvim/.git").is_dir())
        self.assertFalse(list((self.root / "common").glob(".nvim-*")))

    def test_declining_keeps_checkout_without_git_calls(self):
        self.prompt.return_value = "n"
        with patch("setup.run") as run:
            setup.prepare_neovim("repo", "linux")
        run.assert_not_called()
        self.assertEqual((self.root / "common/nvim/init.lua").read_text(), "Neovim config")

    def test_failed_clone_preserves_existing_checkout(self):
        with patch("setup.run", side_effect=setup.SetupError("clone failed")):
            with self.assertRaisesRegex(setup.SetupError, "clone failed"):
                setup.prepare_neovim("repo", "linux")
        self.assertEqual((self.root / "common/nvim/init.lua").read_text(), "Neovim config")
        self.assertFalse(list((self.root / "common").glob(".nvim-*")))

    def test_successful_clone_replaces_checkout_and_clears_windows_cache(self):
        cache = self.home / "AppData/Local/nvim-data"
        self.write(cache / "cached", "cache")

        def clone(command):
            self.assertEqual(command[:4], ["git", "clone", "--", "repo"])
            self.write(Path(command[4]) / "init.lua", "new config")

        with patch("setup.run", side_effect=clone):
            setup.prepare_neovim("repo", "windows")
        self.assertEqual((self.root / "common/nvim/init.lua").read_text(), "new config")
        self.assertFalse(cache.exists())

    def test_first_clone_does_not_prompt_or_clear_cache(self):
        shutil.rmtree(self.root / "common/nvim")
        cache = self.write(self.home / "AppData/Local/nvim-data/keep", "cache")
        with patch("setup.run", side_effect=lambda args: self.write(Path(args[-1]) / "init.lua", "new")):
            setup.prepare_neovim("repo", "windows")
        self.prompt.assert_not_called()
        self.assertEqual(cache.read_text(), "cache")


class TestRunnerTests(TemporarySetup):
    def test_uses_current_python_and_repository_working_directory(self):
        self.write(self.root / "common/tests/test_probe.py", "import unittest\n")
        with patch("setup.run") as run:
            setup.run_tests()
        run.assert_called_once_with(
            [
                sys.executable, "-B", "-m", "unittest", "discover",
                "-s", "common/tests", "-v",
            ],
            cwd=self.root,
        )

    def test_missing_or_empty_test_directory_is_an_error(self):
        with patch("setup.run") as run:
            for create_directory in (False, True):
                if create_directory:
                    (self.root / "common/tests").mkdir()
                with self.assertRaisesRegex(setup.SetupError, "No tests found"):
                    setup.run_tests()
        run.assert_not_called()

    def test_real_test_only_command_runs_from_another_directory(self):
        shutil.copy2(REPO / "setup.py", self.root / "setup.py")
        (self.root / "config.toml").unlink()
        probe = self.root / "common/tests/test_probe.py"
        for passing in (True, False):
            with self.subTest(passing=passing):
                self.write(probe, (
                    "from pathlib import Path\n"
                    "import unittest\n"
                    "import setup\n"
                    "class Probe(unittest.TestCase):\n"
                    "    def test_probe(self):\n"
                    "        self.assertEqual(Path.cwd(), setup.ROOT)\n"
                    f"        self.assertTrue({passing})\n"
                ))
                result = subprocess.run(
                    [sys.executable, "-B", str(self.root / "setup.py"), "--test"],
                    cwd=self.base, capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0 if passing else 1, result.stderr)
                self.assertIn("Ran 1 test", result.stderr)
                self.assertNotIn("Installing apps", result.stdout)
                self.assertFalse((self.home / ".tmux.conf").exists())
                self.assertFalse((self.home / ".zshrc").exists())


class MainTests(TemporarySetup):
    def test_default_runs_tests_before_installing(self):
        steps = []
        with patch("setup.run_tests", side_effect=lambda: steps.append("test")), patch(
            "setup.current_platform", return_value="linux"
        ), patch("setup.require_command", return_value="git"), patch(
            "setup.install_apps", side_effect=lambda *_: steps.append("install")
        ), patch("setup.prepare_neovim"):
            self.assertEqual(setup.main([]), 0)
        self.assertEqual(steps, ["test", "install"])
        self.assertTrue((self.home / ".tmux.conf").exists())

    def test_test_only_does_not_prepare_or_install_configs(self):
        with patch("setup.run_tests") as tests, patch(
            "setup.current_platform"
        ) as system, patch("setup.install_apps") as install:
            self.assertEqual(setup.main(["--test"]), 0)
        tests.assert_called_once_with()
        system.assert_not_called()
        install.assert_not_called()
        self.prompt.assert_not_called()

    def test_failed_tests_stop_default_and_test_only_modes(self):
        for arguments in ([], ["--test"]):
            with self.subTest(arguments=arguments), patch(
                "setup.run_tests", side_effect=setup.SetupError("Tests failed")
            ), patch("setup.current_platform") as system, patch(
                "setup.install_apps"
            ) as install, contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(setup.main(arguments), 1)
                self.assertIn("Tests failed", errors.getvalue())
                system.assert_not_called()
                install.assert_not_called()
        self.prompt.assert_not_called()
        self.assertEqual(list(self.home.iterdir()), [])

    def test_install_and_uninstall_skip_tests(self):
        with patch("setup.run_tests") as tests, patch(
            "setup.current_platform", return_value="linux"
        ), patch("setup.require_command", return_value="git"), patch(
            "setup.install_apps"
        ) as install, patch("setup.prepare_neovim"):
            self.assertEqual(setup.main(["--install"]), 0)
            self.assertEqual(setup.main(["--uninstall"]), 0)
        tests.assert_not_called()
        install.assert_called_once()

    def test_zsh_setup_needs_no_confirmation_after_other_configs_are_declined(self):
        for system in ("linux", "mac"):
            with self.subTest(system=system), patch(
                "setup.current_platform", return_value=system
            ), patch("setup.install_apps"), patch(
                "setup.require_command", return_value="git"
            ), patch("setup.prepare_neovim"):
                self.prompt.reset_mock()
                self.prompt.side_effect = ["n", "n"]
                self.assertEqual(setup.main(["--install"]), 0)
                self.assertEqual(self.prompt.call_count, 2)
                content = (self.home / ".zshrc").read_text()
                self.assertIn(
                    shlex.quote(str(self.root / system / "zsh/zshrc")), content
                )
                self.assertEqual(content.count(setup.ZSH_BLOCK_START.decode()), 1)

    def test_install_routes_each_platform_and_copies_configs(self):
        for system in setup.MANAGERS:
            with self.subTest(system=system), patch(
                "setup.current_platform", return_value=system
            ), patch("setup.windows_documents", return_value=self.home / "Documents"), patch(
                "setup.install_apps"
            ) as install, patch("setup.require_command", return_value="git"), patch(
                "setup.prepare_neovim"
            ) as prepare:
                self.assertEqual(setup.main(["--install"]), 0)
                install.assert_called_once_with(system, setup.load_settings(system))
                prepare.assert_called_once_with(setup.load_settings(system).repository, system)
                for source, destination in setup.config_paths(system):
                    if source.is_file():
                        self.assertEqual(source.read_bytes(), destination.read_bytes())
                    else:
                        self.assertEqual((source / "init.lua").read_bytes(), (destination / "init.lua").read_bytes())
                zshrc = self.home / ".zshrc"
                if system == "windows":
                    self.assertFalse(zshrc.exists())
                else:
                    self.assertIn(
                        shlex.quote(str(self.root / system / "zsh/zshrc")),
                        zshrc.read_text(),
                    )
                    self.assertEqual(zshrc.read_bytes().count(setup.ZSH_BLOCK_START), 1)

    def test_uninstall_needs_no_manifest_managers_or_git_and_keeps_checkout(self):
        (self.root / "config.toml").unlink()
        cache = self.write(self.home / "AppData/Local/nvim-data/keep", "cache")
        zshrc = self.write(self.home / ".zshrc", "# user zsh config\n")
        zsh_backup = self.write(self.home / ".zshrc.bak", "older zsh config")
        for system in setup.MANAGERS:
            with self.subTest(system=system), patch(
                "setup.current_platform", return_value=system
            ), patch("setup.windows_documents", return_value=self.home / "Documents"), patch(
                "setup.install_apps"
            ) as install, patch("setup.require_command") as command, patch(
                "setup.prepare_neovim"
            ) as prepare:
                paths = setup.config_paths(system)
                for _, destination in paths:
                    self.write(destination, "installed")
                    self.write(destination.with_name(destination.name + ".bak"), "original")
                if system != "windows":
                    setup.configure_zsh(system)
                self.assertEqual(setup.main(["--uninstall"]), 0)
                for _, destination in paths:
                    self.assertEqual(destination.read_text(), "original")
                install.assert_not_called()
                prepare.assert_not_called()
                command.assert_not_called()
                self.assertEqual(zshrc.read_text(), "# user zsh config\n")
                self.assertEqual(zsh_backup.read_text(), "older zsh config")
        self.assertEqual(cache.read_text(), "cache")
        self.assertTrue((self.root / "common/nvim/init.lua").exists())

    def test_failed_install_stops_before_cloning_and_config_changes(self):
        with patch("setup.current_platform", return_value="linux"), patch(
            "setup.require_command", return_value="git"
        ), patch("setup.install_apps", side_effect=setup.SetupError("install failed")), patch(
            "setup.prepare_neovim"
        ) as prepare, contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(setup.main(["--install"]), 1)
        self.assertIn("install failed", errors.getvalue())
        prepare.assert_not_called()
        self.assertFalse((self.home / ".tmux.conf").exists())

    def test_invalid_toml_has_an_explicit_error(self):
        self.write(self.root / "config.toml", "[invalid")
        with patch("setup.current_platform", return_value="linux"), contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(setup.main(["--install"]), 1)
        self.assertIn("[!]", errors.getvalue())

    def test_cli_help_and_unknown_options_work_from_another_directory(self):
        cases = (
            (["--help"], 0),
            (["--invalid-option"], 2),
            (["--test", "--install"], 2),
            (["--test", "--uninstall"], 2),
            (["--install", "--uninstall"], 2),
        )
        for options, code in cases:
            with self.subTest(options=options):
                result = subprocess.run(
                    [sys.executable, str(REPO / "setup.py"), *options],
                    cwd=self.base, capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, code, result.stderr)
                for option in ("--test", "--install", "--uninstall"):
                    self.assertIn(option, result.stdout + result.stderr)

    @unittest.skipUnless(sys.platform == "linux", "Real subprocess uses Linux home resolution")
    def test_real_uninstall_entrypoint_from_another_directory(self):
        self.write(self.home / ".tmux.conf", "installed")
        self.write(self.home / ".tmux.conf.bak", "original")
        self.write(self.home / ".config/nvim/init.lua", "installed")
        zshrc = self.write(self.home / ".zshrc", "# keep my zsh config\n")
        setup.configure_zsh("linux")
        result = subprocess.run(
            [sys.executable, str(REPO / "setup.py"), "--uninstall"],
            cwd=self.base, input="y\ny\ny\n", capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.home / ".config/nvim").exists())
        self.assertEqual((self.home / ".tmux.conf").read_text(), "original")
        self.assertEqual(zshrc.read_text(), "# keep my zsh config\n")


class PowerShellProfileTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell profile checks require pwsh")
    def test_existing_profile_helpers(self):
        script = r"""
$ErrorActionPreference = "Stop"
. $env:DOTCONFIG_TEST_PROFILE
if ((Format-NumHex 255) -ne "0xff") { throw "Format-NumHex 255" }
if ((Format-NumHex 0) -ne "0x0") { throw "Format-NumHex 0" }
if ((Format-NumHex 4096) -ne "0x1000") { throw "Format-NumHex 4096" }
if ((hex 255) -ne "0xff") { throw "hex alias" }
foreach ($name in "prompt", "Enter-Dev", "Enter-PreviewDev", "Update-Path", "Set-Path", "ll") {
    if (!(Get-Command $name -ErrorAction SilentlyContinue)) { throw "Missing $name" }
}
if ($IsWindows) {
    $savedPath = $env:PATH
    try {
        Set-Path -AddPath "C:\dotconfig\testpath" -Scope Process
        if (($env:PATH -split ";") -notcontains "C:\dotconfig\testpath") { throw "Set-Path add" }
        Set-Path -RemovePath "C:\dotconfig\testpath" -Scope Process
        if (($env:PATH -split ";") -contains "C:\dotconfig\testpath") { throw "Set-Path remove" }
    } finally {
        $env:PATH = $savedPath
    }
}
"""
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
            env={**os.environ, "DOTCONFIG_TEST_PROFILE": str(REPO / "windows/pwsh/profile.ps1")},
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
