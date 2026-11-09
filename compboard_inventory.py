"""Manual, per-user board counts. Claims and undo commit atomically in SQLite."""
import json
import sqlite3
import math
from contextlib import closing
from pathlib import Path

FILENAME = 'compboard_inventory.sqlite3'
MAX_COUNT = 9999
BOARD_LOCATIONS = ('Checkmate', 'Checkmate', 'Checkmate', 'Orbituary', 'Ruin Station', 'Ruin Station', 'Orbituary')


class StaleInventoryError(ValueError):
    pass


def valid_counts(counts):
    if not isinstance(counts, list) or len(counts) != 7:
        raise ValueError('Enter a quantity for each of the seven boards.')
    if any(type(n) is not int or not 0 <= n <= MAX_COUNT for n in counts):
        raise ValueError(f'Board quantities must be whole numbers from 0 to {MAX_COUNT}.')
    return counts


def _view(row):
    if row is None:
        raise ValueError('Saved board inventory is missing. The file has been left untouched.')
    counts = valid_counts(json.loads(row[0]))
    if type(row[1]) is not int or row[1] < 0:
        raise ValueError('Invalid inventory revision.')
    undo = valid_counts(json.loads(row[2])) if row[2] is not None else None
    return dict(counts=counts, revision=row[1], complete_sets=min(counts), total=sum(counts),
                can_undo=undo is not None and row[3] == row[1], undo_counts=undo)


def read_inventory(directory):
    """Read-only HUD access: never creates a database or resets damaged data."""
    path = Path(directory) / FILENAME
    if not path.exists():
        return dict(counts=[0]*7, revision=0, complete_sets=0, total=0, can_undo=False)
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=.05)) as db:
        if db.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise ValueError('Unsupported board inventory version.')
        return _view(db.execute('SELECT counts,revision,undo_counts,undo_revision FROM board_inventory WHERE id=1').fetchone())


class CompboardInventory:
    def __init__(self, directory):
        path = Path(directory) / FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=.5, isolation_level=None)
        try:
            self.db.execute('BEGIN IMMEDIATE')
            version = self.db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise ValueError('Unsupported board inventory version.')
            if version == 0:
                self.db.execute('CREATE TABLE board_inventory (id INTEGER PRIMARY KEY CHECK(id=1), counts TEXT NOT NULL, revision INTEGER NOT NULL, undo_counts TEXT, undo_revision INTEGER)')
                self.db.execute('INSERT INTO board_inventory VALUES(1,?,0,NULL,NULL)', (json.dumps([0]*7),))
                self.db.execute('PRAGMA user_version=1')
            self.view()
            self.db.execute('COMMIT')
        except Exception:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            self.db.close()
            raise

    def view(self):
        return _view(self.db.execute('SELECT counts,revision,undo_counts,undo_revision FROM board_inventory WHERE id=1').fetchone())

    def _change(self, operation, expected_revision):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old = self.view()
            if type(expected_revision) is not int or old['revision'] != expected_revision:
                raise StaleInventoryError('Counts changed in another window. Review the refreshed inventory and try again.')
            counts, undo = operation(old)
            valid_counts(counts)
            if counts != old['counts']:
                revision = old['revision']+1
                self.db.execute('UPDATE board_inventory SET counts=?,revision=?,undo_counts=?,undo_revision=? WHERE id=1',
                                (json.dumps(counts), revision, json.dumps(undo) if undo is not None else None,
                                 revision if undo is not None else None))
            result = self.view()
            self.db.execute('COMMIT')
            return result
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def set_counts(self, counts, expected_revision):
        valid_counts(counts)
        return self._change(lambda old: (counts, None), expected_revision)

    def use_set(self, expected_revision):
        def consume(old):
            if old['complete_sets'] < 1:
                raise ValueError('A complete set needs at least one of every board, 1–7.')
            return [n-1 for n in old['counts']], old['counts']
        return self._change(consume, expected_revision)

    def adjust(self, index, delta, expected_revision):
        if type(index) is not int or not 0 <= index < 7 or type(delta) is not int or delta not in (-1, 1):
            raise ValueError('Choose a board and add or subtract one.')
        def change(old):
            counts = list(old['counts']);counts[index] += delta
            return counts, None
        return self._change(change, expected_revision)

    def add_set(self, expected_revision):
        return self._change(lambda old: ([n+1 for n in old['counts']], None), expected_revision)

    def undo_set(self, expected_revision):
        def undo(old):
            if not old['can_undo']:
                raise ValueError('There is no set use to undo. Editing counts clears undo.')
            return old['undo_counts'], None
        return self._change(undo, expected_revision)

    def close(self):
        self.db.close()


class CompboardHudCommands:
    """One pending native-HUD edit, using the same revision-checked inventory.

    Commands are never retried against a newer revision. Replaying a command
    after a helper restart cannot apply the same edit twice.
    """
    def __init__(self, directory, owner):
        self.directory=Path(directory);self.owner=owner;self.last_id='';self.result={}

    def tick(self, now):
        from telemetry_ipc import read_shared_json
        try:command=read_shared_json(self.directory/'compboard_hud_command.json',limit=16384) or {}
        except (OSError,ValueError):command={}
        if not isinstance(command,dict):command={}
        identifier=command.get('id')
        if isinstance(identifier,str) and identifier and identifier!=self.last_id:
            self.last_id=identifier
            try:
                at=command.get('at')
                if (command.get('owner_pid')!=self.owner or type(at) not in (int,float)
                        or not math.isfinite(at) or not 0<=now-at<15):
                    raise ValueError('That edit expired. Review the current counts and try again.')
                action=command.get('action');revision=command.get('revision')
                if action not in ('adjust','add_set','use_set','undo_set','set_counts'):
                    raise ValueError('Unknown board inventory action.')
                repository=CompboardInventory(self.directory)
                try:
                    if action=='adjust':repository.adjust(command.get('index'),command.get('delta'),revision)
                    elif action=='set_counts':repository.set_counts(command.get('counts'),revision)
                    else:getattr(repository,action)(revision)
                finally:repository.close()
                self.result=dict(id=identifier,ok=True,message='Counts saved on this PC.')
            except (OSError,ValueError,sqlite3.Error) as exc:
                self.result=dict(id=identifier,ok=False,message=str(exc))
        try:inventory=read_inventory(self.directory)
        except (OSError,ValueError,sqlite3.Error):inventory=dict(unavailable=True)
        inventory.pop('undo_counts',None)
        return dict(at=now,owner_pid=self.owner,result=self.result,**inventory)
