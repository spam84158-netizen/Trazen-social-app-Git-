import time, logging
from datetime import date
from telegram import LabeledPrice
from bot import database as D
from bot.config import CE, PLANS, PACKS, LOTTERY_TICKET_PRICE
from bot.keyboards import btn, kb, back, web_btn, M
from bot.utils.fonts import sc, em, fmt
from bot.utils.ui import send, show, toast, ready, esc
log = logging.getLogger("economy")
today = lambda: time.strftime("%Y-%m-%d", time.gmtime())

# ---------- /premium /buy /balance ----------
@ready
async def premium_cmd(update, ctx):
    u = await D.get_user(update.effective_user.id)
    st = f"✅ {sc('Active until')} {time.strftime('%Y-%m-%d', time.gmtime(u['premium_until']))}" if D.is_premium(u) else f"❌ {sc('Not active')}"
    lines = "\n".join(f"{'💎' if k == '1y' else '🥇' if k == '3m' else '🥈'} <b>{sc(p['label'])}</b> — {p['stars']}⭐" + (f" (+{p['tickets']}🎟 +{p['bonus']}⭐)" if p["bonus"] else "") for k, p in PLANS.items())
    await show(update, ctx, f"{em(CE['premium'], '💎')} <b>{sc('Premium')}</b>\n{st}\n\n{lines}\n\n{sc('Unlimited AI · more limits · VIP tier · bonus tickets')}",
               kb([btn(f"{p['label']} · {p['stars']}⭐", f"buy:{k}", style="success") for k, p in PLANS.items()], "menu:home"))

async def buy_cb(update, ctx):
    k = update.callback_query.data.split(":")[1]; p = PLANS.get(k)
    if not p: return
    await toast(update, "💳")
    await ctx.bot.send_invoice(update.effective_chat.id, f"Premium {p['label']}", f"Trazen Society Premium — {p['label']}", f"plan:{k}", "XTR", [LabeledPrice(p["label"], p["stars"])], provider_token="")

@ready
async def buy_cmd(update, ctx):
    await show(update, ctx, f"⭐ <b>{sc('Top up wallet')}</b>\n\n{sc('Pay with Telegram Stars, get the same amount in wallet credits (lottery, perks).')}",
               kb([btn(f"{v}⭐", f"pack:{k}", style="success") for k, v in PACKS.items()] + [web_btn("Wallet", "wallet")], "menu:home"))

async def pack_cb(update, ctx):
    k = update.callback_query.data.split(":")[1]; v = PACKS.get(k)
    if not v: return
    await toast(update, "💳")
    await ctx.bot.send_invoice(update.effective_chat.id, f"{v} Stars credits", "Wallet top-up", f"pack:{k}", "XTR", [LabeledPrice(f"{v} credits", v)], provider_token="")

async def pre_checkout(update, ctx):
    q = update.pre_checkout_query; kind, k = (q.invoice_payload.split(":") + [""])[:2]
    await q.answer(ok=(kind == "plan" and k in PLANS) or (kind == "pack" and k in PACKS), error_message="Invalid product")

async def grant_payment(bot, uid, payload, stars, charge_id):
    """Idempotent: used by the bot's successful_payment and nowhere else."""
    if await D.execute("INSERT OR IGNORE INTO payments(user_id,charge_id,payload,stars,created_at) VALUES(?,?,?,?,?)", (uid, charge_id, payload, stars, D.now())) == 0: return None
    kind, k = payload.split(":")
    if kind == "pack": await D.credit(uid, PACKS[k]); return f"⭐ +{PACKS[k]} {sc('credits')}"
    p = PLANS[k]; u = await D.get_user(uid); base = max(D.now(), u["premium_until"])
    await D.execute("UPDATE users SET is_premium=1, premium_until=?, vip_tier=? WHERE id=?", (base + p["days"] * 86400, p["tier"], uid))
    if p["bonus"]: await D.credit(uid, p["bonus"])
    for _ in range(p["tickets"]): await D.add_ticket(uid, 1)
    return f"💎 {sc('Premium activated')} — {sc(p['label'])} · VIP {p['tier'].upper()}"

async def successful_payment(update, ctx):
    sp = update.message.successful_payment
    msg = await grant_payment(ctx.bot, update.effective_user.id, sp.invoice_payload, sp.total_amount, sp.telegram_payment_charge_id)
    if msg: await send(update, ctx, f"{em(CE['ok'], '✅')} {msg}", kb([], "menu:home"))

@ready
async def balance_cmd(update, ctx):
    u = await D.get_user(update.effective_user.id); f, p = await D.ticket_counts(u["id"])
    pr = f"until {time.strftime('%Y-%m-%d', time.gmtime(u['premium_until']))}" if D.is_premium(u) else "no"
    await show(update, ctx, f"{em(CE['star'], '⭐')} <b>{sc('Wallet')}</b>\n\n{sc('Credits')}: <b>{fmt(u['stars'])}</b>⭐\n{sc('VIP tier')}: <b>{u['vip_tier'].upper()}</b>\n{sc('Premium')}: {pr}\n🎟 {f} free · {p} paid\n🔥 {sc('Streak')}: {u['streak']}",
               kb([btn("Top up", "menu:buy", style="success"), web_btn("Wallet", "wallet")], "menu:home"))

# ---------- /lottery ----------
@ready
async def lottery_cmd(update, ctx, note=""):
    u = await D.get_user(update.effective_user.id); f, p = await D.ticket_counts(u["id"])
    await show(update, ctx, f"{em(CE['game'], '🎰')} <b>{sc('Lottery')}</b>\n\n⭐ {fmt(u['stars'])} · 🎟 {f} {sc('free')} · {p} {sc('paid')}\n{sc('Ticket price')}: {LOTTERY_TICKET_PRICE}⭐\n<i>{sc('Free tickets only win the 0.01⭐ consolation. Paid tickets can win up to 500⭐.')}</i>{note}",
               kb([btn("Free ticket", "lot:free"), btn(f"Buy · {LOTTERY_TICKET_PRICE}⭐", "lot:buy", style="success"), btn("Play ticket", "lot:play", style="primary"), web_btn("Wheel", "lottery")], "menu:home"))

async def lottery_cb(update, ctx):
    act = update.callback_query.data.split(":")[1]; uid = update.effective_user.id; note = ""
    if act == "free":
        u = await D.get_user(uid)
        if u["last_free_ticket"] == today(): return await toast(update, "Already claimed today — come back tomorrow")
        await D.update_user(uid, last_free_ticket=today()); await D.add_ticket(uid, 0); await toast(update, "🎟 +1")
    elif act == "buy":
        if not await D.spend(uid, LOTTERY_TICKET_PRICE): return await toast(update, "Insufficient funds — top up first", alert=True)
        await D.add_ticket(uid, 1); await toast(update, "🎟 +1 paid")
    elif act == "play":
        r = await D.play_ticket(uid)
        if not r: return await toast(update, "No tickets", alert=True)
        await toast(update, "🎰")
        note = f"\n\n🎰 {'🎉 <b>' + sc('You won') + ' ' + fmt(r['prize']) + '⭐</b>' if r['prize'] else '💨 ' + sc('No prize')}"
    await lottery_cmd(update, ctx, note)

# ---------- /daily ----------
@ready
async def daily_cmd(update, ctx):
    u = await D.get_user(update.effective_user.id); n = D.now()
    if n - u["last_daily"] < 20 * 3600:
        left = 20 * 3600 - (n - u["last_daily"])
        return await show(update, ctx, f"📅 <b>{sc('Daily')}</b>\n\n{sc('Come back in')} {left // 3600}h {left % 3600 // 60}m\n🔥 {sc('Streak')}: {u['streak']}", back())
    streak = u["streak"] + 1 if n - u["last_daily"] < 48 * 3600 else 1
    reward = 1 + min(streak - 1, 6); bonus = ""
    await D.update_user(u["id"], streak=streak, last_daily=n); await D.credit(u["id"], reward)
    if streak % 7 == 0: await D.add_ticket(u["id"], 0); bonus = f"\n🎟 {sc('Weekly bonus ticket!')}"
    await toast(update, f"+{reward}⭐")
    await show(update, ctx, f"📅 <b>{sc('Daily claimed')}</b>\n\n+{reward}⭐ · 🔥 {sc('Streak')}: <b>{streak}</b>{bonus}", back())

# ---------- /referral ----------
@ready
async def referral_cmd(update, ctx):
    u = await D.get_user(update.effective_user.id); me = u["id"]
    c1 = (await D.fetchone("SELECT COUNT(*) c FROM users WHERE referred_by=? AND onboarded=1", (me,)))["c"]
    c2 = (await D.fetchone("SELECT COUNT(*) c FROM users a JOIN users b ON a.referred_by=b.id WHERE b.referred_by=? AND a.onboarded=1", (me,)))["c"]
    c3 = (await D.fetchone("SELECT COUNT(*) c FROM users a JOIN users b ON a.referred_by=b.id JOIN users c ON b.referred_by=c.id WHERE c.referred_by=? AND a.onboarded=1", (me,)))["c"]
    link = f"https://t.me/{ctx.bot.username}?start=ref_{u['referral_code']}"
    await show(update, ctx, f"{em(CE['star'], '⭐')} <b>{sc('Referral')}</b>\n\n<code>{link}</code>\n\n🥇 L1: <b>{c1}</b> (+5⭐)\n🥈 L2: <b>{c2}</b> (+2⭐)\n🥉 L3: <b>{c3}</b> (+1⭐)",
               kb([btn("Share", url=f"https://t.me/share/url?url={link}&text=Join%20Trazen%20Society", style="primary")], "menu:home"))

# ---------- /tasks ----------
@ready
async def tasks_cmd(update, ctx):
    done = {r["code"] for r in await D.fetchall("SELECT code FROM task_claims WHERE user_id=? AND day=?", (update.effective_user.id, today()))}
    link = f"https://t.me/{ctx.bot.username}?start=ref_{(await D.get_user(update.effective_user.id))['referral_code']}"
    b = [btn("Share link", url=f"https://t.me/share/url?url={link}&text=Join%20Trazen%20Society"),
         btn("✅ Claim share" if "share" not in done else "✔️ Done", "task:claim:share", style="success" if "share" not in done else None),
         web_btn("Watch ad", "earn", style="success")]
    await show(update, ctx, f"{em(CE['gift'], '🎁')} <b>{sc('Daily tasks')}</b>\n\n📣 {sc('Share the bot')} → +2⭐\n📺 {sc('Watch an ad')} → +5⭐ ({sc('up to 10/day')})", kb(b, "menu:home"))

async def task_cb(update, ctx):
    uid = update.effective_user.id
    if await D.execute("INSERT OR IGNORE INTO task_claims VALUES(?,?,?)", (uid, "share", today())) == 0: return await toast(update, "Already claimed today")
    await D.credit(uid, 2); await toast(update, "+2⭐"); await tasks_cmd(update, ctx)
