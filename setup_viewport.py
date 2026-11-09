"""Scrollable first-run panels that fit smaller displays without global input hooks."""
import tkinter as tk
from tkinter import ttk


def size(window,width,height):
    available_width=max(420,window.winfo_screenwidth()-80)
    available_height=max(360,window.winfo_screenheight()-100)
    window.geometry(f'{min(width,available_width)}x{min(height,available_height)}')
    window.minsize(min(760,available_width),min(560,available_height))


def panel(window,padding=28):
    host=ttk.Frame(window);host.pack(fill='both',expand=True)
    canvas=tk.Canvas(host,bg='#101820',highlightthickness=0,bd=0)
    bar=ttk.Scrollbar(host,orient='vertical',command=canvas.yview);bar.pack(side='right',fill='y')
    canvas.configure(yscrollcommand=bar.set);canvas.pack(side='left',fill='both',expand=True)
    outer=ttk.Frame(canvas,padding=padding);item=canvas.create_window((0,0),window=outer,anchor='nw')
    outer.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
    def wheel(event):canvas.yview_scroll(-int(event.delta/120),'units');return 'break'
    def bind_widgets(widget):
        widget.bind('<MouseWheel>',wheel)
        for child in widget.winfo_children():bind_widgets(child)
    window.after_idle(lambda:bind_widgets(host))
    return outer
