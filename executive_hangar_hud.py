"""Optional passive five-light strip, rendered from the same SVG used for QA."""
from datetime import datetime
from html import escape
from pathlib import Path
import os,re,time
from executive_hangar import countdown

WIDTH,HEIGHT=430,94
COLORS={'green':'#4ade80','red':'#fb7185','empty':'#111827'}


def hangar_position(bar,bounds,width=WIDTH,height=HEIGHT):
    x,y,w,h=bar;left=bounds['left'];top=bounds['top'];right=left+bounds['width'];bottom=top+bounds['height']
    factor=min(1,bounds['width']/width,bounds['height']/height);width=max(1,round(width*factor));height=max(1,round(height*factor))
    x=max(left,min(x+(w-width)//2,right-width));y=y+h+4
    if y+height>bottom:y=bar[1]-height-4
    return int(x),int(max(top,min(y,bottom-height))),width,height


def hangar_svg(view,inventory=None):
    if view is None:
        title='PYAM · WAITING';primary='Schedule unavailable';lights=['empty']*5;secondary='Waiting for timer sync';footer='Schedule estimate · no hangar availability feed'
    else:
        phase=view['phase'];title='PYAM · '+{'charging':'CHARGING','open':'OPEN WINDOW','reset':'RESET'}[phase]
        primary={'charging':'Opens ','open':'Closes ','reset':'Charges in '}[phase]+countdown(view['remaining_ms'])
        lights=view['lights'];secondary='Next light '+countdown(view['light_remaining_ms'])
        if phase=='reset':secondary='Next opening '+datetime.fromtimestamp(view['next_open_ms']/1000).strftime('%H:%M')+' local'
        date=view.get('source_modified','')
        try:date=datetime.strptime(date,'%Y-%m-%d').strftime('%d %b')
        except ValueError:date='undated'
        patch=view.get('patch','').removesuffix('-LIVE')
        footer='Schedule estimate · sync '+date+(' · '+patch if patch else '')
        if view.get('refresh_error'):footer='Saved schedule · sync '+date+' · refresh pending'
    accent='#4ade80' if view is not None and view['phase']=='open' else '#fbbf24'
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
         f'<rect x="0.5" y="0.5" width="429" height="{HEIGHT-1}" rx="6" fill="#0b111a" stroke="#334155"/>',
         f'<text x="12" y="19" fill="{accent}" font-family="Segoe UI" font-weight="600" font-size="12">{escape(title)}</text>',
         f'<text x="418" y="19" text-anchor="end" fill="#e2e8f0" font-family="Consolas" font-size="13">{escape(primary)}</text>']
    for i,color in enumerate(lights):
        x=21+i*25;stroke='#475569' if color=='empty' else COLORS[color];ink='#94a3b8' if color=='empty' else '#071015'
        svg.append(f'<circle cx="{x}" cy="39" r="7" fill="{COLORS[color]}" stroke="{stroke}"/>')
        svg.append(f'<text x="{x}" y="42" text-anchor="middle" font-family="Consolas" font-size="8" font-weight="bold" fill="{ink}">{i+1}</text>')
    svg.extend([f'<text x="151" y="43" fill="#cbd5e1" font-family="Consolas" font-size="12">{escape(secondary)}</text>',
                f'<text x="12" y="61" fill="#94a3b8" font-family="Segoe UI" font-size="10">{escape(footer)}</text>',
                '<path d="M10 68H420" stroke="#263446"/>'])
    if inventory is not None and inventory.get('unavailable'):
        svg.append('<text x="12" y="84" fill="#fbbf24" font-family="Segoe UI" font-size="10">Board counts unavailable · open Compboard inventory</text>')
    else:
        counts=(inventory or {}).get('counts',[0]*7);sets=min(counts)
        svg.append('<text x="12" y="84" fill="#94a3b8" font-family="Segoe UI" font-size="9">Boards</text>')
        for i,n in enumerate(counts):
            x=50+i*43;ink='#a7f3d0' if n else '#94a3b8';fill='#12332c' if n else '#1b2635'
            svg.extend([f'<rect x="{x}" y="73" width="39" height="16" rx="3" fill="{fill}"/>',
                        f'<text x="{x+19.5}" y="84" text-anchor="middle" fill="{ink}" font-family="Consolas" font-size="9">{i+1}:{n}</text>'])
        svg.append(f'<text x="418" y="84" text-anchor="end" fill="#e2e8f0" font-family="Consolas" font-size="10">{sets} '+('set' if sets==1 else 'sets')+'</text>')
    svg.append('</svg>')
    return ''.join(svg)


def render_png(svg,width=None,height=None):
    import resvg_py
    fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    files=[str(fonts/name) for name in ['segoeui.ttf','segoeuil.ttf','seguisb.ttf','consola.ttf','consolab.ttf'] if (fonts/name).exists()]
    return resvg_py.svg_to_bytes(svg_string=svg,font_files=files,skip_system_fonts=bool(files),width=width,height=height)


class ExecutiveHangarHUD:
    def __init__(self,root,directory=None):
        import tkinter as tk
        import ctypes
        from ctypes import wintypes as w
        self.window=tk.Toplevel(root);self.window.withdraw();self.window.overrideredirect(True)
        self.window.title('SynthScan Executive Hangar Timer');self.window.attributes('-topmost',True)
        self.canvas=tk.Canvas(self.window,width=WIDTH,height=HEIGHT,bg='#0b111a',highlightthickness=0,bd=0)
        self.canvas.pack(fill='both',expand=True);self.window.update_idletasks()
        api=ctypes.windll.user32;api.GetParent.argtypes=[w.HWND];api.GetParent.restype=w.HWND
        self.hwnd=api.GetParent(self.window.winfo_id()) or self.window.winfo_id()
        api.GetWindowLongW.argtypes=[w.HWND,ctypes.c_int];api.SetWindowLongW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_long]
        api.SetWindowLongW(self.hwnd,-20,api.GetWindowLongW(self.hwnd,-20)|0x80000|0x80|0x08000000|0x20)
        api.SetLayeredWindowAttributes.argtypes=[w.HWND,w.DWORD,w.BYTE,w.DWORD];api.SetLayeredWindowAttributes(self.hwnd,0,240,2)
        api.SetWindowDisplayAffinity.argtypes=[w.HWND,w.DWORD];api.SetWindowDisplayAffinity(self.hwnd,0x11)
        self.visible=False;self.geometry=None;self.last_svg=None;self.image=None;self.item=None;self.view=None
        self.directory=directory;self.inventory=None;self.inventory_checked=-float('inf')
    def follow(self,ribbon,bounds):
        if not self.visible:return
        import ctypes
        from ctypes import wintypes as w
        match=re.fullmatch(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)',getattr(ribbon,'_last_geometry','') or '')
        if not match:return
        bar=(int(match[3]),int(match[4]),int(match[1]),int(match[2]));geometry=hangar_position(bar,bounds)
        if geometry!=self.geometry:
            x,y,width,height=geometry;self.window.geometry(f'{width}x{height}')
            api=ctypes.windll.user32;api.SetWindowPos.argtypes=[w.HWND,w.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.UINT]
            api.SetWindowPos(self.hwnd,w.HWND(-1),x,y,width,height,0x10|0x40);self.geometry=geometry
    def sync(self,ribbon,enabled,view,bounds):
        visible=bool(enabled and getattr(ribbon,'_visible',False) and not getattr(getattr(ribbon,'region_history',None),'open',False))
        self.view=view
        if not visible:
            if self.visible:self.window.withdraw()
            self.visible=False;return
        if self.directory is not None and time.monotonic()-self.inventory_checked>=1:
            from compboard_inventory import read_inventory
            self.inventory_checked=time.monotonic()
            try:self.inventory=read_inventory(self.directory)
            except Exception:self.inventory={'unavailable':True}
        svg=hangar_svg(view,self.inventory);target=hangar_position((0,0,WIDTH,0),bounds)[2:];key=(svg,target)
        if key!=self.last_svg:
            import tkinter as tk
            self.image=tk.PhotoImage(master=self.window,data=render_png(svg,*target),format='png')
            if self.item is None:self.item=self.canvas.create_image(0,0,anchor='nw',image=self.image)
            else:self.canvas.itemconfigure(self.item,image=self.image)
            self.last_svg=key
        if not self.visible:self.window.deiconify();self.geometry=None
        self.visible=True;self.follow(ribbon,bounds)
        from overlay_input import set_passthrough
        set_passthrough(self.hwnd,True)
    def close(self):self.window.destroy()
