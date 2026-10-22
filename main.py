import os, hmac, hashlib, json, time, asyncio, logging, secrets
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from telegram import Update, BotCommand, LabeledPrice
from telegram.constants import ChatType
from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, PreCheckoutQueryHandler,
                          ChatMemberHandler, TypeHandler, ApplicationHandlerStop, filters)

from bot import database as D
from bot.config import *
from bot.handlers import onboarding, menu, ai_features as A, economy as E, moderation as Mo, channels as Ch, owner as O

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("trazen")
ptb = ApplicationBuilder().token(BOT_TOKEN).updater(None).build()
GROUP = filters.ChatType.GROUPS; PRIV = filters.ChatType.PRIVATE

async def pre(update: Update, ctx):
    """Logging + maintenance + ban gate (runs before everything)."""
    u = update.effective_user
    if not u: return
    m = update.effective_message
    if m and m.text and m.text.startswith("/"): await D.execute("INSERT INTO logs(ts,user_id,chat_id,text) VALUES(?,?,?,?)", (D.now(), u.id, update.effective_chat.id, m.text[:200]))
    if u.id == OWNER_ID: return
    if await D.get_setting("maintenance") == "1":
        if update.callback_query: await update.callback_query.answer("🛠 Maintenance — back soon", show_alert=True)
        elif m and update.effective_chat.type == "private": await m.reply_text("🛠 Maintenance — back soon.")
        raise ApplicationHandlerStop
    row = await D.get_user(u.id)
    if row and row["banned"]: raise ApplicationHandlerStop

async def my_chat_member(update: Update, ctx):
    c = update.my_chat_member
    if c.chat.type == ChatType.PRIVATE: return
    if c.new_chat_member.status in ("member", "administrator"):
        await D.execute("INSERT OR REPLACE INTO broadcast_targets(chat_id,kind,title,added_at) VALUES(?,?,?,?)", (c.chat.id, "channel" if c.chat.type == "channel" else "group", c.chat.title, D.now()))
    else: await D.execute("DELETE FROM broadcast_targets WHERE chat_id=?", (c.chat.id,))

async def on_error(update, ctx): log.exception("handler error", exc_info=ctx.error)

ptb.add_handler(TypeHandler(Update, pre), group=-1)
ptb.add_handler(onboarding.conversation())
for h in onboarding.stateless(): ptb.add_handler(h)

cmds = {"menu": menu.menu_cmd, "dream": A.dream_cmd, "crm": A.crm_cmd, "clone": A.clone_cmd, "whale": A.whale_cmd, "capsule": A.capsule_cmd, "roast": A.roast_cmd,
        "swarm": A.swarm_cmd, "ghost": A.ghost_cmd, "premium": E.premium_cmd, "buy": E.buy_cmd, "balance": E.balance_cmd, "lottery": E.lottery_cmd, "daily": E.daily_cmd,
        "referral": E.referral_cmd, "tasks": E.tasks_cmd, "addchannel": Ch.addchannel_cmd, "mychannels": Ch.mychannels_cmd, "removechannel": Ch.removechannel_cmd, "send": Ch.send_cmd,
        "ban": Mo.ban_cmd, "unban": Mo.unban_cmd, "kick": Mo.kick_cmd, "mute": Mo.mute_cmd, "warn": Mo.warn_cmd, "warnings": Mo.warnings_cmd, "captcha": Mo.captcha_cmd,
        "antiflood": Mo.antiflood_cmd, "trustscore": Mo.trustscore_cmd, "karma": Mo.karma_cmd, "level": Mo.level_cmd, "welcome": Mo.welcome_cmd, "rules": Mo.rules_cmd,
        "translate": Mo.translate_cmd, "stats": O.stats_cmd, "broadcast": O.broadcast_cmd, "grantpremium": O.grantpremium_cmd, "revokepremium": O.revokepremium_cmd,
        "setfreetier": O.setfreetier_cmd, "maintenance": O.maintenance_cmd, "logs": O.logs_cmd, "refund": O.refund_cmd, "stars_balance": O.stars_balance_cmd, "stars_withdraw": O.stars_withdraw_cmd}
for name, fn in cmds.items(): ptb.add_handler(CommandHandler(name, fn))

cb = lambda f, p: ptb.add_handler(CallbackQueryHandler(f, pattern=p))
cb(menu.menu_router, r"^menu:"); cb(E.buy_cb, r"^buy:"); cb(E.pack_cb, r"^pack:"); cb(E.lottery_cb, r"^lot:"); cb(E.task_cb, r"^task:")
cb(A.whale_sub_cb, r"^whale:sub:"); cb(A.roast_cb, r"^roast:"); cb(A.ghost_cb, r"^ghost:"); cb(A.clone_chat_cb, r"^clone:chat$"); cb(Mo.group_captcha_cb, r"^gc:")
ptb.add_handler(PreCheckoutQueryHandler(E.pre_checkout))
ptb.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, E.successful_payment))
ptb.add_handler(ChatMemberHandler(my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
ptb.add_handler(MessageHandler(GROUP & filters.StatusUpdate.NEW_CHAT_MEMBERS, Mo.new_members))
ptb.add_handler(MessageHandler(PRIV & filters.Document.ALL, A.doc_router))
ptb.add_handler(MessageHandler(PRIV & filters.TEXT & ~filters.COMMAND, A.text_router))
ptb.add_handler(MessageHandler(GROUP & ~filters.COMMAND & ~filters.StatusUpdate.ALL, Mo.group_tracker), group=1)
ptb.add_error_handler(on_error)

COMMAND_LIST = [("start", "Start"), ("menu", "Main menu"), ("clone", "Clone your style"), ("dream", "Dream analyzer"), ("crm", "Relationship CRM"), ("whale", "Crypto whale radar"),
                ("capsule", "Time capsule"), ("roast", "Roast"), ("swarm", "AI debate"), ("ghost", "AI reply drafts"), ("premium", "Premium"), ("buy", "Top up"),
                ("balance", "Wallet"), ("lottery", "Lottery"), ("daily", "Daily reward"), ("referral", "Referral"), ("tasks", "Tasks")]
BG = []
@asynccontextmanager
async def lifespan(app: FastAPI):
    await D.init_db(); await ptb.initialize(); await ptb.start()
    await ptb.bot.set_my_commands([BotCommand(c, d) for c, d in COMMAND_LIST])
    if WEBAPP_URL:
        if not WEBAPP_URL.startswith("https://"):
            raise RuntimeError("WEBAPP_URL must be the public HTTPS Railway domain, without a trailing slash.")
        await ptb.bot.set_webhook(f"{WEBAPP_URL}/webhook", secret_token=WEBHOOK_SECRET, drop_pending_updates=False,
                                  allowed_updates=["message", "callback_query", "pre_checkout_query", "my_chat_member"])
        log.info("Telegram webhook configured: %s/webhook", WEBAPP_URL)
    else:
        # First deployment: Railway must start once so its public domain can be generated.
        # Add WEBAPP_URL in Railway Variables afterwards; the next restart registers the webhook.
        log.warning("WEBAPP_URL is not set yet; web app can start, but Telegram updates will not arrive until it is configured.")
    BG.extend([asyncio.create_task(A.whale_loop(ptb.bot)), asyncio.create_task(A.capsule_loop(ptb.bot))])
    yield
    for t in BG: t.cancel()
    await ptb.stop(); await ptb.shutdown()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/healthz")
async def healthz(): return {"status": "ok"}

@app.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(None)):
    if not hmac.compare_digest(x_telegram_bot_api_secret_token or "", WEBHOOK_SECRET): raise HTTPException(403)
    await ptb.process_update(Update.de_json(await request.json(), ptb.bot)); return {"ok": True}

# ------------------------------------------------ Mini App API ------------------------------------------------
def verify(init_data: str) -> dict:
    """Telegram WebApp initData: HMAC-SHA256 (key = HMAC('WebAppData', bot_token)) + freshness check."""
    p = dict(parse_qsl(init_data or "", keep_blank_values=True)); h = p.pop("hash", None)
    if not h: raise HTTPException(401, "missing hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(p.items()))
    key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(key, check.encode(), hashlib.sha256).hexdigest(), h): raise HTTPException(401, "bad signature")
    if time.time() - int(p.get("auth_date", 0)) > 86400: raise HTTPException(401, "expired")
    return json.loads(p["user"])

async def me_(x_init_data: str):
    u = verify(x_init_data); db = await D.get_user(u["id"])
    if not db or not db["onboarded"]: raise HTTPException(403, "Open the bot and finish /start first")
    return db

@app.get("/api/me")
async def api_me(x_init_data: str = Header(...)):
    db = await me_(x_init_data); f, p = await D.ticket_counts(db["id"]); n = D.now()
    ads = (await D.fetchone("SELECT COUNT(*) c FROM ad_views WHERE user_id=? AND rewarded=1 AND completed_at>?", (db["id"], n - n % 86400)))["c"]
    return {"id": db["id"], "name": db["first_name"], "stars": db["stars"], "vip_tier": db["vip_tier"], "premium": D.is_premium(db), "premium_until": db["premium_until"],
            "streak": db["streak"], "tickets_free": f, "tickets_paid": p, "ads_today": ads, "ad_cap": AD_DAILY_CAP, "ad_reward": AD_REWARD, "monetag_zone": MONETAG_ZONE,
            "ticket_price": LOTTERY_TICKET_PRICE, "plans": PLANS, "packs": PACKS}

@app.get("/api/dreams")
async def api_dreams(x_init_data: str = Header(...)):
    db = await me_(x_init_data); rows = await D.fetchall("SELECT id,content,analysis,symbols,mood,created_at FROM dreams WHERE user_id=? ORDER BY id DESC LIMIT 60", (db["id"],))
    for r in rows: r["symbols"] = json.loads(r["symbols"] or "[]")
    return rows

@app.get("/api/crm")
async def api_crm(x_init_data: str = Header(...)):
    db = await me_(x_init_data); return await D.fetchall("SELECT id,name,relation,kind,date,note,status FROM crm_events WHERE user_id=? ORDER BY id DESC LIMIT 300", (db["id"],))

class Status(BaseModel): status: str
@app.patch("/api/crm/{eid}")
async def api_crm_patch(eid: int, body: Status, x_init_data: str = Header(...)):
    db = await me_(x_init_data)
    if body.status not in ("upcoming", "done"): raise HTTPException(400)
    await D.execute("UPDATE crm_events SET status=? WHERE id=? AND user_id=?", (body.status, eid, db["id"])); return {"ok": True}

@app.delete("/api/crm/{eid}")
async def api_crm_del(eid: int, x_init_data: str = Header(...)):
    db = await me_(x_init_data); await D.execute("DELETE FROM crm_events WHERE id=? AND user_id=?", (eid, db["id"])); return {"ok": True}

@app.post("/api/lottery/free")
async def api_free(x_init_data: str = Header(...)):
    db = await me_(x_init_data); today = time.strftime("%Y-%m-%d", time.gmtime())
    if db["last_free_ticket"] == today: raise HTTPException(400, "Already claimed today")
    await D.update_user(db["id"], last_free_ticket=today); await D.add_ticket(db["id"], 0); return {"ok": True}

@app.post("/api/lottery/buy")
async def api_buy_ticket(x_init_data: str = Header(...)):
    db = await me_(x_init_data)
    if not await D.spend(db["id"], LOTTERY_TICKET_PRICE): raise HTTPException(402, "Insufficient funds")
    await D.add_ticket(db["id"], 1); return {"ok": True}

@app.post("/api/lottery/spin")
async def api_spin(x_init_data: str = Header(...)):
    db = await me_(x_init_data); r = await D.play_ticket(db["id"])
    if not r: raise HTTPException(400, "No tickets")
    return {"prize": r["prize"], "paid": r["paid"]}

class Inv(BaseModel): kind: str; key: str
@app.post("/api/invoice")
async def api_invoice(body: Inv, x_init_data: str = Header(...)):
    db = await me_(x_init_data)
    if body.kind == "pack" and body.key in PACKS: title, stars = f"{PACKS[body.key]} Stars credits", PACKS[body.key]
    elif body.kind == "plan" and body.key in PLANS: title, stars = f"Premium {PLANS[body.key]['label']}", PLANS[body.key]["stars"]
    else: raise HTTPException(400, "bad product")
    link = await ptb.bot.create_invoice_link(title, "Trazen Society", f"{body.kind}:{body.key}", "XTR", [LabeledPrice(title, stars)], provider_token="")
    return {"link": link}

@app.post("/api/ad/start")
async def api_ad_start(x_init_data: str = Header(...)):
    db = await me_(x_init_data); n = D.now()
    if (await D.fetchone("SELECT COUNT(*) c FROM ad_views WHERE user_id=? AND rewarded=1 AND completed_at>?", (db["id"], n - n % 86400)))["c"] >= AD_DAILY_CAP: raise HTTPException(429, "Daily ad cap reached")
    tok = secrets.token_urlsafe(16); await D.execute("INSERT INTO ad_views(user_id,token,started_at) VALUES(?,?,?)", (db["id"], tok, n)); return {"token": tok}

class Tok(BaseModel): token: str
@app.post("/api/ad/complete")
async def api_ad_complete(body: Tok, x_init_data: str = Header(...)):
    db = await me_(x_init_data); v = await D.fetchone("SELECT * FROM ad_views WHERE token=? AND user_id=?", (body.token, db["id"]))
    if not v or v["rewarded"] or v["completed_at"]: raise HTTPException(400, "invalid token")
    if D.now() - v["started_at"] < AD_MIN_SECONDS: raise HTTPException(400, "ad not watched")
    await D.execute("UPDATE ad_views SET completed_at=? WHERE id=?", (D.now(), v["id"]))
    if AD_REQUIRE_POSTBACK: return {"pending": True}                  # reward comes from the network's postback
    await D.execute("UPDATE ad_views SET rewarded=1 WHERE id=?", (v["id"],)); await D.credit(db["id"], AD_REWARD); return {"reward": AD_REWARD}

@app.get("/api/ad/postback")          # Monetag S2S postback: /api/ad/postback?secret=..&ymid={token}&telegram_id={id}
@app.post("/api/ad/postback")
async def api_postback(request: Request):
    q = request.query_params
    if not hmac.compare_digest(q.get("secret", ""), AD_POSTBACK_SECRET): raise HTTPException(401)
    v = await D.fetchone("SELECT * FROM ad_views WHERE token=?", (q.get("ymid", ""),))
    if v and not v["rewarded"] and await D.execute("UPDATE ad_views SET rewarded=1, completed_at=COALESCE(completed_at,?) WHERE id=? AND rewarded=0", (D.now(), v["id"])):
        await D.credit(v["user_id"], AD_REWARD)
    return {"ok": True}

if os.path.isdir("web/dist"):
    app.mount("/assets", StaticFiles(directory="web/dist/assets"), name="assets")
    @app.get("/{path:path}")
    async def spa(path: str):
        f = os.path.join("web/dist", path)
        return FileResponse(f if path and os.path.isfile(f) else "web/dist/index.html")

if __name__ == "__main__": uvicorn.run(app, host="0.0.0.0", port=PORT)
