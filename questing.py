"""Contract observations and verified balances; never book estimated rep as earned."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import time
from telemetry_ipc import publish_json, read_shared_json

ROOT = Path(__file__).resolve().parent
UUID = r'[0-9a-fA-F-]{36}'

def mission_event(line):
    match = re.search(r'<CLocalMissionPhaseMarker::CreateMarker>.*missionId \[(' + UUID + r')\].*contractDefinitionId\[(' + UUID + r')\]',line)
    if match:
        return dict(id=match[1].lower(), definition_id=match[2].lower())
    match = re.search(r'<SHUDEvent_OnNotification> Added notification "Contract Accepted:\s*(.*?)".*MissionId: \[(' + UUID + r')\]', line)
    if match:
        title = re.sub(r'<[^>]*>', '', match[1]).rstrip(': ').strip()
        return dict(id=match[2].lower(), title=title, status='Accepted')
    match = re.search(r'<EndMission>.*MissionId\[(' + UUID + r')\].*CompletionType\[([^]]+)\]', line)
    if match:
        return dict(id=match[1].lower(), status=match[2])
    match = re.search(r'<SHUDEvent_OnNotification> Added notification "New Objective:\s*(.*?)".*MissionId: \[(' + UUID + r')\]',line)
    if match:
        return dict(id=match[2].lower(), objective=re.sub(r'<[^>]*>','',match[1]).rstrip(': ').strip())
    return None

def own_missions(client):
    q = client.message('sc.external.services.mission_service.v1.QueryActiveMissionsRequest')
    q.queries.add().urn = client.subject
    ids = client.read('mission_service', 'MissionService', 'QueryActiveMissions', q)
    if len(ids.mission_ids) > 100:
        raise ValueError('Mission list exceeds bounded request limit')
    q = client.message('sc.external.services.mission_service.v1.QueryMissionsRequest')
    for row in ids.mission_ids: q.queries.add().mission_id = row.mission_id
    if not q.queries: return []
    response = client.read('mission_service', 'MissionService', 'QueryMissions', q)
    allowed = {row.mission_id for row in ids.mission_ids}
    rows = []
    for m in response.missions:
        if m.mission_id not in allowed or not any(p.player_urn == client.subject for p in m.participants):
            raise ValueError('Mission did not verify own participation')
        rows.append(dict(id=m.mission_id.lower(), definition_id=m.mission_template.contract_definition_id,
                         participants=len(m.participants), state=int(m.mission_state)))
    return rows

def own_reputation(client):
    q = client.message('sc.external.services.reputation.v1.QueryReputationsRequest')
    q.query.pagination.first = 100
    prop = q.query.filter.property_filter
    prop.property = 'subject'; prop.operator = 1; prop.value = client.subject
    records = []; cursors = set()
    for _ in range(10):
        response = client.read('reputation', 'ReputationService', 'QueryReputations', q)
        for v in response.results:
            if v.reputation.subject != client.subject: raise ValueError('Reputation subject mismatch')
            r = v.reputation
            records.append(dict(entity=r.entity, scope=r.scope, score=r.score, updated_at=r.updated_at,
                                last_drifted_at=r.last_drifted_at, standing_id=r.standings_id, version=v.version,
                                standing=dict(name=v.standing.name, minimum=getattr(v.standing, 'min'), gated=v.standing.gated)))
        if not response.page_info.has_next_page: break
        cursor = response.page_info.end_cursor
        if not cursor or cursor in cursors: raise ValueError('Invalid reputation pagination')
        cursors.add(cursor); q.query.pagination.after = cursor
    else: raise ValueError('Reputation pagination limit')
    if not records: raise ValueError('No reputation records returned')
    return dict(schema=1, source='authenticated_reputation_service', read_at=time.time(),
                character_key=hashlib.sha256(client.subject.encode()).hexdigest(),
                own_character_verified=True, complete=True, records=records)

class Questing:
    def __init__(self, directory, log):
        self.directory = Path(directory); self.log = Path(log)
        self.offset = 0; self.stamp = None; self.pending = b''
        self.journal = {}; self.selected = ''; self.service = []; self.read_at = 0
        self.error = ''; self.next_poll = 0; self.future = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='questing-read')
        self.catalog = {}; self.catalog_by_title = {}; self.balance_names = {}; self.scopes = {}

    def load_catalog(self):
        from game_records import GameRecords, walk_nodes
        from installation import reference_paths
        paths=reference_paths()
        audit=json.loads(paths['audit'].read_text(encoding='utf-8'))
        manifest=json.loads((paths['game']/'build_manifest.id').read_text())
        if manifest['Data']['BuildId'] != audit['build']['BuildId']:
            raise ValueError('Game build changed; reward catalog requires extraction')
        store = GameRecords(paths['records'],paths['localization'])
        catalog={};catalog_by_title={};balance_names={}
        scopes = {s['name']:s for s in audit['scopes']}
        for p in (store.root/'libs/foundry/records/factions/factionreputation').rglob('*.json'):
            v = store.read(p)['_RecordValue_']
            if v.get('GEID'): balance_names[str(v['GEID'])] = store.text(v.get('displayName'))
        for m in audit['missions']:
            v = store.read(store.root/m['source'])['_RecordValue_']
            # Keep outcome identity explicit until its enum mapping is validated.
            candidates = [o for o in m['outcomes'] if any(isinstance(r['configured_amount'], (int,float)) and r['configured_amount'] > 0 for r in o['rewards'])]
            rewards = candidates[0]['rewards'] if len(candidates) == 1 else []
            row = dict(title=m['title'], payout=(v.get('missionReward') or {}).get('reward'), rewards=rewards)
            catalog[m['id'].lower()] = row
            catalog_by_title.setdefault(m['title'].strip().casefold(), []).append(row)
        # Current career missions are embedded contracts, not MissionBrokerEntry
        # records. Their IDs are the contractDefinitionId emitted by Game.log.
        career_root=paths['career']
        for path in (career_root/'libs/foundry/records/contracts/contractgenerator').rglob('*.json'):
            record=json.loads(path.read_text(encoding='utf-8'))
            for contract in walk_nodes(record):
                if contract.get('_Type_')!='CareerContract' or not contract.get('id'):continue
                strings=(contract.get('paramOverrides') or {}).get('stringParamOverrides',[])
                key=next((v.get('value') for v in strings if v.get('param')=='Title'),None)
                rewards=[];extras=[]
                for result in (contract.get('contractResults') or {}).get('contractResults',[]):
                    flags=result.get('missionResults',[])
                    # The preserved native contract generator uses completion
                    # slot 0. Base definitions remain estimates, never balances.
                    if not flags or flags[0] is not True:continue
                    if result.get('_Type_')=='ContractResult_LegacyReputation':
                        params=result.get('contractResultReputationAmounts') or {}
                        try:
                            faction=store.value(params['factionReputation'])
                            scope=store.value(params['reputationScope'])
                            reward=store.value(params['reward'])
                            amount=reward.get('reputationAmount')
                            if isinstance(amount,(int,float)):
                                rewards.append(dict(faction=store.text(faction.get('displayName')),scope=scope.get('scopeName',''),configured_amount=amount))
                        except (KeyError,ValueError,OSError):pass
                    if result.get('_Type_')=='BlueprintRewards':extras.append('Blueprint pool reward')
                    if result.get('_Type_')=='ContractResult_Item':
                        extras.append(str(result.get('amount','?'))+' item reward'+(' · owner only' if result.get('awardOnlyToMissionOwner') else ''))
                row=dict(title=store.text(key) or contract.get('debugName',''),payout=None,rewards=rewards,extras=extras)
                catalog[contract['id'].lower()]=row
                if row['title']:catalog_by_title.setdefault(row['title'].strip().casefold(),[]).append(row)

        self.catalog=catalog;self.catalog_by_title=catalog_by_title
        self.balance_names=balance_names;self.scopes=scopes

    def poll_log(self):
        try:
            st = self.log.stat()
            identity = (st.st_dev, st.st_ino)
            if identity != self.stamp or st.st_size < self.offset:
                self.offset = 0; self.pending = b''; self.journal = {}; self.selected = ''; self.stamp = identity
            with self.log.open('rb') as f:
                f.seek(self.offset); raw = f.read(2*1024*1024); self.offset = f.tell()
            parts = (self.pending + raw).split(b'\n'); self.pending = parts.pop()
            if len(self.pending)>65536: self.pending=b''
            changed = False
            for raw in parts:
                event = mission_event(raw.decode('utf-8',errors='replace'))
                if event:
                    old = self.journal.get(event['id'], {})
                    merged=dict(old, **event)
                    if old != merged:
                        stamp=re.match(r'<(\d{4}-[^>]+)>',raw.decode('utf-8',errors='replace'))
                        if stamp:merged['event_timestamp']=stamp[1]
                        self.journal[event['id']] = merged
                        if event.get('status')=='Accepted': self.selected=event['id']
                        changed=True
            if changed:
                self.next_poll = min(self.next_poll, time.time()+2)
                publish_json(self.directory/'questing_journal.json', dict(schema=1, missions=list(self.journal.values())))
        except OSError: pass

    def query(self):
        from game_account import OwnAccount
        if not self.catalog:self.load_catalog()
        client=OwnAccount()
        try:
            mission_error=''
            try: missions = own_missions(client)
            except Exception as exc:
                missions=[];mission_error='Mission read unavailable ('+type(exc).__name__+')'
            return missions, own_reputation(client), mission_error
        finally: client.close()

    def tick(self, enabled, game_running=True, now=None):
        now=time.time() if now is None else now
        if game_running: self.poll_log()
        if self.future and self.future.done():
            try:
                self.service, snapshot, mission_error = self.future.result()
                publish_json(self.directory/'reputation_snapshot.json', snapshot)
                self.read_at = snapshot['read_at']; self.error=mission_error
                from installation import RELEASE
                if RELEASE:
                    try:
                        from tools.sync_reputation_names import sync
                        result=sync(True)
                        publish_json(self.directory/'reputation_labels_status.json',dict(at=now,ok=True,**result))
                    except Exception as exc:
                        publish_json(self.directory/'reputation_labels_status.json',dict(at=now,ok=False,
                            error='Labels unavailable ('+type(exc).__name__+'); check SynthStrings setup.'))
            except Exception as exc:
                # Never publish RPC details, credentials or request metadata.
                self.error = 'Account read unavailable ('+type(exc).__name__+')'
            self.future = None
        if enabled and game_running and not self.future and now >= self.next_poll:
            self.future=self.pool.submit(self.query);self.next_poll=now+30
        active = [dict(m, **self.journal.get(m['id'],{})) for m in self.service
                  if m['state'] in (1,2,3) and self.journal.get(m['id'],{}).get('status','Accepted')=='Accepted'] if 0<=now-self.read_at<65 else []
        known={m['id'] for m in active}
        active.extend(m for m in self.journal.values() if m.get('status')=='Accepted' and m['id'] not in known)
        if not game_running: active=[]
        selected = next((m for m in active if m['id']==self.selected), active[-1] if active else {})
        self.selected=selected.get('id','')
        definition = self.catalog.get(selected.get('definition_id','').lower(),{})
        title = selected.get('title') or definition.get('title') or ('Contract '+selected['id'][:8] if selected else 'No active contract observed')
        plain = re.sub(r'\s*\[\d+ Rep\].*$', '', title).strip()
        if not definition:
            matches=self.catalog_by_title.get(plain.casefold(),[])
            if len(matches)==1: definition=matches[0]
        lines=[]
        if not selected:
            lines=['Accept a contract in game to begin.', 'Account checks run every 30s in Missions.']
            ended=[m for m in self.journal.values() if m.get('status') not in (None,'Accepted')]
            if ended: lines.append('Last contract: '+ended[-1]['status'])
        else:
            if selected.get('objective'):lines.append('Objective: '+selected['objective'])
            amount=definition.get('payout')
            lines.append(f'Configured payout: {amount:,} aUEC' if isinstance(amount,(int,float)) else 'Payout: not exposed by current source')
            participants=selected.get('participants')
            lines.append(f'Mission participants: {participants}' if participants else 'Mission participants: unknown')
            if participants and participants>1 and isinstance(amount,(int,float)):
                lines.append(f'Equal-split scenario: {amount/participants:,.0f} aUEC each')
            for reward in definition.get('rewards',[])[:3]:
                if isinstance(reward['configured_amount'], (int,float)) and reward['configured_amount']>0:
                    label=self.scopes.get(reward['scope'],{}).get('display_name') or reward['scope']
                    lines.append(f"{reward['faction']} / {label}: +{reward['configured_amount']:,} base rep")
                    if participants and participants>1: lines.append(f"Equal-split scenario: +{reward['configured_amount']/participants:,.1f} rep each")
            if not definition.get('rewards'): lines.append('Reputation reward: not yet resolved')
            for extra in dict.fromkeys(definition.get('extras',[])):lines.append(extra)
        try: snapshot=read_shared_json(self.directory/'reputation_snapshot.json',limit=1024*1024) or {}
        except (OSError,ValueError): snapshot={}
        verified=snapshot.get('complete') and snapshot.get('own_character_verified') and 0<=now-self.read_at<65 and snapshot.get('read_at')==self.read_at
        balances=[]
        if verified:
            for r in snapshot.get('records',[]):
                name=self.balance_names.get(r['entity'].rsplit(':',1)[-1],'')
                if name and (name.casefold() in plain.casefold() or any(v.get('faction')==name and v.get('scope')==r['scope'] for v in definition.get('rewards',[]))):
                    scope=self.scopes.get(r['scope'],{})
                    above=sorted(s['minimum'] for s in scope.get('standings',[]) if s['minimum']>r['score'])
                    label=scope.get('display_name') or r['scope']
                    balances.append(f"{name} / {label}: {r['score']:,}"+(f" / {above[0]:,}" if above else '')+' verified')
        # Current points are the most useful number; don't truncate them behind
        # additional item rewards or split scenarios.
        lines=balances[:2]+lines
        return dict(title=title, lines=lines[:8], count=len(active), source='Selected contract · not game tracking',
                    footer=self.error or (f'Balances verified {max(0,int(now-self.read_at))}s ago' if verified else 'Balance refresh pending'),
                    warning='Configured rewards / split scenarios are estimates.', active_ids=[m['id'] for m in active])

    def next_contract(self):
        ids=self.tick(False).get('active_ids',[])
        if ids: self.selected=ids[(ids.index(self.selected)+1)%len(ids)] if self.selected in ids else ids[0]

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
