import random
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, filters
from bot import database as D
from bot.config import OWNER_ID, CE, MENU_PHOTO
from bot.i18n import LANGS, t
from bot.keyboards import btn, grid, M, main_menu
from bot.services.force_join import check_membership, join_keyboard
from bot.utils.fonts import sc, em, mention, fmt
from bot.utils.ui import send, show, toast

LANG, CAPTCHA, JOIN = range(3)

async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    ref = ctx.args[0] if ctx.args and ctx.args[0] != "g" else None
    await D.get_or_create_user(u.id, u.username, u.first_name, ref)
    st = await advance(update, ctx)
    return st if st is not None else ConversationHandler.END

async def advance(update, ctx):
    """Single source of truth: decides the next onboarding step from the DB (survives restarts)."""
    u = update.effective_user; chat = update.effective_chat
    db = await D.get_user(u.id) or await D.get_or_create_user(u.id, u.username, u.first_name)
    if chat.type != "private":
        return await update.effective_message.reply_text("Open me in private to start 👇",
            reply_markup=M([[btn("Open bot", url=f"https://t.me/{ctx.bot.username}?start=g")]]))
    lang = db["lang"] or "en"
    if db["kick_until"] > D.now():
        await send(update, ctx, t(lang, "wait", s=db["kick_until"] - D.now())); return ConversationHandler.END
    if not db["lang"]:                                     # 1. language
        kb = M(grid([btn(n, f"lang:{c}", raw=True) for c, n in LANGS]))
        await show(update, ctx, f"{em(CE['crown'], '👑')} <b>{sc('TRAZEN SOCIETY')}</b>\n\n🌐 {t('en', 'pick')}", kb) if update.callback_query \
            else await send(update, ctx, f"{em(CE['crown'], '👑')} <b>{sc('TRAZEN SOCIETY')}</b>\n\n🌐 {t('en', 'pick')}", kb)
        return LANG
    if not db["captcha_passed"]:                           # 2. captcha
        a, b = random.randint(2, 9), random.randint(2, 9); ans = a + b
        opts = {ans}
        while len(opts) < 4: opts.add(max(2, ans + random.choice([-4, -3, -2, -1, 1, 2, 3, 4])))
        opts = random.sample(sorted(opts), 4); ctx.user_data["cap"] = ans
        kb = M(grid([btn(str(o), f"cap:{o}", raw=True) for o in opts]))
        txt = f"🤖 {t(lang, 'cap', q=f'{a} + {b}')}"
        await (show if update.callback_query else send)(update, ctx, txt, kb); return CAPTCHA
    if not await check_membership(ctx.bot, u.id):         # 3. force join
        txt = f"{em(CE['crown'], '👑')} <b>{sc('TRAZEN SOCIETY')}</b>\n\n{t(lang, 'join')}"
        await (show if update.callback_query else send)(update, ctx, txt, join_keyboard(lang)); return JOIN
    await finish(update, ctx, db); return ConversationHandler.END   # 4. main menu

async def finish(update, ctx, db):
    u = update.effective_user
    if not db["onboarded"]:
        await D.update_user(u.id, onboarded=1)
        await _referral_rewards(ctx, db)
    await toast(update, t(db["lang"], "joined"))
    await render_home(update, ctx, force_new=True)

async def _referral_rewards(ctx, db):
    """3-tier: L1 +5, L2 +2, L3 +1 credits."""
    cur, name = db["referred_by"], db["first_name"]
    for lvl, amt in enumerate((5, 2, 1), 1):
        if not cur: break
        await D.credit(cur, amt)
        try: await ctx.bot.send_message(cur, f"🎉 {sc('Referral')} L{lvl}: <b>{esc_name(name)}</b> +{amt}⭐", parse_mode="HTML")
        except Exception: pass
        r = await D.get_user(cur); cur = r["referred_by"] if r else None

def esc_name(n): 
    import html; return html.escape(str(n or ""))

async def lang_cb(update, ctx):
    q = update.callback_query; code = q.data.split(":")[1]
    await D.update_user(q.from_user.id, lang=code); await toast(update, "✅")
    st = await advance(update, ctx); return st if st is not None else ConversationHandler.END

async def captcha_cb(update, ctx):
    q = update.callback_query; u = q.from_user; db = await D.get_user(u.id); lang = db["lang"] or "en"
    if int(q.data.split(":")[1]) == ctx.user_data.get("cap"):
        await D.update_user(u.id, captcha_passed=1); await toast(update, t(lang, "cap_ok"))
    else:   # failed -> "kick": locked out for 2 minutes, must restart
        await D.update_user(u.id, kick_until=D.now() + 120); ctx.user_data.pop("cap", None)
        await toast(update, t(lang, "cap_fail", s=120), alert=True)
        await show(update, ctx, t(lang, "cap_fail", s=120)); return ConversationHandler.END
    st = await advance(update, ctx); return st if st is not None else ConversationHandler.END

async def force_cb(update, ctx):
    q = update.callback_query; db = await D.get_user(q.from_user.id); lang = (db or {}).get("lang") or "en"
    if await check_membership(ctx.bot, q.from_user.id):
        st = await advance(update, ctx); return st if st is not None else ConversationHandler.END
    await toast(update, t(lang, "nojoin"), alert=True); return JOIN

def home_text(u, db):
    return (f"{em(CE['crown'], '👑')} <b>{sc('TRAZEN SOCIETY')}</b>\n<i>{sc('IA · Clone · Premium · Earn')}</i>\n\n"
            f"{em(CE['user'], '👤')} {mention(u.id, u.first_name)}\n{em(CE['star'], '⭐')} {sc('Stars')} : <b>{fmt(db['stars'])}</b>\n\n<i>{sc('Choose an option')}</i>")

async def render_home(update, ctx, force_new=False):
    """Main menu = photo message (Unsplash). From a sub-menu we edit the caption in place."""
    u = update.effective_user; db = await D.get_user(u.id); kb = main_menu(u.id == OWNER_ID); txt = home_text(u, db)
    q = update.callback_query
    if q and q.message.photo and not force_new:
        await show(update, ctx, txt, kb); return
    if q:
        try: await q.message.delete()
        except Exception: pass
    await send(update, ctx, txt, kb, photo=MENU_PHOTO)

def conversation():
    only_cb = lambda p, f: CallbackQueryHandler(f, pattern=p)
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_cmd, filters=filters.ChatType.PRIVATE)],
        states={LANG: [only_cb(r"^lang:", lang_cb)], CAPTCHA: [only_cb(r"^cap:", captcha_cb)], JOIN: [only_cb(r"^force:check$", force_cb)]},
        fallbacks=[CommandHandler("start", start_cmd, filters=filters.ChatType.PRIVATE)],
        allow_reentry=True, name="onboarding")

# stateless fallbacks (used when the bot restarted and the in-memory conversation is gone)
def stateless():
    return [CallbackQueryHandler(lang_cb, pattern=r"^lang:"), CallbackQueryHandler(captcha_cb, pattern=r"^cap:"),
            CallbackQueryHandler(force_cb, pattern=r"^force:check$")]
