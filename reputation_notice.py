"""A quiet, non-activating notification; never restarts or controls the game."""

class NoticeGate:
    def __init__(self):self.seen=set()
    def consume(self,view,pids):
        key=tuple(sorted(pids))
        if view.get('state')!='restart' or not key or key in self.seen:return False
        self.seen.add(key);return True
