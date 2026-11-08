"""Unattended setup refresh, deferred while the game or guided setup is open."""
def main():
    from app_lifecycle import SingleInstance,game_process_ids
    lock=SingleInstance('setup')
    if not lock.acquired:return 2
    try:
        if game_process_ids():return 2
        from community_setup import prepare
        prepare(force=True)
        return 0
    finally:lock.close()

if __name__=='__main__':
    raise SystemExit(main())
