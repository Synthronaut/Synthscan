"""Own-session social reads and explicitly selected, one-shot social actions."""
import re
import json
import os
import uuid
from threading import RLock
import time
from pathlib import Path

_DIAGNOSTIC_LOCK=RLock()

def save_social_error(directory,error,**context):
    """Local bounded evidence; never serialize RPC requests, headers or credentials."""
    try:code=error.code().name
    except Exception:code='LOCAL_ERROR'
    try:detail=error.details()
    except Exception:detail=str(error)
    detail=str(detail or '')
    detail=re.sub(r'(?i)bearer\s+[^\s,;]+','Bearer [redacted]',detail)
    detail=re.sub(r'[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]+','[redacted token]',detail)
    detail=re.sub(r'(?i)(authorization|auth_token|access_token|refresh_token|password|secret)([\s\"\':=]+)[^\s,;\"\']+',r'\1=[redacted]',detail)
    entry=dict(schema=1,id=uuid.uuid4().hex[:12],at=time.time(),code=code,exception_type=type(error).__name__,detail=detail[:1200],
               **{k:v for k,v in context.items() if k in ('route','elapsed_ms','queue_id','operation','recipient_id','recipient_handle','phase')})
    saved=False
    if directory is not None:
        try:
            folder=Path(directory);folder.mkdir(parents=True,exist_ok=True);path=folder/'social_errors.jsonl'
            with _DIAGNOSTIC_LOCK:
                if path.exists() and path.stat().st_size>=2*1024*1024:os.replace(path,folder/'social_errors.previous.jsonl')
                with path.open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps(entry,ensure_ascii=True)+'\n');stream.flush();os.fsync(stream.fileno())
            saved=True
        except (OSError,ValueError):pass
    return dict(entry,saved=saved)

PLAYER_PREFIX='urn:sc:global:player:geid:'
READS={('social','SocialService','ListGroups'),('social','SocialService','ListPendingInvitations'),
       ('identity','IdentityService','GetPlayersNames'),
       ('contacts','ContactsService','SearchAccount'),('contacts','ContactsService','ListContacts'),
       ('contacts','ContactsService','ListPendingFriendRequests'),
       ('chat','ChatService','ListMessages')}
WRITES={('contacts','ContactsService','SendFriendRequest'),('social','SocialService','InviteToParty'),
        ('social','SocialService','KickGroupMember'),('social','SocialService','TransferGroupLeadership'),
        ('social','SocialService','LeaveGroup'),('chat','ChatService','SendMessage')}

class PlayerLeftShard(ValueError):pass


def public_error(error):
    try:code=error.code().name
    except Exception:code='UNAVAILABLE'
    return {'UNAUTHENTICATED':'Sign in to Star Citizen again to refresh social access.',
            'PERMISSION_DENIED':'The game service did not permit this action.',
            'UNIMPLEMENTED':'This action is unavailable at the current game service.',
            'ALREADY_EXISTS':'A friendship or pending request already exists.',
            'RESOURCE_EXHAUSTED':'The game service is busy or a social limit was reached.',
            'DEADLINE_EXCEEDED':'No confirmation received. Check in-game before trying again.',
            'NOT_FOUND':'This player could not be found by the social service.',
            'INVALID_ARGUMENT':'The game service rejected this recipient or party state.'}.get(code,'The social request failed ('+code+'). No confirmation was received.' )


class PlayerClient:
    def __init__(self):
        from game_account import OwnAccount
        from installation import reference_paths
        from google.protobuf.descriptor_pb2 import FileDescriptorSet
        self.account=OwnAccount()
        from installation import PROFILE
        self.diagnostic_directory=PROFILE
        self.descriptors={d.name:d for d in FileDescriptorSet.FromString(reference_paths()['schemas'].read_bytes()).file}

    def close(self):self.account.close()

    def message(self,domain,name):
        from google.protobuf import message_factory
        prefix='sc.external.services.'+domain+'.v1.'
        def add(name):
            try:self.account.pool.FindFileByName(name);return
            except KeyError:pass
            for dependency in self.descriptors[name].dependency:add(dependency)
            self.account.pool.AddSerializedFile(self.descriptors[name].SerializeToString())
        target=next(k for k,v in self.descriptors.items() if v.package==prefix.rstrip('.') and any(m.name==name for m in v.message_type))
        add(target)
        return message_factory.GetMessageClass(self.account.pool.FindMessageTypeByName(prefix+name))

    def call(self,domain,service,method,request,confirmed=False):
        route=(domain,service,method)
        if route not in READS and not (route in WRITES and confirmed):raise ValueError('Social action requires explicit confirmation')
        from account_permission import require_account_access
        require_account_access()
        response=self.message(domain,method+'Response')
        started=time.monotonic()
        try:
            return self.account.channel.unary_unary('/sc.external.services.'+domain+'.v1.'+service+'/'+method,
            request_serializer=lambda v:v.SerializeToString(),response_deserializer=response.FromString)(request,timeout=8,metadata=self.account.metadata)
        except Exception as error:
            context=dict(getattr(self,'_diagnostic_context',{}),route='/sc.external.services.'+domain+'.v1.'+service+'/'+method,elapsed_ms=round((time.monotonic()-started)*1000))
            evidence=save_social_error(getattr(self,'diagnostic_directory',None),error,**context)
            try:error.social_diagnostic=evidence
            except Exception:pass
            raise


    def scope(self,context):
        from player_session import require_current_session
        require_current_session(context)

    def search(self,query,context):
        query=query.strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{2,64}',query):raise ValueError('Enter at least two handle characters (letters, numbers, _ or -).')
        self.scope(context)
        request=self.message('contacts','SearchAccountRequest')();request.search=query;request.pagination.first=25
        response=self.call('contacts','ContactsService','SearchAccount',request)
        rows=[]
        for account in response.accounts:
            if not account.nickname or not account.player_id or not account.account_id:continue
            rows.append(dict(id=PLAYER_PREFIX+str(account.player_id),handle=account.nickname,display_name=account.display_name,
                             account_id=account.account_id,player_id=str(account.player_id),is_self=PLAYER_PREFIX+str(account.player_id)==self.account.subject))
        self.scope(context)
        return dict(rows=rows,limited=response.page_info.has_next_page,observed_at=time.time())

    def server_member_ids(self,context):
        self.scope(context);groups=[];cursor=''
        for _ in range(4):
            request=self.message('social','ListGroupsRequest')();request.filters.types.append(2);request.pagination.first=5
            if cursor:request.pagination.after=cursor
            response=self.call('social','SocialService','ListGroups',request)
            pattern=r'(?<![a-z0-9_])'+re.escape(context['full_shard_id'].casefold())+r'(?![a-z0-9_])'
            groups.extend(g for g in response.groups if g.type==2 and re.search(pattern,g.name.casefold())
                          and any(m.urn==self.account.subject for m in g.members))
            if not response.page_info.has_next_page:break
            next_cursor=response.page_info.end_cursor
            if not next_cursor or next_cursor==cursor:raise ValueError('Incomplete shard group response.')
            cursor=next_cursor
        else:raise ValueError('Shard group result limit reached.')
        if len(groups)!=1:raise ValueError('Current shard member group is not available yet.')
        urns={m.urn for m in groups[0].members}
        if not 0<len(urns)<=4096 or any(not u.startswith(PLAYER_PREFIX) or not u[len(PLAYER_PREFIX):].isdigit() for u in urns):
            raise ValueError('Unrecognised shard member identities.')
        self.scope(context);return urns

    def roster(self,context,known=None):
        urns=self.server_member_ids(context);known=known or {}
        names={u:known[u] for u in urns if known.get(u)}
        missing=sorted(int(u[len(PLAYER_PREFIX):]) for u in urns if u not in names)
        for start in range(0,len(missing),256):
            batch=set(missing[start:start+256]);request=self.message('identity','GetPlayersNamesRequest')();request.player_geids.extend(sorted(batch))
            result=self.call('identity','IdentityService','GetPlayersNames',request)
            if any(n.geid not in batch for n in result.names):raise ValueError('Unexpected player-name response.')
            for row in result.names:
                if row.name.strip():names[PLAYER_PREFIX+str(row.geid)]=row.name.strip()
        self.scope(context)
        if len(names)!=len(urns):raise ValueError('Some player names are unavailable; previous list retained.')
        return dict(rows=[dict(id=u,handle=names[u],is_self=u==self.account.subject) for u in sorted(urns,key=lambda u:names[u].casefold())],
                    observed_at=time.time(),full_shard_id=context['full_shard_id'],session_token=context['session_token'],
                    coverage='Current shard server-group members; complete online population is unverified')

    def send(self,action,person,context,confirmed=False,allow_friend=False):
        if action not in ('friend','party') or confirmed is not True:raise ValueError('Choose and confirm a social action.')
        self.scope(context)
        found=self.search(person['handle'],context)
        exact=[r for r in found['rows'] if r['id']==person['id'] and r['handle'].casefold()==person['handle'].casefold()]
        if len(exact)!=1 or exact[0]['id']==self.account.subject:raise ValueError('Exact recipient could not be verified. Refresh and select again.')
        target=exact[0]
        self.scope(context)
        if target['id'] not in self.server_member_ids(context):
            friends=self.relationships(context) if allow_friend and action=='party' else {}
            if not friends.get('friends_at') or target['id'] not in friends.get('friends',[]):raise PlayerLeftShard('Player is no longer on your shard or verified friends list.')
        if action=='friend':
            request=self.message('contacts','SendFriendRequestRequest')();request.account_id=target['account_id'];request.player_id=int(target['player_id'])
            response=self.call('contacts','ContactsService','SendFriendRequest',request,confirmed=True)
            if not response.request_id:raise ValueError('No request receipt returned. Check in-game before retrying.')
            return 'Friend request sent to '+target['handle']+'. Awaiting their acceptance.'
        request=self.message('social','InviteToPartyRequest')();request.member_urn=target['id'];request.name=target['handle']
        response=self.call('social','SocialService','InviteToParty',request,confirmed=True)
        if not response.invitation.id:raise ValueError('No invitation receipt returned. Check in-game before retrying.')
        return 'Party invitation sent to '+target['handle']+'. Awaiting their acceptance.'

    def relationships(self,context):
        self.scope(context)
        output=dict(friends=[],party=[],friends_at=0,party_at=0,friends_error='',party_error='')
        try:
            friends=set();cursor=''
            for _ in range(20):
                request=self.message('contacts','ListContactsRequest')();request.relationship_types.append(1);request.pagination.first=100
                if cursor:request.pagination.after=cursor
                response=self.call('contacts','ContactsService','ListContacts',request)
                for contact in response.contacts:
                    types={r.type for r in contact.relationships}
                    if 1 in types and 2 not in types and contact.account.player_id:
                        friends.add(PLAYER_PREFIX+str(contact.account.player_id))
                if not response.page_info.has_next_page:break
                next_cursor=response.page_info.end_cursor
                if not next_cursor or next_cursor==cursor:raise ValueError('Incomplete friends response')
                cursor=next_cursor
            else:raise ValueError('Friends result limit reached')
            output.update(friends=sorted(friends),friends_at=time.time())
        except Exception:output['friends_error']='Friends list unavailable'
        try:
            groups=[];cursor=''
            for _ in range(4):
                request=self.message('social','ListGroupsRequest')();request.filters.types.append(4);request.pagination.first=5
                if cursor:request.pagination.after=cursor
                response=self.call('social','SocialService','ListGroups',request)
                groups.extend(g for g in response.groups if g.type==4 and any(m.urn==self.account.subject for m in g.members))
                if not response.page_info.has_next_page:break
                next_cursor=response.page_info.end_cursor
                if not next_cursor or next_cursor==cursor:raise ValueError('Incomplete party response')
                cursor=next_cursor
            else:raise ValueError('Party result limit reached')
            if len(groups)>1:raise ValueError('Current party is ambiguous')
            members={m.urn for g in groups for m in g.members}
            if any(not u.startswith(PLAYER_PREFIX) for u in members):raise ValueError('Unrecognised party identities')
            party_group=groups[0] if len(groups)==1 else None
            party_group_id=str(getattr(party_group,'id','') or '') if party_group else ''
            party_leader_id=str(getattr(party_group,'leader_urn','') or '') if party_group else ''
            output.update(party=sorted(members),party_at=time.time(),party_group_id=party_group_id,party_leader_id=party_leader_id)
        except Exception:output['party_error']='Party membership unavailable'
        output['pending_party_out']=[];output['pending_party_known']=False
        try:
            pending_party=set();cursor=''
            for _ in range(4):
                request=self.message('social','ListPendingInvitationsRequest')();request.group_type=4;request.pagination.first=50
                if cursor:request.pagination.after=cursor
                response=self.call('social','SocialService','ListPendingInvitations',request)
                for inv in getattr(response,'invitations',[]):
                    if getattr(inv,'from_urn','')==self.account.subject and getattr(inv,'to_urn','').startswith(PLAYER_PREFIX):
                        pending_party.add(inv.to_urn)
                if not response.page_info.has_next_page:break
                next_cursor=response.page_info.end_cursor
                if not next_cursor or next_cursor==cursor:break
                cursor=next_cursor
            output.update(pending_party_out=sorted(pending_party),pending_party_known=True)
        except Exception:pass
        output['pending_friend_out']=[];output['pending_friend_known']=False
        try:
            pending_friends=set();cursor=''
            for _ in range(4):
                request=self.message('contacts','ListPendingFriendRequestsRequest')();request.pagination.first=50
                if cursor:request.pagination.after=cursor
                response=self.call('contacts','ContactsService','ListPendingFriendRequests',request)
                for req in getattr(response,'pending_friend_requests',[]):
                    sender_pid=getattr(getattr(req,'sender',None),'player_id',0)
                    recv_pid=getattr(getattr(req,'receiver',None),'player_id',0)
                    if sender_pid and recv_pid and PLAYER_PREFIX+str(sender_pid)==self.account.subject:
                        pending_friends.add(PLAYER_PREFIX+str(recv_pid))
                if not response.page_info.has_next_page:break
                next_cursor=response.page_info.end_cursor
                if not next_cursor or next_cursor==cursor:break
                cursor=next_cursor
            output.update(pending_friend_out=sorted(pending_friends),pending_friend_known=True)
        except Exception:pass
        # Resolve the complete contact list without guessing blank/raw-ID names.
        output['friend_rows']=[];output['friend_names_error']=''
        if output['friends_at']:
            try:
                ids=set(output['friends']);names={}
                ordered=sorted(int(u[len(PLAYER_PREFIX):]) for u in ids)
                for start in range(0,len(ordered),256):
                    batch=set(ordered[start:start+256]);request=self.message('identity','GetPlayersNamesRequest')();request.player_geids.extend(sorted(batch))
                    response=self.call('identity','IdentityService','GetPlayersNames',request)
                    if any(n.geid not in batch for n in response.names):raise ValueError('Unexpected friend-name response')
                    for row in response.names:
                        if row.name.strip():names[PLAYER_PREFIX+str(row.geid)]=row.name.strip()
                output['friend_rows']=[dict(id=u,handle=names[u],is_self=u==self.account.subject) for u in sorted(names,key=lambda u:names[u].casefold())]
                if len(names)!=len(ids):output['friend_names_error']=str(len(ids)-len(names))+' friend name(s) unavailable; refresh to retry.'
            except Exception:output['friend_names_error']='Some friend names could not be loaded; refresh to retry.'
        output['party_rows']=[];output['self_id']=self.account.subject
        if output.get('party_at') and output.get('party'):
            try:
                p_ids=set(output['party']);p_names={}
                p_ordered=sorted(int(u[len(PLAYER_PREFIX):]) for u in p_ids if u[len(PLAYER_PREFIX):].isdigit())
                for start in range(0,len(p_ordered),256):
                    batch=set(p_ordered[start:start+256]);request=self.message('identity','GetPlayersNamesRequest')();request.player_geids.extend(sorted(batch))
                    response=self.call('identity','IdentityService','GetPlayersNames',request)
                    if any(n.geid not in batch for n in response.names):raise ValueError('Unexpected party-name response')
                    for row in response.names:
                        if row.name.strip():p_names[PLAYER_PREFIX+str(row.geid)]=row.name.strip()
                leader_id=output.get('party_leader_id','')
                output['party_rows']=[
                    dict(id=u,handle=p_names[u],is_self=u==self.account.subject,is_leader=(u==leader_id))
                    for u in sorted(p_names,key=lambda u:(0 if u==leader_id else 1,p_names[u].casefold()))
                ]
            except Exception:pass
        self.scope(context)
        return output

    def invite_many(self,people,context,confirmed=False,previous=(),cancel=None,control=None,require_shard=True,operation='party',allow_friends=False):
        if operation not in ('friend','party'):raise ValueError('Unknown social operation')
        if not require_shard:raise ValueError('Social actions are limited to the current shard.')
        if confirmed is not True:raise ValueError('Confirm the selected recipients first.')
        from party_invites import PartyInviteQueue,validate_batch_size
        validate_batch_size(people)
        if len({p['id'] for p in people})!=len(people):raise ValueError('Invalid party recipients.')
        control=control or PartyInviteQueue(people,cancel=cancel,operation=operation)
        revision=control.membership_revision()
        # Recheck shard and party immediately before the first outgoing invitation.
        roster=self.server_member_ids(context)
        relations=self.relationships(context)
        membership='friends' if operation=='friend' else 'party';stamp='friends_at' if operation=='friend' else 'party_at'
        if not relations.get(stamp):raise ValueError('Social membership unavailable. No requests sent; refresh and try again.')
        friends=set(relations.get('friends',[])) if relations.get('friends_at') else set()
        party=set(relations[membership]);attempted=set(previous);results=[];stopped=False;sent=0
        for person in people:
            row=dict(id=person['id'],handle=person['handle'])
            self._diagnostic_context=dict(queue_id=control.identifier,operation=operation,recipient_id=person['id'],recipient_handle=person['handle'],phase='recipient processing')
            reason='You' if person['id']==self.account.subject else ('Already a friend' if operation=='friend' else 'Already in party') if person['id'] in party else 'No longer on shard' if require_shard and person['id'] not in roster and not (allow_friends and operation=='party' and person['id'] in friends) else 'Already attempted this session; explicitly enable repeat requests' if person['id'] in attempted else ''
            if reason:row.update(outcome='Skipped',detail=reason)
            elif control.cancel_event.is_set():row.update(outcome='Not sent',detail='Invitation queue cancelled.')
            elif stopped:row.update(outcome='Not sent',detail='Batch stopped after an unsuccessful invitation.')
            else:
                try:
                    if not control.before_send(person):row.update(outcome='Not sent',detail='Invitation queue cancelled.')
                    else:
                        if control.membership_revision()!=revision:
                            roster=self.server_member_ids(context)
                            latest=self.relationships(context)
                            if not latest.get(stamp):raise ValueError('Could not recheck social membership after resuming.')
                            party=set(latest[membership]);friends=set(latest.get('friends',[])) if latest.get('friends_at') else set();revision=control.membership_revision()
                        reason=('Already a friend' if operation=='friend' else 'Already in party') if person['id'] in party else 'No longer on shard after resume' if require_shard and person['id'] not in roster and not (allow_friends and operation=='party' and person['id'] in friends) else ''
                        if reason:row.update(outcome='Skipped',detail=reason)
                        else:
                            try:control.remember(person)
                            except (OSError,ValueError) as error:
                                row.update(outcome='Not sent',detail=str(error));stopped=True
                        if not stopped and not reason:
                            if control.cancel_event.is_set():row.update(outcome='Not sent',detail='Invitation queue cancelled before sending.')
                            else:
                                detail=self.send(operation,person,context,True,allow_friend=True) if allow_friends and operation=='party' else self.send(operation,person,context,True)
                                row.update(outcome='Sent',detail=detail);sent+=1
                except PlayerLeftShard as error:row.update(outcome='Skipped',detail=str(error))
                except Exception as error:
                    evidence=getattr(error,'social_diagnostic',None) or save_social_error(getattr(self,'diagnostic_directory',None),error,**self._diagnostic_context)
                    row['error_id']=evidence['id'];row['error_code']=evidence['code']
                    message=public_error(error)+' ['+evidence['code']+']'
                    message+=(' Error reference '+evidence['id']+'.' if evidence['saved'] else ' Diagnostic file could not be saved.')
                    try:code=error.code().name
                    except Exception:code=''
                    if code in ('ALREADY_EXISTS','NOT_FOUND','INVALID_ARGUMENT'):
                        row.update(outcome='Skipped',detail=message+' Continuing with the next player; this request will not be retried.')
                    else:
                        row.update(outcome='Check in game',detail=message+' Queue stopped because delivery or service availability is uncertain. Check in-game before retrying.');stopped=True
            results.append(row);control.update(row)
        skipped=sum(r['outcome']=='Skipped' for r in results)
        unsent=sum(r['outcome']=='Not sent' for r in results)
        control.finish(results,error='Queue stopped after an unsuccessful invitation.' if stopped else '')
        return dict(status=('Friend requests' if operation=='friend' else 'Party invites')+f': {sent} sent, {skipped} skipped'+(', queue stopped' if stopped else '')+(f', {unsent} not sent' if unsent else '')+'. See Queue / results.',results=results)

    def party_manage(self,action,member_id,context,confirmed=False,member_handle=''):
        if action not in ('kick_party_member','transfer_party_leader','leave_party') or confirmed is not True:
            raise ValueError('Choose and confirm a party action.')
        self.scope(context)
        groups=[];cursor=''
        for _ in range(4):
            request=self.message('social','ListGroupsRequest')();request.filters.types.append(4);request.pagination.first=5
            if cursor:request.pagination.after=cursor
            response=self.call('social','SocialService','ListGroups',request)
            groups.extend(g for g in response.groups if g.type==4 and any(m.urn==self.account.subject for m in g.members))
            if not response.page_info.has_next_page:break
            next_cursor=response.page_info.end_cursor
            if not next_cursor or next_cursor==cursor:break
            cursor=next_cursor
        if len(groups)!=1 or not getattr(groups[0],'id',''):
            raise ValueError('You are not currently in an active party.')
        party_group=groups[0]
        group_id=str(party_group.id)
        leader_urn=str(getattr(party_group,'leader_urn','') or '')
        member_urns={m.urn for m in party_group.members}
        self.scope(context)
        if action=='leave_party':
            req=self.message('social','LeaveGroupRequest')()
            req.group_id=group_id
            self.call('social','SocialService','LeaveGroup',req,confirmed=True)
            return 'Left party.'
        member_id=str(member_id or '').strip()
        if not member_id or member_id==self.account.subject or member_id not in member_urns:
            raise ValueError('Selected player is no longer in your party.')
        if leader_urn and leader_urn!=self.account.subject:
            raise ValueError('Only the party leader can manage party members.')
        label=member_handle or member_id
        if action=='kick_party_member':
            req=self.message('social','KickGroupMemberRequest')()
            req.group_id=group_id
            req.member_urn=member_id
            self.call('social','SocialService','KickGroupMember',req,confirmed=True)
            return f'Removed {label} from the party.'
        req=self.message('social','TransferGroupLeadershipRequest')()
        req.group_id=group_id
        req.player_urn=member_id
        self.call('social','SocialService','TransferGroupLeadership',req,confirmed=True)
        return f'Made {label} the party leader.'

    def _list_active_chat_groups(self,context):
        self.scope(context)
        groups=[];cursor=''
        for _ in range(4):
            request=self.message('social','ListGroupsRequest')();request.pagination.first=50
            if cursor:request.pagination.after=cursor
            response=self.call('social','SocialService','ListGroups',request)
            for g in response.groups:
                if any(m.urn==self.account.subject for m in g.members):
                    groups.append(g)
            if not response.page_info.has_next_page:break
            next_cursor=response.page_info.end_cursor
            if not next_cursor or next_cursor==cursor:break
            cursor=next_cursor
        return groups

    def chat_snapshot(self,context,known=None,translator=None,auto_translate=True):
        import chat_codec
        known=dict(known or {})
        groups=self._list_active_chat_groups(context)
        shard_id=str(context.get('full_shard_id') or '').casefold()
        shard_pattern=r'(?<![a-z0-9_])'+re.escape(shard_id)+r'(?![a-z0-9_])' if shard_id else ''

        channels=[]
        dm_other_urns=set()
        for g in groups:
            gid=str(getattr(g,'id','') or '')
            if not gid:continue
            gtype=int(getattr(g,'type',0) or 0)
            if gtype == 6:
                # Exclude ship channels completely (too many and buggy in-game)
                continue
            gname=str(getattr(g,'name','') or '').strip()
            chat_enabled=True
            try:
                if hasattr(g,'settings') and hasattr(g.settings,'chat'):
                    chat_enabled=bool(g.settings.chat.enabled)
            except Exception:
                chat_enabled=True
            if not chat_enabled:continue

            if gtype==2:
                if shard_pattern and not re.search(shard_pattern,gname.casefold()):
                    continue
                kind='global'
                label='Global'
                sort_order=0
            elif gtype==4:
                kind='party'
                label='Party'
                sort_order=1
            elif gtype==5:
                kind='dm'
                other_urn=next((m.urn for m in g.members if m.urn!=self.account.subject),'')
                if other_urn:dm_other_urns.add(other_urn)
                other_name=known.get(other_urn) or gname or 'Direct'
                label=f'DM · {other_name}'
                sort_order=3
            else:
                kind='group'
                label=gname or 'Channel'
                sort_order=4

            updated_at=int(getattr(g,'updated_at',0) or getattr(g,'created_at',0) or 0)
            channels.append(dict(
                id=gid,
                kind=kind,
                group_type=gtype,
                name=gname,
                label=label,
                member_count=len(getattr(g,'members',[])),
                leader_urn=str(getattr(g,'leader_urn','') or ''),
                updated_at=updated_at,
                _sort=(sort_order,-updated_at,label.casefold()),
            ))

        channels.sort(key=lambda c:c['_sort'])
        for c in channels:c.pop('_sort',None)

        # Fetch messages for up to 8 active channels (Global, Party, Ship, DM, etc.)
        raw_messages=[]
        for ch in channels[:8]:
            try:
                req=self.message('chat','ListMessagesRequest')()
                req.group_id=ch['id']
                req.pagination.first=50
                resp=self.call('chat','ChatService','ListMessages',req)
                for m in resp.messages:
                    raw_messages.append((ch,m))
            except Exception:
                continue

        # Sort messages chronologically (oldest -> newest)
        raw_messages.sort(key=lambda pair:(int(getattr(pair[1],'created_at',0) or 0),str(getattr(pair[1],'id','') or '')))
        # Keep the last 160 messages across active channels
        raw_messages=raw_messages[-160:]

        messages=[]
        translate_budget=18
        for ch,m in raw_messages:
            mid=str(getattr(m,'id','') or '')
            sender_urn=str(getattr(m,'sender_urn','') or '')
            handle=str(getattr(m,'sender_nickname','') or known.get(sender_urn) or '').strip()
            display_name=str(getattr(m,'sender_display_name','') or handle).strip()
            if not handle:
                handle=display_name or (sender_urn[len(PLAYER_PREFIX):] if sender_urn.startswith(PLAYER_PREFIX) else 'Citizen')
            content=str(getattr(m,'content','') or '')
            created_ms=int(getattr(m,'created_at',0) or 0)
            created_at=created_ms/1000.0 if created_ms>10_000_000_000 else float(created_ms)

            decoded_info=chat_codec.decode_sc_chat(content)
            decoded_text=str(decoded_info.get('decoded') or content)
            was_zh=bool(decoded_info.get('was_zh_encoded'))
            needs_tr=bool(decoded_info.get('needs_translation'))
            lang_hint=str(decoded_info.get('lang_hint') or 'en')

            translated_text=''
            detected_lang=lang_hint
            if auto_translate and needs_tr and translator is not None and translate_budget>0:
                translate_budget-=1
                tr_text,det=translator.translate(decoded_text,target_lang='en',source_lang=lang_hint if lang_hint!='en' else 'auto')
                detected_lang=det or lang_hint
                if tr_text and tr_text.strip().casefold()!=decoded_text.strip().casefold():
                    translated_text=tr_text.strip()

            messages.append(dict(
                id=mid or f"{ch['id']}:{created_ms}:{sender_urn}",
                group_id=ch['id'],
                channel_kind=ch['kind'],
                channel_label=ch['label'],
                sender_id=sender_urn,
                sender_handle=handle,
                sender_display_name=display_name,
                is_self=(sender_urn==self.account.subject),
                raw_content=content,
                content=decoded_text,
                translated_content=translated_text,
                was_zh_encoded=was_zh,
                source_lang=detected_lang,
                at=created_at,
            ))

        self.scope(context)
        return dict(
            channels=channels,
            messages=messages,
            observed_at=time.time(),
            full_shard_id=context.get('full_shard_id',''),
            session_token=context.get('session_token',''),
        )

    def send_chat(self,group_id,content,context,confirmed=False,encode_zh=False,translator=None):
        import chat_codec
        if confirmed is not True:
            raise ValueError('Confirm sending the chat message.')
        self.scope(context)
        group_id=str(group_id or '').strip()
        text=str(content or '').strip()
        if not group_id:
            raise ValueError('Select a chat channel before sending.')
        if not text:
            raise ValueError('Enter a message to send.')
        if len(text)>480:
            raise ValueError('Chat message is too long (maximum 480 characters).')

        groups=self._list_active_chat_groups(context)
        target_group=next((g for g in groups if str(getattr(g,'id','') or '')==group_id),None)
        if target_group is None:
            raise ValueError('Selected chat channel is no longer active on this shard.')

        outgoing=text
        if encode_zh:
            if translator is not None:
                encoded_bundle=translator.translate_and_encode_zh(text)
                outgoing=encoded_bundle.get('encoded') or chat_codec.encode_sc_zh_chat(text)
            else:
                outgoing=chat_codec.encode_sc_zh_chat(text)

        req=self.message('chat','SendMessageRequest')()
        req.group_id=group_id
        req.content=outgoing
        if hasattr(req,'metadata') and context.get('full_shard_id'):
            req.metadata.shard_id=str(context['full_shard_id'])
        self.scope(context)
        self.call('chat','ChatService','SendMessage',req,confirmed=True)
        return dict(sent=True,group_id=group_id,content=outgoing,at=time.time())


def social_job(kind,context,**options):
    client=None
    try:
        client=PlayerClient()
        if kind=='roster':return client.roster(context,options.get('known'))
        if kind=='search':return client.search(options['query'],context)
        if kind=='relationships':return client.relationships(context)
        if kind in ('party_many','friend_many'):return client.invite_many(options['people'],context,options.get('confirmed'),options.get('previous',()),options.get('cancel'),options.get('control'),options.get('require_shard',True),'friend' if kind=='friend_many' else 'party',options.get('allow_friends',False))
        if kind in ('friend','party'):return client.send(kind,options['person'],context,options.get('confirmed'))
        if kind in ('kick_party_member','transfer_party_leader','leave_party'):
            return client.party_manage(kind,options.get('player_id',''),context,options.get('confirmed'),options.get('handle',''))
        if kind=='chat_snapshot':
            return client.chat_snapshot(context,options.get('known'),options.get('translator'),options.get('auto_translate',True))
        if kind=='send_chat':
            return client.send_chat(options.get('group_id',''),options.get('content',''),context,options.get('confirmed'),options.get('encode_zh',False),options.get('translator'))
        raise ValueError('Unknown social operation')
    except (ValueError,FileNotFoundError) as error:
        if isinstance(error,FileNotFoundError):raise ValueError('Sign in to Star Citizen to use social tools.') from None
        raise ValueError(str(error)) from None
    except Exception as error:raise ValueError(public_error(error)) from None
    finally:
        if client is not None:client.close()
