"""Clean SynthScan panel painter shared by the HUD and its in-app preview."""

COLORS = dict(title='#f1f5f9', body='#cbd5e1', muted='#94a3b8', visit='#9ed5d2',
              metric='#c8e7f4', warning='#efb66a', edit='#e9c677', section='#9ed5d2')
HEIGHTS = dict(title=27, body=22, muted=21, visit=22, metric=24, warning=23, edit=25, section=30)


def panel_size(rows, scale=1):
    return round(392*scale), round((32+sum(HEIGHTS[r['role']] for r in rows)+10)*scale)


def paint_panel(canvas, rows, scale=1, measure=None):
    """Return actual size. Fixed row extents and measured elision prevent clipping."""
    width, height = panel_size(rows,scale)
    canvas.delete('all')
    canvas.create_rectangle(1,1,width-1,height-1,fill='#131a22',outline='#34424f',width=1)
    canvas.create_line(12*scale,1,width-12*scale,1,fill='#6b9796',width=2)
    def font(role):
        size = 16 if role=='title' else 11 if role=='brand' else 12
        return ('Bahnschrift',-max(8,round(size*scale)), 'bold' if role in ('title','brand') else 'normal')
    def fit(text, role):
        spec = font(role)
        probe = None
        if measure:
            length = lambda value: measure(value,spec)
        else:
            # Measure the actual canvas font. Named font measurements can round
            # differently at small pixel sizes on mixed-DPI Windows displays.
            probe = canvas.create_text(0,0,text='',font=spec,anchor='w')
            def length(value):
                canvas.itemconfigure(probe,text=value)
                box = canvas.bbox(probe)
                return box[2]-box[0] if box else 0
        available = width-28*scale
        try:
            if length(text)<=available:
                return text
            lo, hi = 0,len(text)
            while lo<hi:
                mid=(lo+hi+1)//2
                if length(text[:mid]+'…')<=available:
                    lo=mid
                else:
                    hi=mid-1
            return text[:lo]+'…'
        finally:
            if probe is not None:
                canvas.delete(probe)
    canvas.create_text(14*scale,16*scale,text='SYNTHSCAN',anchor='w',fill='#9ed5d2',font=font('brand'))
    y = 32*scale
    for row in rows:
        role = row['role']
        extent = HEIGHTS[role]*scale
        if role=='section':
            canvas.create_line(14*scale,y+2*scale,width-14*scale,y+2*scale,fill='#34424f')
        canvas.create_text(14*scale,y+extent/2,text=fit(row['text'],role),anchor='w',
                           fill=COLORS[role],font=font(role))
        y += extent
    return width,height
