"""Last reported law-zone conditions, never a prediction of security hostility."""
import math
import re


class JurisdictionWatch:
    TITLES = {
        'Entered Monitored Space': ('monitoring', 'monitored'),
        'Exited Monitored Space': ('monitoring', 'unmonitored'),
        'Monitored Space Down': ('monitoring', 'down'),
        'Monitored Space Restored': ('monitoring', 'monitored'),
        'Entering Armistice Zone - Combat Prohibited': ('armistice', 'inside'),
        'Leaving Armistice Zone - Caution Advised': ('armistice', 'outside'),
    }

    def __init__(self):
        self.reset()

    def reset(self):
        self.fields = {}
        self.changed_at = None
        self.first_view_at = None

    def feed(self, line, at, time_source):
        if '<SHUDEvent_OnNotification> Added notification "' not in line:
            return False
        if time_source != 'game_log_timestamp' or not math.isfinite(at):
            return False
        match = re.search(r'<SHUDEvent_OnNotification> Added notification "([^"\r\n]+)" \[\d+\] to queue\.', line)
        if not match:
            return False
        title = re.sub(r'<[^>]+>', '', match[1]).strip().removesuffix(':').strip()
        condition = self.TITLES.get(title)
        if condition is None:
            match = re.fullmatch(r'Entered ([^\r\n]{1,100}) Jurisdiction', title)
            if not match:
                return False
            condition = ('jurisdiction', match[1].strip())
        key, value = condition
        old = self.fields.get(key)
        if old and at <= old['observed_at']:
            return False
        self.fields[key] = dict(value=value, observed_at=at)
        if not old or old['value'] != value:
            self.changed_at = max(self.changed_at or at, at)
        return True

    def view(self, now, active=True, session_token=None):
        if self.first_view_at is None:
            self.first_view_at = now
        observations = {key: dict(row, age_s=now-row['observed_at'])
                        for key, row in self.fields.items()
                        if active and session_token and 0 <= now-row['observed_at']}
        changed = self.changed_at
        pulse = bool(active and session_token and changed is not None
                     and changed > self.first_view_at and 0 <= now-changed < 3)
        return dict(available=bool(observations), session_token=session_token if active else None,
                    monitoring=observations.get('monitoring', {}).get('value', 'unknown'),
                    armistice=observations.get('armistice', {}).get('value', 'unknown'),
                    jurisdiction=observations.get('jurisdiction', {}).get('value', ''),
                    observations=observations, changed_at=changed if pulse else None,
                    source='game_log_zone_notifications', semantics='last_reported',
                    security_hostility='unknown')
