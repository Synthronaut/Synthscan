"""Read-only service client, restricted to the locally signed-in character."""
import base64
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent

class OwnAccount:
    def __init__(self):
        from account_permission import require_account_access
        require_account_access()
        sys.path.insert(0, str(ROOT / 'third_party/python_services'))
        import grpc
        from google.protobuf import descriptor_pool, message_factory
        from google.protobuf.descriptor_pb2 import FileDescriptorSet
        from installation import reference_paths
        paths=reference_paths();game=paths['game']
        cached=json.loads(paths['schema_manifest'].read_text(encoding='utf-8'))
        installed=json.loads((game/'build_manifest.id').read_text())
        if cached['build_id'] != installed['Data']['BuildId']:
            raise ValueError('Game changed; service schemas require refresh')
        config = json.loads((game / 'loginData.json').read_text(encoding='utf-8'))
        endpoint = urlparse(config['star_network']['services_endpoint'])
        if endpoint.scheme != 'https' or not endpoint.hostname.endswith('.cloudimperiumgames.com'):
            raise ValueError('Unexpected service endpoint')
        token = config['auth_token']
        payload = token.split('.')[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
        if claims.get('exp', 0) <= time.time():
            raise ValueError('Sign-in credential expired')
        log = (game / 'Game.log').read_text(encoding='utf-8', errors='replace')
        pairs = re.findall(r'<AccountLoginCharacterStatus_Character>[^\r\n]*?geid (\d+) - accountId (\d+)[^\r\n]*?state STATE_CURRENT', log)
        own = next((p for p in reversed(pairs) if p[1] == str(claims.get('account_id'))), None)
        if not own:
            raise ValueError('Own character identity unavailable')
        self.subject = 'urn:sc:global:player:geid:' + own[0]
        self.metadata = (('authorization', 'Bearer ' + token), ('account_id', own[1]), ('player_id', own[0]))
        descriptors = {d.name: d for d in FileDescriptorSet.FromString(paths['schemas'].read_bytes()).file}
        self.pool = descriptor_pool.DescriptorPool()
        added = set()
        def add(name):
            if name in added: return
            d = descriptors[name]
            for dep in d.dependency: add(dep)
            self.pool.AddSerializedFile(d.SerializeToString()); added.add(name)
        for name in ('sc/external/services/mission_service/v1/api.proto', 'sc/external/services/reputation/v1/api.proto'): add(name)
        for optional_proto in ('sc/external/services/ledger/v1/api.proto', 'sc/external/services/blueprint_library/v1/api.proto', 'sc/external/services/entitygraph/v1/api.proto', 'sc/external/services/entitlement/v2/api.proto'):
            if optional_proto in descriptors:
                add(optional_proto)
        self.factory = message_factory.GetMessageClass
        self.channel = grpc.secure_channel(endpoint.netloc, grpc.ssl_channel_credentials())

    def message(self, name):
        return self.factory(self.pool.FindMessageTypeByName(name))()

    def read(self, domain, service, method, request):
        from account_permission import require_account_access
        require_account_access()
        # This allowlist prevents accidental invocation of a mutating RPC.
        if (service, method) not in {
            ('MissionService', 'QueryActiveMissions'),
            ('MissionService', 'QueryMissions'),
            ('ReputationService', 'QueryReputations'),
            ('LedgerService', 'GetFunds'),
            ('BlueprintLibraryService', 'QueryBlueprintEntries'),
            ('EntityGraphService', 'GetInventories'),
            ('EntityGraphService', 'EntityQuery'),
        }:
            raise ValueError('Read method not allowed')
        if service == 'LedgerService' and (domain != 'ledger' or request.ledger_name):
            raise ValueError('Only the authenticated own-wallet lookup is allowed')
        if service == 'BlueprintLibraryService' and domain != 'blueprint_library':
            raise ValueError('Unexpected blueprint service domain')
        if service == 'EntityGraphService':
            if domain != 'entitygraph':
                raise ValueError('Unexpected entitygraph service domain')
            own_geid = self.subject.rsplit(':', 1)[-1]
            if method == 'GetInventories' and request.body.owner_id != own_geid:
                raise ValueError('Only own-character inventory list is allowed')
            if method == 'EntityQuery':
                q = request.body.query
                pf = q.filter.property_filter
                vals = list(pf.values)
                if (
                    request.body.scope.type != 2
                    or not q.inventory_id.startswith(own_geid + ':')
                    or pf.property != 'owner_id'
                    or len(vals) != 1
                    or vals[0].string_value != own_geid
                ):
                    raise ValueError('Only own-character inventory queries are allowed')
        prefix = 'sc.external.services.' + domain + '.v1.'
        response = self.factory(self.pool.FindMessageTypeByName(prefix + method + 'Response'))
        rpc_timeout = 20 if service == 'EntityGraphService' else 8
        return self.channel.unary_unary('/' + prefix + service + '/' + method,
            request_serializer=lambda v: v.SerializeToString(), response_deserializer=response.FromString)(request, timeout=rpc_timeout, metadata=self.metadata)

    def read_stream(self, domain, service, method, request, version='v2'):
        from account_permission import require_account_access
        require_account_access()
        if (domain, service, method, version) not in {
            ('entitlement', 'ExternalEntitlementService', 'QueryEntitlementsStream', 'v2'),
            ('entitlement', 'ExternalEntitlementService', 'QuerySnapshotsWithEntitlementsStream', 'v2'),
        }:
            raise ValueError('Read stream method not allowed')
        prefix = f'sc.external.services.{domain}.{version}.'
        response = self.factory(self.pool.FindMessageTypeByName(prefix + method + 'Response'))
        stream = self.channel.unary_stream(
            '/' + prefix + service + '/' + method,
            request_serializer=lambda v: v.SerializeToString(),
            response_deserializer=response.FromString,
        )(request, timeout=20, metadata=self.metadata)
        return list(stream)

    def close(self):
        self.channel.close()
