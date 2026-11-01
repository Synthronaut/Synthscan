"""Compact native-HUD artwork and its read-only background publisher."""
from html import escape
from pathlib import Path
import os,time
from executive_hangar import countdown
from executive_hangar_hud import render_png
from compboard_inventory import read_inventory
from hangar_verification import installed_build,HangarVerification
from telemetry_ipc import publish_json

WIDTH,HEIGHT=430,150


def card_svg(view,inventory=None,verification=None):
    sync=verification or dict(community_synced=False,reason='Waiting for a community timing sync')
    certain=bool(sync.get('community_synced'))
    phase=(view or {}).get('phase','waiting');lights=(view or {}).get('lights',['empty']*5)
    label={'open':'CLOSES IN','charging':'OPENS IN','reset':'RESET ENDS IN','waiting':'AWAITING SYNC'}[phase]
    if not certain and view:label='EST. '+label
    timer=countdown(view['remaining_ms']) if view else '— : —'
    status={'open':'OPEN WINDOW','charging':'CHARGING','reset':'RESET','waiting':'SCHEDULE OFFLINE'}[phase]
    colors={'green':'#76c9a5','red':'#cf7c7c','empty':'#252b35'}
    sets=None if (inventory or {}).get('unavailable') else (inventory or {}).get('complete_sets',0)
    sets_label='Sets —' if sets is None else str(sets)+' '+('set' if sets==1 else 'sets')+' ready'
    footer=sync.get('reason','Community schedule · estimate')
    if certain and view:
        date=view.get('source_modified','');footer='Community estimate · '+date
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
         '<defs><linearGradient id="bg" x2="0.9" y2="1"><stop stop-color="#171b23"/><stop offset="1" stop-color="#0c1016"/></linearGradient><linearGradient id="edge"><stop stop-color="#baa37b" stop-opacity=".55"/><stop offset="1" stop-color="#baa37b" stop-opacity=".10"/></linearGradient><radialGradient id="glow"><stop stop-color="#80d5b0" stop-opacity=".16"/><stop offset="1" stop-color="#80d5b0" stop-opacity="0"/></radialGradient></defs>',
         '<rect x=".5" y=".5" width="429" height="149" rx="8" fill="url(#bg)" stroke="url(#edge)"/>',
         '<text x="18" y="23" fill="#c7b28c" font-family="Segoe UI" font-size="10" letter-spacing="2.4">PYAM / EXECUTIVE</text>',
         '<path d="M18 34H42" stroke="#a28c65" stroke-width="1"/>',
         '<path d="M32 68H176" stroke="#303745" stroke-width="1"/>']
    if not certain:
        out.append('<rect x="224" y="11" width="82" height="18" rx="4" fill="#332a1e" stroke="#736044" stroke-width=".5"/><text x="265" y="23" text-anchor="middle" fill="#dfbc87" font-family="Segoe UI" font-size="8" letter-spacing=".8">UNVERIFIED</text>')
    for i,color in enumerate(lights):
        x=32+i*36;ink=colors[color]
        if color=='green' and certain:out.append(f'<circle cx="{x}" cy="68" r="23" fill="url(#glow)"/>')
        opacity='1' if certain else '.50'
        out.append(f'<circle cx="{x}" cy="68" r="8" fill="{ink}" fill-opacity="{opacity}" stroke="{ink}" stroke-width=".7"/>')
        out.append(f'<circle cx="{x-2}" cy="66" r="1.6" fill="#ffffff" fill-opacity=".18"/>')
    out.extend([f'<text x="416" y="49" text-anchor="end" fill="#a9a18e" font-family="Segoe UI" font-size="9" letter-spacing="1.5">{escape(label)}</text>',
                f'<text x="418" y="87" text-anchor="end" fill="#f0ede5" font-family="Segoe UI" font-weight="300" font-size="36">{escape(timer)}</text>',
                f'<text x="18" y="104" fill="#8895a4" font-family="Segoe UI" font-size="8" letter-spacing="1.7">{escape(status)}</text>',
                '<path d="M18 116H412" stroke="#3b3a36" stroke-opacity=".60"/>',
                f'<text x="18" y="136" fill="#b2a68f" font-family="Segoe UI" font-size="10">{escape(sets_label)}</text>',
                f'<text x="412" y="136" text-anchor="end" fill="'+('#768395' if certain else '#d0aa74')+'" font-family="Segoe UI" font-size="9">'+escape(footer)+'</text>',
                '</svg>'])
    return ''.join(out)


class HangarPublisher:
    visible=False
    geometry=None
    view=None
    def __init__(self,directory,owner):
        self.directory=Path(directory);self.owner=owner;self.verification=HangarVerification(directory)
        self.last_key=None;self.next_check=0;self.inventory=None;self.build=None;self.enabled=False
        try:
            from installation import game_directory
            self.game=game_directory()
        except OSError:self.game=None

    def tick(self,service,enabled,now=None):
        now=time.time() if now is None else now
        if now>=self.next_check:
            self.next_check=now+1
            try:self.build=installed_build(self.game) if self.game else None
            except (OSError,ValueError,TypeError,KeyError):self.build=None
            try:self.inventory=read_inventory(self.directory)
            except Exception:self.inventory={'unavailable':True}
        reset_check=(service.schedule or {}).get('reset_check',{})
        verification=self.verification.evaluate(self.build,service.schedule,now,service.fetched_at,bool(service.note),reset_check)
        if verification['build_changed']:service.attempted_at=-float('inf')
        view=service.tick(enabled,now,refresh_interval=600,force_refresh=verification['needs_resync'],retry_interval=120)
        reset_check=(service.schedule or {}).get('reset_check',{})
        verification=self.verification.evaluate(self.build,service.schedule,now,service.fetched_at,bool(service.note),reset_check)
        self.view=view
        if not enabled:return
        svg=card_svg(view,self.inventory,verification)
        if svg!=self.last_key:
            raw=render_png(svg,WIDTH*2,HEIGHT*2);path=self.directory/'hangar_hud.png';temporary=path.with_suffix('.png.tmp')
            temporary.write_bytes(raw);os.replace(temporary,path);self.last_key=svg
        publish_json(self.directory/'hangar_hud.json',dict(at=now,owner_pid=self.owner,community_synced=verification['community_synced'],reason=verification['reason'],phase=(view or {}).get('phase'),complete_sets=(self.inventory or {}).get('complete_sets')))
