import json
import tempfile
import unittest
from pathlib import Path
from compboard_inventory import CompboardHudCommands,CompboardInventory,MAX_COUNT,read_inventory


class CompboardHudTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.directory=Path(self.folder.name);self.hud=CompboardHudCommands(self.directory,42)
        self.sequence=0

    def command(self,action,**fields):
        self.sequence+=1
        command=dict(id=str(self.sequence),owner_pid=42,at=100,action=action,
                     revision=read_inventory(self.directory)['revision'])
        command.update(fields)
        (self.directory/'compboard_hud_command.json').write_text(json.dumps(command))
        return self.hud.tick(101)

    def seed(self,counts):
        db=CompboardInventory(self.directory)
        try:db.set_counts(counts,db.view()['revision'])
        finally:db.close()

    def test_hud_and_desktop_share_counts_and_full_sets(self):
        state=self.command('add_set');self.assertEqual(state['counts'],[1]*7)
        state=self.command('adjust',index=0,delta=1)
        self.assertEqual(state['counts'],[2,1,1,1,1,1,1]);self.assertEqual(state['complete_sets'],1)
        state=self.command('adjust',index=1,delta=-1)
        self.assertEqual(state['complete_sets'],0);self.assertEqual(state['total'],7)
        self.assertEqual(read_inventory(self.directory)['counts'],state['counts'])
        self.seed([4,2,3,8,7,6,5])
        self.assertEqual(self.hud.tick(102)['complete_sets'],2)

    def test_use_and_undo_full_set_keep_extras_and_only_one_undo(self):
        self.seed([2,3,1,5,2,1,4]);before=read_inventory(self.directory)
        used=self.command('use_set');self.assertEqual(used['counts'],[1,2,0,4,1,0,3])
        self.assertTrue(used['can_undo'])
        restored=self.command('undo_set');self.assertEqual(restored['counts'],before['counts'])
        self.assertFalse(restored['can_undo']);self.assertNotIn('undo_counts',restored)
        self.assertFalse(self.command('undo_set')['result']['ok'])

    def test_repeated_poll_and_helper_restart_cannot_apply_edit_twice(self):
        first=self.command('add_set')
        self.assertEqual(self.hud.tick(102)['revision'],first['revision'])
        restarted=CompboardHudCommands(self.directory,42).tick(102)
        self.assertFalse(restarted['result']['ok']);self.assertEqual(restarted['counts'],[1]*7)

    def test_desktop_typed_counts_share_revision_checks_with_hud_buttons(self):
        typed=self.command('set_counts',counts=[4,2,3,8,7,6,5])
        self.assertTrue(typed['result']['ok']);self.assertEqual(typed['complete_sets'],2)
        hud=self.command('adjust',index=1,delta=-1)
        self.assertEqual(hud['complete_sets'],1)
        stale=self.command('set_counts',counts=[9]*7,revision=typed['revision'])
        self.assertFalse(stale['result']['ok']);self.assertEqual(stale['counts'],hud['counts'])
        for counts in ([1]*6,[-1]*7,[10000]*7,['2']*7):
            invalid=self.command('set_counts',counts=counts)
            self.assertFalse(invalid['result']['ok']);self.assertEqual(invalid['counts'],hud['counts'])

    def test_stale_desktop_revision_rejected_without_losing_any_counts(self):
        old=read_inventory(self.directory)['revision'];self.seed([3]*7)
        state=self.command('adjust',index=0,delta=1,revision=old)
        self.assertFalse(state['result']['ok']);self.assertEqual(state['counts'],[3]*7)
        self.assertIn('another window',state['result']['message'])

    def test_invalid_expired_and_wrong_owner_edits_leave_inventory_unchanged(self):
        self.seed([1]*7)
        for fields in (dict(owner_pid=43),dict(at=80),dict(at=102),dict(at=float('nan')),
                       dict(index=7),dict(delta=2),dict(index=True),dict(revision=True),dict(revision=-1)):
            state=self.command('adjust',**(dict(index=0,delta=1)|fields))
            self.assertFalse(state['result']['ok'],fields);self.assertEqual(state['counts'],[1]*7)
        self.assertFalse(self.command('unknown')['result']['ok'])

    def test_bounds_and_incomplete_set_fail_atomically(self):
        self.assertFalse(self.command('adjust',index=0,delta=-1)['result']['ok'])
        self.seed([1,1,0,1,1,1,1]);self.assertFalse(self.command('use_set')['result']['ok'])
        self.seed([MAX_COUNT,2,2,2,2,2,2]);state=self.command('add_set')
        self.assertFalse(state['result']['ok']);self.assertEqual(state['counts'],[MAX_COUNT,2,2,2,2,2,2])
        self.assertFalse(self.command('adjust',index=0,delta=1)['result']['ok'])

    def test_corrupt_inventory_is_preserved_and_controls_unavailable(self):
        self.seed([1]*7)
        path=self.directory/'compboard_inventory.sqlite3';path.write_bytes(b'broken database')
        (self.directory/'compboard_hud_command.json').write_text(json.dumps(dict(id='broken',owner_pid=42,at=100,action='add_set',revision=0)))
        state=self.hud.tick(101)
        self.assertTrue(state['unavailable']);self.assertFalse(state['result']['ok'])
        self.assertEqual(path.read_bytes(),b'broken database')


if __name__=='__main__':unittest.main()
