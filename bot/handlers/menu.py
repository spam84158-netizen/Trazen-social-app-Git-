from telegram.constants import ChatType
from bot import database as D
from bot.handlers import onboarding, ai_features as A, economy as E, owner
from bot.utils.ui import ready, toast

@ready
async def menu_cmd(update, ctx):
    ctx.user_data.pop("await", None); await onboarding.render_home(update, ctx, force_new=True)

ROUTES = {"clone": A.clone_cmd, "premium": E.premium_cmd, "buy": E.buy_cmd, "lottery": E.lottery_cmd, "daily": E.daily_cmd, "dream": A.dream_cmd,
          "crm": A.crm_cmd, "whale": A.whale_cmd, "capsule": A.capsule_cmd, "roast": A.roast_cmd, "swarm": A.swarm_cmd, "ghost": A.ghost_cmd,
          "referral": E.referral_cmd, "tasks": E.tasks_cmd, "balance": E.balance_cmd, "admin": owner.admin_panel}

async def menu_router(update, ctx):
    q = update.callback_query; key = q.data.split(":")[1]
    db = await D.get_user(q.from_user.id)
    if not db or not db["onboarded"]: await toast(update, "…"); return await onboarding.advance(update, ctx)
    ctx.user_data.pop("await", None)
    try:
        if key == "home": await onboarding.render_home(update, ctx)
        elif key in ROUTES: await ROUTES[key](update, ctx)
    finally:
        try: await q.answer()
        except Exception: pass
