"""No-op views for absent optional providers. Never starts a worker or reads a screen."""
class IdleProvider:
    balance_names = {}
    scopes = {}
    def tick(self, *args, **kwargs): return {}
    def close(self): pass
    def start(self): pass
    def view(self, *args, **kwargs): return {}


class IdleNavigation(IdleProvider):
    def command(self, *args, **kwargs): raise ValueError('Install Mining Tools to use rock bookmarks')


class IdleDiary(IdleProvider):
    def execute(self, *args, **kwargs): raise ValueError('Install Mining Tools to use the mining diary')
    def observe(self, *args, **kwargs): pass


class IdleQuests(IdleProvider):
    def next_contract(self): pass


class HangarRunner:
    """Hangars work independently of the optional server ribbon."""
    def __init__(self, directory, owner):
        from executive_hangar import HangarScheduleService
        from hangar_card import HangarPublisher
        self.service=HangarScheduleService(directory)
        self.publisher=HangarPublisher(directory,owner)
        self.directory=directory
        self.due=0
    def tick(self, current_patch=''):
        import time
        from telemetry_ipc import read_shared_json
        now=time.time()
        if now<self.due:return
        self.due=now+1
        try:settings=read_shared_json(self.directory/'native_settings.json') or {}
        except (OSError,ValueError):settings={}
        self.publisher.tick(self.service,settings.get('hud_mode')=='hangars',now)
    def close(self):self.service.close()
