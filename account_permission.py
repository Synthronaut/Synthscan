"""Account consent, separate from screen-reading installation."""
import json
from pathlib import Path
def require_account_access(directory=None):
    if directory is None:
        from installation import PROFILE
        directory=PROFILE
    directory=Path(directory)
    try:
        data=json.loads((directory/'capture_privacy.json').read_text())
        if not isinstance(data,dict) or data.get('schema')!=1:raise PermissionError('Invalid privacy preferences')
        allowed=data.get('account_access',False)
        if not isinstance(allowed,bool) or not allowed:raise PermissionError('Game-account features are disabled in Privacy & capture')
    except FileNotFoundError:raise PermissionError('Enable game-account features in Privacy & capture first')
    except PermissionError:raise
    except (OSError,ValueError) as error:raise PermissionError('Cannot verify game-account permission') from error
