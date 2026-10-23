"""Render the real HUD painter to a labelled offline layout preview, without game input."""
import html
from pathlib import Path
import sys
import tkinter as tk

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hud_layout import panel_rows
from hud_panel import paint_panel
from radar_db import parse_signature


class SvgCanvas:
    def __init__(self):
        self.items=[]
    def delete(self,target):
        self.items=[]
    def create_rectangle(self,x,y,right,bottom,**options):
        self.items.append(f'<rect x="{x}" y="{y}" width="{right-x}" height="{bottom-y}" fill="{options.get("fill","none")}" stroke="{options.get("outline","none")}"/>')
    def create_line(self,x,y,right,bottom,**options):
        self.items.append(f'<path d="M{x},{y} L{right},{bottom}" stroke="{options.get("fill","none")}" stroke-width="{options.get("width",1)}"/>')
    def create_text(self,x,y,**options):
        family,size,weight=options['font']
        self.items.append(f'<text x="{x}" y="{y}" dominant-baseline="central" font-family="{family}" font-size="{abs(size)}" font-weight="{weight}" fill="{options["fill"]}">{html.escape(options["text"])}</text>')


def main():
    root=tk.Tk();root.withdraw()
    measure_canvas=tk.Canvas(root)
    def measure(text,font):
        item=measure_canvas.create_text(0,0,text=text,font=font)
        box=measure_canvas.bbox(item)
        measure_canvas.delete(item)
        return box[2]-box[0] if box else 0
    state=dict(session_token='example',shard_id='020',callsign='SHARD 020',region_display='Asia (Hong Kong)',
               server_name='--',hop_status='RETURN #2 · Last visit 42m ago',location_display='CRU-L1 Ambitious Dream Station',
               client_fps=68,ping_ms=12.5,health=dict(status='UNKNOWN'),metric_meta=dict(ping_ms=dict(source='game_udp_ping_pong')))
    match=parse_signature(3370);match['ocr_confidence']=.96
    scan=dict(match=match,signature=3370,observed_at=100,session_token='example')
    panels=[]
    for x,enabled,title in [(28,False,'SESSION DETAILS'),(452,True,'SESSION + MINING RESULT')]:
        canvas=SvgCanvas()
        paint_panel(canvas,panel_rows(state,scan,now=101,mining_enabled=enabled),1,measure)
        panels.append(f'<text x="{x}" y="90" font-size="12" fill="#94a3b8">{title}</text><g transform="translate({x},110)">'+''.join(canvas.items)+'</g>')
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="872" height="410"><rect width="872" height="410" fill="#0b1016"/><g font-family="Bahnschrift"><text x="28" y="35" font-size="23" fill="#f1f5f9">SynthScan HUD</text><text x="28" y="59" font-size="13" fill="#94a3b8">Layout preview · example readings, not live telemetry</text>'+''.join(panels)+'</g></svg>'
    directory=ROOT/'research'
    (directory/'hud_workspace_preview.svg').write_text(svg,encoding='utf-8')
    import resvg_py
    (directory/'hud_workspace_preview.png').write_bytes(resvg_py.svg_to_bytes(svg_string=svg))
    root.destroy()
    print(directory/'hud_workspace_preview.png')


if __name__=='__main__':main()
