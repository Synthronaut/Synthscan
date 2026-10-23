"""HUD presentation model and monitor-relative geometry; no telemetry acquisition."""
import math


def bounded(value, default, low, high):
    try:
        number = float(value)
        return max(low, min(high, number)) if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def preferences(cfg):
    position = cfg.get('hud_position')
    position = position if isinstance(position, dict) else {}
    return dict(layout='ribbon' if cfg.get('hud_layout')=='ribbon' else 'panel',
                scale=bounded(cfg.get('hud_scale'), 1.0, .75, 1.75),
                x=bounded(position.get('x'), .5, 0, 1), y=bounded(position.get('y'), 0, 0, 1))


def placed_rect(bounds, width, height, position):
    width, height = min(int(width), bounds['width']), min(int(height), bounds['height'])
    left = bounds['left'] + round(max(0, bounds['width']-width)*bounded(position.get('x'), .5, 0, 1))
    top = bounds['top'] + round(max(0, bounds['height']-height)*bounded(position.get('y'), 0, 0, 1))
    return dict(left=left, top=top, width=width, height=height)


def position_from_point(bounds, width, height, left, top):
    def fraction(value, origin, extent):
        return max(0, min(1, (value-origin)/extent)) if extent>0 else 0
    return dict(x=fraction(left,bounds['left'],bounds['width']-width),
                y=fraction(top,bounds['top'],bounds['height']-height))


def panel_rows(state, mining=None, *, session=True, mining_enabled=True, now=0, editing=False, rock=None):
    """Each row has an explicit meaning. No stale or fabricated numeric fields."""
    rows = []
    def row(text, role='body'):
        if text:
            rows.append(dict(text=str(text), role=role))
    if editing:
        row('Drag to move · Right-click to lock', 'edit')
    if session:
        connected = bool(state.get('session_token'))
        if connected:
            name = state.get('callsign') or f"Shard {state.get('shard_id', '—')}"
            row(name, 'title')
            detail = [state.get('region_display')]
            if not name.upper().startswith('SHARD '):
                detail.append('Shard '+str(state.get('shard_id', '—')))
            node = state.get('server_name')
            if node and node!='--':
                detail.append(node)
            row(' · '.join(str(v) for v in detail if v and v!='--'), 'muted')
            row(state.get('hop_status'), 'visit')
        else:
            row('Main menu' if state.get('connection_status')!='game_closed' else 'Game closed', 'title')
            row('Waiting for a universe session', 'muted')
        # MetricStore already applies source, session and age validation.
        metrics = []
        fps = state.get('client_fps')
        if fps is not None:
            metrics.append(f'Player {fps:.0f} FPS')
        if connected:
            ping = state.get('ping_ms')
            if ping is not None:
                source = (state.get('metric_meta', {}).get('ping_ms') or {}).get('source')
                metrics.append(('Net RTT' if source=='game_udp_ping_pong' else 'Ping')+f' {ping:.1f} ms')
            sfps = state.get('server_fps')
            if sfps is not None:
                metrics.append(f'Server {sfps:.1f} FPS')
        # Two metrics per line avoids squeezing all fields into one ribbon.
        for offset in range(0,len(metrics),2):
            row('   ·   '.join(metrics[offset:offset+2]), 'metric')
        if connected:
            pop = []
            for key, name in [('shard_pop','Shard'),('srv_pop','Server')]:
                if state.get(key) is not None:
                    pop.append(f'{name} {int(state[key]):,}')
            if pop:
                row('Players · '+'   ·   '.join(pop), 'metric')
            health = state.get('health') or {}
            if health.get('status') in ('DISCONNECTED','RECOVERING','STALLED','SLOW','PACKET_LOSS','LATENCY'):
                row(health.get('label'), 'warning')
            location = state.get('location_display')
            if location and location not in ('--','UNKNOWN'):
                row('Last location · '+location, 'muted')
            reminders = state.get('cooldowns') or []
            if reminders:
                row(f'{len(reminders)} saved shard reminder'+('s' if len(reminders)!=1 else ''), 'visit')
        if state.get('storage_warning'):
            row('Session history could not be saved', 'warning')
    rock_active = (mining_enabled and rock and 0<=now-rock['observed_at']<=5
                   and rock.get('session_token')==state.get('session_token'))
    active = (not rock_active and mining_enabled and mining and 0 <= now-mining['observed_at'] <= 5
              and mining.get('session_token') == state.get('session_token'))
    if active:
        row(('Manual lookup' if mining.get('manual') else 'Mining scan')+f" · RS {mining['signature']:,}", 'section')
        match = mining['match']
        row(match.get('title','Unresolved signature'), 'title')
        if match.get('ambiguous'):
            choices = match.get('candidates', [])
            for candidate in choices[:3]:
                row(candidate.get('label') or candidate.get('name'), 'warning')
            if len(choices)>3:
                row(f'+{len(choices)-3} more · see Mining scanner', 'muted')
        confidence = match.get('ocr_confidence')
        row(f'OCR {confidence:.0%} · signature match, confirm in scanner' if confidence is not None else 'Signature table match · confirm in scanner', 'muted')
    elif rock_active:
        stats=rock['panel']['stats']
        row('Scanned rock', 'section')
        volume=f"{stats['scu']:.2f} SCU" if stats['scu']>0 else 'volume unread'
        row((stats.get('ore') or 'Rock')+' · '+volume, 'title')
        row(f"{stats['mass']:,.0f} kg · Resistance {stats['resistance']:g}% · Instability {stats['instability']:.2f}", 'body')
        contents=rock['panel'].get('contents',{})
        if contents.get('whole'):
            for part in contents['parts'][:6]:
                if part['inert']:
                    row(f"{part['percent']:.2f}% inert", 'muted')
                else:
                    row(f"{part['percent']:.2f}% {part['ore']} · Q{part['quality']}", 'metric')
        else:
            row('Composition not fully read yet', 'muted')
        advice=rock.get('advice')
        if advice:
            if advice.get('safest_single_head'):
                row(f"Estimated solo option · Head {advice['safest_single_head']}", 'visit')
            elif advice.get('comfortable'):
                row('Estimated crew · Heads '+' + '.join(map(str,advice['selected_heads'])), 'visit')
            else:
                row('Limited power reserve · check fitted heads & range', 'warning')
            if advice.get('combined_hold_percent') is not None:
                row(f"All configured heads · {advice['combined_hold_percent']:.0f}% hold", 'body')
            if any(h.get('overpowered') for h in advice['heads']):
                row('A head is too strong at its minimum throttle', 'warning')
            if advice.get('suggested_gadget'):
                row('Suggested gadget · '+advice['suggested_gadget'], 'visit')
            row('Active modules assumed on' if advice['actives_included'] else 'Passive modules only', 'muted')
            row('Full-power range assumed' if advice['distance_metres']==0 else f"Range set to {advice['distance_metres']:g} m", 'muted')
        else:
            row('Set your mining loadout for head advice', 'muted')
    elif mining_enabled and editing:
        row('Mining results appear here when a scan is accepted', 'muted')
    return rows
