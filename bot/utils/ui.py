import functools, html
from telegram import Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes
from bot import database as D
from bot.config import OWNER_ID

def esc(s): return html.escape(str(s or ""))

async def send(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text, kb=None, photo=None):
    """Zero-clutter: in private chats the previous bot message (and the typed command) is deleted first."""
    chat = update.effective_chat; m = update.effective_message; private = chat.type == "private"
    if private:
        last = ctx.user_data.pop("last", None)
        if last:
            try: await ctx.bot.delete_message(chat.id, last)
            except TelegramError: pass
        if m and not update.callback_query and m.text and m.text.startswith("/"):
            try: await m.delete()
            except TelegramError: pass
    if photo: sent = await ctx.bot.send_photo(chat.id, photo, caption=text, reply_markup=kb, parse_mode="HTML")
    else: sent = await ctx.bot.send_message(chat.id, text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    if private: ctx.user_data["last"] = sent.message_id
    return sent

async def show(update, ctx, text, kb=None):
    """Menus: edit in place (caption if the menu is the photo message)."""
    q = update.callback_query
    if not q: return await send(update, ctx, text, kb)
    m = q.message
    try:
        if m.photo and len(text) <= 1000:
            await q.edit_message_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        elif m.photo:
            await m.delete(); return await send(update, ctx, text, kb)
        else:
            await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        if m.chat.type == "private": ctx.user_data["last"] = m.message_id
    except BadRequest as e:
        if "not modified" not in str(e).lower(): raise

async def toast(update, text, alert=False):
    """show_alert=True only for critical errors."""
    q = update.callback_query
    if q:
        try: await q.answer(text, show_alert=alert)
        except TelegramError: pass

def ready(fn):
    """Gate: onboarding done, not banned, maintenance off."""
    @functools.wraps(fn)
    async def w(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        u = update.effective_user
        db = await D.get_or_create_user(u.id, u.username, u.first_name)
        if update.effective_chat.type != "private":
            if not db["onboarded"]:
                from bot.keyboards import M, btn
                return await update.effective_message.reply_text("Start the bot in private first.",
                    reply_markup=M([[btn("Open bot", url=f"https://t.me/{ctx.bot.username}?start=g", raw=False)]]))
        elif not db["onboarded"]:
            from bot.handlers.onboarding import advance
            return await advance(update, ctx)
        if db["banned"] and u.id != OWNER_ID: return
        return await fn(update, ctx)
    return w

def owner_only(fn):
    @functools.wraps(fn)
    async def w(update, ctx):
        if update.effective_user.id != OWNER_ID: return
        return await fn(update, ctx)
    return w
