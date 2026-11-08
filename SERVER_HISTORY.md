# Shard history and server age

SynthScan records visits using the full logged shard identity. Short numbers such
as 110 are not globally unique; another region or environment can reuse that
number. Personal history includes the earliest retained visit, visit count and
the span since that first observation. The complete retained history is used,
not just the recent-visits dropdown's eight rows or the server log's current page.

The HUD shows HISTORY followed by that recorded span once it reaches an hour.
The region dropdown shows the exact first-recorded time in UTC+8 and explicitly
labels this personal history. Server log details and exports include the same
first-recorded timestamp and recorded-visit count.

These are observations, not a measured server age. A first recorded visit means
SynthScan has not recorded an earlier visit to this identity on this PC. It does
not prove that the shard has just been created. Likewise, observations nine days
apart do not prove nine days of uninterrupted uptime or rule out a restart/reset.
Clearing local history changes what can be established from these records.

The November 8, 2026 local audit found no verified shard startup/reset timestamp
in the client log or inspected service descriptors. The logged `uptime_secs`
belongs to network channels: a new connection to an existing shard starts near
zero. The Instance Manager's `Instance.created_at` describes an instance object;
it is not validated as the birth of the connected PU shard. Local frontend
`local_shard` creation records are not remote PU-server creation records either.

Accordingly, server age, server startup and last reset remain unknown. High or
low shard numbers and reports that a server feels fresh are not converted into
automatic age estimates. No additional service calls or history uploads are
required for this feature. Sharing observations across an organization could
extend recorded history, but would still not establish a server's startup time.

### Shard labels and names

The ribbon shows a numeric shard identifier once. Recent visits show a saved
name alongside that number; entries remain keyed by the full shard ID, including
region and environment, rather than by number alone. Names entered in server
history are local labels, not verified CIG names.

The loading queue's word-based shard name is separate from both the numeric ID
and a local DGS label such as GAME-7. The inspected client schema contains a
PlayerShardHistory.shard_name field, but the current collector has no verified
read source for it. Automatic loading-name capture is not implemented. Unknown
names remain numeric identifiers; SynthScan does not manufacture a mapping.
