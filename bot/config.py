import os, hashlib
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "8725329015"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://127.0.0.1:8000").rstrip("/")
PORT = int(os.getenv("PORT", 8000))
DB_PATH = os.getenv("DB_PATH", "trazen.db")          # on Railway: /data/trazen.db (Volume)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or hashlib.sha256(BOT_TOKEN.encode()).hexdigest()[:32]

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")

# Ads (Monetag rewarded interstitial)
MONETAG_ZONE = os.getenv("MONETAG_ZONE", "")
AD_POSTBACK_SECRET = os.getenv("AD_POSTBACK_SECRET", "change_me")
AD_REQUIRE_POSTBACK = os.getenv("AD_REQUIRE_POSTBACK", "0") == "1"
AD_REWARD, AD_DAILY_CAP, AD_MIN_SECONDS = 5, 10, 12

MENU_PHOTO = "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1080&q=80"

FORCE_CHANNELS = [
    {"username": "Voldigone_Yuiiki", "name": "Vᴏʟᴅɪɢᴏɴᴇ Yᴜɪɪᴋɪ"},
    {"username": "Heaven_Helpchat", "name": "Hᴇᴀᴠᴇɴ Hᴇʟᴘ Cʜᴀᴛ"},
]

CE = {  # premium animated emoji ids
    "crown": "6021808310955545463", "premium": "5253844862528157321",
    "diamond": "5253737930727384427", "star": "5253844862528157321",
    "think": "5251386049585768540", "agent": "5251386049585768540",
    "arch": "5251660768578927322", "game": "5253526785840146919",
    "ok": "5343909794149310690", "user": "5251415238183511552",
    "clone": "5251415238183511552", "fist": "5253526785840146919",
    "daily": "5253601909113122325", "gift": "5253601909113122325",
}

PLANS = {
    "1m": {"label": "1 Month", "stars": 50, "days": 30, "tickets": 0, "bonus": 0, "tier": "silver"},
    "3m": {"label": "3 Months", "stars": 120, "days": 90, "tickets": 5, "bonus": 50, "tier": "gold"},
    "1y": {"label": "1 Year", "stars": 400, "days": 365, "tickets": 20, "bonus": 200, "tier": "diamond"},
}
PACKS = {"s50": 50, "s150": 150, "s500": 500}   # wallet top-up packs (price in Stars = credits)
LOTTERY_TICKET_PRICE = 25
WITHDRAW_MIN_STARS = 1000
FREE_AI_DAILY = 5
