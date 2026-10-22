import asyncio, time, httpx, logging
from telegram.error import Forbidden, RetryAfter, TelegramError
from bot import database as D
from bot.config import BOT_TOKEN, WITHDRAW_MIN_STARS, CE
from bot.keyboards import kb, btn, back
from bot.utils.fonts import sc, em, fmt
from bot.utils.ui import owner_only, esc, show
log = logging.getLogger("owner")

def _api(method, **params):
    async def go():
        async with httpx.AsyncClient(timeout=20) as c: return (await c.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=params)).json()
    return go()

@owner_only
async def admin_panel(update, ctx):
    await show(update, ctx, f"{em(CE['crown'], '👑')} <b>{sc('Owner panel')}</b>\n\n/stats · /broadcast\n/grantpremium id days · /revokepremium id\n/setfreetier n · /maintenance on|off\n/logs · /refund user_id charge_id\n/stars_balance · /stars_withdraw", back())

@owner_only
async def stats_cmd(update, ctx):
    q = lambda s: D.fetchone(s)
    u, pr, g, pay, tk, dr, cp = await asyncio.gather(q("SELECT COUNT(*) c FROM users"), q(f"SELECT COUNT(*) c FROM users WHERE is_premium=1 AND premium_until>{D.now()}"),
        q("SELECT COUNT(*) c FROM broadcast_targets WHERE kind!='user'"), q("SELECT COALESCE(SUM(stars),0) c, COUNT(*) n FROM payments WHERE refunded=0"),
        q("SELECT COUNT(*) c FROM lottery_tickets"), q("SELECT COUNT(*) c FROM dreams"), q("SELECT COUNT(*) c FROM capsules WHERE delivered=0"))
    await update.effective_message.reply_html(f"📊 <b>{sc('Stats')}</b>\n\n👥 {u['c']} · 💎 {pr['c']} · 💬 {g['c']}\n⭐ {pay['c']} ({pay['n']} {sc('payments')})\n🎟 {tk['c']} · 🌙 {dr['c']} · ⏳ {cp['c']}")

@owner_only
async def broadcast_cmd(update, ctx):
    m = update.effective_message; text = m.text.partition(" ")[2].strip(); src = m.reply_to_message
    if not text and not src: return await m.reply_text("Usage: /broadcast <text>  (or reply to a message)")
    targets = await D.fetchall("SELECT chat_id FROM broadcast_targets"); total = len(targets); ok = fail = 0
    prog = await m.reply_text(f"📣 0/{total}")
    for i, t in enumerate(targets, 1):
        try:
            if src: await ctx.bot.copy_message(t["chat_id"], src.chat_id, src.message_id)
            else: await ctx.bot.send_message(t["chat_id"], text, parse_mode="HTML")
            ok += 1
        except RetryAfter as e: await asyncio.sleep(e.retry_after + 1); fail += 1
        except Forbidden: fail += 1; await D.execute("DELETE FROM broadcast_targets WHERE chat_id=?", (t["chat_id"],))
        except TelegramError: fail += 1
        await asyncio.sleep(0.05)                                   # 50 ms
        if i % 20 == 0 or i == total:
            try: await prog.edit_text(f"📣 {i}/{total} · ✅ {ok} · ❌ {fail}")
            except TelegramError: pass
    await m.reply_html(f"📣 <b>{sc('Done')}</b> ✅ {ok} · ❌ {fail}")

@owner_only
async def grantpremium_cmd(update, ctx):
    a = ctx.args
    if len(a) < 2 or not a[0].isdigit() or not a[1].isdigit(): return await update.effective_message.reply_text("Usage: /grantpremium user_id days")
    u = await D.get_user(int(a[0]))
    if not u: return await update.effective_message.reply_text("Unknown user")
    await D.execute("UPDATE users SET is_premium=1, premium_until=?, vip_tier='gold' WHERE id=?", (max(D.now(), u["premium_until"]) + int(a[1]) * 86400, u["id"]))
    try: await ctx.bot.send_message(u["id"], f"💎 {sc('Premium granted')}: {a[1]}d")
    except TelegramError: pass
    await update.effective_message.reply_text("✅")

@owner_only
async def revokepremium_cmd(update, ctx):
    if not ctx.args or not ctx.args[0].isdigit(): return await update.effective_message.reply_text("Usage: /revokepremium user_id")
    await D.execute("UPDATE users SET is_premium=0, premium_until=0, vip_tier='bronze' WHERE id=?", (int(ctx.args[0]),)); await update.effective_message.reply_text("✅")

@owner_only
async def setfreetier_cmd(update, ctx):
    if not ctx.args or not ctx.args[0].isdigit(): return await update.effective_message.reply_text(f"Usage: /setfreetier N (current {await D.get_setting('free_ai_daily', 5)} AI uses/day)")
    await D.set_setting("free_ai_daily", ctx.args[0]); await update.effective_message.reply_text(f"✅ free tier = {ctx.args[0]}/day")

@owner_only
async def maintenance_cmd(update, ctx):
    v = (ctx.args or [""])[0].lower()
    if v not in ("on", "off"): return await update.effective_message.reply_text(f"Maintenance is {'ON' if await D.get_setting('maintenance') == '1' else 'OFF'} — /maintenance on|off")
    await D.set_setting("maintenance", "1" if v == "on" else "0"); await update.effective_message.reply_text(f"🛠 {v.upper()}")

@owner_only
async def logs_cmd(update, ctx):
    rows = await D.fetchall("SELECT * FROM logs ORDER BY id DESC LIMIT 25")
    await update.effective_message.reply_html("<pre>" + esc("\n".join(f"{time.strftime('%d %H:%M', time.gmtime(r['ts']))} {r['user_id']} {r['text'][:60]}" for r in rows) or "empty") + "</pre>")

@owner_only
async def refund_cmd(update, ctx):
    if len(ctx.args) < 2 or not ctx.args[0].isdigit(): return await update.effective_message.reply_text("Usage: /refund user_id charge_id")
    r = await _api("refundStarPayment", user_id=int(ctx.args[0]), telegram_payment_charge_id=ctx.args[1])
    if r.get("ok"):
        await D.execute("UPDATE payments SET refunded=1 WHERE charge_id=?", (ctx.args[1],)); await update.effective_message.reply_text("✅ refunded")
    else: await update.effective_message.reply_text(f"⚠️ {r.get('description')}")

async def _balance():
    r = await _api("getMyStarBalance"); return (r.get("result") or {}).get("amount"), r

@owner_only
async def stars_balance_cmd(update, ctx):
    amt, r = await _balance()
    await update.effective_message.reply_html(f"⭐ <b>{sc('Bot Stars balance')}</b>: {amt}" if amt is not None else f"⚠️ {r.get('description')}")

@owner_only
async def stars_withdraw_cmd(update, ctx):
    amt, _ = await _balance()
    await update.effective_message.reply_html(f"⭐ <b>{sc('Stars withdrawal')}</b>\n\n{sc('Balance')}: <b>{amt}</b> (min {WITHDRAW_MIN_STARS})\n\n{sc('Telegram has no API to withdraw: open @BotFather → your bot → Balance (or Fragment) and withdraw as TON from there.')}")
