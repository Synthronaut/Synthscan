"""One read-only reputation Get request using the existing signed-in account.

No login/refresh, no other subject parameter, no mutation, no periodic polling.
Tokens stay in memory. Only status/field presence is saved, never credentials.
"""
import base64
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import time
import uuid
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(os.environ['TEMP']) / 'SynthScanRpcTools'))
from google.protobuf import descriptor_pool, message_factory
from tools.inspect_game_schema import iter_descriptors, DEFAULT_EXE


def matches_subject(subject, geid):
    return subject == 'urn:sc:global:player:geid:' + str(geid)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query-own',action='store_true')
    parser.add_argument('--all',action='store_true',help='Read bounded pages of verified own-subject records into the private profile')
    args=parser.parse_args()
    if args.all and not args.query_own:parser.error('--all requires --query-own')
    import grpc
    game = Path(DEFAULT_EXE).parents[1]
    config = json.loads((game / 'loginData.json').read_text(encoding='utf-8'))
    endpoint = urlparse(config['star_network']['services_endpoint'])
    if endpoint.scheme != 'https' or not endpoint.hostname.endswith('.cloudimperiumgames.com'):
        raise ValueError('Refusing an unexpected service endpoint')
    token = config['auth_token']
    parts = token.split('.')
    claims = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)))
    if claims.get('exp', 0) <= time.time():
        raise ValueError('Existing credential expired; no refresh will be attempted')
    # Match normal RPC identity metadata to the current character's own account.
    # The client parses these exact keys in its on-disk metadata helpers.
    log=(game/'Game.log').read_text(encoding='utf-8',errors='replace')
    characters=re.findall(r'<AccountLoginCharacterStatus_Character>[^\r\n]*?geid (\d+) - accountId (\d+)[^\r\n]*?state STATE_CURRENT',log)
    own=next((pair for pair in reversed(characters) if pair[1]==str(claims.get('account_id'))),None)
    if not own:
        raise ValueError('Current character could not be matched to signed-in account; no request sent')
    def is_own_subject(subject):
        return matches_subject(subject, own[0])
    raw = Path(DEFAULT_EXE).read_bytes()
    descriptors = {d.name: d for d, _ in iter_descriptors(raw)}
    pool = descriptor_pool.DescriptorPool()
    added = set()

    def add(name):
        if name in added:
            return
        descriptor = descriptors[name]
        for dependency in descriptor.dependency:
            add(dependency)
        pool.AddSerializedFile(descriptor.SerializeToString())
        added.add(name)

    add('sc/external/services/reputation/v1/api.proto')
    prefix = 'sc.external.services.reputation.v1.'
    method='QueryReputations' if args.query_own else 'Get'
    Request = message_factory.GetMessageClass(pool.FindMessageTypeByName(prefix + method+'Request'))
    Response = message_factory.GetMessageClass(pool.FindMessageTypeByName(prefix + method+'Response'))
    catalog = json.loads((ROOT / 'research/reputation_12913470/audit.json').read_text(encoding='utf-8'))
    faction = next(t['faction_id'] for t in catalog['faction_tracks'] if t['faction'] == 'Hurston Dynamics')
    faction_record=json.loads((ROOT/'research/reputation_12913470/records/libs/foundry/records/factions/factionreputation/factionreputation_hurstondynamics.json').read_text())
    if faction_record['_RecordId_']!=faction:
        raise ValueError('Faction identity does not match extracted catalog')
    faction='urn:sc:reputations:org:geid:'+str(faction_record['_RecordValue_']['GEID'])
    scope = 'Security'
    request = Request()
    if args.query_own:
        request.query.pagination.first=100 if args.all else 1
        prop=request.query.filter.property_filter
        prop.property='subject';prop.operator=1;prop.value='urn:sc:global:player:geid:'+own[0]
    else:
        request.entity=faction;request.scope=scope
    result = dict(method='ReputationService/'+method, track='Own subject only' if args.query_own else 'Hurston Dynamics / Security',
                  exe_sha256=hashlib.sha256(raw).hexdigest(),
                  request_scope='Authenticated own subject, matched to current character',
                  mutating_calls=0, credential_saved=False, identity_metadata_matched=True)
    with grpc.secure_channel(endpoint.netloc, grpc.ssl_channel_credentials()) as channel:
        call = channel.unary_unary('/' + prefix + 'ReputationService/'+method,
                                  request_serializer=lambda value: value.SerializeToString(),
                                  response_deserializer=Response.FromString)
        try:
            response = call(request, timeout=12, metadata=(('authorization', 'Bearer ' + token),
                            ('account_id',own[1]),('player_id',own[0])))
            result.update(status='OK',
                          populated_fields=[field.name for field, _ in response.ListFields()])
            if args.query_own:
                records=list(response.results)
                cursors=set()
                if args.all:
                    for page in range(9):
                        if not response.page_info.has_next_page:break
                        cursor=response.page_info.end_cursor
                        if not cursor or cursor in cursors:raise ValueError('Invalid pagination cursor; refusing partial snapshot')
                        cursors.add(cursor);request.query.pagination.after=cursor
                        response=call(request,timeout=12,metadata=(('authorization','Bearer '+token),('account_id',own[1]),('player_id',own[0])))
                        records.extend(response.results)
                    if response.page_info.has_next_page:raise ValueError('Reputation snapshot exceeds bounded page limit')
                result['count']=len(records)
                result['own_character_verified']=all(is_own_subject(v.reputation.subject) for v in records)
                if args.all:
                    if not records or not result['own_character_verified']:
                        raise ValueError('No verified own-character snapshot; existing file preserved')
                    from native_control import DATA
                    from telemetry_ipc import publish_json
                    snapshot=dict(schema=1,source='authenticated_reputation_service',read_at=time.time(),
                                  character_key=hashlib.sha256(('urn:sc:global:player:geid:'+own[0]).encode()).hexdigest(),
                                  own_character_verified=True,complete=True,
                                  records=[dict(entity=v.reputation.entity,scope=v.reputation.scope,score=v.reputation.score,
                                                updated_at=v.reputation.updated_at,last_drifted_at=v.reputation.last_drifted_at,
                                                standing_id=v.reputation.standings_id,version=v.version,
                                                standing=dict(name=v.standing.name,minimum=getattr(v.standing,'min'),gated=v.standing.gated)) for v in records])
                    if not publish_json(DATA/'reputation_snapshot.json',snapshot):raise OSError('Snapshot temporarily locked')
                    result['snapshot_saved']=True
                    result['read_at']=snapshot['read_at']
                response.results.clear();response.results.extend(records)
                result['subject_formats']=[dict(length=len(v.reputation.subject),decimal=v.reputation.subject.isdecimal()) for v in response.results[:1]]
                def describe(subject):
                    try:
                        value=uuid.UUID(subject)
                        return dict(uuid=True,zero_high_half=value.int>>64==0,
                                    low64_matches_character=(value.int&((1<<64)-1))==int(own[0]),
                                    matches_account=value.int==int(own[1]),
                                    byte_swapped_matches=int.from_bytes(value.bytes,'little')==int(own[0]))
                    except ValueError:return dict(uuid=False,format=re.sub(r'\d+','<number>',subject),
                                                  ends_with_own_character=subject.endswith(':'+own[0]))
                result['subject_identity_diagnostics']=[describe(v.reputation.subject) for v in response.results[:1]]
                if result['count'] and result['own_character_verified']:
                    value=response.results[0].reputation
                    result['verified_own_score']=value.score
                    result['entity']=value.entity;result['scope']=value.scope
            elif response.HasField('reputation'):
                result['score_response_present'] = response.reputation.HasField('reputation')
                if response.reputation.HasField('reputation'):
                    value=response.reputation.reputation
                    result['own_character_verified']=value.subject==own[0]
                    if value.subject==own[0] and value.entity==faction and value.scope==scope:
                        result['verified_own_score']=value.score
        except grpc.RpcError as error:
            # Error text/metadata may contain session details; retain the canonical code only.
            result['status'] = error.code().name
            details=error.details().lower()
            result['reason_class']=next((reason for reason in ('expired','missing','invalid token','permission','unimplemented') if reason in details),'unspecified')
            safe=error.details()
            for secret in (config.get('token',''),token,config.get('username',''),own[0],own[1]):
                if secret:safe=safe.replace(secret,'[redacted]')
            safe=re.sub(r'[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]+','[token]',safe)
            result['reason_redacted']=safe[:600]
    output = ROOT / 'research/reputation_12913470'/('service_probe_query.json' if args.query_own else 'service_probe_identity.json')
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    if result.get('status')!='OK':raise SystemExit(1)


if __name__ == '__main__':
    main()
