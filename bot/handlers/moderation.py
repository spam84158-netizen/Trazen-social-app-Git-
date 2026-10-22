import asyncio, time, math, logging, collections
from datetime import datetime, timedelta, timezone
from telegram import ChatPermissions, Update
from telegram.constants import ChatType
from telegram.error import TelegramError
from bot import database as D
from bot.config import OWNER_ID
from bot.keyboards import btn, M
from bot.utils.ai import ask, LANGNAME
from bot.utils.fonts import sc, mention
from bot.utils.ui import esc
log = logging.getLogger("mod")
PENDING = {}                       # (chat,user) -> asyncio.Task (captcha kick timers)
FLOOD = collections.defaultdict(list)

async def is_admin(ctx, chat_id, uid):
    if uid == OWNER_ID: return True
    try: return (await ctx.bot.get_chat_member(chat_id, uid)).status in ("administrator", "creator")
    except TelegramError: return False

async def settings(chat_id):
    r = await D.fetchone("SELECT * FROM chat_settings WHERE chat_id=?", (chat_id,))
    if not r: await D.execute("INSERT OR IGNORE INTO chat_settings(chat_id) VALUES(?)", (chat_id,)); r = await D.fetchone("SELECT * FROM chat_settings WHERE chat_id=?", (chat_id,))
    return r

async def _guard(update, ctx):
    """Group-only + admin-only."""
    m = update.effective_message
    if update.effective_chat.type == "private": await m.reply_text(sc("Use this command in a group.")); return False
    if not await is_admin(ctx, update.effective_chat.id, update.effective_user.id): await m.reply_text(sc("Admins only.")); return False
    return True

async def _target(update, ctx):
    """reply > text_mention > @username > numeric id -> (id, name, rest_args)"""
    m = update.effective_message; a = list(ctx.args or [])
    if m.reply_to_message and m.reply_to_message.from_user: u = m.reply_to_message.from_user; return u.id, u.first_name, a
    for e in m.entities or []:
        if e.type == "text_mention" and e.user: return e.user.id, e.user.first_name, a[1:]
    if a:
        if a[0].lstrip("-").isdigit(): return int(a[0]), a[0], a[1:]
        if a[0].startswith("@"):
            r = await D.fetchone("SELECT id,first_name FROM users WHERE lower(username)=?", (a[0][1:].lower(),))
            if r: return r["id"], r["first_name"], a[1:]
    return None

async def _t(update, ctx):
    t = await _target(update, ctx)
    if not t: await update.effective_message.reply_text(sc("Reply to a user, or give @username / id."))
    return t

async def _protect(update, ctx, tid):
    if await is_admin(ctx, update.effective_chat.id, tid) or tid == ctx.bot.id:
        await update.effective_message.reply_text(sc("I can't do that to an admin.")); return True

async def ban_cmd(update, ctx):
    if not await _guard(update, ctx): return
    t = await _t(update, ctx)
    if not t or await _protect(update, ctx, t[0]): return
    try: await ctx.bot.ban_chat_member(update.effective_chat.id, t[0]); await update.effective_message.reply_html(f"🔨 {mention(*t[:2])} {sc('banned')}.")
    except TelegramError as e: await update.effective_message.reply_text(f"⚠️ {e}")

async def unban_cmd(update, ctx):
    if not await _guard(update, ctx): return
    t = await _t(update, ctx)
    if not t: return
    try: await ctx.bot.unban_chat_member(update.effective_chat.id, t[0], only_if_banned=True); await update.effective_message.reply_html(f"♻️ {mention(*t[:2])} {sc('unbanned')}.")
    except TelegramError as e: await update.effective_message.reply_text(f"⚠️ {e}")

async def kick_cmd(update, ctx):
    if not await _guard(update, ctx): return
    t = await _t(update, ctx)
    if not t or await _protect(update, ctx, t[0]): return
    try:
        await ctx.bot.ban_chat_member(update.effective_chat.id, t[0]); await ctx.bot.unban_chat_member(update.effective_chat.id, t[0])
        await update.effective_message.reply_html(f"👢 {mention(*t[:2])} {sc('kicked')}.")
    except TelegramError as e: await update.effective_message.reply_text(f"⚠️ {e}")

async def mute_cmd(update, ctx):
    if not await _guard(update, ctx): return
    t = await _t(update, ctx)
    if not t or await _protect(update, ctx, t[0]): return
    mins = int(t[2][0]) if t[2] and t[2][0].isdigit() else 60
    try:
        await ctx.bot.restrict_chat_member(update.effective_chat.id, t[0], ChatPermissions(can_send_messages=False), until_date=datetime.now(timezone.utc) + timedelta(minutes=mins))
        await update.effective_message.reply_html(f"🔇 {mention(*t[:2])} {sc('muted')} — {mins} min.")
    except TelegramError as e: await update.effective_message.reply_text(f"⚠️ {e}")

async def warn_cmd(update, ctx):
    if not await _guard(update, ctx): return
    t = await _t(update, ctx)
    if not t or await _protect(update, ctx, t[0]): return
    cid = update.effective_chat.id; reason = " ".join(t[2]) or "—"
    await D.execute("INSERT INTO warnings(chat_id,user_id,reason,by_id,created_at) VALUES(?,?,?,?,?)", (cid, t[0], reason[:200], update.effective_user.id, D.now()))
    n = (await D.fetchone("SELECT COUNT(*) c FROM warnings WHERE chat_id=? AND user_id=?", (cid, t[0])))["c"]
    await update.effective_message.reply_html(f"⚠️ {mention(*t[:2])} — {n}/3\n<i>{esc(reason)}</i>")
    if n >= 3:
        try: await ctx.bot.ban_chat_member(cid, t[0]); await D.execute("DELETE FROM warnings WHERE chat_id=? AND user_id=?", (cid, t[0])); await update.effective_message.reply_html(f"🔨 {mention(*t[:2])} {sc('banned (3 warnings)')}.")
        except TelegramError as e: await update.effective_message.reply_text(f"⚠️ {e}")

async def warnings_cmd(update, ctx):
    if update.effective_chat.type == "private": return
    t = await _target(update, ctx) or (update.effective_user.id, update.effective_user.first_name, [])
    rows = await D.fetchall("SELECT reason FROM warnings WHERE chat_id=? AND user_id=? ORDER BY id", (update.effective_chat.id, t[0]))
    await update.effective_message.reply_html(f"⚠️ {mention(*t[:2])}: <b>{len(rows)}/3</b>\n" + "\n".join(f"{i}. {esc(r['reason'])}" for i, r in enumerate(rows, 1)))

# ---- settings commands ----
async def _toggle(update, ctx, col, label):
    if not await _guard(update, ctx): return
    a = (ctx.args or [""])[0].lower(); cid = update.effective_chat.id; s = await settings(cid)
    val = 1 if a in ("on", "1", "yes") else 0 if a in ("off", "0", "no") else None
    if val is None: return await update.effective_message.reply_html(f"{sc(label)}: <b>{'ON' if s[col] else 'OFF'}</b> — /{label.split()[0].lower()} on|off")
    await D.execute(f"UPDATE chat_settings SET {col}=? WHERE chat_id=?", (val, cid)); await update.effective_message.reply_html(f"{sc(label)}: <b>{'ON' if val else 'OFF'}</b>")

async def captcha_cmd(update, ctx): await _toggle(update, ctx, "captcha", "captcha")
async def antiflood_cmd(update, ctx): await _toggle(update, ctx, "antiflood", "antiflood")
async def translate_cmd(update, ctx): await _toggle(update, ctx, "translate", "translate")

async def welcome_cmd(update, ctx):
    if not await _guard(update, ctx): return
    text = update.effective_message.text.partition(" ")[2].strip(); cid = update.effective_chat.id; await settings(cid)
    if not text: return await update.effective_message.reply_html(f"{sc('Usage')}: /welcome Hello {{mention}}, welcome to {{chat}}!")
    await D.execute("UPDATE chat_settings SET welcome=? WHERE chat_id=?", (text[:1000], cid)); await update.effective_message.reply_text("✅")

async def rules_cmd(update, ctx):
    if update.effective_chat.type == "private": return
    cid = update.effective_chat.id; text = update.effective_message.text.partition(" ")[2].strip()
    if text:
        if not await _guard(update, ctx): return
        await settings(cid); await D.execute("UPDATE chat_settings SET rules=? WHERE chat_id=?", (text[:3000], cid)); return await update.effective_message.reply_text("✅")
    s = await settings(cid); await update.effective_message.reply_html(f"📜 <b>{sc('Rules')}</b>\n\n{esc(s['rules']) or sc('No rules set. Admins: /rules <text>')}")

# ---- new members: welcome + captcha ----
def _fmt_welcome(s, user, chat):
    return (s["welcome"] or "Welcome {mention} to {chat}! 🎉").replace("{mention}", mention(user.id, user.first_name)).replace("{chat}", esc(chat.title))

async def new_members(update, ctx):
    chat = update.effective_chat; s = await settings(chat.id)
    for u in update.effective_message.new_chat_members:
        if u.is_bot: continue
        if s["captcha"]:
            try: await ctx.bot.restrict_chat_member(chat.id, u.id, ChatPermissions(can_send_messages=False))
            except TelegramError: pass
            m = await ctx.bot.send_message(chat.id, f"🤖 {mention(u.id, u.first_name)} — {sc('press the button within 90s')}", parse_mode="HTML", reply_markup=M([[btn("I am human", f"gc:{u.id}", style="success")]]))
            PENDING[(chat.id, u.id)] = asyncio.create_task(_captcha_timeout(ctx, chat.id, u.id, m.message_id))
        else: await ctx.bot.send_message(chat.id, _fmt_welcome(s, u, chat), parse_mode="HTML")

async def _captcha_timeout(ctx, cid, uid, mid):
    try:
        await asyncio.sleep(90)
        await ctx.bot.ban_chat_member(cid, uid); await ctx.bot.unban_chat_member(cid, uid)
        await ctx.bot.delete_message(cid, mid)
    except Exception: pass
    PENDING.pop((cid, uid), None)

async def group_captcha_cb(update, ctx):
    q = update.callback_query; uid = int(q.data.split(":")[1])
    if q.from_user.id != uid: return await q.answer("Not for you", show_alert=False)
    cid = q.message.chat.id
    try: await ctx.bot.restrict_chat_member(cid, uid, ChatPermissions.all_permissions())
    except TelegramError: pass
    t = PENDING.pop((cid, uid), None)
    if t: t.cancel()
    await q.answer("✅"); 
    try: await q.message.delete()
    except TelegramError: pass
    s = await settings(cid); await ctx.bot.send_message(cid, _fmt_welcome(s, q.from_user, q.message.chat), parse_mode="HTML")

# ---- message tracker: xp / karma / antiflood / private translation ----
THANKS = {"+", "+1", "👍", "thanks", "thx", "merci", "gracias", "danke", "shukran", "شكرا"}
async def level_of(xp): return int(math.sqrt(xp / 10))

async def group_tracker(update, ctx):
    m = update.effective_message; u = update.effective_user; chat = update.effective_chat
    if not m or not u or u.is_bot: return
    await D.execute("INSERT OR IGNORE INTO broadcast_targets(chat_id,kind,title,added_at) VALUES(?,?,?,?)", (chat.id, "group", chat.title, D.now()))
    s = await settings(chat.id); n = time.time(); key = (chat.id, u.id)
    if s["antiflood"]:
        FLOOD[key] = [t for t in FLOOD[key] if n - t < 6] + [n]
        if len(FLOOD[key]) > 6 and not await is_admin(ctx, chat.id, u.id):
            FLOOD[key] = []
            try:
                await ctx.bot.restrict_chat_member(chat.id, u.id, ChatPermissions(can_send_messages=False), until_date=datetime.now(timezone.utc) + timedelta(minutes=5))
                await ctx.bot.send_message(chat.id, f"🌊 {mention(u.id, u.first_name)} — {sc('flood detected, muted 5 min')}", parse_mode="HTML")
            except TelegramError: pass
            return
    await D.execute("INSERT OR IGNORE INTO member_stats(chat_id,user_id) VALUES(?,?)", (chat.id, u.id))
    st = await D.fetchone("SELECT * FROM member_stats WHERE chat_id=? AND user_id=?", (chat.id, u.id))
    if D.now() - st["last_xp"] >= 30:
        await D.execute("UPDATE member_stats SET xp=xp+10,last_xp=? WHERE chat_id=? AND user_id=?", (D.now(), chat.id, u.id))
        if await level_of(st["xp"] + 10) > await level_of(st["xp"]): await m.reply_html(f"🆙 {mention(u.id, u.first_name)} → {sc('level')} <b>{await level_of(st['xp'] + 10)}</b>")
    text = (m.text or "").strip()
    r = m.reply_to_message
    if r and r.from_user and not r.from_user.is_bot and r.from_user.id != u.id and text.lower() in THANKS:
        await D.execute("INSERT OR IGNORE INTO member_stats(chat_id,user_id) VALUES(?,?)", (chat.id, r.from_user.id))
        if D.now() - st["last_karma"] >= 60:
            await D.execute("UPDATE member_stats SET last_karma=? WHERE chat_id=? AND user_id=?", (D.now(), chat.id, u.id))
            await D.execute("UPDATE member_stats SET karma=karma+1 WHERE chat_id=? AND user_id=?", (chat.id, r.from_user.id))
            k = (await D.fetchone("SELECT karma FROM member_stats WHERE chat_id=? AND user_id=?", (chat.id, r.from_user.id)))["karma"]
            await m.reply_html(f"✨ {mention(r.from_user.id, r.from_user.first_name)} {sc('karma')}: <b>{k}</b>")
    if s["translate"] and len(text) > 3: await _private_translate(update, ctx, text)

async def _private_translate(update, ctx, text):
    m = update.effective_message; u = update.effective_user; targets = set()
    if m.reply_to_message and m.reply_to_message.from_user and not m.reply_to_message.from_user.is_bot: targets.add(m.reply_to_message.from_user.id)
    for e in m.entities or []:
        if e.type == "text_mention" and e.user: targets.add(e.user.id)
        elif e.type == "mention":
            r = await D.fetchone("SELECT id FROM users WHERE lower(username)=?", (m.parse_entity(e)[1:].lower(),))
            if r: targets.add(r["id"])
    for tid in targets - {u.id}:
        row = await D.get_user(tid)
        if not row or not row["onboarded"] or not row["lang"]: continue
        out = await ask(f"Translate the message into {LANGNAME[row['lang']]}. If it is already in {LANGNAME[row['lang']]}, answer exactly SAME. Output only the translation.", text, max_tokens=400, temperature=0.2)
        if out.strip().upper().startswith("SAME") or out.startswith("⚠️"): continue
        try: await ctx.bot.send_message(tid, f"🌐 {mention(u.id, u.first_name)} @ <b>{esc(update.effective_chat.title)}</b>\n\n{esc(out)}\n\n<a href=\"{m.link}\">↗️</a>", parse_mode="HTML")
        except TelegramError: pass

async def _stats_target(update):
    r = update.effective_message.reply_to_message
    return (r.from_user if r and r.from_user else update.effective_user)

async def karma_cmd(update, ctx):
    if update.effective_chat.type == "private": return
    t = await _stats_target(update); st = await D.fetchone("SELECT karma FROM member_stats WHERE chat_id=? AND user_id=?", (update.effective_chat.id, t.id))
    await update.effective_message.reply_html(f"✨ {mention(t.id, t.first_name)} — {sc('karma')}: <b>{st['karma'] if st else 0}</b>")

async def level_cmd(update, ctx):
    if update.effective_chat.type == "private": return
    t = await _stats_target(update); st = await D.fetchone("SELECT xp FROM member_stats WHERE chat_id=? AND user_id=?", (update.effective_chat.id, t.id)); xp = st["xp"] if st else 0
    lv = await level_of(xp); nxt = (lv + 1) ** 2 * 10; bar = "█" * int((xp - lv ** 2 * 10) / max(nxt - lv ** 2 * 10, 1) * 10)
    await update.effective_message.reply_html(f"🆙 {mention(t.id, t.first_name)}\n{sc('Level')} <b>{lv}</b> · {xp}/{nxt} XP\n<code>{bar.ljust(10, '░')}</code>")

async def trustscore_cmd(update, ctx):
    if update.effective_chat.type == "private": return
    t = await _stats_target(update); cid = update.effective_chat.id
    st = await D.fetchone("SELECT karma,xp FROM member_stats WHERE chat_id=? AND user_id=?", (cid, t.id)) or {"karma": 0, "xp": 0}
    w = (await D.fetchone("SELECT COUNT(*) c FROM warnings WHERE chat_id=? AND user_id=?", (cid, t.id)))["c"]; u = await D.get_user(t.id)
    age = min((D.now() - u["created_at"]) // 86400, 30) if u else 0
    score = max(0, min(100, 40 + age + min(st["karma"] * 3, 20) + min(st["xp"] // 100, 10) + (10 if D.is_premium(u) else 0) - w * 20))
    await update.effective_message.reply_html(f"🛡 {mention(t.id, t.first_name)} — {sc('Trust score')}: <b>{score}/100</b>\n{'🟢' if score >= 70 else '🟡' if score >= 40 else '🔴'} ⚠️ {w} · ✨ {st['karma']}")
