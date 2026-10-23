"""Install/remove the per-user Windows startup watcher, or run it hidden.

This watches process names and starts SynthScan; it never launches or controls
Star Citizen. The watcher requires neither administrator rights nor game memory.
"""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys
import time

from app_lifecycle import ROOT, LaunchPolicy, Signal, SingleInstance, game_process_ids, instance_running, send_signal


def python_windowless():
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return str(candidate if candidate.exists() else Path(sys.executable))


def spawn(script, *args):
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    return subprocess.Popen([python_windowless(), '-B', str(ROOT / script), *args], cwd=ROOT,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                            startupinfo=startup)


def shortcut_path():
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup/SynthScan Game Watcher.lnk"


def install():
    destination = shortcut_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    def literal(value):
        return "'" + str(value).replace("'", "''") + "'"
    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$shell = New-Object -ComObject WScript.Shell",
        f"$link = $shell.CreateShortcut({literal(destination)})",
        f"$link.TargetPath = {literal(python_windowless())}",
        f"$link.Arguments = {literal(subprocess.list2cmdline(['-B', str(ROOT / 'auto_launch.py'), '--watch']))}",
        f"$link.WorkingDirectory = {literal(ROOT)}",
        "$link.Description = 'Start SynthScan when Star Citizen launches'",
        "$link.WindowStyle = 7",
        "$link.Save()",
    ])
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                   check=True, creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True)
    if not instance_running("watcher"):
        spawn("auto_launch.py", "--watch")
    print(json.dumps({"installed": destination.exists(), "shortcut": str(destination)}))


def watch():
    try:
        target=json.loads((ROOT/'launch_target.json').read_text()).get('target')
    except (OSError,ValueError):target='legacy'
    if target=='native':
        from native_control import watch as watch_native
        return watch_native()
    lock = SingleInstance("watcher")
    if not lock.acquired:
        return
    stop = Signal("watcher-stop")
    handler = RotatingFileHandler(ROOT / "launcher.log", maxBytes=256000, backupCount=1, encoding="utf-8")
    logging.basicConfig(handlers=[handler], level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    policy = LaunchPolicy()
    logging.info("Game watcher started")
    try:
        while True:
            try:
                games = game_process_ids()
                if policy.needs_launch(games, instance_running()):
                    process = spawn("main.py", "--autostart")
                    policy.mark_launched()
                    logging.info("Started SynthScan pid=%s for game pids=%s", process.pid, sorted(games))
            except Exception:
                logging.exception("Game watcher poll failed")
            if stop.wait(3):
                break
    finally:
        logging.info("Game watcher stopped")
        stop.close()
        lock.close()


def uninstall():
    shortcut_path().unlink(missing_ok=True)
    send_signal("watcher-stop")
    deadline = time.monotonic() + 2
    while instance_running("watcher") and time.monotonic() < deadline:
        time.sleep(0.05)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true")
    group.add_argument("--uninstall", action="store_true")
    group.add_argument("--watch", action="store_true")
    group.add_argument("--status", action="store_true")
    options = parser.parse_args()
    if options.install:
        install()
    elif options.uninstall:
        uninstall()
        print("Automatic launch disabled. The running app has been left open.")
    elif options.watch:
        watch()
    else:
        try:target=json.loads((ROOT/'launch_target.json').read_text()).get('target')
        except (OSError,ValueError):target='legacy'
        if target=='native':
            from native_control import native_running,native_ready,read_status
            print(json.dumps(dict(installed=shortcut_path().exists(),watcher_running=instance_running('watcher'),
                                  app_running=native_running(),ready=native_ready(),target='native',native_status=read_status(),game_pids=sorted(game_process_ids()))))
            return
        print(json.dumps({"installed": shortcut_path().exists(), "watcher_running": instance_running("watcher"),
                          "app_running": instance_running(), "game_pids": sorted(game_process_ids())}))


if __name__ == "__main__":
    main()
