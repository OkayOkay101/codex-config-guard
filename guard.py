"""Local syntax guard. Production CLI deliberately has no target override."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parent
TARGET = Path(r'C:\Users\Smart\.codex\config.toml')
STATE = ROOT / 'state'


class ConfigError(Exception):
    pass


class ConflictError(Exception):
    pass


class NoBackupError(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def validate(data):
    if data is None:
        raise ConfigError('missing_file')
    try:
        tomllib.loads(data.decode('utf-8-sig'))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        # Never propagate parser text: it can include configuration secrets.
        line = getattr(exc, 'lineno', None)
        column = getattr(exc, 'colno', None)
        if line is None:
            match = re.search(r'line (\d+), column (\d+)', str(exc))
            if match:
                line, column = map(int, match.groups())
        raise ConfigError(f'invalid_toml line={line} column={column}') from None


def read_optional(path):
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def atomic_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.guard-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def exclusive(path):
    """Locks release on process death, unlike stale PID/lockfile sentinels."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


class Guard:
    def __init__(self, target=TARGET, state=STATE, notify=True):
        self.target = Path(target)
        self.state = Path(state)
        self.backups = self.state / 'backups'
        self.quarantine = self.state / 'quarantine'
        self.log_path = self.state / 'events.jsonl'
        self.notify_enabled = notify
        self.signature = object()
        self.changed_at = 0
        self.handled = False
        self.last_heartbeat = -100
        self.last_error = None
        for path in (self.state, self.backups, self.quarantine):
            path.mkdir(parents=True, exist_ok=True)

    def event(self, event, **values):
        record = {'time': dt.datetime.now(dt.timezone.utc).isoformat(), 'event': event, **values}
        # Bounded local history. No config values or arbitrary exception text.
        if self.log_path.exists() and self.log_path.stat().st_size > 2_000_000:
            os.replace(self.log_path, self.state / 'events.previous.jsonl')
        with self.log_path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=True) + '\n')

    def notify(self, kind):
        if self.notify_enabled and os.name == 'nt':
            try:
                subprocess.Popen(
                    ['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden',
                     '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'Notify.ps1'), '-Kind', kind],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                self.event('notification_unavailable')

    def valid_backups(self):
        found = []
        for meta_path in sorted(self.backups.glob('*.json'), reverse=True):
            path = meta_path.with_suffix('.toml')
            try:
                meta = json.loads(meta_path.read_text(encoding='utf-8'))
                data = path.read_bytes()
                if digest(data) != meta['sha256']:
                    continue
                validate(data)
                found.append((path, data))
            except (OSError, ValueError, KeyError, TypeError, ConfigError):
                continue
        return found

    def snapshot(self, data):
        validate(data)
        verified = self.valid_backups()
        if verified and digest(verified[0][1]) == digest(data):
            return verified[0][0]
        name = f'{time.time_ns():020d}-{digest(data)[:12]}'
        path = self.backups / (name + '.toml')
        atomic_file(path, data)
        metadata = {'time': dt.datetime.now(dt.timezone.utc).isoformat(), 'sha256': digest(data)}
        atomic_file(path.with_suffix('.json'), json.dumps(metadata).encode('utf-8'))
        # Read back before treating the snapshot as a recovery point.
        if digest(path.read_bytes()) != metadata['sha256']:
            raise OSError('snapshot_readback_failed')
        self.event('snapshot', sha256=digest(data))
        for old, _ in self.valid_backups()[20:]:
            old.with_suffix('.json').unlink(missing_ok=True)
            old.unlink(missing_ok=True)
        return path

    def check(self, seed=False, expected_signature=None):
        with exclusive(self.state / 'operation.lock'):
            if expected_signature is not None and self.file_signature() != expected_signature:
                raise ConflictError('config_changed')
            data = read_optional(self.target)
            validate(data)
            if seed:
                if expected_signature is not None and self.file_signature() != expected_signature:
                    raise ConflictError('config_changed')
                if digest(read_optional(self.target)) != digest(data):
                    raise ConflictError('config_changed')
                self.snapshot(data)
            return {'valid_toml': True, 'sha256': digest(data)}

    def atomic_replace(self, data, expected):
        validate(data)
        fd, temporary = tempfile.mkstemp(prefix='.config-guard-', suffix='.tmp', dir=self.target.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if self.target.exists():
                shutil.copymode(self.target, temporary)
            if digest(read_optional(self.target)) != expected:
                raise ConflictError('config_changed')
            os.replace(temporary, self.target)
            readback = self.target.read_bytes()
            if readback != data:
                raise ConflictError('readback_changed')
            validate(readback)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def preserve_bad(self, data):
        if data is not None:
            name = f'{time.time_ns():020d}-{digest(data)[:12]}.toml'
            atomic_file(self.quarantine / name, data)
            self.event('quarantined', sha256=digest(data))

    def apply(self, draft):
        proposed = Path(draft).read_bytes()
        validate(proposed)
        with exclusive(self.state / 'operation.lock'):
            current = read_optional(self.target)
            expected = digest(current)
            try:
                validate(current)
                self.snapshot(current)
            except ConfigError:
                self.preserve_bad(current)
            self.atomic_replace(proposed, expected)
            self.snapshot(proposed)
            self.event('applied', sha256=digest(proposed))
        return {'applied': True, 'sha256': digest(proposed)}

    def restore(self, expected_signature=None):
        with exclusive(self.state / 'operation.lock'):
            if expected_signature is not None and self.file_signature() != expected_signature:
                raise ConflictError('config_changed')
            current = read_optional(self.target)
            expected = digest(current)
            verified = self.valid_backups()
            if not verified:
                self.event('no_valid_backup', sha256=expected)
                self.notify('no_backup')
                raise NoBackupError('no_valid_backup')
            chosen, data = verified[0]
            try:
                validate(current)
                self.snapshot(current)
            except ConfigError:
                self.preserve_bad(current)
            if expected_signature is not None and self.file_signature() != expected_signature:
                raise ConflictError('config_changed')
            self.atomic_replace(data, expected)
            self.event('restored', sha256=digest(data), previous_sha256=expected)
            self.notify('restored')
        return {'restored': True, 'sha256': digest(data), 'backup': chosen.name}

    def file_signature(self):
        try:
            before = self.target.stat()
            data = self.target.read_bytes()
            after = self.target.stat()
            if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
                raise ConflictError('config_changed')
            return (after.st_size, after.st_mtime_ns, digest(data))
        except FileNotFoundError:
            return (None, None, None)

    def heartbeat(self):
        value = {'time': time.time(), 'pid': os.getpid(), 'last_error': self.last_error}
        atomic_file(self.state / 'watcher.json', json.dumps(value).encode('utf-8'))

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        signature = self.file_signature()
        if signature != self.signature:
            self.signature, self.changed_at, self.handled = signature, now, False
        if not self.handled and now - self.changed_at >= 3:
            try:
                self.check(seed=True, expected_signature=signature)
                self.last_error = None
            except ConfigError as exc:
                self.event('invalid_config', detail=str(exc), sha256=signature[2])
                try:
                    self.restore(expected_signature=signature)
                    self.last_error = None
                except NoBackupError:
                    self.last_error = 'no_valid_backup'
            self.handled = True
        if now - self.last_heartbeat >= 10:
            self.heartbeat()
            self.last_heartbeat = now

    def status(self):
        try:
            config = self.check()
        except ConfigError as exc:
            config = {'valid_toml': False, 'detail': str(exc)}
        try:
            watcher = json.loads((self.state / 'watcher.json').read_text(encoding='utf-8'))
            watcher['heartbeat_recent'] = 0 <= time.time() - watcher['time'] < 20
        except (OSError, ValueError):
            watcher = {'heartbeat_recent': False}
        return {'target': str(self.target), **config, 'verified_backups': len(self.valid_backups()), 'watcher': watcher}

    def watch(self):
        try:
            watcher_lock = exclusive(self.state / 'watch.lock')
            watcher_lock.__enter__()
        except OSError:
            return 0  # Already running; do not launch a second watcher.
        try:
            self.event('watch_started')
            while True:
                try:
                    self.tick()
                except (OSError, ConflictError) as exc:
                    code = type(exc).__name__
                    if self.last_error != code:
                        self.event('retry', detail=code)
                        if not isinstance(exc, ConflictError):
                            self.notify('attention')
                    self.last_error = code
                    self.handled = False
                time.sleep(2)
        finally:
            watcher_lock.__exit__(None, None, None)


def main():
    parser = argparse.ArgumentParser(description='Codex config.toml syntax guard (fixed production target)')
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check')
    check.add_argument('--seed', action='store_true')
    apply = sub.add_parser('apply')
    apply.add_argument('draft', type=Path)
    for command in ('status', 'restore', 'watch'):
        sub.add_parser(command)
    args = parser.parse_args()
    guard = Guard()
    try:
        if args.command == 'watch':
            return guard.watch()
        if args.command == 'check':
            result = guard.check(args.seed)
        elif args.command == 'apply':
            result = guard.apply(args.draft)
        elif args.command == 'restore':
            result = guard.restore()
        else:
            result = guard.status()
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result.get('valid_toml', True) else 2
    except (ConfigError, NoBackupError, ConflictError, OSError) as exc:
        detail = str(exc) if isinstance(exc, (ConfigError, NoBackupError, ConflictError)) else type(exc).__name__
        print(json.dumps({'ok': False, 'error': detail}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
