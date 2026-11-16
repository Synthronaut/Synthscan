"""Buyer watches, player tags and bounded background social operations."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
from threading import Event
import time
import uuid

from telemetry_ipc import read_shared_json,publish_json
from party_invites import InviteHistory,PartyInviteQueue,validate_batch_size,MAX_BATCH_REQUESTS

MARKET_INTERVAL=1800
ROSTER_INTERVAL=30
TAG_PRESETS=('Org','Enemy Org','Friend','Friendly','Aggressive','Trader','Org Affiliate','Crew','Buyer','Avoid')


def tag_labels(value):
    if not isinstance(value,str) or len(value)>240:raise ValueError('Enter up to eight short tags, separated by commas.')
    labels=[];seen=set();canonical={v.casefold():v for v in TAG_PRESETS}
    for part in value.split(','):
        label=' '.join(part.split())
        if not label:continue
        if len(label)>32:raise ValueError('Each tag can contain up to 32 characters.')
        label=canonical.get(label.casefold(),label)
        if label.casefold() not in seen:labels.append(label);seen.add(label.casefold())
    if len(labels)>8:raise ValueError('Use at most eight tags per player.')
    return labels


def is_org(tag):
    return any(label.casefold() in ('org','org affiliate') for label in tag_labels(tag.get('label','')))


def load(path,default):
    try:return read_shared_json(path,limit=8*1024*1024)
    except FileNotFoundError:return default


def fetch_rsi_org_members(symbol,max_members=1000):
    import urllib.request
    import re
    symbol=str(symbol).strip().upper()
    if not symbol:return dict(symbol=symbol,handles=[],total_rows=0,error='Enter an RSI Org symbol.')
    url='https://robertsspaceindustries.com/api/orgs/getOrgMembers'
    headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36','Content-Type':'application/json','Accept':'application/json, text/javascript, */*; q=0.01'}
    handles=[];seen=set();page=1;total_rows=0;pagesize=32
    while len(handles)<max_members:
        payload=json.dumps({'symbol':symbol,'search':'','pagesize':pagesize,'page':page}).encode('utf-8')
        req=urllib.request.Request(url,data=payload,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=12) as resp:data=json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            if not handles:return dict(symbol=symbol,handles=[],total_rows=0,error=f'RSI request failed: {e}')
            break
        data_obj=data.get('data') or {}
        total_rows=data_obj.get('totalrows') or total_rows
        html=data_obj.get('html','')
        if not html:break
        items=html.split('class="member-item')
        if len(items)<=1:break
        page_added=0
        for item in items[1:]:
            if 'org-visibility-R' in item:continue
            nick_match=re.search(r'class="[^"]*nick[^"]*">([^<]+)<',item)
            if nick_match:
                handle=nick_match.group(1).strip()
                if handle and handle.casefold() not in seen:
                    seen.add(handle.casefold());handles.append(handle);page_added+=1
        if page_added==0 or len(handles)>=total_rows or page*pagesize>=total_rows:break
        page+=1
        time.sleep(0.12)
    return dict(symbol=symbol,handles=handles,total_rows=total_rows,error='' if handles else f'No public members found for {symbol}.')


class PresenceChanges:
    def __init__(self):self.reset()
    def reset(self):self.members=None;self.absent={};self.at=0
    def observe(self,rows,now):
        current={r['id'] for r in rows}
        if self.members is None or not 0<=now-self.at<=120:
            self.members=current;self.absent={};self.at=now;return set()
        arrivals=current-self.members
        for identifier in self.members-current:self.absent[identifier]=self.absent.get(identifier,0)+1
        for identifier in current:self.absent.pop(identifier,None)
        self.members|=current
        self.members-={identifier for identifier,count in self.absent.items() if count>=2}
        self.at=now
        return arrivals


class CompanionStore:
    def __init__(self,directory):
        self.path=Path(directory)/'companion_private.json';self.read_only=False
        self.data=dict(schema=1,watches=[],tags={},notifications=[],commands=[],actions=[],org_rosters={},org_handles={},action_log=[])
        try:
            value=load(self.path,None)
            if value is not None:
                if value.get('schema')!=1 or not isinstance(value.get('watches'),list) or not isinstance(value.get('tags'),dict) or not isinstance(value.get('notifications'),list) or not isinstance(value.get('commands'),list):raise ValueError('Invalid saved companion data')
                for watch in value['watches']:
                    if not isinstance(watch,dict) or not all(k in watch for k in ('id','item_id','name','identity','quality','minimum_price','unit','enabled','initialized','seen','matches')) or not isinstance(watch['seen'],list):raise ValueError('Invalid buyer watch')
                for key,tag in value['tags'].items():
                    if not isinstance(tag,dict) or not isinstance(tag.get('handle'),str) or not isinstance(tag.get('label'),str):raise ValueError('Invalid saved player tag')
                actions=value.setdefault('actions',[])
                if not isinstance(actions,list) or len(actions)>4096 or any(not isinstance(p,dict) or not isinstance(p.get('id'),str) or not isinstance(p.get('handle'),str) for p in actions):raise ValueError('Invalid action list')
                value.setdefault('org_rosters',{})
                value.setdefault('org_handles',{})
                if not isinstance(value.get('action_log'),list):value['action_log']=[]
                self.data=value
        except (OSError,ValueError,TypeError):self.read_only=True
    def save(self):
        if self.read_only or not publish_json(self.path,self.data):raise ValueError('Saved data is unavailable; original records were preserved.')
    def notice(self,kind,title,detail,url='',session_token=None,now=None,category=''):
        now=time.time() if now is None else now
        event=dict(id=uuid.uuid4().hex,kind=kind,title=title,detail=detail,url=url,category=category,at=now,session_token=session_token)
        self.data['notifications']=(self.data['notifications']+[event])[-100:]
        return event
    def record_action(self,kind,handle,detail,player_id='',outcome='',session_token=None,now=None,dedupe_key=''):
        now=time.time() if now is None else now
        log=self.data.setdefault('action_log',[])
        if dedupe_key and any(entry.get('dedupe_key')==dedupe_key for entry in log):return None
        entry=dict(id=uuid.uuid4().hex,at=now,kind=kind,player_id=player_id,handle=handle,outcome=outcome,detail=detail,session_token=session_token,dedupe_key=dedupe_key)
        self.data['action_log']=(log+[entry])[-300:]
        return entry
    def watch(self,item,quality,price=0,unit=''):
        if type(quality)!=int or not 0<=quality<=1000:raise ValueError('Quality must be a whole number from 0 to 1000; 0 means any.')
        if isinstance(price,bool) or not isinstance(price,(float,int)) or not math.isfinite(price) or price<0:raise ValueError('Enter a valid minimum price.')
        unit=unit.strip()[:30]
        if price and not unit:raise ValueError('Enter the listing unit for your minimum price, such as unit or SCU.')
        if any(w['item_id']==item['id'] and w['quality']==quality and w['minimum_price']==price and w['unit'].casefold()==unit.casefold() for w in self.data['watches']):raise ValueError('That buyer watch is already saved.')
        if len(self.data['watches'])>=25:raise ValueError('Up to 25 buyer watches can be saved.')
        watch=dict(id=uuid.uuid4().hex,item_id=item['id'],name=item['name'],identity=item['identity'],quality=quality,
                   minimum_price=price,unit=unit,enabled=True,initialized=False,seen=[],checked_at=0,due_at=0,matches=[],error='')
        self.data['watches'].append(watch);self.save();return watch
    def market_result(self,identifier,rows,now,limited=False):
        notified=set()
        for watch in self.data['watches']:
            if watch['item_id']!=identifier or not watch['enabled']:continue
            seen=set(watch['seen']);eligible=[row for row in rows if (not watch['quality'] or row['quality']==watch['quality']) and
                (not watch['minimum_price'] or row['price']>=watch['minimum_price'] and row['unit'].casefold()==watch['unit'].casefold())]
            if watch['initialized']:
                for row in eligible:
                    if row['id'] in seen or row['id'] in notified:continue
                    notified.add(row['id'])
                    quality='Q'+str(int(row['quality'])) if row['quality'] is not None else 'quality unspecified'
                    self.notice('buyer_match','BUY REQUEST · '+watch['name'],quality+' · '+f"{row['price']:,.0f} UEC / {row['unit']}"+' · Details in Buyer alerts',row['url'],now=now)
            watch.update(initialized=True,seen=list(dict.fromkeys(watch['seen']+[r['id'] for r in rows]))[-5000:],
                         checked_at=now,due_at=now+MARKET_INTERVAL,matches=eligible[:100],error='',limited=limited)
        self.save()


def fetch_buyers(identifier):
    from finder_market import listings
    from item_directory import uex_json
    return listings(uex_json(f'marketplace_listings?id_item={identifier}&operation=buy'),identifier,'buy',time.time())


class CompanionService:
    def __init__(self,directory,owner,social=None,market=fetch_buyers,pool=None):
        from player_services import social_job
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.owner=owner;self.store=CompanionStore(directory);self.social=social or social_job;self.market=market
        self.pool=pool or ThreadPoolExecutor(max_workers=2,thread_name_prefix='companion')
        self.context={};self.session=None;self.roster=[];self.search=[];self.roster_at=0;self.roster_due=0
        self.roster_error='';self.action_status='Select a player to tag, add as a friend, or invite.'
        if len(self.store.data['actions'])>MAX_BATCH_REQUESTS and not self.store.read_only:
            self.store.data['actions']=self.store.data['actions'][:MAX_BATCH_REQUESTS];self.store.save()
            self.action_status=f'Action list limited to the first {MAX_BATCH_REQUESTS} saved players. Review the list before sending.'
        self.search_query='';self.search_limited=False;self.gate=PresenceChanges();self.jobs={};self.next_publish=0
        self.relationships={};self.relationships_due=0
        self.known_friends=None;self.known_party=None
        self.pending_friend_out=set();self.pending_party_out=set()
        self.pending_friend_known=False;self.pending_party_known=False
        self.awaiting_friend_response=set();self.awaiting_party_response=set()
        self.batch_results=[];self.invited=set()
        self.invite_queue=None;self.invite_history=InviteHistory(directory)
        self.friend_history=InviteHistory(directory,'friend_request_attempts.json');self.friend_requested=set()
        self.cancel_batch=Event()
        self.started_at=time.time();self.revision=0;self.notice_revision=0;self.market_last_request=0
        from chat_codec import ChatTranslator
        self.translator=ChatTranslator(self.directory/'chat_translations_cache.json')
        self.chat_active=False;self.chat_auto_translate=True
        self.chat_channels=[];self.chat_messages=[];self.chat_at=0;self.chat_due=0;self.chat_error=''
        from voice_dictation import VoiceDictationService
        self.voice_dictation=VoiceDictationService.get_instance()
        self.voice_dictating=False;self.last_dictated_text=''
        self.command_dir=self.directory/'companion_commands';self.command_dir.mkdir(exist_ok=True)
    def changed(self):self.revision+=1;self.next_publish=0
    def fetch_org_members(self,symbol,tag_label,alert):
        res=fetch_rsi_org_members(symbol)
        res['tag_label']=tag_label
        res['alert']=alert
        return res
    def start_party_queue(self,targets,command,operation='party'):
        if command.get('confirmed') is not True:raise ValueError('Confirm the selected recipients first.')
        # Reject the entire batch before recording or submitting any work.
        # A larger Action list is still useful for tags and selecting a subset.
        validate_batch_size(targets)
        if 'action' in self.jobs:raise ValueError('A social action is already running.')
        history=self.friend_history if operation=='friend' else self.invite_history
        if history.error:raise ValueError(history.error)
        identifier=command['id']
        self.store.data['commands']=(self.store.data['commands']+[identifier])[-1000:];self.store.save()
        self.batch_results=[];self.cancel_batch=Event()
        remembered=self.friend_requested if operation=='friend' else self.invited;remembered.update(history.ids(self.session))
        next_send=self.invite_queue.due if self.invite_queue else 0.
        self.invite_queue=PartyInviteQueue(targets,identifier,cancel=self.cancel_batch,history=history,session=self.session,operation=operation)
        self.invite_queue.due=next_send
        previous=[] if command.get('resend') is True else list(remembered)
        self.jobs['action']=(self.pool.submit(self.social,'friend_many' if operation=='friend' else 'party_many',dict(self.context),people=[dict(p) for p in targets],confirmed=True,previous=previous,
                            cancel=self.cancel_batch,control=self.invite_queue,require_shard=True,allow_friends=operation=='party' and (command.get('from_actions') is True or command.get('allow_friends') is True)),dict(self.context))
        label='friend request' if operation=='friend' else 'party invite'
        self.action_status=f'Queued {len(targets)} {label}(s). Random 0.09–0.99s gaps; Pause / Cancel is available.'
    def friend_ids(self,now):
        stamp=self.relationships.get('friends_at',0)
        return set(self.relationships.get('friends',[])) if stamp and 0<=now-stamp<120 else set()
    def party_ids(self,now):
        stamp=self.relationships.get('party_at',0)
        return set(self.relationships.get('party',[])) if stamp and 0<=now-stamp<120 else set()
    def available_people(self):
        saved=[dict(id=key,handle=value['handle']) for key,value in self.store.data['tags'].items()]
        chat_senders=[dict(id=m['sender_id'],handle=m['sender_handle'],is_self=m.get('is_self',False)) for m in getattr(self,'chat_messages',[]) if m.get('sender_id') and m.get('sender_handle')]
        return {p['id']:p for p in reversed(self.roster+self.relationships.get('party_rows',[])+self.relationships.get('friend_rows',[])+self.search+self.store.data['actions']+chat_senders+saved)}
    def stage(self,targets,friends=()):
        if self.invite_queue and self.invite_queue.snapshot()['active']:raise ValueError('Cancel the running queue before changing the Action list.')
        current={p['id']:p for p in self.store.data['actions']}
        before=len(current);omitted=set()
        for p in targets:
            if p.get('is_self'):continue
            if p['id'] not in current and len(current)>=MAX_BATCH_REQUESTS:omitted.add(p['id']);continue
            current[p['id']]=dict(id=p['id'],handle=p['handle'],friend_scope=p['id'] in friends)
        self.store.data['actions']=list(current.values());self.store.data['actions_session']=self.session
        self.action_status=f'Added {len(current)-before} player(s). Action list: {len(current)}/{MAX_BATCH_REQUESTS}.'
        if omitted:self.action_status+=f' {len(omitted)} not added because the list is full; remove players to make room.'
    def command(self,command,now):
        if command.get('owner_pid')!=self.owner or not isinstance(command.get('at'),(int,float)) or not 0<=now-command['at']<30:return
        identifier=command.get('id','')
        if not isinstance(identifier,str) or not identifier or len(identifier)>100 or identifier in self.store.data['commands']:return
        if self.store.read_only:raise ValueError('Saved companion records are unavailable.')
        action=command.get('action')
        if action in ('friend','party','party_many','friend_many','kick_party_member','transfer_party_leader','leave_party','stage_people','stage_tag','pause_invites','resume_invites','cancel_invites','search','refresh_people','refresh_chat','send_chat_message','start_voice_dictation','stop_voice_dictation','tag','tag_many','mark_org'):
            if not self.session or command.get('session_token')!=self.session:raise ValueError('Session changed. Refresh People before continuing.')
        if action=='stage_people':
            ids=command.get('player_ids');available=self.available_people()
            active={p['id'] for p in self.roster}|self.friend_ids(now)
            if not isinstance(ids,list) or not ids or len(ids)>4096 or any(not isinstance(key,str) or key not in available or key not in active for key in ids):raise ValueError('Only current shard members or verified friends can be added to the Action list.')
            self.stage([available[key] for key in ids],self.friend_ids(now))
        elif action=='stage_tag':
            if command.get('scope','shard')!='shard':raise ValueError('Add by tag is limited to current shard members.')
            label=command.get('label','');wanted=tag_labels(label)
            if len(wanted)!=1:raise ValueError('Choose one exact tag to add.')
            matched={key for key,tag in self.store.data['tags'].items() if wanted[0].casefold() in {v.casefold() for v in tag_labels(tag['label'])} or command.get('include_org_affiliate') is True and wanted[0]=='Org' and is_org(tag)}
            available={p['id']:p for p in self.roster}
            if wanted[0]=='Friend':
                matched=self.friend_ids(now);available=self.available_people()
                if not self.relationships.get('friends_at') or not 0<=now-self.relationships['friends_at']<120:raise ValueError('Friends are still loading or stale. Refresh People and try again.')
            self.stage([p for key,p in available.items() if key in matched],self.friend_ids(now))
        elif action in ('unstage_people','clear_actions'):
            if self.invite_queue and self.invite_queue.snapshot()['active']:raise ValueError('Cancel the running queue before changing the Action list.')
            ids=command.get('player_ids',[])
            if not isinstance(ids,list) or any(not isinstance(key,str) for key in ids):raise ValueError('Invalid Action list selection')
            self.store.data['actions']=[] if action=='clear_actions' else [p for p in self.store.data['actions'] if p['id'] not in ids]
            self.action_status='Action list updated.'
        elif action in ('pause_invites','resume_invites','cancel_invites'):
            if not self.invite_queue or command.get('queue_id')!=self.invite_queue.identifier:raise ValueError('Invitation queue changed. Review the current queue.')
            if action=='cancel_invites':self.invite_queue.cancel();self.action_status='Cancelling invitations after any request already in flight.'
            else:self.invite_queue.pause(action=='pause_invites');self.action_status='Invitation queue paused after any request in flight.' if action=='pause_invites' else 'Invitation queue resumed.'
        elif action=='refresh_people':self.roster_due=0;self.relationships_due=0
        elif action=='set_chat_active':
            self.chat_active=bool(command.get('active',True))
            if self.chat_active:self.chat_due=0
        elif action=='set_chat_translate':
            self.chat_auto_translate=bool(command.get('enabled',True))
            self.chat_due=0
        elif action=='refresh_chat':
            self.chat_active=True;self.chat_due=0
        elif action in ('kick_party_member','transfer_party_leader','leave_party'):
            if command.get('confirmed') is not True:raise ValueError('Confirm the party action first.')
            if 'action' in self.jobs:raise ValueError('A social action is already running.')
            player_id=str(command.get('player_id') or '').strip()
            target=self.available_people().get(player_id,dict(id=player_id,handle=player_id))
            if action!='leave_party':
                party_set=set(self.relationships.get('party',[]))
                if not player_id or target.get('is_self') or (party_set and player_id not in party_set):
                    raise ValueError('Select another current party member first.')
            self.store.data['commands']=(self.store.data['commands']+[identifier])[-1000:];self.store.save()
            self.jobs['action']=(self.pool.submit(self.social,action,dict(self.context),player_id=player_id,handle=target.get('handle',''),confirmed=True),dict(self.context))
            if action=='kick_party_member':
                self.action_status=f"Removing {target.get('handle') or player_id} from party…"
                self.store.record_action('party_manage',target.get('handle') or player_id,'Removed from party',player_id=player_id,outcome='Removed',session_token=self.session,now=now)
            elif action=='transfer_party_leader':
                self.action_status=f"Making {target.get('handle') or player_id} party leader…"
                self.store.record_action('party_manage',target.get('handle') or player_id,'Promoted to party leader',player_id=player_id,outcome='Promoted',session_token=self.session,now=now)
            else:
                self.action_status='Leaving party…'
                self.store.record_action('party_manage','Party','Left party',player_id='',outcome='Left',session_token=self.session,now=now)
        elif action=='send_chat_message':
            if command.get('confirmed') is not True:raise ValueError('Confirm sending the chat message.')
            if 'chat_send' in self.jobs:raise ValueError('A chat message is already being sent.')
            group_id=str(command.get('group_id') or '').strip()
            content=str(command.get('text') or command.get('query') or '').strip()
            encode_zh=bool(command.get('encode_zh',False))
            if not group_id:raise ValueError('Select a chat channel before sending.')
            if not content:raise ValueError('Enter a message to send.')
            self.store.data['commands']=(self.store.data['commands']+[identifier])[-1000:];self.store.save()
            self.jobs['chat_send']=(self.pool.submit(self.social,'send_chat',dict(self.context),group_id=group_id,content=content,confirmed=True,encode_zh=encode_zh,translator=self.translator),dict(self.context))
            self.action_status='Sending chat message…'
        elif action=='start_voice_dictation':
            ok=self.voice_dictation.start_recording()
            self.voice_dictating=ok
            self.action_status='Listening to microphone (Push-To-Talk)…' if ok else 'Microphone unavailable.'
            self.changed()
        elif action=='stop_voice_dictation':
            send=bool(command.get('send',True))
            group_id=str(command.get('group_id') or '').strip()
            encode_zh=bool(command.get('encode_zh',False))
            text=self.voice_dictation.stop_recording_and_recognize()
            self.voice_dictating=False
            self.last_dictated_text=text
            if text:
                if send and group_id:
                    if 'chat_send' in self.jobs:
                        self.action_status=f'Voice: "{text}" (sending queued)'
                    else:
                        self.store.data['commands']=(self.store.data['commands']+[identifier])[-1000:];self.store.save()
                        self.jobs['chat_send']=(self.pool.submit(self.social,'send_chat',dict(self.context),group_id=group_id,content=text,confirmed=True,encode_zh=encode_zh,translator=self.translator),dict(self.context))
                        self.action_status=f'Voice sent: "{text}"'
                else:
                    self.action_status=f'Voice transcribed: "{text}"'
            else:
                self.action_status='No speech detected.'
            self.changed()
        elif action=='search':
            if 'search' in self.jobs:raise ValueError('A player search is already running.')
            query=str(command.get('query','')).strip()
            self.search_query=query;self.search=[];self.action_status='Searching handles…'
            self.jobs['search']=(self.pool.submit(self.social,'search',dict(self.context),query=query),dict(self.context))
        elif action in ('tag','friend','party'):
            saved=[dict(id=key,handle=value['handle']) for key,value in self.store.data['tags'].items()]
            target=self.available_people().get(command.get('player_id'))
            chat_ids={m['sender_id'] for m in self.chat_messages if m.get('sender_id')}
            if not target or target.get('is_self') or target['id'] not in ({p['id'] for p in self.roster}|self.friend_ids(now)|self.party_ids(now)|chat_ids):raise ValueError('Select another current-shard player first.')
            if action=='tag':
                labels=tag_labels(command.get('label',''))
                if 'Friend' in labels:raise ValueError('Friend is automatic from your game friends list; use Friendly for a custom tag.')
                if labels:
                    self.store.data['tags'][target['id']]=dict(handle=target['handle'],label=', '.join(labels),labels=labels,alert=command.get('alert') is True)
                    self.store.record_action('tag',target['handle'],'Tagged: '+', '.join(labels),player_id=target['id'],outcome='Tagged',session_token=self.session,now=now)
                else:
                    self.store.data['tags'].pop(target['id'],None)
                    self.store.record_action('tag',target['handle'],'Tags cleared',player_id=target['id'],outcome='Cleared',session_token=self.session,now=now)
            elif action=='party':self.start_party_queue([target],command)
            else:
                self.start_party_queue([target],command,'friend')
        elif action in ('tag_many','mark_org','party_many','friend_many'):
            ids=command.get('player_ids')
            if not isinstance(ids,list) or not ids or len(ids)>4096 or any(not isinstance(v,str) for v in ids):raise ValueError('Select one or more verified players.')
            ids=list(dict.fromkeys(ids))
            saved=[dict(id=key,handle=value['handle']) for key,value in self.store.data['tags'].items()]
            available=self.available_people()
            active={p['id'] for p in self.roster}|self.friend_ids(now)
            if any(key not in available or available[key].get('is_self') or key not in active for key in ids):raise ValueError('Selection changed. Actions are limited to current shard members or verified friends.')
            targets=[available[key] for key in ids]
            if action in ('party_many','friend_many'):
                if command.get('from_actions') is True and not set(ids).issubset({p['id'] for p in self.store.data['actions']}):raise ValueError('Action list changed. Review the recipients again.')
                if command.get('org_only'):
                    current={p['id'] for p in self.roster}
                    if any(key not in current or not is_org(self.store.data['tags'].get(key,{})) for key in ids):raise ValueError('Org membership or shard list changed. Review the recipients again.')
                self.start_party_queue(targets,command,'friend' if action=='friend_many' else 'party')
            else:
                labels=['Org'] if action=='mark_org' else tag_labels(command.get('label',''))
                if 'Friend' in labels:raise ValueError('Friend is automatic from your game friends list; use Friendly for a custom tag.')
                if not labels and command.get('clear_tags') is not True:raise ValueError('Choose a tag to add, or use Remove tags.')
                updates={}
                for p in targets:
                    old=self.store.data['tags'].get(p['id'],{})
                    # Bulk additions preserve each person's existing tags and alert choice.
                    merged=tag_labels(old.get('label','')+', '+', '.join(labels)) if labels else []
                    updates[p['id']]=dict(handle=p['handle'],label=', '.join(merged),labels=merged,alert=old.get('alert',False)) if merged else None
                for key,value in updates.items():
                    if value:
                        self.store.data['tags'][key]=value
                        self.store.record_action('tag',value['handle'],'Tagged: '+value['label'],player_id=key,outcome='Tagged',session_token=self.session,now=now)
                    else:
                        old_handle=(self.store.data['tags'].get(key) or {}).get('handle') or available.get(key,{}).get('handle',key)
                        self.store.data['tags'].pop(key,None)
                        self.store.record_action('tag',old_handle,'Tags cleared',player_id=key,outcome='Cleared',session_token=self.session,now=now)
                self.action_status=f'Updated tags for {len(targets)} player(s).'
        elif action=='add_watch':
            catalog=load(self.directory/'finder_market_index.json',{}) or {}
            item=catalog.get('items',{}).get(str(command.get('item_id')))
            if not item:raise ValueError('Choose an exact UEX material or item from the list.')
            self.store.watch(item,command.get('quality'),command.get('price',0),str(command.get('unit','')))
            self.action_status='Buyer watch saved. Existing matches will load quietly.'
        elif action in ('remove_watch','toggle_watch'):
            watch=next((w for w in self.store.data['watches'] if w['id']==command.get('watch_id')),None)
            if not watch:raise ValueError('Select a saved buyer watch first.')
            if action=='remove_watch':self.store.data['watches'].remove(watch)
            else:watch['enabled']=not watch['enabled'];watch['due_at']=0 if watch['enabled'] else now+MARKET_INTERVAL
        elif action=='refresh_market':
            if now-self.market_last_request<10:raise ValueError('Please wait a few seconds before refreshing again.')
            for watch in self.store.data['watches']:watch['due_at']=0
            self.market_last_request=now
        elif action=='import_org':
            symbol=str(command.get('symbol','')).strip().upper()
            tag_label=str(command.get('tag_label','Org')).strip() or 'Org'
            alert=command.get('alert',True) is True
            if not symbol or len(symbol)>20:raise ValueError('Enter a valid RSI Org Symbol / SID (e.g. TEST).')
            if 'import_org' in self.jobs:raise ValueError('An org import is already running.')
            self.action_status=f'Importing {symbol} members from RSI…'
            self.jobs['import_org']=(self.pool.submit(self.fetch_org_members,symbol,tag_label,alert),dict(symbol=symbol,tag_label=tag_label,alert=alert))
        elif action=='dismiss_notices':self.store.data['notifications']=[]
        elif action=='clear_action_log':self.store.data['action_log']=[];self.action_status='Actions log cleared.'
        else:raise ValueError('Unknown companion action')
        if identifier not in self.store.data['commands']:self.store.data['commands']=(self.store.data['commands']+[identifier])[-1000:]
        self.store.save();self.changed()
    def tick(self,context,people_visible=False,now=None):
        now=time.time() if now is None else now
        self.context=dict(context);token=context.get('session_token')
        if token!=self.session:
            self.cancel_batch.set()
            if self.invite_queue:self.invite_queue.cancel()
            self.session=token;self.roster=[];self.search=[];self.roster_at=0;self.roster_due=0;self.gate.reset();self.roster_error='';self.relationships={};self.relationships_due=0;self.invited=self.invite_history.ids(token);self.friend_requested=self.friend_history.ids(token);self.batch_results=[];self.invite_queue=None
            self.known_friends=None;self.known_party=None;self.pending_friend_out=set();self.pending_party_out=set();self.pending_friend_known=False;self.pending_party_known=False;self.awaiting_friend_response=set();self.awaiting_party_response=set()
            self.chat_channels=[];self.chat_messages=[];self.chat_at=0;self.chat_due=0;self.chat_error=''
            self.changed()
            if token and self.store.data.get('actions_session')!=token and not self.store.read_only:
                self.store.data['actions']=[];self.store.data['actions_session']=token
                try:self.store.save()
                except (OSError,ValueError):self.action_status='Could not save the Action list for this session.'
        for path in sorted(self.command_dir.glob('*.json'))[:12]:
            try:
                command=read_shared_json(path,limit=1024*1024);self.command(command,now)
            except (ValueError,TypeError,OSError,KeyError) as error:self.action_status=str(error)[:240];self.changed()
            finally:path.unlink(missing_ok=True)
        for kind,(job,scope) in list(self.jobs.items()):
            if not job.done():continue
            del self.jobs[kind]
            try:
                result=job.result()
                if kind.startswith('market:'):
                    identifier=int(kind.split(':')[1]);self.store.market_result(identifier,result[0],now,limited=result[1])
                elif kind=='import_org':
                    symbol=scope['symbol'];tag_label=scope['tag_label'];alert=scope['alert']
                    if result.get('error'):
                        self.action_status=f'Org import failed: {result["error"]}'
                    else:
                        handles=result.get('handles',[]);total_rows=result.get('total_rows',len(handles))
                        self.store.data.setdefault('org_rosters',{})[symbol]=dict(symbol=symbol,tag=tag_label,alert=alert,total=total_rows,count=len(handles),handles=handles,updated_at=now)
                        org_handles=self.store.data.setdefault('org_handles',{})
                        for h in handles:org_handles[h.casefold()]=dict(handle=h,org=symbol,tag=tag_label,alert=alert)
                        tagged_count=0
                        for person in self.roster:
                            if person['handle'].casefold() in org_handles:
                                old_tag=self.store.data['tags'].get(person['id'],{})
                                merged=tag_labels(old_tag.get('label','')+ ', ' + tag_label)
                                self.store.data['tags'][person['id']]=dict(handle=person['handle'],label=', '.join(merged),labels=merged,alert=old_tag.get('alert',alert),org=symbol)
                                tagged_count+=1
                        self.store.save()
                        self.action_status=f'Imported {len(handles)} members for {symbol} ({tag_label}).'+(f' {tagged_count} on shard tagged!' if tagged_count else '')
                elif scope.get('session_token')!=self.session:
                    if kind=='action':self.action_status='Session changed while sending. Check in-game before retrying.'
                    continue
                elif kind=='roster':
                    self.roster=result['rows'];self.roster_at=result['observed_at'];self.roster_error=''
                    active={p['id'] for p in self.roster};old=len(self.store.data['actions'])
                    self.store.data['actions']=[p for p in self.store.data['actions'] if p['id'] in active or p.get('friend_scope')]
                    if old!=len(self.store.data['actions']):self.store.save()
                    arrivals=self.gate.observe(self.roster,now)
                    notified=False
                    friends=self.friend_ids(now)
                    org_handles=self.store.data.get('org_handles',{})
                    for person in self.roster:
                        h_lower=person['handle'].casefold()
                        if h_lower in org_handles:
                            org_info=org_handles[h_lower]
                            old_tag=self.store.data['tags'].get(person['id'],{})
                            if org_info['tag'] not in tag_labels(old_tag.get('label','')):
                                merged=tag_labels(old_tag.get('label','')+ ', ' + org_info['tag'])
                                self.store.data['tags'][person['id']]=dict(handle=person['handle'],label=', '.join(merged),labels=merged,alert=old_tag.get('alert',org_info['alert']),org=org_info['org'])
                                notified=True

                        tag=self.store.data['tags'].get(person['id'])
                        labels=tag.get('labels',[]) if tag else []
                        is_friend=person['id'] in friends or 'Friend' in labels
                        is_enemy='Enemy Org' in labels
                        is_org_member='Org' in labels

                        if person['id'] in arrivals:
                            if is_enemy:
                                self.store.notice('player_join','Enemy Org joined: '+person['handle'],'Enemy Org member joined your shard · '+(tag.get('org') or 'Enemy Org'),category='enemy_org',session_token=self.session,now=now)
                                notified=True
                            elif is_friend:
                                self.store.notice('player_join','Friend joined: '+person['handle'],'Friend joined your shard',category='friend',session_token=self.session,now=now)
                                notified=True
                            elif is_org_member:
                                self.store.notice('player_join','Org member joined: '+person['handle'],'Org member joined your shard · '+(tag.get('org') or 'Org'),category='org',session_token=self.session,now=now)
                                notified=True
                            elif tag and tag.get('alert'):
                                self.store.notice('player_join',tag['label']+' joined: '+person['handle'],'Tagged player joined your shard · '+tag['label'],category='tagged',session_token=self.session,now=now)
                                notified=True
                    if notified:self.store.save()
                elif kind=='search':self.search=result['rows'];self.search_limited=result['limited'];self.action_status=f"{len(self.search)} search result(s). Select the exact handle."
                elif kind=='relationships':
                    # A failed read invalidates that highlight independently.
                    self.relationships=result
                    avail=self.available_people()
                    def handle_for(uid):
                        return (avail.get(uid) or {}).get('handle') or (uid[len('urn:sc:global:player:geid:'):] if uid.startswith('urn:sc:global:player:geid:') else uid)
                    log_changed=False
                    if result.get('friends_at'):
                        new_friends=set(result.get('friends',[]))
                        allowed={p['id'] for p in self.roster}|new_friends
                        self.store.data['actions']=[p for p in self.store.data['actions'] if p['id'] in allowed]
                        if self.known_friends is not None:
                            for uid in sorted(new_friends-self.known_friends):
                                if uid in self.awaiting_friend_response or uid in self.friend_requested or uid in self.pending_friend_out:
                                    self.store.record_action('friend_accepted',handle_for(uid),'Accepted your friend request',player_id=uid,outcome='Accepted',session_token=self.session,now=now)
                                    self.awaiting_friend_response.discard(uid);log_changed=True
                        self.known_friends=new_friends
                        if result.get('pending_friend_known'):
                            new_pf=set(result.get('pending_friend_out',[]))
                            if self.pending_friend_known:
                                for uid in sorted(self.pending_friend_out-new_pf):
                                    if uid not in new_friends and (uid in self.awaiting_friend_response or uid in self.friend_requested):
                                        self.store.record_action('friend_rejected',handle_for(uid),'Friend request declined or cancelled',player_id=uid,outcome='Declined',session_token=self.session,now=now)
                                        self.awaiting_friend_response.discard(uid);log_changed=True
                            self.pending_friend_out=new_pf;self.pending_friend_known=True
                        self.store.save()
                    if result.get('party_at'):
                        new_party=set(result.get('party',[]))
                        if self.known_party is not None:
                            for uid in sorted(new_party-self.known_party):
                                if uid in self.awaiting_party_response or uid in self.invited or uid in self.pending_party_out:
                                    self.store.record_action('party_accepted',handle_for(uid),'Accepted your party invite',player_id=uid,outcome='Accepted',session_token=self.session,now=now)
                                    self.awaiting_party_response.discard(uid);log_changed=True
                        self.known_party=new_party
                        if result.get('pending_party_known'):
                            new_pp=set(result.get('pending_party_out',[]))
                            if self.pending_party_known:
                                for uid in sorted(self.pending_party_out-new_pp):
                                    if uid not in new_party and (uid in self.awaiting_party_response or uid in self.invited):
                                        self.store.record_action('party_rejected',handle_for(uid),'Party invite declined or expired',player_id=uid,outcome='Declined',session_token=self.session,now=now)
                                        self.awaiting_party_response.discard(uid);log_changed=True
                            self.pending_party_out=new_pp;self.pending_party_known=True
                    if log_changed and not self.store.read_only:self.store.save()
                elif kind=='action':
                    if isinstance(result,dict):
                        self.action_status=result['status'];self.batch_results=result['results']
                        if self.invite_queue:self.invite_queue.finish(result['results'])
                        remembered=self.friend_requested if self.invite_queue and self.invite_queue.operation=='friend' else self.invited
                        remembered.update(row['id'] for row in self.batch_results if row['outcome'] in ('Sent','Check in game'))
                    else:self.action_status=result
                    self.relationships_due=0
                elif kind=='chat':
                    self.chat_channels=result.get('channels',[])
                    self.chat_messages=result.get('messages',[])
                    self.chat_at=result.get('observed_at',now)
                    self.chat_error=''
                elif kind=='chat_send':
                    self.action_status='Chat message sent.'
                    self.chat_due=0
            except Exception as error:
                message=str(error)[:240] if isinstance(error,ValueError) else 'Refresh unavailable. Previous data retained.'
                if kind=='roster':self.roster_error=message;self.gate.reset()
                elif kind=='relationships':self.relationships={}
                elif kind=='chat':self.chat_error=message
                elif kind.startswith('market:'):
                    for watch in self.store.data['watches']:
                        if watch['item_id']==int(kind.split(':')[1]):watch.update(error='UEX refresh unavailable; cached matches retained.',due_at=now+MARKET_INTERVAL)
                    if not self.store.read_only:self.store.save()
                else:
                    self.action_status=message
                    if kind=='action' and self.invite_queue:self.invite_queue.finish(error=message)
            self.changed()
        want_people=people_visible or any(t.get('alert') for t in self.store.data['tags'].values())
        if self.session and people_visible and 'relationships' not in self.jobs and now>=self.relationships_due:
            rel_interval=15 if (self.awaiting_friend_response or self.awaiting_party_response) else 60
            self.jobs['relationships']=(self.pool.submit(self.social,'relationships',dict(self.context)),dict(self.context));self.relationships_due=now+rel_interval
        if self.session and want_people and 'roster' not in self.jobs and now>=self.roster_due:
            known={p['id']:p['handle'] for p in self.roster}
            self.jobs['roster']=(self.pool.submit(self.social,'roster',dict(self.context),known=known),dict(self.context));self.roster_due=now+ROSTER_INTERVAL
        if self.session and people_visible and self.chat_active and 'chat' not in self.jobs and now>=self.chat_due:
            known={p['id']:p['handle'] for p in self.available_people().values() if p.get('id') and p.get('handle')}
            self.jobs['chat']=(self.pool.submit(self.social,'chat_snapshot',dict(self.context),known=known,translator=self.translator,auto_translate=self.chat_auto_translate),dict(self.context));self.chat_due=now+4
        if not self.store.read_only and not any(k.startswith('market:') for k in self.jobs):
            for watch in self.store.data['watches']:
                if watch['enabled'] and now>=watch.get('due_at',0):
                    catalog=load(self.directory/'finder_market_index.json',{}) or {}
                    item=catalog.get('items',{}).get(str(watch['item_id']))
                    if item is not None and item.get('identity')!=watch['identity']:
                        watch.update(error='UEX item identity changed; recreate this watch.',due_at=now+MARKET_INTERVAL);self.store.save();self.changed();continue
                    self.jobs['market:'+str(watch['item_id'])]=(self.pool.submit(self.market,watch['item_id']),{});break
        if now>=self.next_publish:
            self.publish(now);self.next_publish=now+(1 if self.invite_queue and self.invite_queue.snapshot()['active'] else 5)
    def publish(self,now):
        self.invited.update(self.invite_history.ids(self.session))
        self.friend_requested.update(self.friend_history.ids(self.session))
        queue=self.invite_queue.snapshot() if self.invite_queue else {}
        if queue:self.batch_results=queue['results']
        saved_changed=False
        if self.session and self.store.data.get('request_results_session')!=self.session:
            self.store.data['request_results_session']=self.session;self.store.data['request_results']={};saved_changed=True
        saved=self.store.data.setdefault('request_results',{})
        if queue and queue.get('operation') in ('friend','party'):
            operation=queue['operation']
            for row in queue.get('results',[]):
                outcome=row.get('outcome','')
                if outcome in ('Sent','Skipped','Check in game','Not sent'):
                    person=saved.setdefault(row['id'],{})
                    if person.get(operation,{}).get('queue_id')!=queue['id']:
                        person[operation]=dict(queue_id=queue['id'],outcome=outcome,detail=row.get('detail',''),at=now);saved_changed=True
                    log_kind='friend_sent' if operation=='friend' else 'party_sent'
                    if outcome=='Sent':
                        if operation=='friend':self.awaiting_friend_response.add(row['id'])
                        else:self.awaiting_party_response.add(row['id'])
                    detail_text=row.get('detail','') or ('Friend request sent' if operation=='friend' else 'Party invite sent')
                    if self.store.record_action(log_kind,row.get('handle',row['id']),detail_text,player_id=row['id'],outcome=outcome,session_token=self.session,now=now,dedupe_key=f"{queue['id']}:{operation}:{row['id']}:{outcome}"):
                        saved_changed=True
        if saved_changed and not self.store.read_only:self.store.save()
        def request_status(identifier):
            if self.store.data.get('request_results_session')!=self.session:return {}
            result=dict(saved.get(identifier,{}) if isinstance(saved.get(identifier),dict) else {})
            if queue and queue.get('operation') in ('friend','party'):
                row=next((r for r in queue.get('results',[]) if r.get('id')==identifier),None)
                if row:result[queue['operation']]=dict(outcome=row.get('outcome',''),detail=row.get('detail',''))
            return result
        tags=self.store.data['tags'];relations=self.relationships;active={p['id'] for p in self.roster};available=self.available_people()
        friends_known=bool(relations.get('friends_at')) and 0<=now-relations['friends_at']<120
        party_known=bool(relations.get('party_at')) and 0<=now-relations['party_at']<120
        friends=set(relations.get('friends',[])) if friends_known else set();eligible=active|friends;party=set(relations.get('party',[])) if party_known else set()
        def decorate(p):
            is_friend=p['id'] in friends;in_party=p['id'] in party
            relationship='You' if p.get('is_self') else 'Party + Friend' if in_party and is_friend else 'Party' if in_party else 'Friend' if is_friend else '—' if friends_known and party_known else 'Unknown'
            manual=', '.join(label for label in tag_labels(tags.get(p['id'],{}).get('label','')) if label!='Friend')
            labels=([manual] if manual else [])+(['Friend'] if is_friend else [])
            return dict(p,tag=', '.join(labels),manual_tag=manual,requests=request_status(p['id']),alert=tags.get(p['id'],{}).get('alert',False),is_org=is_org(tags.get(p['id'],{})),is_friend=is_friend,in_party=in_party,relationship=relationship,invited_before=p['id'] in self.invited,friend_requested_before=p['id'] in self.friend_requested,on_shard=p['id'] in active)
        rows=[decorate(p) for p in self.roster];search=[decorate(p) for p in self.search]
        party_group_id=str(relations.get('party_group_id','') or '') if party_known else ''
        party_leader_id=str(relations.get('party_leader_id','') or '') if party_known else ''
        self_id=str(relations.get('self_id','') or next((p['id'] for p in self.roster if p.get('is_self')),''))
        is_party_leader=bool(party_known and party and (not party_leader_id or party_leader_id==self_id))
        party_people=[]
        if party_known and party:
            for uid in party:
                base=available.get(uid) or dict(id=uid,handle=uid[len('urn:sc:global:player:geid:'):] if uid.startswith('urn:sc:global:player:geid:') else uid,is_self=(uid==self_id))
                dec=decorate(dict(base,is_self=bool(base.get('is_self') or uid==self_id)))
                dec['is_leader']=bool(uid==party_leader_id or (not party_leader_id and uid==self_id))
                party_people.append(dec)
            party_people.sort(key=lambda p:(0 if p.get('is_leader') else 1 if p.get('is_self') else 2,str(p.get('handle','')).casefold()))
        chat_messages=[]
        tags_by_handle={str(v.get('handle','')).strip().casefold():v for v in tags.values() if v.get('handle')}
        for m in self.chat_messages:
            sid=str(m.get('sender_id','') or '')
            bare_id=sid[len('urn:sc:global:player:geid:'):] if sid.startswith('urn:sc:global:player:geid:') else sid
            pref_id=sid if sid.startswith('urn:sc:global:player:geid:') else (f"urn:sc:global:player:geid:{sid}" if sid else '')
            shandle=str(m.get('sender_handle') or '').strip().casefold()
            tag_entry=tags.get(sid) or (tags.get(bare_id) if bare_id else None) or (tags.get(pref_id) if pref_id else None) or (tags_by_handle.get(shandle) if shandle else None) or {}
            is_friend=sid in friends or bare_id in friends or (pref_id in friends if pref_id else False)
            in_party=sid in party or bare_id in party or (pref_id in party if pref_id else False)
            raw_labels=tag_labels(tag_entry.get('label','')) if tag_entry else []
            stags=[lbl for lbl in raw_labels if lbl not in ('Friend','Party')]
            if is_friend and 'Friend' not in stags:stags.append('Friend')
            if in_party and not m.get('is_self') and 'Party' not in stags:stags.append('Party')
            chat_messages.append(dict(
                m,
                sender_tags=stags,
                sender_tag=', '.join(stags),
                is_friend=is_friend,
                in_party=in_party,
                is_org=is_org(tag_entry) if tag_entry else False,
            ))
        tagged={key:dict(tag,is_friend=key in friends,in_party=key in party,on_shard=key in active,relationship='Party + Friend' if key in party and key in friends else 'Party' if key in party else 'Friend' if key in friends else '—' if friends_known and party_known else 'Unknown') for key,tag in tags.items()}
        notices=self.store.data['notifications']
        watches=[{key:value for key,value in watch.items() if key not in ('seen','identity')} for watch in self.store.data['watches']]
        view=dict(owner_pid=self.owner,written_at=now,revision=self.revision,session_token=self.session,rows=rows,search=search,action_limit=MAX_BATCH_REQUESTS,
            search_query=self.search_query,search_limited=self.search_limited,roster_at=self.roster_at,roster_error=self.roster_error,
            roster_loading='roster' in self.jobs,status=self.action_status,read_only=self.store.read_only,
            watches=watches,tags=tagged,notifications=list(reversed(notices[-40:])),market_interval=MARKET_INTERVAL,
            org_rosters=self.store.data.get('org_rosters',{}),
            friends_known=friends_known,party_known=party_known,friend_people=[decorate(p) for p in sorted(available.values(),key=lambda p:p['handle'].casefold()) if p['id'] in friends],friend_names_error=relations.get('friend_names_error',''),
            party_people=party_people,party_group_id=party_group_id,party_leader_id=party_leader_id,is_party_leader=is_party_leader,
            chat_active=self.chat_active,chat_auto_translate=self.chat_auto_translate,chat_channels=self.chat_channels,chat_messages=chat_messages,
            chat_at=self.chat_at,chat_loading='chat' in self.jobs,chat_sending='chat_send' in self.jobs,chat_error=self.chat_error,
            voice_dictating=self.voice_dictating,last_dictated_text=self.last_dictated_text,voice_available=self.voice_dictation.is_available,
            social_busy='action' in self.jobs,search_busy='search' in self.jobs,batch_results=self.batch_results,invite_queue=queue,
            action_log=list(reversed(self.store.data.get('action_log',[])[-200:])),
            action_people=[decorate(dict(available.get(p['id'],p))) for p in self.store.data['actions'] if p['id'] in eligible],tag_options=sorted({label for t in tags.values() for label in tag_labels(t['label'])}|set(TAG_PRESETS),key=lambda label:(0 if label=='Org' else 1 if label=='Friend' else 2 if label=='Friendly' else 3,label.casefold())))
        publish_json(self.directory/'companion_state.json',view)
        publish_json(self.directory/'companion_alerts.json',dict(owner_pid=self.owner,written_at=now,events=notices[-20:]))
    def close(self):
        self.cancel_batch.set()
        if self.invite_queue:self.invite_queue.cancel()
        self.pool.shutdown(wait=False,cancel_futures=True)


class CompanionRunner:
    """Adapter to the existing independent Finder worker; no additional poll thread."""
    def __init__(self,directory,owner):
        self.service=CompanionService(directory,owner);self.directory=Path(directory);self.owner=owner;self.due=0;self.context={}
    def tick(self,current_patch=''):
        now=time.time()
        if now<self.due:return
        self.due=now+1
        from player_session import require_current_session
        published=load(self.directory/'session_ribbon.json',None)
        context=self.context if published is None else published
        stamp=context.get('written_at',0) if isinstance(context,dict) else 0
        if not isinstance(context,dict) or context.get('owner_pid')!=self.owner or type(stamp) not in (int,float) or not math.isfinite(stamp) or now<stamp:
            context={}
        else:
            try:require_current_session(context)
            except (OSError,ValueError,TypeError):context={}
        self.context=dict(context)
        desktop=load(self.directory/'home_status.json',{}) or {}
        visible=desktop.get('owner_pid')==self.owner and desktop.get('visible') and desktop.get('active_page')=='people'
        self.service.tick(context,visible,now)
    def close(self):self.service.close()
