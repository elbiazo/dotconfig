import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch

import setup
from common.tests.test_setup import REPO, TemporarySetup


class ZshTests(TemporarySetup):
    def setUp(self):
        super().setUp()
        self.zshrc = self.home / ".zshrc"
        self.backup = self.write(self.home / ".zshrc.bak", "previous backup")

    def test_append_is_idempotent_and_uninstall_preserves_original_bytes(self):
        for original in (b"", b"# existing settings\n", b"alias custom='pwd'", b"# old \xe9\r\n"):
            with self.subTest(original=original):
                self.zshrc.write_bytes(original)
                setup.configure_zsh("linux")
                self.prompt.assert_not_called()
                content = self.zshrc.read_bytes()
                self.assertTrue(content.startswith(original + b"\n" + setup.ZSH_BLOCK_START))
                self.assertEqual(content.count(setup.ZSH_BLOCK_START), 1)
                self.assertEqual(content.count(setup.ZSH_BLOCK_END), 1)
                self.assertIn(self.source_line("common"), content)
                self.assertIn(self.source_line("linux"), content)
                self.assertNotIn(self.source_line("mac"), content)

                self.prompt.reset_mock()
                modified = self.zshrc.stat().st_mtime_ns
                setup.configure_zsh("linux")
                self.prompt.assert_not_called()
                self.assertEqual(self.zshrc.read_bytes(), content)
                self.assertEqual(self.zshrc.stat().st_mtime_ns, modified)

                setup.configure_zsh("linux", uninstall=True)
                self.assertEqual(self.zshrc.read_bytes(), original)
                self.assertEqual(self.backup.read_text(), "previous backup")
                self.prompt.reset_mock()
                setup.configure_zsh("linux", uninstall=True)
                self.prompt.assert_not_called()

    def test_creates_missing_rc_and_leaves_empty_file_on_uninstall(self):
        setup.configure_zsh("mac")
        self.prompt.assert_not_called()
        self.assertTrue(self.zshrc.is_file())
        self.assertIn(self.source_line("mac"), self.zshrc.read_bytes())
        setup.configure_zsh("mac", uninstall=True)
        self.assertTrue(self.zshrc.is_file())
        self.assertEqual(self.zshrc.read_bytes(), b"")
        self.assertEqual(self.backup.read_text(), "previous backup")

    def test_append_update_and_rerun_do_not_require_stdin(self):
        self.prompt.side_effect = EOFError
        self.zshrc.write_bytes(b"# keep this\n")
        setup.configure_zsh("linux")
        self.assertIn(self.source_line("linux"), self.zshrc.read_bytes())
        setup.configure_zsh("mac")
        content = self.zshrc.read_bytes()
        self.assertTrue(content.startswith(b"# keep this\n"))
        self.assertEqual(content.count(setup.ZSH_BLOCK_START), 1)
        self.assertIn(self.source_line("mac"), content)
        self.assertNotIn(self.source_line("linux"), content)
        setup.configure_zsh("mac")
        self.prompt.assert_not_called()
        self.assertEqual(self.zshrc.read_bytes(), content)
        self.assertEqual(self.backup.read_text(), "previous backup")

    def test_declining_uninstall_preserves_content(self):
        self.zshrc.write_bytes(b"# keep this\n")
        setup.configure_zsh("linux")
        content = self.zshrc.read_bytes()
        self.prompt.assert_not_called()
        self.prompt.return_value = "n"
        setup.configure_zsh("linux", uninstall=True)
        self.prompt.assert_called_once()
        self.assertEqual(self.zshrc.read_bytes(), content)
        self.assertEqual(self.backup.read_text(), "previous backup")

    def test_updates_only_the_block_when_platform_or_checkout_path_changes(self):
        self.zshrc.write_bytes(b"# my original settings\n")
        setup.configure_zsh("linux")
        with self.zshrc.open("ab") as stream:
            stream.write(b"# settings added later\n")
        moved = self.base / "moved repo"
        self.root.rename(moved)
        with patch.object(setup, "ROOT", moved):
            setup.configure_zsh("mac")
        self.prompt.assert_not_called()
        content = self.zshrc.read_bytes()
        self.assertEqual(content.count(setup.ZSH_BLOCK_START), 1)
        self.assertTrue(content.startswith(b"# my original settings\n"))
        self.assertTrue(content.endswith(b"# settings added later\n"))
        self.assertIn(os.fsencode(shlex.quote(str(moved / "common/zsh/zshrc"))), content)
        self.assertIn(os.fsencode(shlex.quote(str(moved / "mac/zsh/zshrc"))), content)
        self.assertNotIn(self.source_line("linux"), content)
        setup.configure_zsh("mac", uninstall=True)
        self.assertEqual(
            self.zshrc.read_bytes(), b"# my original settings\n# settings added later\n"
        )

    def test_uninstall_does_not_join_user_lines_around_the_block(self):
        self.zshrc.write_bytes(b"alias original='pwd'")
        setup.configure_zsh("linux")
        with self.zshrc.open("ab") as stream:
            stream.write(b"alias later='date'\n")
        setup.configure_zsh("linux", uninstall=True)
        self.assertEqual(
            self.zshrc.read_bytes(), b"alias original='pwd'\nalias later='date'\n"
        )

    def test_uninstall_leaves_unmanaged_rc_and_legacy_backup_alone(self):
        setup.configure_zsh("mac", uninstall=True)
        self.assertFalse(self.zshrc.exists())
        self.zshrc.write_bytes(b"# a previously copied zsh config\n")
        setup.configure_zsh("linux", uninstall=True)
        self.prompt.assert_not_called()
        self.assertEqual(self.zshrc.read_bytes(), b"# a previously copied zsh config\n")
        self.assertEqual(self.backup.read_text(), "previous backup")

    def test_incomplete_reversed_or_duplicate_markers_are_rejected(self):
        start = setup.ZSH_BLOCK_START + b"\n"
        end = setup.ZSH_BLOCK_END + b"\n"
        for content in (start, end, end + start, start + start + end, (start + end) * 2):
            for uninstall in (False, True):
                with self.subTest(content=content, uninstall=uninstall):
                    self.zshrc.write_bytes(content)
                    with self.assertRaisesRegex(setup.SetupError, "Malformed or duplicate"):
                        setup.configure_zsh("linux", uninstall=uninstall)
                    self.assertEqual(self.zshrc.read_bytes(), content)
        self.prompt.assert_not_called()
        self.assertEqual(self.backup.read_text(), "previous backup")

    def test_exported_zdotdir_is_used_without_changing_home_rc(self):
        self.zshrc.write_bytes(b"# default rc\n")
        directory = self.home / "custom zsh directory"
        rc = directory / ".zshrc"
        with patch.dict(os.environ, {"ZDOTDIR": str(directory)}):
            setup.configure_zsh("linux")
            self.assertIn(setup.ZSH_BLOCK_START, rc.read_bytes())
            setup.configure_zsh("linux", uninstall=True)
        self.assertEqual(rc.read_bytes(), b"")
        self.assertEqual(self.zshrc.read_bytes(), b"# default rc\n")

    def test_relative_zdotdir_and_non_file_rc_are_errors(self):
        with patch.dict(os.environ, {"ZDOTDIR": "relative"}):
            with self.assertRaisesRegex(setup.SetupError, "absolute path"):
                setup.configure_zsh("linux")
        self.zshrc.mkdir()
        with self.assertRaisesRegex(setup.SetupError, "regular zsh config"):
            setup.configure_zsh("linux")
        self.prompt.assert_not_called()

    def test_missing_source_preserves_existing_rc(self):
        self.zshrc.write_bytes(b"# existing\n")
        (self.root / "common/zsh/zshrc").unlink()
        with self.assertRaisesRegex(setup.SetupError, "Zsh config source not found"):
            setup.configure_zsh("linux")
        self.assertEqual(self.zshrc.read_bytes(), b"# existing\n")

    def test_uninstall_eof_preserves_existing_rc(self):
        self.zshrc.write_bytes(b"# existing\n")
        setup.configure_zsh("linux")
        content = self.zshrc.read_bytes()
        self.prompt.side_effect = EOFError
        with self.assertRaisesRegex(setup.SetupError, "No response received"):
            setup.configure_zsh("linux", uninstall=True)
        self.assertEqual(self.zshrc.read_bytes(), content)

    def test_uninstall_does_not_need_source_files(self):
        self.zshrc.write_bytes(b"# existing\n")
        setup.configure_zsh("linux")
        (self.root / "common/zsh/zshrc").unlink()
        (self.root / "linux/zsh/zshrc").unlink()
        setup.configure_zsh("linux", uninstall=True)
        self.assertEqual(self.zshrc.read_bytes(), b"# existing\n")

    def test_failed_write_preserves_rc_and_removes_temporary_files(self):
        self.zshrc.write_bytes(b"# existing\n")
        with patch.object(Path, "replace", side_effect=OSError("write failed")):
            with self.assertRaisesRegex(OSError, "write failed"):
                setup.configure_zsh("linux")
        self.assertEqual(self.zshrc.read_bytes(), b"# existing\n")
        self.assertFalse(list(self.home.glob(".dotconfig-*")))

    def test_concurrent_edits_are_not_overwritten(self):
        self.zshrc.write_bytes(b"# existing\n")
        write_bytes = Path.write_bytes

        def edit_during_staging(path, content):
            result = write_bytes(path, content)
            write_bytes(self.zshrc, b"# user edited during setup\n")
            return result

        with patch.object(Path, "write_bytes", edit_during_staging):
            with self.assertRaisesRegex(setup.SetupError, "changed during setup"):
                setup.configure_zsh("linux")
        self.assertEqual(
            self.zshrc.read_bytes(), b"# user edited during setup\n"
        )
        self.assertFalse(list(self.home.glob(".dotconfig-*")))

    @unittest.skipIf(os.name == "nt", "Windows symlinks can require elevation")
    def test_symlink_and_file_permissions_are_preserved(self):
        target = self.write(self.home / "my dotfiles/zshrc", "# original\n")
        target.chmod(0o600)
        self.zshrc.symlink_to(target)
        setup.configure_zsh("linux")
        self.assertTrue(self.zshrc.is_symlink())
        self.assertIn(setup.ZSH_BLOCK_START, target.read_bytes())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        setup.configure_zsh("linux", uninstall=True)
        self.assertTrue(self.zshrc.is_symlink())
        self.assertEqual(target.read_bytes(), b"# original\n")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    @unittest.skipIf(os.name == "nt", "Windows symlinks can require elevation")
    def test_dangling_and_self_sourcing_symlinks_are_rejected(self):
        self.zshrc.symlink_to(self.home / "missing")
        with self.assertRaisesRegex(setup.SetupError, "regular zsh config"):
            setup.configure_zsh("linux")
        self.zshrc.unlink()
        self.zshrc.symlink_to(self.root / "common/zsh/zshrc")
        with self.assertRaisesRegex(setup.SetupError, "Refusing"):
            setup.configure_zsh("linux")
        self.prompt.assert_not_called()

    def source_line(self, folder):
        return os.fsencode(f"source {shlex.quote(str(self.root / folder / 'zsh/zshrc'))}\n")

    @unittest.skipUnless(os.name == "posix" and shutil.which("zsh"), "Source evaluation requires zsh")
    def test_quoted_source_paths_load_common_then_only_the_active_platform(self):
        moved = self.base / "repo 'quoted' $dollar [brackets]"
        self.root.rename(moved)
        self.write(moved / "common/zsh/zshrc", "typeset -ga DOTCONFIG_ORDER=(common)\n")
        self.write(moved / "linux/zsh/zshrc", "DOTCONFIG_ORDER+=(linux)\n")
        self.write(moved / "mac/zsh/zshrc", "DOTCONFIG_ORDER+=(mac)\n")
        self.zshrc.write_text("DOTCONFIG_USER_SETTING=kept\n")
        with patch.object(setup, "ROOT", moved):
            for system in ("linux", "mac"):
                setup.configure_zsh(system)
                result = subprocess.run(
                    ["zsh", "-f", "-c", (
                        'source "$DOTCONFIG_TEST_RC"\n'
                        'print -r -- "$DOTCONFIG_USER_SETTING:${(j:,:)DOTCONFIG_ORDER}"'
                    )],
                    env={**os.environ, "DOTCONFIG_TEST_RC": str(self.zshrc)},
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), f"kept:common,{system}")

    @unittest.skipUnless(os.name == "posix" and shutil.which("zsh"), "Config evaluation requires zsh")
    def test_shared_and_platform_settings_load_into_an_existing_shell(self):
        for folder in ("common", "linux", "mac"):
            shutil.copy2(REPO / folder / "zsh/zshrc", self.root / folder / "zsh/zshrc")
        self.zshrc.write_text(
            "DOTCONFIG_USER_SETTING=kept\n"
            "compdef() { :; }\n"
            "compinit() { print -u2 'Do not reinitialize completion'; return 1; }\n"
        )
        for system in ("linux", "mac"):
            with self.subTest(system=system):
                setup.configure_zsh(system)
                script = (
                    'source "$DOTCONFIG_TEST_RC" || exit\n'
                    '[[ $DOTCONFIG_USER_SETTING == kept ]] || exit 1\n'
                    '[[ $aliases[vim] == nvim ]] || exit 1\n'
                    '[[ -n $LS_COLORS && $PROMPT == *"%F{green}"* ]] || exit 1\n'
                )
                if system == "linux":
                    script += "[[ $aliases[ls] == 'ls --color=auto' ]] || exit 1\n"
                else:
                    script += "[[ $CLICOLOR == 1 && -n $LSCOLORS ]] || exit 1\n"
                result = subprocess.run(
                    ["zsh", "-f", "-c", script],
                    env={**os.environ, "DOTCONFIG_TEST_RC": str(self.zshrc)},
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("Do not reinitialize", result.stderr)

    @unittest.skipUnless(os.name == "posix" and shutil.which("zsh"), "Plugin evaluation requires zsh")
    def test_mac_plugins_use_homebrew_prefix_and_are_loaded_once_in_order(self):
        prefix = self.home / "fake Homebrew"
        self.write(
            prefix / "share/zsh-autosuggestions/zsh-autosuggestions.zsh",
            "DOTCONFIG_PLUGIN_ORDER+=(autosuggestions)\n_zsh_autosuggest_start() { :; }\n",
        )
        self.write(
            prefix / "share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh",
            "DOTCONFIG_PLUGIN_ORDER+=(highlighting)\n_zsh_highlight() { :; }\n",
        )
        script = (
            'typeset -ga DOTCONFIG_PLUGIN_ORDER=()\n'
            'source "$DOTCONFIG_PLATFORM_RC"\n'
            'source "$DOTCONFIG_PLATFORM_RC"\n'
            'print -r -- "${(j:,:)DOTCONFIG_PLUGIN_ORDER}"\n'
        )
        result = subprocess.run(
            ["zsh", "-f", "-c", script],
            env={
                **os.environ,
                "HOMEBREW_PREFIX": str(prefix),
                "DOTCONFIG_PLATFORM_RC": str(REPO / "mac/zsh/zshrc"),
            },
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "autosuggestions,highlighting")

    @unittest.skipUnless(
        sys.platform == "linux"
        and shutil.which("zsh")
        and Path("/usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh").is_file()
        and Path("/usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh").is_file(),
        "Interactive Linux startup requires zsh and its apt plugins",
    )
    def test_real_linux_startup_loads_plugins_and_keeps_user_settings(self):
        for folder in ("common", "linux"):
            shutil.copy2(REPO / folder / "zsh/zshrc", self.root / folder / "zsh/zshrc")
        self.zshrc.write_text("DOTCONFIG_USER_SETTING=kept\n")
        setup.configure_zsh("linux")
        environment = {**os.environ, "HOME": str(self.home)}
        environment.pop("ZDOTDIR", None)
        result = subprocess.run(
            ["zsh", "-d", "-i", "-c", (
                '[[ $DOTCONFIG_USER_SETTING == kept ]] || exit 1\n'
                '[[ $aliases[vim] == nvim ]] || exit 1\n'
                '[[ $aliases[ls] == "ls --color=auto" ]] || exit 1\n'
                '(( ${+functions[compdef]} )) || exit 1\n'
                '(( ${+functions[_zsh_autosuggest_start]} )) || exit 1\n'
                '(( ${+functions[_zsh_highlight]} )) || exit 1\n'
                'print -r -- ready\n'
            )],
            cwd=self.home, env=environment, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ready")
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
