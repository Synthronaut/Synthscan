"""Inspect/test one read-only population lookup for the signed-in character.

No game input, bindings, setting changes, credential refresh, other-player
queries, retries, or matchmaking requests. Returned counts remain experimental.
"""
import argparse
import json
import re
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
RPC='/sc.external.services.social.v1.SocialService/GetInstanceInfo'
CONTACTS_RPC='/sc.external.services.contacts.v1.ContactsService/GetShardInfo'


def configure_own_request(request,client,service):
    if service=='social':
        request.player_urn=client.subject
    elif service=='contacts':
        identity=dict(client.metadata)
        request.account_id=int(identity['account_id'])
        request.player_id=int(identity['player_id'])
    else:raise ValueError('Unsupported read-only probe')


def safe_rpc_details(error,client):
    """Keep validation text while excluding local identity/credential material."""
    try:details=str(error.details())
    except Exception:return ''
    sensitive=[getattr(client,'subject','')]
    sensitive.extend(str(value) for _,value in getattr(client,'metadata',()))
    for value in sorted(filter(None,sensitive),key=len,reverse=True):
        details=details.replace(value,'[redacted]')
    details=re.sub(r'(?i)Bearer\s+\S+','Bearer [redacted]',details)
    details=re.sub(r'\beyJ[A-Za-z0-9_.-]+','[redacted-token]',details)
    details=re.sub(r'urn:[A-Za-z0-9:_-]+','[redacted-urn]',details)
    details=re.sub(r'\b\d{5,}\b','[redacted-id]',details)
    return details[:600]


def projection(info,has_info,current_shard):
    return dict(has_info=has_info,shard_id_present=bool(info.id),
        matches_current_log_shard=bool(has_info and current_shard and info.id==current_shard),
        dgs_id_present=bool(info.dgs_id),player_count=info.player_count,total_players=info.total_players,
        semantics_verified=False)


def probe(service='social'):
    if service not in ('social','contacts'):raise ValueError('Unsupported read-only probe')
    from app_lifecycle import game_process_ids
    from installation import reference_paths
    if not game_process_ids():return dict(status='blocked_game_closed',requests_sent=0)
    paths=reference_paths()
    if not (paths['game']/'loginData.json').is_file():
        return dict(status='blocked_no_game_sign_in',requests_sent=0)
    from game_account import OwnAccount
    from google.protobuf.descriptor_pb2 import FileDescriptorSet
    from google.protobuf import message_factory
    from telemetry_core import IncrementalGameLog
    client=None;sent=0
    try:
        client=OwnAccount()
        descriptors={f.name:f for f in FileDescriptorSet.FromString(paths['schemas'].read_bytes()).file}
        def add(name):
            try:client.pool.FindFileByName(name);return
            except KeyError:pass
            for dependency in descriptors[name].dependency:add(dependency)
            client.pool.AddSerializedFile(descriptors[name].SerializeToString())
        service_name,method,rpc=('SocialService','GetInstanceInfo',RPC) if service=='social' else ('ContactsService','GetShardInfo',CONTACTS_RPC)
        target=next(name for name,f in descriptors.items() if f.package=='sc.external.services.'+service+'.v1' and any(s.name==service_name for s in f.service))
        add(target);prefix='sc.external.services.'+service+'.v1.'
        request=message_factory.GetMessageClass(client.pool.FindMessageTypeByName(prefix+method+'Request'))()
        configure_own_request(request,client,service)
        response_type=message_factory.GetMessageClass(client.pool.FindMessageTypeByName(prefix+method+'Response'))
        reader=IncrementalGameLog(paths['game']/'Game.log')
        size=reader.log_path.stat().st_size if isinstance(reader.log_path,Path) else Path(reader.log_path).stat().st_size
        while reader.last_pos<size:
            previous=reader.last_pos;reader.poll()
            if reader.last_pos==previous:break
        before=(reader.session_token,reader.full_shard_id)
        if not reader.connected:return dict(status='blocked_no_active_shard',requests_sent=0)
        sent=1
        response=client.channel.unary_unary(rpc,request_serializer=lambda q:q.SerializeToString(),
            response_deserializer=response_type.FromString)(request,timeout=8,metadata=client.metadata)
        reader.poll();unchanged=bool(game_process_ids()) and reader.connected and before==(reader.session_token,reader.full_shard_id)
        values=projection(response.shard_info,response.HasField('shard_info'),reader.full_shard_id if unchanged else '')
        return dict(status='response_received',received_at=time.time(),requests_sent=1,own_character_only=True,
                    session_unchanged=unchanged,credentials_saved=False,**values)
    except Exception as error:
        rpc_status=''
        try:rpc_status=error.code().name
        except Exception:pass
        return dict(status='failed',requests_sent=sent,error_class=type(error).__name__,rpc_status=rpc_status,
                    rpc_details=safe_rpc_details(error,client),own_character_only=True,credentials_saved=False)
    finally:
        if client is not None:client.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query-own',action='store_true')
    parser.add_argument('--service',choices=('social','contacts'),default='social')
    args=parser.parse_args()
    result=probe(args.service) if args.query_own else dict(status='offline_candidate',rpc=RPC if args.service=='social' else CONTACTS_RPC,
        request_fields=['player_urn'] if args.service=='social' else ['account_id','player_id'],response_fields=['id','dgs_id','player_count','total_players'],requests_sent=0)
    result['service']=args.service
    print(json.dumps(result,indent=2))
