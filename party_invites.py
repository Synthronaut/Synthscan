"""User-controlled invitation pacing and local, session-scoped attempt history."""
import math
import random
from pathlib import Path
from threading import Condition,Event,RLock
import time

from telemetry_ipc import read_shared_json,publish_json

INVITE_INTERVAL_MIN=0.09
INVITE_INTERVAL_MAX=0.99
MAX_BATCH_REQUESTS=50


def validate_batch_size(people):
    if not people or len(people)>MAX_BATCH_REQUESTS:
        raise ValueError(f'Select 1–{MAX_BATCH_REQUESTS} players per request batch. Nothing was sent; select fewer players and try again.')


class InviteHistory:
    def __init__(self,directory,filename='party_invite_attempts.json'):
        self.path=Path(directory)/filename;self.lock=RLock();self.error=''
        self.data=dict(schema=1,session_token='',people={})
        try:
            value=read_shared_json(self.path,1024*1024)
            if not isinstance(value,dict) or value.get('schema')!=1 or not isinstance(value.get('session_token'),str) or not isinstance(value.get('people'),dict) or len(value['people'])>4096:raise ValueError('Invalid history')
            if any(not isinstance(key,str) or not isinstance(person,dict) or not isinstance(person.get('handle'),str) for key,person in value['people'].items()):raise ValueError('Invalid recipients')
            self.data=value
        except FileNotFoundError:pass
        except (OSError,ValueError,TypeError):self.error='Invitation history is unavailable; the original file was preserved.'

    def ids(self,session):
        with self.lock:return set(self.data['people']) if session==self.data['session_token'] else set()

    def record(self,session,person):
        with self.lock:
            if self.error:raise ValueError(self.error)
            people=dict(self.data['people']) if session==self.data['session_token'] else {}
            people[person['id']]=dict(handle=person['handle'],attempted_at=time.time())
            if len(people)>4096:raise ValueError('Invitation history limit reached; no invitation sent.')
            value=dict(schema=1,session_token=session,people=people)
            if not publish_json(self.path,value):raise ValueError('Could not save invitation history; no invitation sent.')
            self.data=value


class PartyInviteQueue:
    def __init__(self,people,identifier='',*,cancel=None,history=None,session='',interval=None,clock=time.monotonic,operation='party',sample_interval=random.uniform):
        validate_batch_size(people)
        self.identifier=identifier;self.cancel_event=cancel if cancel is not None else Event()
        self.history=history;self.session=session;self.interval=interval;self.clock=clock;self.sample_interval=sample_interval
        self.last_interval=0.
        self.operation=operation
        self.condition=Condition();self.paused=False;self.finished=False;self.phase='Checking'
        self.inflight=False;self.current='';self.due=0.;self.error=''
        self.revision=0
        self.rows={p['id']:dict(id=p['id'],handle=p['handle'],outcome='Queued',detail='Waiting for the queue to send this request.') for p in people}

    def pause(self,paused):
        with self.condition:
            if self.finished or self.cancel_event.is_set():raise ValueError('This invitation queue has finished or is cancelling.')
            if self.paused and not paused:self.revision+=1
            self.paused=paused;self.condition.notify_all()

    def membership_revision(self):
        with self.condition:return self.revision

    def cancel(self):
        with self.condition:self.cancel_event.set();self.condition.notify_all()

    def before_send(self,person):
        with self.condition:
            while not self.cancel_event.is_set():
                if self.paused:self.condition.wait(.2);continue
                remaining=self.due-self.clock()
                if remaining>0:self.phase='Waiting';self.condition.wait(min(remaining,.2));continue
                self.phase='Sending';self.inflight=True;self.current=person['handle']
                self.rows[person['id']].update(outcome='Sending',detail='One invitation in flight; pause/cancel applies after it finishes.')
                return True
            return False

    def remember(self,person):
        if self.history:self.history.record(self.session,person)

    def update(self,row):
        with self.condition:
            if row['id'] not in self.rows:raise ValueError('Unexpected invitation recipient')
            self.rows[row['id']]=dict(row)
            if self.inflight:
                # Draw once per completed request; polling, pauses and skips do not redraw.
                self.last_interval=self.interval if self.interval is not None else self.sample_interval(INVITE_INTERVAL_MIN,INVITE_INTERVAL_MAX)
                self.inflight=False;self.current='';self.due=self.clock()+self.last_interval
            self.condition.notify_all()

    def finish(self,results=None,error=''):
        with self.condition:
            if self.finished:return
            for row in results or []:
                if row['id'] in self.rows:self.rows[row['id']]=dict(row)
            self.error=error
            for row in self.rows.values():
                if row['outcome'] in ('Queued','Sending'):row.update(outcome='Not sent',detail=error or 'Queue cancelled; no further invitation was sent.')
            self.inflight=False;self.current='';self.finished=True
            self.phase='Cancelled' if self.cancel_event.is_set() else 'Stopped' if error or any(p['outcome']=='Check in game' for p in self.rows.values()) else 'Completed'
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            rows=[dict(row) for row in self.rows.values()]
            processed=sum(p['outcome'] not in ('Queued','Sending') for p in rows)
            state=self.phase if self.finished else 'Cancelling' if self.cancel_event.is_set() else ('Pausing' if self.inflight else 'Paused') if self.paused else self.phase
            return dict(id=self.identifier,operation=self.operation,active=not self.finished,paused=self.paused,cancelling=self.cancel_event.is_set(),state=state,
                        total=len(rows),processed=processed,remaining=len(rows)-processed,sent=sum(p['outcome']=='Sent' for p in rows),
                        skipped=sum(p['outcome']=='Skipped' for p in rows),current_handle=self.current,interval_seconds=self.last_interval,
                        interval_min_seconds=self.interval if self.interval is not None else INVITE_INTERVAL_MIN,
                        interval_max_seconds=self.interval if self.interval is not None else INVITE_INTERVAL_MAX,
                        next_in_seconds=max(0,math.ceil(self.due-self.clock())) if not self.finished and not self.paused else 0,error=self.error,results=rows)
