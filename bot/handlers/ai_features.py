import asyncio, json, re, time, logging, httpx, collections
from telegram import Update
from telegram.ext import ContextTypes
from bot import database as D
from bot.config import CE
from bot.keyboards import btn, kb, back, M, grid, web_btn
from bot.utils.ai import ask, ask_json, LANGNAME
from bot.utils.fonts import sc, em, mention, fmt
from bot.utils.ui import send, show, toast, ready, esc
log = logging.getLogger("features")

def _args(ctx): return ctx.args or []
def _lang(db): return LANGNAME.get((db or {}).get("lang") or "en", "English")

async def _gate(update, ctx):
    if await D.ai_gate(update.effective_user.id): return True
    await show(update, ctx, f"⛔ {sc('Daily free AI limit reached')}\n{sc('Upgrade to Premium for unlimited use.')}",
               kb([btn("Premium", "menu:premium", CE["premium"], "success")], "menu:home")); return False

def _wait(ctx, key): ctx.user_data["await"] = key

# ---------------- /dream ----------------
@ready
async def dream_cmd(update, ctx):
    if _args(ctx): return await do_dream(update, ctx, " ".join(_args(ctx)))
    _wait(ctx, "dream")
    await show(update, ctx, f"🌙 <b>{sc('Dream analyzer')}</b>\n\n{sc('Tell me your dream. I will decode it and add it to your constellation map.')}",
               kb([web_btn("Dream Map", "dream")], "menu:home"))

async def do_dream(update, ctx, text):
    if not await _gate(update, ctx): return
    db = await D.get_user(update.effective_user.id); note = await ctx.bot.send_message(update.effective_chat.id, "🌙 …")
    j = await ask_json(f"You are a warm dream analyst (Jungian + symbolic). Reply in {_lang(db)}. JSON: "
                       '{"analysis":"max 120 words","symbols":["3-6 single-word symbols, lowercase"],"mood":"one word"}', text[:3000])
    j = j if isinstance(j, dict) else {"analysis": "I could not decode this one, try again.", "symbols": [], "mood": "unknown"}
    await D.execute("INSERT INTO dreams(user_id,content,analysis,symbols,mood,created_at) VALUES(?,?,?,?,?,?)",
                    (update.effective_user.id, text[:3000], j.get("analysis", ""), json.dumps(j.get("symbols", [])), j.get("mood", ""), D.now()))
    ctx.user_data.pop("await", None)
    try: await note.delete()
    except Exception: pass
    await send(update, ctx, f"🌙 <b>{sc(j.get('mood', ''))}</b>\n\n{esc(j.get('analysis'))}\n\n✨ {', '.join(esc(s) for s in j.get('symbols', []))}",
               kb([web_btn("Dream Map", "dream")], "menu:home"))

# ---------------- /crm ----------------
@ready
async def crm_cmd(update, ctx):
    _wait(ctx, "crm")
    n = (await D.fetchone("SELECT COUNT(*) c FROM crm_events WHERE user_id=?", (update.effective_user.id,)))["c"]
    await show(update, ctx, f"🧠 <b>{sc('Relationship CRM')}</b>\n\n{sc('Paste a chat (text) or upload a Telegram JSON export. I extract birthdays, relations and key dates.')}\n\n📇 {n} {sc('saved')}",
               kb([web_btn("Open Kanban", "crm")], "menu:home"))

async def do_crm(update, ctx, text):
    if not await _gate(update, ctx): return
    uid = update.effective_user.id; note = await ctx.bot.send_message(update.effective_chat.id, "🧠 …")
    j = await ask_json("Extract people and important dates from this chat. JSON list (max 25) of "
                       '{"name":"","relation":"friend|family|partner|colleague|other","kind":"birthday|anniversary|event|other","date":"YYYY-MM-DD or MM-DD or empty","note":"short"}. '
                       "Only include what is explicitly in the text.", text[:14000], max_tokens=1500)
    items = [i for i in (j if isinstance(j, list) else []) if isinstance(i, dict) and i.get("name")]
    for i in items:
        await D.execute("INSERT INTO crm_events(user_id,name,relation,kind,date,note,created_at) VALUES(?,?,?,?,?,?,?)",
                        (uid, str(i["name"])[:60], str(i.get("relation", ""))[:20], str(i.get("kind", ""))[:20], str(i.get("date", ""))[:10], str(i.get("note", ""))[:200], D.now()))
    ctx.user_data.pop("await", None)
    try: await note.delete()
    except Exception: pass
    lines = "\n".join(f"• <b>{esc(i['name'])}</b> — {esc(i.get('kind'))} {esc(i.get('date'))}" for i in items[:12]) or sc("Nothing found.")
    await send(update, ctx, f"🧠 <b>{len(items)}</b> {sc('contacts/dates saved')}\n\n{lines}", kb([web_btn("Open Kanban", "crm")], "menu:home"))

# ---------------- /clone ----------------
def parse_export(raw: bytes, uid):
    data = json.loads(raw.decode("utf-8", "ignore")); msgs = []
    chats = data["chats"]["list"] if "chats" in data else [data]
    for ch in chats:
        for m in ch.get("messages", []):
            if m.get("type") != "message": continue
            t = m.get("text", "")
            if isinstance(t, list): t = "".join(x if isinstance(x, str) else x.get("text", "") for x in t)
            if t.strip(): msgs.append((m.get("from", "?"), m.get("from_id", ""), t.strip()))
    return msgs

def style_stats(texts):
    words = [w for t in texts for w in re.findall(r"\w+", t.lower())]
    stop = set("the a an and or to of in is it i you me my we on for with that this be are was at as so but not de la le les et un une des du je tu il elle on nous vous que qui en pour pas ne se ce el los las y es lo un por con para que".split())
    top = [w for w, _ in collections.Counter(w for w in words if len(w) > 2 and w not in stop).most_common(15)]
    emoji = sum(len(re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", t)) for t in texts)
    n = max(len(texts), 1)
    return {"messages": n, "avg_words": round(len(words) / n, 1), "emoji_per_msg": round(emoji / n, 2),
            "lowercase_ratio": round(sum(t[:1].islower() for t in texts) / n, 2), "ends_with_punct": round(sum(t[-1] in ".!?" for t in texts) / n, 2),
            "exclaim_ratio": round(sum("!" in t for t in texts) / n, 2), "top_words": top}

@ready
async def clone_cmd(update, ctx):
    a = _args(ctx); uid = update.effective_user.id; db = await D.get_user(uid)
    if a and a[0] == "reset":
        await D.update_user(uid, clone_style=None); ctx.user_data.pop("clonechat", None); return await show(update, ctx, "🧬 ✅ reset", back())
    if a and a[0] == "chat" or (db["clone_style"] and ctx.user_data.get("want_chat")):
        ctx.user_data["want_chat"] = False
        if not db["clone_style"]: return await show(update, ctx, sc("Upload your export first."), back())
        _wait(ctx, "clonechat"); return await show(update, ctx, f"🧬 {sc('Clone chat ON — write anything, I answer as you. /menu to stop.')}", back())
    _wait(ctx, "clone")
    st = json.loads(db["clone_style"]) if db["clone_style"] else None
    info = f"\n\n✅ {sc('Style profile ready')}: {esc(st['summary'][:300])}" if st else ""
    b = [btn("Chat as me", "clone:chat", style="primary")] if st else []
    await show(update, ctx, f"🧬 <b>{sc('Clone')}</b>\n\n{sc('Upload your Telegram JSON export (Desktop → Export chat history → JSON).')}{info}", kb(b, "menu:home"))

async def clone_chat_cb(update, ctx):
    ctx.user_data["want_chat"] = True; await toast(update, "🧬"); await clone_cmd(update, ctx)

async def do_clone(update, ctx, msgs):
    uid = update.effective_user.id
    if not await _gate(update, ctx): return
    mine = [t for n, fid, t in msgs if fid == f"user{uid}"]
    if len(mine) < 30:      # fall back: most active sender
        top = collections.Counter(f for _, f, _ in msgs).most_common(1)
        mine = [t for _, f, t in msgs if top and f == top[0][0]]
    mine = [t for t in mine if 3 <= len(t) <= 400][-800:]
    if len(mine) < 20: return await send(update, ctx, sc("Not enough messages (need 20+)."), back())
    stats = style_stats(mine); samples = "\n".join(mine[-60:])[:6000]
    db = await D.get_user(uid)
    summary = await ask("You are a linguist. From the stats and samples, write a precise STYLE PROFILE (tone, vocabulary, slang, rhythm, emoji habits, typical openers/closers, language) in under 150 words, as instructions an AI could follow to imitate this person.",
                        f"STATS: {json.dumps(stats)}\nSAMPLES:\n{samples}", max_tokens=400, temperature=0.4)
    await D.update_user(uid, clone_style=json.dumps({"summary": summary, "stats": stats, "samples": mine[-15:]}))
    ctx.user_data.pop("await", None)
    await send(update, ctx, f"🧬 <b>{sc('Style cloned')}</b> ({stats['messages']} msgs)\n\n{esc(summary)}", kb([btn("Chat as me", "clone:chat", style="primary")], "menu:home"))

# ---------------- /whale ----------------
CG = "https://api.coingecko.com/api/v3"
KNOWN = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin", "XRP": "ripple", "DOGE": "dogecoin", "TON": "the-open-network", "ADA": "cardano", "TRX": "tron", "AVAX": "avalanche-2"}

async def cg_coin(sym):
    sym = sym.upper(); cid = KNOWN.get(sym)
    async with httpx.AsyncClient(timeout=20) as c:
        if not cid:
            r = (await c.get(f"{CG}/search", params={"query": sym})).json()
            hit = next((x for x in r.get("coins", []) if x["symbol"].upper() == sym), None)
            if not hit: return None
            cid = hit["id"]
        r = (await c.get(f"{CG}/coins/markets", params={"vs_currency": "usd", "ids": cid})).json()
    return r[0] if r else None

@ready
async def whale_cmd(update, ctx):
    uid = update.effective_user.id
    if not _args(ctx):
        subs = await D.fetchall("SELECT symbol FROM whale_subs WHERE user_id=?", (uid,)); _wait(ctx, "whale")
        return await show(update, ctx, f"🐋 <b>{sc('Whale radar')}</b>\n\n{sc('Send a ticker (BTC, ETH…) for live data + alerts.')}\n\n🔔 {', '.join(s['symbol'] for s in subs) or '—'}", back())
    await do_whale(update, ctx, _args(ctx)[0])

async def do_whale(update, ctx, sym):
    sym = re.sub(r"[^A-Za-z0-9]", "", sym).upper()[:10]; uid = update.effective_user.id
    try: c = await cg_coin(sym)
    except Exception: c = None
    if not c: return await send(update, ctx, f"🐋 {sc('Unknown or unavailable')}: {esc(sym)}", back())
    sub = await D.fetchone("SELECT 1 FROM whale_subs WHERE user_id=? AND symbol=?", (uid, sym))
    ratio = (c["total_volume"] / c["market_cap"] * 100) if c.get("market_cap") else 0
    txt = (f"🐋 <b>{sym}</b> — ${c['current_price']:,}\n24h: <b>{c['price_change_percentage_24h'] or 0:+.2f}%</b>\n"
           f"{sc('Volume')}: ${c['total_volume']:,.0f}\n{sc('Vol/MCap')}: {ratio:.1f}% {'🔥' if ratio > 10 else ''}")
    ctx.user_data.pop("await", None)
    await send(update, ctx, txt, kb([btn("🔕 Alert off" if sub else "🔔 Alert on", f"whale:sub:{sym}", style="success")], "menu:home"))

async def whale_sub_cb(update, ctx):
    uid = update.effective_user.id; sym = update.callback_query.data.split(":")[2]
    if await D.fetchone("SELECT 1 FROM whale_subs WHERE user_id=? AND symbol=?", (uid, sym)):
        await D.execute("DELETE FROM whale_subs WHERE user_id=? AND symbol=?", (uid, sym)); return await toast(update, "🔕")
    n = (await D.fetchone("SELECT COUNT(*) c FROM whale_subs WHERE user_id=?", (uid,)))["c"]
    if n >= (10 if D.is_premium(await D.get_user(uid)) else 2): return await toast(update, "Limit reached — go Premium", True)
    c = await cg_coin(sym)
    await D.execute("INSERT OR REPLACE INTO whale_subs VALUES(?,?,?)", (uid, sym, c["current_price"] if c else 0)); await toast(update, "🔔 ON")

async def whale_loop(bot):
    while True:
        await asyncio.sleep(180)
        try:
            pct = float(await D.get_setting("whale_pct", "1.5"))
            for s in await D.fetchall("SELECT DISTINCT symbol FROM whale_subs"):
                c = await cg_coin(s["symbol"])
                if not c: continue
                p = c["current_price"]
                for sub in await D.fetchall("SELECT user_id,last_price FROM whale_subs WHERE symbol=?", (s["symbol"],)):
                    lp = sub["last_price"] or p; ch = (p - lp) / lp * 100 if lp else 0
                    if abs(ch) >= pct:
                        try: await bot.send_message(sub["user_id"], f"🐋 <b>{s['symbol']}</b> {'🟢' if ch > 0 else '🔴'} {ch:+.2f}% → ${p:,}", parse_mode="HTML")
                        except Exception: pass
                        await D.execute("UPDATE whale_subs SET last_price=? WHERE user_id=? AND symbol=?", (p, sub["user_id"], s["symbol"]))
                    elif not sub["last_price"]: await D.execute("UPDATE whale_subs SET last_price=? WHERE user_id=? AND symbol=?", (p, sub["user_id"], s["symbol"]))
                await asyncio.sleep(2)
        except Exception as e: log.warning("whale loop: %s", e)

# ---------------- /capsule ----------------
@ready
async def capsule_cmd(update, ctx):
    a = _args(ctx); uid = update.effective_user.id
    if a and re.fullmatch(r"\d+(\.\d+)?", a[0]) and len(a) > 1: return await do_capsule(update, ctx, a[0], " ".join(a[1:]))
    n = (await D.fetchone("SELECT COUNT(*) c FROM capsules WHERE user_id=? AND delivered=0", (uid,)))["c"]; _wait(ctx, "capsule")
    await show(update, ctx, f"⏳ <b>{sc('Time capsule')}</b>\n\n{sc('Send: years | message')}\n<code>5 | Dear me, I hope you made it…</code>\n\n🔒 {n} {sc('sealed')}", back())

async def do_capsule(update, ctx, years, message):
    y = float(years)
    if not 0 < y <= 50: return await send(update, ctx, sc("Years must be between 0 and 50."), back())
    at = D.now() + int(y * 31557600)
    await D.execute("INSERT INTO capsules(user_id,message,deliver_at,created_at) VALUES(?,?,?,?)", (update.effective_user.id, message[:3500], at, D.now()))
    ctx.user_data.pop("await", None)
    await send(update, ctx, f"⏳ 🔒 {sc('Sealed until')} <b>{time.strftime('%Y-%m-%d', time.gmtime(at))}</b>", back())

async def capsule_loop(bot):
    while True:
        await asyncio.sleep(60)
        try:
            for c in await D.fetchall("SELECT * FROM capsules WHERE delivered=0 AND deliver_at<=?", (D.now(),)):
                try: await bot.send_message(c["user_id"], f"⏳ <b>{sc('A message from your past self')}</b>\n<i>{time.strftime('%Y-%m-%d', time.gmtime(c['created_at']))}</i>\n\n{esc(c['message'])}", parse_mode="HTML")
                except Exception as e: log.info("capsule undeliverable: %s", e)
                await D.execute("UPDATE capsules SET delivered=1 WHERE id=?", (c["id"],))
        except Exception as e: log.warning("capsule loop: %s", e)

# ---------------- /roast ----------------
@ready
async def roast_cmd(update, ctx):
    m = update.effective_message; target = update.effective_user
    if m and m.reply_to_message and m.reply_to_message.from_user and not m.reply_to_message.from_user.is_bot: target = m.reply_to_message.from_user
    await do_roast(update, ctx, target)

async def do_roast(update, ctx, target):
    if not await _gate(update, ctx): return
    db = await D.get_user(update.effective_user.id)
    j = await ask_json(f"You write playful, witty comedy-roast jokes in {_lang(db)}. Never touch race, religion, health, sexuality or tragedies. Max 60 words. "
                       'JSON: {"roast":"","score":1-100 (how brutal+funny)}', f"Roast {target.first_name} (@{target.username or 'no username'}).")
    if not isinstance(j, dict) or not j.get("roast"): return await send(update, ctx, "⚠️ …", back())
    score = max(1, min(100, int(j.get("score", 50))))
    await D.execute("INSERT INTO roasts(user_id,name,text,score,created_at) VALUES(?,?,?,?,?)", (target.id, target.first_name, j["roast"], score, D.now()))
    await send(update, ctx, f"🔥 <b>{esc(target.first_name)}</b>\n\n{esc(j['roast'])}\n\n💥 {sc('Burn score')}: <b>{score}/100</b>",
               kb([btn("Leaderboard", "roast:top"), btn("Again", "roast:again", style="danger")], "menu:home"))

async def roast_cb(update, ctx):
    act = update.callback_query.data.split(":")[1]
    if act == "again": await toast(update, "🔥"); return await do_roast(update, ctx, update.effective_user)
    rows = await D.fetchall("SELECT name, MAX(score) s, text FROM roasts GROUP BY user_id ORDER BY s DESC LIMIT 10")
    medals = ["🥇", "🥈", "🥉"]
    txt = f"🏆 <b>{sc('Global roast leaderboard')}</b>\n\n" + "\n".join(f"{medals[i] if i < 3 else '▫️'} {esc(r['name'])} — <b>{r['s']}</b>" for i, r in enumerate(rows))
    await show(update, ctx, txt if rows else sc("No roasts yet."), back("menu:roast"))

# ---------------- /swarm ----------------
AGENTS = [("Nova", "🟢", "an optimistic visionary who sees opportunities"), ("Rex", "🔴", "a ruthless skeptic who finds flaws and risks"), ("Sage", "🔵", "a calm strategist who synthesizes and decides")]

@ready
async def swarm_cmd(update, ctx):
    if _args(ctx): return await do_swarm(update, ctx, " ".join(_args(ctx)))
    _wait(ctx, "swarm"); await show(update, ctx, f"🤖 <b>{sc('Swarm')}</b>\n\n{sc('Send a topic. Three AI agents debate it. Works in groups too: /swarm topic')}", back())

async def do_swarm(update, ctx, topic):
    if not await _gate(update, ctx): return
    cid = update.effective_chat.id; db = await D.get_user(update.effective_user.id); ctx.user_data.pop("await", None)
    await ctx.bot.send_message(cid, f"🤖 <b>{sc('Swarm debate')}</b>: {esc(topic[:200])}", parse_mode="HTML")
    log_ = []
    for rnd in range(2):
        for name, ic, role in AGENTS:
            await ctx.bot.send_chat_action(cid, "typing")
            out = await ask(f"You are {name}, {role}, in a 3-agent debate. Reply in {_lang(db)}, max 55 words, directly address the others, no preamble.",
                            f"Topic: {topic}\nDebate so far:\n" + "\n".join(log_) + f"\nRound {rnd + 1}: speak.", max_tokens=200)
            log_.append(f"{name}: {out}")
            await ctx.bot.send_message(cid, f"{ic} <b>{name}</b>: {esc(out)}", parse_mode="HTML")
    v = await ask(f"You are Sage. Give a final VERDICT in {_lang(db)}, max 40 words.", f"Topic: {topic}\n" + "\n".join(log_), max_tokens=150)
    await ctx.bot.send_message(cid, f"⚖️ <b>{sc('Verdict')}</b>: {esc(v)}", parse_mode="HTML", reply_markup=back() if update.effective_chat.type == "private" else None)

# ---------------- /ghost ----------------
@ready
async def ghost_cmd(update, ctx):
    a = _args(ctx)
    if a and len(a) >= 2: return await do_ghost(update, ctx, a[0], " ".join(a[1:]))
    if a: ctx.user_data["ghost_target"] = a[0]; _wait(ctx, "ghost_msg"); return await send(update, ctx, f"👻 {sc('Paste the message you received.')}", back())
    _wait(ctx, "ghost_target"); await show(update, ctx, f"👻 <b>{sc('Ghost')}</b>\n\n{sc('Who should receive the reply? Send a numeric user id, or @channel / @group.')}\n{sc('Tip: /ghost target message')}", back())

async def do_ghost(update, ctx, target, incoming):
    if not await _gate(update, ctx): return
    db = await D.get_user(update.effective_user.id); st = json.loads(db["clone_style"]) if db["clone_style"] else None
    style = f"Imitate this style exactly: {st['summary']}\nExamples:\n" + "\n".join(st.get("samples", [])) if st else "Write naturally, casual and concise."
    draft = await ask(f"You draft replies on behalf of the user, in the language of the incoming message. {style}\nOutput ONLY the reply text.", f"Incoming message:\n{incoming}", max_tokens=300)
    ctx.user_data["ghost"] = {"target": target, "draft": draft, "incoming": incoming}; ctx.user_data.pop("await", None)
    await send(update, ctx, f"👻 <b>{sc('Draft')}</b> → {esc(target)}\n\n{esc(draft)}",
               kb([btn("Send", "ghost:send", style="success"), btn("Redo", "ghost:redo"), btn("Cancel", "ghost:cancel", style="danger")]))

async def ghost_cb(update, ctx):
    act = update.callback_query.data.split(":")[1]; g = ctx.user_data.get("ghost")
    if act == "cancel": ctx.user_data.pop("ghost", None); await toast(update, "❌"); return await show(update, ctx, sc("Cancelled."), back())
    if not g: return await toast(update, "Expired", True)
    if act == "redo": await toast(update, "🔄"); return await do_ghost(update, ctx, g["target"], g["incoming"])
    t = g["target"]
    if t.startswith("@"):
        r = await D.fetchone("SELECT id FROM users WHERE lower(username)=?", (t[1:].lower(),)); t = r["id"] if r else t
    try:
        await ctx.bot.send_message(int(t) if str(t).lstrip("-").isdigit() else t, g["draft"]); ctx.user_data.pop("ghost", None)
        await toast(update, "✅ Sent"); await show(update, ctx, f"👻 ✅ {sc('Sent')}", back())
    except Exception as e:
        await toast(update, f"Cannot send: {str(e)[:150]}", True)

# ---------------- routing of free text / files ----------------
@ready
async def text_router(update, ctx):
    m = update.message; text = m.text or ""; w = ctx.user_data.get("await")
    if w == "dream": return await do_dream(update, ctx, text)
    if w == "crm": return await do_crm(update, ctx, text)
    if w == "whale": return await do_whale(update, ctx, text.split()[0])
    if w == "swarm": return await do_swarm(update, ctx, text)
    if w == "ghost_target": ctx.user_data["ghost_target"] = text.strip(); _wait(ctx, "ghost_msg"); return await send(update, ctx, f"👻 {sc('Now paste the message you received.')}", back())
    if w == "ghost_msg": return await do_ghost(update, ctx, ctx.user_data.get("ghost_target", ""), text)
    if w == "capsule":
        mm = re.match(r"\s*(\d+(?:\.\d+)?)\s*[|:]\s*(.+)", text, re.S)
        return await do_capsule(update, ctx, mm.group(1), mm.group(2)) if mm else await send(update, ctx, sc("Format: years | message"), back())
    if w == "clonechat":
        db = await D.get_user(update.effective_user.id); st = json.loads(db["clone_style"])
        if not await _gate(update, ctx): return
        out = await ask(f"You ARE this person. Reply as them, same style, same language as the message. Style: {st['summary']}\nExamples:\n" + "\n".join(st.get("samples", [])), text, max_tokens=250)
        return await m.reply_text(out)
    await send(update, ctx, sc("Use the menu 👇"), back())

@ready
async def doc_router(update, ctx):
    w = ctx.user_data.get("await"); d = update.message.document
    if w not in ("clone", "crm") or not d: return
    if d.file_size and d.file_size > 19_000_000: return await send(update, ctx, sc("File too large (max ~19 MB)."), back())
    note = await update.message.reply_text("⏳ …")
    try:
        raw = bytes(await (await ctx.bot.get_file(d.file_id)).download_as_bytearray()); msgs = parse_export(raw, update.effective_user.id)
    except Exception: await note.delete(); return await send(update, ctx, sc("Invalid JSON export."), back())
    await note.delete()
    if w == "clone": await do_clone(update, ctx, msgs)
    else: await do_crm(update, ctx, "\n".join(f"{n}: {t}" for n, _, t in msgs[-600:]))
