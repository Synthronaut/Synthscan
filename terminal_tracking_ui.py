"""Terminal capture controls and refinery history, within the existing vault page."""
import customtkinter as ctk
from refinery_orders import RefineryOrderBook


class TerminalTrackingPanel(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color='#1e222a', corner_radius=6)
        self.app = app
        self.pack(fill='x', pady=(0, 10), before=parent.winfo_children()[0] if parent.winfo_children() else None)
        row = ctk.CTkFrame(self, fg_color='transparent')
        row.pack(fill='x', padx=12, pady=8)
        self.watch = ctk.CTkSwitch(row, text='Watch refinery / fabricator screens', command=self.toggle)
        self.watch.pack(side='left')
        if app.terminal_tracking:
            self.watch.select()
        self.station = ctk.CTkEntry(row, placeholder_text='Refinery station (if not read on screen)', width=270)
        self.station.pack(side='left', padx=12)
        self.station.insert(0, app.terminal_station)
        self.station.bind('<KeyRelease>', self.set_station)
        ctk.CTkButton(row, text='Work orders', width=110, command=self.open_orders).pack(side='right')
        self.status = ctk.CTkLabel(self, text='Passive capture: terminal must be visible. Two agreeing reads confirm an order. Finished stock stays at its refinery.',
                                   text_color='#929eb1', anchor='w', wraplength=900, justify='left')
        self.status.pack(fill='x', padx=12, pady=(0, 8))

    def toggle(self):
        self.app.terminal_tracking = bool(self.watch.get())
        self.app.cfg['terminal_tracking'] = self.app.terminal_tracking
        from config import save_config
        save_config(self.app.cfg)

    def set_station(self, event=None):
        self.app.terminal_station = self.station.get().strip()
        # Avoid saving configuration on every keystroke while a player is typing.

    def open_orders(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title('Refinery work orders')
        dialog.geometry('820x640')
        ctk.CTkLabel(dialog, text='REFINERY WORK ORDERS', font=('Bahnschrift', 23, 'bold')).pack(anchor='w', padx=20, pady=(18, 5))
        ctk.CTkLabel(dialog, text='Completion is confirmed at the terminal. Timers are estimates. Partial scans may omit materials.\nCollected stock is not automatically added to the cargo vault.',
                     justify='left', text_color='#929eb1').pack(anchor='w', padx=20, pady=6)
        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.pack(fill='both', expand=True, padx=16, pady=12)
        def refresh():
            for child in scroll.winfo_children():
                child.destroy()
            rows = self.app.refinery_orders.snapshot()
            if not rows:
                ctk.CTkLabel(scroll, text='No confirmed orders yet. Browse your processing/completed terminal panels.').pack(pady=35)
            for order in rows:
                card = ctk.CTkFrame(scroll, fg_color='#262b35')
                card.pack(fill='x', padx=4, pady=5)
                ctk.CTkLabel(card, text=f"{order['station']}  ·  Order {order['number']}  ·  {order['display_status']}",
                             font=('Bahnschrift', 16, 'bold'), anchor='w').pack(fill='x', padx=12, pady=8)
                for part in order['parts']:
                    ctk.CTkLabel(card, text=f"{part['material']}  ·  {part['scu']:g} SCU  ·  Quality {part['quality']}", anchor='w').pack(fill='x', padx=12, pady=2)
                ctk.CTkLabel(card, text=f"First seen: {order['first_seen']}\nLast seen: {order['last_seen']}", anchor='w', justify='left', text_color='#929eb1').pack(fill='x', padx=12, pady=8)
                if order['status'] == 'completed' and not order.get('collected_at'):
                    ctk.CTkButton(card, text='I collected this order', command=lambda key=order['id']: collect(key)).pack(anchor='w', padx=12, pady=(0, 10))
                elif order.get('collected_at') and not order.get('archived'):
                    ctk.CTkButton(card, text='Archive / allow this order number again', command=lambda key=order['id']: archive(key)).pack(anchor='w', padx=12, pady=(0, 10))
        def collect(key):
            self.app.refinery_orders.mark_collected(key)
            refresh()
        def archive(key):
            self.app.refinery_orders.archive_for_reuse(key)
            refresh()
        ctk.CTkButton(dialog, text='Refresh orders', command=refresh).pack(pady=(0, 14))
        refresh()
