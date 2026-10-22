# Trazen Society — Telegram Bot + Mini App

## Architecture
```
trazen/
├── main.py                  FastAPI + webhook + Mini App API (/healthz, /webhook, /api/*)
├── Procfile · railway.json · nixpacks.toml · requirements.txt · .env.example
├── bot/
│   ├── config.py            env, plans, force-join channels, emoji ids
│   ├── database.py          SQLite schema + helpers (aiosqlite), lottery bias logic
│   ├── i18n.py              EN/FR/ES/DE/AR onboarding texts
│   ├── keyboards.py         2-per-row 50/50 grid, colored buttons (Bot API 9.4)
│   ├── services/force_join.py
│   ├── utils/ (ai.py · fonts.py · ui.py)
│   └── handlers/
│       ├── onboarding.py    Language → Captcha → Force Join → Main menu (photo)
│       ├── menu.py          menu router
│       ├── ai_features.py   /clone /dream /crm /whale /capsule /roast /swarm /ghost
│       ├── moderation.py    /ban /unban /kick /mute /warn /warnings /captcha /antiflood
│       │                    /trustscore /karma /level /welcome /rules /translate
│       ├── channels.py      /addchannel /mychannels /removechannel /send
│       ├── economy.py       /premium /buy /balance /lottery /daily /referral /tasks + Stars payments
│       └── owner.py         /stats /broadcast /grantpremium /revokepremium /setfreetier
│                            /maintenance /logs /refund /stars_balance /stars_withdraw
└── web/                     React 19 + Vite (Landing, Wallet, Lottery, Dream Map, CRM, Earn)
```

## Railway deployment
1. Push this folder to a GitHub repo → Railway → *New Project → Deploy from GitHub*.
2. **Volume**: add a Volume mounted on `/data` (SQLite persistence).
3. **Variables** (see `.env.example`): `BOT_TOKEN`, `OWNER_ID`, `OPENROUTER_API_KEY`, `DB_PATH=/data/trazen.db`, `AD_POSTBACK_SECRET`, `MONETAG_ZONE`.
4. *Settings → Networking → Generate Domain*, then set `WEBAPP_URL=https://<your-domain>` (must be https, no trailing slash) and redeploy. The webhook (`/webhook`, protected by a secret token) is registered automatically at startup.
5. Healthcheck is `/healthz` (already in `railway.json`). Build = `nixpacks.toml` (Python 3.11 + Node 20, builds `web/`).
6. In @BotFather: `/newapp` (Web App URL = your domain, short name `app`), and `/setdomain` for the bot.
7. Add the bot as **admin** in the force-join channels `@Voldigone_Yuiiki` and `@Heaven_Helpchat` (otherwise membership can't be checked and users stay blocked).
8. Local panel/VPS: `pip install -r requirements.txt && (cd web && npm i && npm run build) && python main.py`.

## Ad SDK (Monetag rewarded interstitial)
1. Create a Telegram Mini App *Rewarded interstitial* zone on Monetag → copy the **zone id** → `MONETAG_ZONE`.
2. Flow (already coded in `web/src/pages.jsx` + `main.py`): `POST /api/ad/start` (token) → `show_<ZONE>({ymid: token})` → `POST /api/ad/complete`. The server enforces ≥12 s, 10 ads/day, single-use tokens.
3. Safer mode: set `AD_REQUIRE_POSTBACK=1` and in Monetag set the postback URL to  
   `https://<domain>/api/ad/postback?secret=<AD_POSTBACK_SECRET>&ymid={ymid}&telegram_id={telegram_id}`  
   Rewards are then credited only when the network confirms the view.
4. Adsterra: same pattern — replace the script URL/show function in `Earn()`.

## Notes
- Buttons use `style` / `icon_custom_emoji_id` through `api_kwargs`, so they work on PTB 21.6 as long as Telegram accepts them.
- Stars withdrawal has no Bot API: use @BotFather / Fragment (the command explains it).
- Lottery bias: free tickets → `0` or `0.01⭐`; paid tickets EV = 15⭐ for a 25⭐ price.
