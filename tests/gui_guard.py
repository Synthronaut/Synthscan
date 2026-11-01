"""Never create even hidden UI fixtures alongside an active Star Citizen game."""
import unittest

def require_game_closed():
    from app_lifecycle import game_process_ids
    if game_process_ids():
        raise unittest.SkipTest('Close Star Citizen before running UI fixtures')
