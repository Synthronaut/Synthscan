"""Buyer watches, player tags and bounded background social operations."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
from threading import Event
import time
import uuid

from telemetry_ipc import read_shared_json,publish_json

MARKET_INTERVAL=1800
ROSTER_INTERVAL=30
TAG_PRESETS=('Aggressive','Trader','Friendly','Org','Org Affiliate','Crew','Buyer','Avoid')


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
        self.data=dict(schema=1,watches=[],tags={},notifications=[],commands=[])
        try:
            value=load(self.path,None)
            if value is not None:
                if value.get('schema')!=1 or not isinstance(value.get('watches'),list) or not isinstance(value.get('tags'),dict) or not isinstance(value.get('notifications'),list) or not isinstance(value.get('commands'),list):raise ValueError('Invalid saved companion data')
                for watch in value['watches']:
                    if not isinstance(watch,dict) or not all(k in watch for k in ('id','item_id','name','identity','quality','minimum_price','unit','enabled','initialized','seen','matches')) or not isinstance(watch['seen'],list):raise ValueError('Invalid buyer watch')
                for key,tag in value['tags'].items():
                    if not isinstance(tag,dict) or not isinstance(tag.get('handle'),str) or not isinstance(tag.get('label'),str):raise ValueError('Invalid saved player tag')
                self.data=value
        except (OSError,ValueError,TypeError):self.read_only=True
    def save(self):
        if self.read_only or not publish_json(self.path,self.data):raise ValueError('Saved data is unavailable; original records were preserved.')
    def notice(self,kind,title,detail,url='',session_token=None,now=None):
        now=time.time() if now is None else now
        event=dict(id=uuid.uuid4().hex,kind=kind,title=title,detail=detail,url=url,at=now,session_token=session_token)
        self.data['notifications']=(self.data['notifications']+[event])[-100:]
        return event
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
        self.search_query='';self.search_limited=False;self.gate=PresenceChanges();self.jobs={};self.next_publish=0
        self.relationships={};self.relationships_due=0
        self.batch_results=[];self.invited=set()
        self.cancel_batch=Event()
        self.started_at=time.time();self.revision=0;self.notice_revision=0;self.market_last_request=0
        self.command_dir=self.directory/'companion_commands';self.command_dir.mkdir(exist_ok=True)
    def changed(self):self.revision+=1;self.next_publish=0
    def command(self,command,now):
        if command.get('owner_pid')!=self.owner or not isinstance(command.get('at'),(int,float)) or not 0<=now-command['at']<30:return
        identifier=command.get('id','')
        if not isinstance(identifier,str) or not identifier or len(identifier)>100 or identifier in self.store.data['commands']:return
        if self.store.read_only:raise ValueError('Saved companion records are unavailable.')
        action=command.get('action')
        if action in ('friend','party','party_many','search','refresh_people','tag','tag_many','mark_org'):
            if not self.session or command.get('session_token')!=self.session:raise ValueError('Session changed. Refresh People before continuing.')
        if action=='refresh_people':self.roster_due=0;self.relationships_due=0
        elif action=='search':
            if 'search' in self.jobs:raise ValueError('A player search is already running.')
            query=str(command.get('query','')).strip()
            self.search_query=query;self.search=[];self.action_status='Searching handles…'
            self.jobs['search']=(self.pool.submit(self.social,'search',dict(self.context),query=query),dict(self.context))
        elif action in ('tag','friend','party'):
            saved=[dict(id=key,handle=value['handle']) for key,value in self.store.data['tags'].items()]
            target=next((p for p in self.roster+self.search+saved if p['id']==command.get('player_id')),None)
            if not target or target.get('is_self'):raise ValueError('Select another verified player first.')
            if action=='tag':
                labels=tag_labels(command.get('label',''))
                if labels:self.store.data['tags'][target['id']]=dict(handle=target['handle'],label=', '.join(labels),labels=labels,alert=command.get('alert') is True)
                else:self.store.data['tags'].pop(target['id'],None)
            else:
                if command.get('confirmed') is not True:raise ValueError('Confirm the selected recipient first.')
                if 'action' in self.jobs:raise ValueError('A social action is awaiting confirmation from the game service.')
                # Persist before sending: never automatically retry an uncertain outgoing action.
                self.store.data['commands']=(self.store.data['commands']+[identifier])[-1000:];self.store.save()
                self.jobs['action']=(self.pool.submit(self.social,action,dict(self.context),person=dict(target),confirmed=True),dict(self.context))
                self.action_status='Sending '+('friend request' if action=='friend' else 'party invitation')+' to '+target['handle']+'…'
        elif action in ('tag_many','mark_org','party_many'):
            ids=command.get('player_ids')
            if not isinstance(ids,list) or not ids or len(ids)>4096 or any(not isinstance(v,str) for v in ids):raise ValueError('Select one or more verified players.')
            ids=list(dict.fromkeys(ids))
            saved=[dict(id=key,handle=value['handle']) for key,value in self.store.data['tags'].items()]
            available={p['id']:p for p in reversed(self.roster+self.search+saved)}
            if any(key not in available or available[key].get('is_self') for key in ids):raise ValueError('Selection changed. Select other verified players again.')
            targets=[available[key] for key in ids]
            if action=='party_many':
                if command.get('confirmed') is not True:raise ValueError('Confirm the selected recipients first.')
                if 'action' in self.jobs:raise ValueError('A social action is already running.')
                if command.get('org_only'):
                    current={p['id'] for p in self.roster}
                    if any(key not in current or not is_org(self.store.data['tags'].get(key,{})) for key in ids):raise ValueError('Org membership or shard list changed. Review the recipients again.')
                self.store.data['commands']=(self.store.data['commands']+[identifier])[-1000:];self.store.save()
                self.batch_results=[]
                self.cancel_batch=Event()
                self.jobs['action']=(self.pool.submit(self.social,'party_many',dict(self.context),people=[dict(p) for p in targets],confirmed=True,previous=list(self.invited),cancel=self.cancel_batch),dict(self.context))
                self.action_status=f'Inviting {len(targets)} player(s), one at a time…'
            else:
                labels=['Org'] if action=='mark_org' else tag_labels(command.get('label',''))
                if not labels and command.get('clear_tags') is not True:raise ValueError('Choose a tag to add, or use Remove tags.')
                updates={}
                for p in targets:
                    old=self.store.data['tags'].get(p['id'],{})
                    # Bulk additions preserve each person's existing tags and alert choice.
                    merged=tag_labels(old.get('label','')+', '+', '.join(labels)) if labels else []
                    updates[p['id']]=dict(handle=p['handle'],label=', '.join(merged),labels=merged,alert=old.get('alert',False)) if merged else None
                for key,value in updates.items():
                    if value:self.store.data['tags'][key]=value
                    else:self.store.data['tags'].pop(key,None)
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
        elif action=='dismiss_notices':self.store.data['notifications']=[]
        else:raise ValueError('Unknown companion action')
        if identifier not in self.store.data['commands']:self.store.data['commands']=(self.store.data['commands']+[identifier])[-1000:]
        self.store.save();self.changed()
    def tick(self,context,people_visible=False,now=None):
        now=time.time() if now is None else now
        self.context=dict(context);token=context.get('session_token')
        if token!=self.session:
            self.cancel_batch.set()
            self.session=token;self.roster=[];self.search=[];self.roster_at=0;self.roster_due=0;self.gate.reset();self.roster_error='';self.relationships={};self.relationships_due=0;self.invited=set();self.batch_results=[];self.changed()
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
                elif scope.get('session_token')!=self.session:
                    if kind=='action':self.action_status='Session changed while sending. Check in-game before retrying.'
                    continue
                elif kind=='roster':
                    self.roster=result['rows'];self.roster_at=result['observed_at'];self.roster_error=''
                    arrivals=self.gate.observe(self.roster,now)
                    notified=False
                    for person in self.roster:
                        tag=self.store.data['tags'].get(person['id'])
                        if person['id'] in arrivals and tag and tag.get('alert'):
                            self.store.notice('player_join','TAGGED PLAYER ON SHARD',person['handle']+' · '+tag['label']+' · Appeared in the latest list update',session_token=self.session,now=now)
                            notified=True
                    if notified:self.store.save()
                elif kind=='search':self.search=result['rows'];self.search_limited=result['limited'];self.action_status=f"{len(self.search)} search result(s). Select the exact handle."
                elif kind=='relationships':
                    # A failed read invalidates that highlight independently.
                    self.relationships=result
                elif kind=='action':
                    if isinstance(result,dict):
                        self.action_status=result['status'];self.batch_results=result['results']
                        self.invited.update(row['id'] for row in self.batch_results if row['outcome'] in ('Sent','Check in game'))
                    else:self.action_status=result
                    self.relationships_due=0
            except Exception as error:
                message=str(error)[:240] if isinstance(error,ValueError) else 'Refresh unavailable. Previous data retained.'
                if kind=='roster':self.roster_error=message;self.gate.reset()
                elif kind=='relationships':self.relationships={}
                elif kind.startswith('market:'):
                    for watch in self.store.data['watches']:
                        if watch['item_id']==int(kind.split(':')[1]):watch.update(error='UEX refresh unavailable; cached matches retained.',due_at=now+MARKET_INTERVAL)
                    if not self.store.read_only:self.store.save()
                else:self.action_status=message
            self.changed()
        want_people=people_visible or any(t.get('alert') for t in self.store.data['tags'].values())
        if self.session and people_visible and 'relationships' not in self.jobs and now>=self.relationships_due:
            self.jobs['relationships']=(self.pool.submit(self.social,'relationships',dict(self.context)),dict(self.context));self.relationships_due=now+60
        if self.session and want_people and 'roster' not in self.jobs and now>=self.roster_due:
            known={p['id']:p['handle'] for p in self.roster}
            self.jobs['roster']=(self.pool.submit(self.social,'roster',dict(self.context),known=known),dict(self.context));self.roster_due=now+ROSTER_INTERVAL
        if not self.store.read_only and not any(k.startswith('market:') for k in self.jobs):
            for watch in self.store.data['watches']:
                if watch['enabled'] and now>=watch.get('due_at',0):
                    catalog=load(self.directory/'finder_market_index.json',{}) or {}
                    item=catalog.get('items',{}).get(str(watch['item_id']))
                    if item is not None and item.get('identity')!=watch['identity']:
                        watch.update(error='UEX item identity changed; recreate this watch.',due_at=now+MARKET_INTERVAL);self.store.save();self.changed();continue
                    self.jobs['market:'+str(watch['item_id'])]=(self.pool.submit(self.market,watch['item_id']),{});break
        if now>=self.next_publish:
            self.publish(now);self.next_publish=now+5
    def publish(self,now):
        tags=self.store.data['tags'];relations=self.relationships
        friends_known=bool(relations.get('friends_at')) and 0<=now-relations['friends_at']<120
        party_known=bool(relations.get('party_at')) and 0<=now-relations['party_at']<120
        friends=set(relations.get('friends',[])) if friends_known else set();party=set(relations.get('party',[])) if party_known else set()
        def decorate(p):
            is_friend=p['id'] in friends;in_party=p['id'] in party
            relationship='You' if p.get('is_self') else 'Party + Friend' if in_party and is_friend else 'Party' if in_party else 'Friend' if is_friend else '—' if friends_known and party_known else 'Unknown'
            return dict(p,tag=tags.get(p['id'],{}).get('label',''),alert=tags.get(p['id'],{}).get('alert',False),is_org=is_org(tags.get(p['id'],{})),is_friend=is_friend,in_party=in_party,relationship=relationship)
        rows=[decorate(p) for p in self.roster];search=[decorate(p) for p in self.search]
        tagged={key:dict(tag,is_friend=key in friends,in_party=key in party,relationship='Party + Friend' if key in party and key in friends else 'Party' if key in party else 'Friend' if key in friends else '—' if friends_known and party_known else 'Unknown') for key,tag in tags.items()}
        notices=self.store.data['notifications']
        watches=[{key:value for key,value in watch.items() if key not in ('seen','identity')} for watch in self.store.data['watches']]
        view=dict(owner_pid=self.owner,written_at=now,revision=self.revision,session_token=self.session,rows=rows,search=search,
            search_query=self.search_query,search_limited=self.search_limited,roster_at=self.roster_at,roster_error=self.roster_error,
            roster_loading='roster' in self.jobs,status=self.action_status,read_only=self.store.read_only,
            watches=watches,tags=tagged,notifications=list(reversed(notices[-40:])),market_interval=MARKET_INTERVAL,
            friends_known=friends_known,party_known=party_known,
            social_busy='action' in self.jobs,search_busy='search' in self.jobs,batch_results=self.batch_results)
        publish_json(self.directory/'companion_state.json',view)
        publish_json(self.directory/'companion_alerts.json',dict(owner_pid=self.owner,written_at=now,events=notices[-20:]))
    def close(self):self.cancel_batch.set();self.pool.shutdown(wait=False,cancel_futures=True)


class CompanionRunner:
    """Adapter to the existing independent Finder worker; no additional poll thread."""
    def __init__(self,directory,owner):
        self.service=CompanionService(directory,owner);self.directory=Path(directory);self.owner=owner;self.due=0
    def tick(self,current_patch=''):
        now=time.time()
        if now<self.due:return
        self.due=now+1
        context=load(self.directory/'session_ribbon.json',{}) or {}
        if context.get('owner_pid')!=self.owner or not 0<=now-context.get('written_at',0)<5:context={}
        desktop=load(self.directory/'home_status.json',{}) or {}
        visible=desktop.get('owner_pid')==self.owner and desktop.get('visible') and desktop.get('active_page')=='people'
        self.service.tick(context,visible,now)
    def close(self):self.service.close()
