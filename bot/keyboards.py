from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as M, WebAppInfo
from bot.config import CE, WEBAPP_URL
from bot.utils.fonts import sc

def btn(label, cb=None, eid=None, style=None, url=None, webapp=None, raw=False):
    """Inline button. Bot API 9.4 `style` + `icon_custom_emoji_id` are sent through api_kwargs (works on any PTB version)."""
    api = {}
    if eid: api["icon_custom_emoji_id"] = eid
    if style: api["style"] = style
    kw = dict(text=label if raw else sc(label), api_kwargs=api or None)
    if webapp: kw["web_app"] = WebAppInfo(webapp)
    elif url: kw["url"] = url
    else: kw["callback_data"] = cb
    return B(**kw)

def grid(btns, per_row=2):
    """Always 2 per row -> Telegram splits the row 50/50 (no gap). A lone last button spans the whole row."""
    return [btns[i:i + per_row] for i in range(0, len(btns), per_row)]

def kb(btns, back=None):
    rows = grid(btns)
    if back: rows.append([btn("⬅️ Back", back)])
    return M(rows)

def back(to="menu:home"): return M([[btn("⬅️ Back", to)]])

def web_btn(label, page="", eid=None, style="primary"):
    url = f"{WEBAPP_URL}/?p={page}" if page else WEBAPP_URL
    return btn(label, webapp=url, eid=eid, style=style) if url.startswith("https") else btn(label, url=url, eid=eid, style=style)

def main_menu(is_owner=False):
    b = [btn("Clone", "menu:clone", CE["clone"], "primary"), btn("Premium", "menu:premium", CE["premium"], "success"),
         btn("Lottery", "menu:lottery", CE["game"]), btn("Daily", "menu:daily", CE["daily"]),
         btn("Dream", "menu:dream", CE["think"]), btn("CRM", "menu:crm", CE["agent"]),
         btn("Whale", "menu:whale", CE["arch"]), btn("Capsule", "menu:capsule"),
         btn("Roast", "menu:roast", CE["fist"]), btn("Swarm", "menu:swarm", CE["agent"]),
         btn("Ghost", "menu:ghost"), btn("Referral", "menu:referral", CE["star"]),
         btn("Tasks", "menu:tasks", CE["gift"]), web_btn("Web App", "", CE["arch"], "primary")]
    if is_owner: b.append(btn("Admin", "menu:admin", CE["crown"], "danger"))
    return M(grid(b))
