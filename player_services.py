"""Own-session social reads and explicitly selected, one-shot social actions."""
import re
import time
from pathlib import Path

PLAYER_PREFIX='urn:sc:global:player:geid:'
READS={('social','SocialService','ListGroups'),('identity','IdentityService','GetPlayersNames'),
       ('contacts','ContactsService','SearchAccount'),('contacts','ContactsService','ListContacts')}
WRITES={('contacts','ContactsService','SendFriendRequest'),('social','SocialService','InviteToParty')}

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
        return self.account.channel.unary_unary('/sc.external.services.'+domain+'.v1.'+service+'/'+method,
            request_serializer=lambda v:v.SerializeToString(),response_deserializer=response.FromString)(request,timeout=8,metadata=self.account.metadata)

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
            output.update(party=sorted(members),party_at=time.time())
        except Exception:output['party_error']='Party membership unavailable'
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
                    message=str(error)[:240] if isinstance(error,ValueError) else public_error(error)
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


def social_job(kind,context,**options):
    client=None
    try:
        client=PlayerClient()
        if kind=='roster':return client.roster(context,options.get('known'))
        if kind=='search':return client.search(options['query'],context)
        if kind=='relationships':return client.relationships(context)
        if kind in ('party_many','friend_many'):return client.invite_many(options['people'],context,options.get('confirmed'),options.get('previous',()),options.get('cancel'),options.get('control'),options.get('require_shard',True),'friend' if kind=='friend_many' else 'party',options.get('allow_friends',False))
        if kind in ('friend','party'):return client.send(kind,options['person'],context,options.get('confirmed'))
        raise ValueError('Unknown social operation')
    except (ValueError,FileNotFoundError) as error:
        if isinstance(error,FileNotFoundError):raise ValueError('Sign in to Star Citizen to use social tools.') from None
        raise ValueError(str(error)) from None
    except Exception as error:raise ValueError(public_error(error)) from None
    finally:
        if client is not None:client.close()
