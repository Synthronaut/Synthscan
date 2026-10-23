"""User-approved elevated FPS helper; exits with the native app, no game input."""
import argparse,ctypes,time,logging
from native_bridge import owner_alive
from app_lifecycle import game_process_ids,SingleInstance,instance_running
from frame_telemetry import PresentMonCollector
from native_control import DATA

def run(owner):
    DATA.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=DATA/'timing_helper.log',level=logging.INFO)
    if not ctypes.windll.shell32.IsUserAnAdmin():raise RuntimeError('Windows timing permission was not granted')
    lock=SingleInstance('native-timing')
    if not lock.acquired:return
    collector=None;pid=None
    try:
        while owner_alive(owner):
            games=game_process_ids()
            if instance_running('network-probe'):
                # The combined network helper already publishes player FPS.
                if collector:collector.stop();collector=None;pid=None
            elif games and pid not in games:
                if collector:collector.stop()
                pid=min(games);collector=PresentMonCollector(pid);collector.start()
            elif not games and collector:
                collector.stop();collector=None;pid=None
            time.sleep(1)
    finally:
        if collector:collector.stop()
        lock.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--owner',type=int,required=True)
    run(parser.parse_args().owner)
