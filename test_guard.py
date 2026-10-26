import hashlib
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from guard import Guard, ConfigError, ConflictError, NoBackupError


class GuardTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).parent / 'work'
        scratch.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / 'config.toml'
        self.original = b"# keep comments\r\nmodel = 'example'\r\n"
        self.target.write_bytes(self.original)
        self.guard = Guard(self.target, self.root / 'state', notify=False)

    def seed(self):
        self.guard.check(seed=True)

    def test_invalid_windows_path_is_rejected_without_touching_target(self):
        self.seed()
        draft = self.root / 'draft.toml'
        draft.write_bytes(b'command = "C:\\Program Files\\nodejs\\node.exe"')
        with self.assertRaises(ConfigError):
            self.guard.apply(draft)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_apply_preserves_exact_bytes_and_original_backup(self):
        self.seed()
        draft = self.root / 'draft.toml'
        wanted = b"# comment\r\ncommand = 'C:\\Program Files\\nodejs\\node.exe'\r\n"
        draft.write_bytes(wanted)
        self.guard.apply(draft)
        self.assertEqual(self.target.read_bytes(), wanted)
        self.assertIn(self.original, [b for _, b in self.guard.valid_backups()])

    def test_watcher_waits_for_stable_partial_write_then_restores(self):
        self.seed()
        self.target.write_bytes(b'model = "unfinished')
        self.guard.tick(0)
        self.guard.tick(2)
        self.assertEqual(self.target.read_bytes(), b'model = "unfinished')
        self.target.write_bytes(b'model = "still unfinished')
        self.guard.tick(3)
        self.guard.tick(5.9)
        self.assertEqual(self.target.read_bytes(), b'model = "still unfinished')
        self.guard.tick(6.1)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertIn(b'model = "still unfinished', [p.read_bytes() for p in self.guard.quarantine.glob('*.toml')])

    def test_corrupt_latest_backup_is_skipped(self):
        self.seed()
        draft = self.root / 'draft.toml'
        draft.write_bytes(b"model = 'second'\n")
        self.guard.apply(draft)
        latest, _ = self.guard.valid_backups()[0]
        latest.write_bytes(b"model = 'tampered but valid TOML'\n")
        self.target.write_bytes(b'model = "broken')
        self.guard.restore()
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_no_valid_backup_never_overwrites(self):
        broken = b'model = "broken'
        self.target.write_bytes(broken)
        with self.assertRaises(NoBackupError):
            self.guard.restore()
        self.guard.tick(0)
        self.guard.tick(4)
        self.assertEqual(self.target.read_bytes(), broken)

    def test_concurrent_change_prevents_replace(self):
        self.seed()
        draft = self.root / 'draft.toml'
        draft.write_bytes(b"model = 'proposed'\n")
        external = b"model = 'external'\n"
        real = self.guard.atomic_replace

        def race(data, expected):
            self.target.write_bytes(external)
            return real(data, expected)

        with patch.object(self.guard, 'atomic_replace', side_effect=race):
            with self.assertRaises(ConflictError):
                self.guard.apply(draft)
        self.assertEqual(self.target.read_bytes(), external)

    def test_valid_change_is_debounced_before_snapshot(self):
        self.seed()
        changed = b"model = 'changed'\n"
        self.target.write_bytes(changed)
        self.guard.tick(0)
        self.guard.tick(2)
        self.assertNotIn(changed, [b for _, b in self.guard.valid_backups()])
        self.guard.tick(3.1)
        self.assertIn(changed, [b for _, b in self.guard.valid_backups()])

    def test_change_between_observation_and_check_is_not_snapshotted(self):
        self.seed()
        first = b"model = 'first'\n"
        later = b"model = 'later'\n"
        self.target.write_bytes(first)
        self.guard.tick(0)
        real = self.guard.check

        def changing_check(*args, **kwargs):
            self.target.write_bytes(later)
            return real(*args, **kwargs)

        with patch.object(self.guard, 'check', side_effect=changing_check):
            try:
                self.guard.tick(4)
            except ConflictError:
                pass
        self.assertNotIn(later, [b for _, b in self.guard.valid_backups()])

    def test_keeps_twenty_verified_snapshots(self):
        for n in range(25):
            self.target.write_bytes(f'model = "version-{n}"'.encode())
            self.guard.check(seed=True)
        self.assertEqual(len(self.guard.valid_backups()), 20)

    def test_missing_target_can_be_recovered_after_debounce(self):
        self.seed()
        self.target.unlink()
        self.guard.tick(0)
        self.guard.tick(4)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_logs_do_not_contain_config_secrets(self):
        self.seed()
        self.target.write_bytes(b'secret = "VERY_PRIVATE_DATA')
        self.guard.tick(0)
        self.guard.tick(4)
        log = self.guard.log_path.read_text(encoding='utf-8')
        self.assertNotIn('VERY_PRIVATE_DATA', log)
        events = [json.loads(s) for s in log.splitlines()]
        self.assertTrue(any(e['event'] == 'restored' for e in events))
        self.assertEqual(hashlib.sha256(self.target.read_bytes()).hexdigest(), hashlib.sha256(self.original).hexdigest())

    def test_real_watcher_recovers_and_restarts_after_process_termination(self):
        self.seed()
        script = 'from guard import Guard; import sys; Guard(sys.argv[1],sys.argv[2],notify=False).watch()'

        def eventually(predicate, timeout=30):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if predicate():
                    return
                time.sleep(0.2)
            self.fail('Watcher did not reach expected state before timeout')

        def heartbeat_pid():
            try:
                return json.loads((self.guard.state / 'watcher.json').read_text())['pid']
            except (OSError, ValueError):
                return None

        for attempt in range(2):
            process = subprocess.Popen([sys.executable, '-c', script, str(self.target), str(self.guard.state)],
                                       cwd=Path(__file__).parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                eventually(lambda: heartbeat_pid() == process.pid)
                broken = f'model = "unfinished-{attempt}'.encode()
                self.target.write_bytes(broken)
                eventually(lambda: self.target.read_bytes() == self.original)
                self.assertIn(broken, [p.read_bytes() for p in self.guard.quarantine.glob('*.toml')])
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
