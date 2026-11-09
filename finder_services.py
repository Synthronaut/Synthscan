"""Keep Finder IPC responsive independently of the slower session collectors."""
import logging
import threading


class FinderServices:
    def __init__(self, shops, market, extras=()):
        self.services = tuple(s for s in (shops, market, *extras) if s is not None)
        self.current_patch = ''
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name='finder-services', daemon=True)

    def start(self):
        self.thread.start()

    def tick(self):
        patch = self.current_patch
        for service in self.services:
            try:
                service.tick(current_patch=patch)
            except Exception:
                logging.exception('Finder refresh failed; last known data retained')

    def run(self):
        while not self.stop.is_set():
            self.tick()
            self.stop.wait(.1)

    def close(self):
        self.stop.set()
        if self.thread.ident is not None:
            self.thread.join()
        for service in self.services:
            service.close()
