import logging
from bot.config import FORCE_CHANNELS, OWNER_ID
from bot.keyboards import btn, M, grid
from bot.i18n import t
log = logging.getLogger("force_join")

async def check_membership(bot, uid) -> bool:
    if uid == OWNER_ID: return True
    for ch in FORCE_CHANNELS:
        try:
            m = await bot.get_chat_member(f"@{ch['username']}", uid)
            if m.status not in ("member", "administrator", "creator") and not (m.status == "restricted" and getattr(m, "is_member", False)):
                return False
        except Exception as e:
            log.warning("force-join check failed for @%s (is the bot admin there?): %s", ch["username"], e); return False
    return True

def join_keyboard(lang="en"):
    chans = [btn(f"📢 {c['name']}", url=f"https://t.me/{c['username']}", style="primary", raw=True) for c in FORCE_CHANNELS]
    rows = grid(chans)
    rows.append([btn(f"✅ {t(lang, 'check')}", "force:check", style="success")])
    return M(rows)
