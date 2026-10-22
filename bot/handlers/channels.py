from telegram.error import TelegramError
from bot import database as D
from bot.utils.fonts import sc
from bot.utils.ui import ready, esc

@ready
async def addchannel_cmd(update, ctx):
    m = update.effective_message; uid = update.effective_user.id
    if not ctx.args: return await m.reply_html(f"{sc('Usage')}: /addchannel @channel\n{sc('Add me as admin first.')}")
    n = (await D.fetchone("SELECT COUNT(*) c FROM user_channels WHERE user_id=?", (uid,)))["c"]
    if n >= (5 if D.is_premium(await D.get_user(uid)) else 1): return await m.reply_text(sc("Channel limit reached — go /premium for more."))
    try:
        ch = await ctx.bot.get_chat(ctx.args[0] if not ctx.args[0].lstrip("-").isdigit() else int(ctx.args[0]))
        if (await ctx.bot.get_chat_member(ch.id, ctx.bot.id)).status != "administrator": return await m.reply_text(sc("I must be an admin there."))
        if (await ctx.bot.get_chat_member(ch.id, uid)).status not in ("administrator", "creator"): return await m.reply_text(sc("You must be an admin there."))
    except TelegramError as e: return await m.reply_text(f"⚠️ {e}")
    if await D.fetchone("SELECT 1 FROM user_channels WHERE user_id=? AND chat_id=?", (uid, ch.id)): return await m.reply_text(sc("Already added."))
    await D.execute("INSERT INTO user_channels(user_id,chat_id,title,username) VALUES(?,?,?,?)", (uid, ch.id, ch.title, ch.username))
    await D.execute("INSERT OR IGNORE INTO broadcast_targets(chat_id,kind,title,added_at) VALUES(?,?,?,?)", (ch.id, "channel", ch.title, D.now()))
    await m.reply_html(f"✅ <b>{esc(ch.title)}</b> {sc('added')}")

@ready
async def mychannels_cmd(update, ctx):
    rows = await D.fetchall("SELECT * FROM user_channels WHERE user_id=? ORDER BY id", (update.effective_user.id,))
    await update.effective_message.reply_html(f"📡 <b>{sc('My channels')}</b>\n\n" + ("\n".join(f"{i}. {esc(r['title'])} {'@' + r['username'] if r['username'] else ''}" for i, r in enumerate(rows, 1)) or sc("None. /addchannel @channel")) + f"\n\n{sc('Post')}: /send 1 text · {sc('or reply to a message with')} /send 1")

@ready
async def removechannel_cmd(update, ctx):
    rows = await D.fetchall("SELECT * FROM user_channels WHERE user_id=? ORDER BY id", (update.effective_user.id,))
    if not ctx.args or not ctx.args[0].isdigit() or not 0 < int(ctx.args[0]) <= len(rows): return await update.effective_message.reply_html(f"{sc('Usage')}: /removechannel 1 — /mychannels")
    r = rows[int(ctx.args[0]) - 1]; await D.execute("DELETE FROM user_channels WHERE id=?", (r["id"],)); await update.effective_message.reply_text("🗑 ✅")

@ready
async def send_cmd(update, ctx):
    m = update.effective_message; rows = await D.fetchall("SELECT * FROM user_channels WHERE user_id=? ORDER BY id", (update.effective_user.id,))
    if not ctx.args or not ctx.args[0].isdigit() or not 0 < int(ctx.args[0]) <= len(rows): return await m.reply_html(f"{sc('Usage')}: /send 1 text — {sc('or reply to a message')}")
    ch = rows[int(ctx.args[0]) - 1]; text = " ".join(ctx.args[1:])
    try:
        if m.reply_to_message: await ctx.bot.copy_message(ch["chat_id"], m.chat_id, m.reply_to_message.message_id)
        elif text: await ctx.bot.send_message(ch["chat_id"], text)
        else: return await m.reply_text(sc("Nothing to send."))
        await m.reply_html(f"📤 ✅ → <b>{esc(ch['title'])}</b>")
    except TelegramError as e: await m.reply_text(f"⚠️ {e}")
