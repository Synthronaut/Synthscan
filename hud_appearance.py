"""Original HUD painting restored from the pre-change project backup.

Field order, fonts, palette, pills, and chamfered outline retain the original
design. Optional compact mode reduces spacing and fits the window to its text.
Data and health remain owned by the current controller; this
module neither acquires metrics nor substitutes estimates for missing readings.
"""
from displayinfo_reader import translate_region


def render_original_bar(self):
    if not self.bar_canvas:
        return

    s = dict(self.state)
    for key in ("shard_pop", "srv_pop", "entities", "restarts"):
        if s.get(key) is not None:
            s[key] = int(s[key])
    game_running = s.get("connection_status") != "game_closed"
    shard_id = s.get("shard_id", "--") if game_running else "--"
    is_connected = bool(s.get("session_token"))
    sfps = s.get("server_fps") if is_connected else None
    cfps = s.get("client_fps")
    ping = s.get("ping_ms") if is_connected else None
    packet_ping = (s.get("metric_meta", {}).get("ping_ms") or {}).get("source") == "game_udp_ping_pong"
    rst = s.get("restarts") if is_connected else None
    shard_pop = s.get("shard_pop") if is_connected else None
    srv_pop = s.get("srv_pop") if is_connected else None
    ent = s.get("entities") if is_connected else None
    srv_id = s.get("srv_id", "--")
    srv_name = s.get("server_name", "--")
    callsign = s.get("callsign", "AWAITING TELEMETRY") if is_connected else "MAIN MENU"
    reg_raw = s.get("region_raw", "")
    loc_display = s.get("location_display", "--") if is_connected else "MAIN MENU"

    cache_key = (
        game_running, is_connected, sfps, cfps, ping, packet_ping, rst, ent,
        shard_pop, srv_pop, shard_id, srv_id, srv_name, callsign,
        reg_raw, loc_display, self.bar_width,
        s.get("hop_status"), s.get("region_shards_seen"), s.get("health", {}).get("label")
    )
    if getattr(self, "_last_rendered_key", None) == cache_key:
        return
    self._last_rendered_key = cache_key

    c = self.bar_canvas
    c.delete("all")
    w, h = self.bar_width, self.BAR_HEIGHT

    # 1. Sleek Aerospace Chamfered Ribbon (45-degree corner chamfers on bottom, flush at top y=0)
    chamfer = 6
    points = [
        0, 0,
        w, 0,
        w, h - chamfer,
        w - chamfer, h,
        chamfer, h,
        0, h - chamfer
    ]
    c.create_polygon(points, fill="#070a0f", outline="#1e293b", width=1)
    # Subtle slate bottom bezel line & aerospace tick marks
    c.create_line(chamfer, h - 1, w - chamfer, h - 1, fill="#1e293b", width=1)
    c.create_line(16, h - 1, 48, h - 1, fill="#334155", width=1)
    c.create_line(w - 48, h - 1, w - 16, h - 1, fill="#334155", width=1)

    # Color-coded critical telemetry
    if sfps is not None:
        sfps_txt = f"SRV FPS: {sfps:.1f}"
        if sfps <= 5.0:
            sfps_col = "#ff2e55"
            sfps_bg = "#26080e"
            sfps_bdr = "#dc2626"
        elif sfps >= 25.0:
            sfps_col = "#22c55e"
            sfps_bg = "#042312"
            sfps_bdr = "#16a34a"
        else:
            sfps_col = "#f59e0b"
            sfps_bg = "#261805"
            sfps_bdr = "#d97706"

    cfps = s.get("client_fps")

    srv_id = s.get("srv_id", "--")
    srv_name = s.get("server_name", "--")
    hop_status = s.get("hop_status", "")
    reg_seen = s.get("region_shards_seen", 0)

    ping = s.get("ping_ms") if is_connected else None
    if ping is None:
        ping_txt = "-- ms"
        ping_col = "#64748b"
    else:
        ping_txt = f"{ping:.1f}ms" if packet_ping else f"{ping:.0f}ms"
        if ping < 100:
            ping_col = "#22c55e"
        elif ping < 200:
            ping_col = "#f59e0b"
        else:
            ping_col = "#ff2e55"

    rst = s.get("restarts") if is_connected else None
    if rst is None:
        rst_txt = "--"
        rst_col = "#64748b"
    else:
        rst_txt = str(rst)
        rst_col = "#22c55e" if rst == 0 else ("#f59e0b" if rst <= 2 else "#ff2e55")

    # Live Server Population & Shard Population
    shard_pop = s.get("shard_pop") if is_connected else None
    srv_pop = s.get("srv_pop") if is_connected else None
    if is_connected and (shard_pop is not None or srv_pop is not None):
        if shard_pop is not None and srv_pop is not None:
            pop_txt = f"{shard_pop} (SRV: {srv_pop})"
        elif shard_pop is not None:
            pop_txt = f"{shard_pop}"
        else:
            pop_txt = f"SRV: {srv_pop}"

        if shard_pop is not None:
            if shard_pop < 85:
                pop_col = "#38bdf8"
            elif shard_pop < 98:
                pop_col = "#f59e0b"
            else:
                pop_col = "#ef4444"
        else:
            pop_col = "#38bdf8"
    else:
        pop_txt = "--"
        pop_col = "#64748b"

    # Values have already passed the controller's session and freshness checks.
    # Never revive an expired value directly from the log reader here.
    ent_txt = f"{ent:,}" if ent is not None else "--"

    # Display server callsign, last shard, and region
    if is_connected:
        callsign = s.get("callsign", "AWAITING TELEMETRY")
        shard_str = f"SHARD {shard_id}"
        if srv_name != "--":
            shard_str += f" [{srv_name}]"
        elif srv_id != "--":
            shard_str += f" [SRV {srv_id}]"
        reg_txt = s.get("region_display", "--")
        reg_lbl_str = "REG:"
        reg_code = (s.get("region_raw") or "").lower()
        loc_txt = s.get("location_display", "--")
    else:
        callsign = "MAIN MENU"
        last_info = self.shard_tracker.get_last_visited()
        if last_info:
            last_cs = last_info.get("name") or last_info.get("callsign") or f"SHARD {last_info.get('shard_id', '--')}"
            last_reg = last_info.get("region_raw") or last_info.get("region", "")
            shard_str = f"LAST: {last_cs}"
            reg_txt = translate_region(last_reg)
            reg_lbl_str = "LAST REG:"
            reg_code = (last_reg or "").lower()
        else:
            shard_str = "STANDBY"
            reg_txt = "--"
            reg_lbl_str = "LAST REG:"
            reg_code = ""
        loc_txt = "MAIN MENU"

    x = 8
    cy = h // 2

    def _sep(xpos):
        c.create_line(xpos, 5, xpos, h - 5, fill="#1c2836", width=1)
        return xpos + (8 if self.compact else 12)

    # Missing telemetry occupies no space and never becomes a green health claim.
    if sfps is not None:
        sfps_tid = c.create_text(x + 20, cy, text=sfps_txt, anchor="w", fill=sfps_col, font=("Consolas", 9, "bold"))
        tb = c.bbox(sfps_tid)
        sfps_w = (tb[2] - tb[0]) if tb else 85
        pill_w = 24 + sfps_w + 12
        c.create_rectangle(x, 3, x + pill_w, h - 4, fill=sfps_bg, outline=sfps_bdr, width=1)
        c.tag_raise(sfps_tid)
        c.create_oval(x + 6, cy - 3, x + 12, cy + 3, fill=sfps_col, outline="")
        x = _sep(x + pill_w + 8)

    # Local frame presentation has an independent source and needs no server FPS.
    if cfps is not None:
        label = c.create_text(x, cy, text="PLAYER FPS:", anchor="w", fill="#64748b", font=("Consolas", 8, "bold"))
        bounds = c.bbox(label)
        x = (bounds[2] + 4) if bounds else x + 80
        value = c.create_text(x, cy, text=f"{cfps:.0f}", anchor="w", fill="#cbd5e1", font=("Consolas", 9, "bold"))
        bounds = c.bbox(value)
        x = _sep((bounds[2] + 8) if bounds else x + 40)

    # Show a badge only for an observed symptom, not a permanent health box.
    hlth = s.get("health") or {}
    if hlth.get("status") in ("DISCONNECTED", "RECOVERING", "STALLED", "SLOW", "PACKET_LOSS", "LATENCY"):
        h_label = hlth["label"]
        tmp_h = c.create_text(0, 0, text=h_label, font=("Consolas", 8, "bold"))
        hb = c.bbox(tmp_h)
        c.delete(tmp_h)
        h_w = ((hb[2] - hb[0]) + 16) if hb else (len(h_label) * 6 + 16)
        c.create_rectangle(x, 3, x + h_w, h - 4, fill=hlth["bg_color"], outline=hlth["border_color"], width=1)
        c.create_text(x + h_w // 2, cy, text=h_label, anchor="center", fill=hlth["color"], font=("Consolas", 8, "bold"))
        x = _sep(x + h_w + 8)

    # Segment B: Server Callsign / Shard Identifier
    lbl_id = c.create_text(x, cy, text="SERVER:", anchor="w", fill="#64748b", font=("Consolas", 8, "bold"))
    bbox = c.bbox(lbl_id)
    x = (bbox[2] + 4) if bbox else (x + 46)

    # Check if user set a custom nickname (e.g. "AEGIS", "PHANTOM BLADE")
    has_custom_callsign = bool(is_connected and callsign and not callsign.startswith("SHARD ") and callsign not in ("AWAITING TELEMETRY", "MAIN MENU"))
    if has_custom_callsign:
        cs_id = c.create_text(x, cy, text=callsign, anchor="w", fill="#cbd5e1", font=("Consolas", 8, "bold"))
        bbox = c.bbox(cs_id)
        x = (bbox[2] + 8) if bbox else (x + 105)
        x = _sep(x)
        sh_item = c.create_text(x, cy, text=shard_str, anchor="w", fill="#94a3b8", font=("Consolas", 8, "bold"))
        bbox = c.bbox(sh_item)
        x = (bbox[2] + 8) if bbox else (x + 140)
    else:
        # Clean unified server string: "SHARD 200 [GAME-7]" or "SHARD 200" (no duplicate "SHARD 200" stutter!)
        display_srv = shard_str if is_connected else callsign
        cs_id = c.create_text(x, cy, text=display_srv, anchor="w", fill="#cbd5e1", font=("Consolas", 8, "bold"))
        bbox = c.bbox(cs_id)
        x = (bbox[2] + 8) if bbox else (x + 105)

    if is_connected and shard_id != "--" and hop_status:
        is_new = "NEW" in hop_status
        h_col = "#38bdf8" if is_new else "#94a3b8"
        h_bg = "#0d131a"
        h_bdr = "#1e293b"
        badge_txt = f"{hop_status} | {reg_seen} SEEN" if reg_seen > 0 else hop_status
        tmp_t = c.create_text(0, 0, text=badge_txt, font=("Consolas", 8, "bold"))
        tb = c.bbox(tmp_t)
        c.delete(tmp_t)
        bw = ((tb[2] - tb[0]) + 10) if tb else (len(badge_txt) * 6 + 10)
        c.create_rectangle(x, 4, x + bw, h - 5, fill=h_bg, outline=h_bdr, width=1)
        c.create_text(x + bw // 2, cy, text=badge_txt, anchor="center", fill=h_col, font=("Consolas", 8, "bold"))
        x += bw + 8

    x = _sep(x)

    # Segment D: Region (Color-Coded: Asia=Dark Red, US=Blue, Europe=Gray, Australia=Yellow)
    reg_txt_low = reg_txt.lower()
    if "apse2" in reg_code or "aus" in reg_txt_low or "syd" in reg_txt_low:
        reg_col = "#eab308"  # Australia -> Yellow
    elif any(k in reg_code for k in ("ape", "apne", "apse", "asia")) or "asia" in reg_txt_low or "apac" in reg_txt_low:
        reg_col = "#dc2626"  # Asia -> Dark Red
    elif any(k in reg_code for k in ("use", "usw", "usc", "us")) or "us (" in reg_txt_low or "us-" in reg_txt_low or "usa" in reg_txt_low:
        reg_col = "#38bdf8"  # USA -> Blue
    elif any(k in reg_code for k in ("euw", "euc", "eu")) or "eu (" in reg_txt_low or "eu-" in reg_txt_low or "europe" in reg_txt_low:
        reg_col = "#94a3b8"  # Europe -> Gray
    else:
        reg_col = "#cbd5e1"

    region_left = x
    r_lbl = c.create_text(x, cy, text=reg_lbl_str, anchor="w", fill="#64748b", font=("Consolas", 8, "bold"))
    bbox = c.bbox(r_lbl)
    x = (bbox[2] + 4) if bbox else (x + 26)
    region_value_x = x
    # Keep the original colored region label on the ribbon itself. Only the
    # chevron needs a separate interactive window when the ribbon is locked.
    r_val = c.create_text(x, cy, text=reg_txt, anchor="w", fill=reg_col, font=("Consolas", 8, "bold"))
    bbox = c.bbox(r_val)
    x = (bbox[2] + 8) if bbox else (x + 95)
    if hasattr(self,'region_history'):
        arrow_left=x
        arrow=c.create_text(x,cy,text='▾',anchor='w',fill=reg_col,font=('Consolas',8,'bold'))
        bbox=c.bbox(arrow);x=(bbox[2]+8) if bbox else x+18
        self.region_hit=dict(left=arrow_left,right=x,value_x=0,label='',text='▾',color=reg_col,
                             region_text=reg_txt)
    x = _sep(x)

    # Segment POP: Population (Shard Population & Local Node Server Population)
    if is_connected and pop_txt != "--":
        pop_lbl = c.create_text(x, cy, text="POP:", anchor="w", fill="#64748b", font=("Consolas", 8, "bold"))
        bbox = c.bbox(pop_lbl)
        x = (bbox[2] + 4) if bbox else (x + 26)
        pop_val = c.create_text(x, cy, text=pop_txt, anchor="w", fill=pop_col, font=("Consolas", 8, "bold"))
        bbox = c.bbox(pop_val)
        x = (bbox[2] + 8) if bbox else (x + 65)
        x = _sep(x)

    # Segment E: Only a fresh measured ping, never a placeholder.
    if ping is not None:
        p_lbl = c.create_text(x, cy, text="NET RTT:" if packet_ping else "PING:", anchor="w", fill="#64748b", font=("Consolas", 8, "bold"))
        bbox = c.bbox(p_lbl)
        x = (bbox[2] + 4) if bbox else (x + 30)
        p_val = c.create_text(x, cy, text=ping_txt, anchor="w", fill=ping_col, font=("Consolas", 9, "bold"))
        bbox = c.bbox(p_val)
        x = (bbox[2] + 8) if bbox else (x + 44)
        x = _sep(x)

    # Segment F: Restarts (Color Coded)
    if is_connected and rst_txt != "--":
        rst_lbl = c.create_text(x, cy, text="RST:", anchor="w", fill="#64748b", font=("Consolas", 8, "bold"))
        bbox = c.bbox(rst_lbl)
        x = (bbox[2] + 4) if bbox else (x + 26)
        rst_val = c.create_text(x, cy, text=rst_txt, anchor="w", fill=rst_col, font=("Consolas", 9, "bold"))
        bbox = c.bbox(rst_val)
        x = (bbox[2] + 8) if bbox else (x + 20)
        x = _sep(x)

    # Segment G: Fresh entities only, with no fallback to old log values.
    if ent is not None:
        e_lbl = c.create_text(x, cy, text="ENT:", anchor="w", fill="#64748b", font=("Consolas", 8, "bold"))
        bbox = c.bbox(e_lbl)
        x = (bbox[2] + 4) if bbox else (x + 26)
        e_val = c.create_text(x, cy, text=ent_txt, anchor="w", fill="#cbd5e1", font=("Consolas", 8, "bold"))
        bbox = c.bbox(e_val)
        x = (bbox[2] + 8) if bbox else (x + 48)
        x = _sep(x)

    # Logs provide a last-known location hint, not continuous player tracking.
    if is_connected and loc_txt not in ("--", "UNKNOWN", ""):
        l_lbl = c.create_text(x, cy, text="LAST LOC:", anchor="w", fill="#64748b", font=("Consolas", 8, "bold"))
        bbox = c.bbox(l_lbl)
        x = (bbox[2] + 4) if bbox else (x + 60)
        l_val = c.create_text(x, cy, text=loc_txt, anchor="w", fill="#38bdf8", font=("Consolas", 8, "bold"))
        bbox = c.bbox(l_val)
        x = (bbox[2] + 8) if bbox else (x + 70)

    # Saved medical text has no verified automatic source. It belongs in the
    # app's manual notes, never in this ribbon as the player's active imprint.
    self._content_width = x + 4
