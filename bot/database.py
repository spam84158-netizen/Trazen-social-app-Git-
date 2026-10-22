import aiosqlite, secrets, time, random, os
from bot.config import DB_PATH, OWNER_ID, FREE_AI_DAILY

def now(): return int(time.time())

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, lang TEXT, captcha_passed INTEGER DEFAULT 0,
  onboarded INTEGER DEFAULT 0, kick_until INTEGER DEFAULT 0, stars REAL DEFAULT 0, is_premium INTEGER DEFAULT 0, premium_until INTEGER DEFAULT 0,
  vip_tier TEXT DEFAULT 'bronze', clone_style TEXT, referral_code TEXT UNIQUE, referred_by INTEGER, streak INTEGER DEFAULT 0,
  last_daily INTEGER DEFAULT 0, last_free_ticket TEXT, ai_day TEXT, ai_used INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, created_at INTEGER);
CREATE TABLE IF NOT EXISTS dreams(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT, analysis TEXT, symbols TEXT, mood TEXT, created_at INTEGER);
CREATE TABLE IF NOT EXISTS crm_events(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, relation TEXT, kind TEXT, date TEXT, note TEXT, status TEXT DEFAULT 'upcoming', created_at INTEGER);
CREATE TABLE IF NOT EXISTS capsules(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT, deliver_at INTEGER, delivered INTEGER DEFAULT 0, created_at INTEGER);
CREATE TABLE IF NOT EXISTS lottery_tickets(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, is_paid INTEGER DEFAULT 0, played INTEGER DEFAULT 0, prize REAL DEFAULT 0, created_at INTEGER);
CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, charge_id TEXT UNIQUE, payload TEXT, stars INTEGER, refunded INTEGER DEFAULT 0, created_at INTEGER);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, title TEXT, reward REAL, kind TEXT);
CREATE TABLE IF NOT EXISTS task_claims(user_id INTEGER, code TEXT, day TEXT, PRIMARY KEY(user_id, code, day));
CREATE TABLE IF NOT EXISTS ad_views(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, token TEXT UNIQUE, started_at INTEGER, completed_at INTEGER, rewarded INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS warnings(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER, reason TEXT, by_id INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS broadcast_targets(chat_id INTEGER PRIMARY KEY, kind TEXT, title TEXT, added_at INTEGER);
CREATE TABLE IF NOT EXISTS chat_settings(chat_id INTEGER PRIMARY KEY, welcome TEXT, rules TEXT, captcha INTEGER DEFAULT 0, antiflood INTEGER DEFAULT 0, translate INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS member_stats(chat_id INTEGER, user_id INTEGER, karma INTEGER DEFAULT 0, xp INTEGER DEFAULT 0, last_xp INTEGER DEFAULT 0, last_karma INTEGER DEFAULT 0, PRIMARY KEY(chat_id, user_id));
CREATE TABLE IF NOT EXISTS user_channels(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, chat_id INTEGER, title TEXT, username TEXT);
CREATE TABLE IF NOT EXISTS whale_subs(user_id INTEGER, symbol TEXT, last_price REAL, PRIMARY KEY(user_id, symbol));
CREATE TABLE IF NOT EXISTS roasts(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, text TEXT, score INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, user_id INTEGER, chat_id INTEGER, text TEXT);
"""
MIGRATE = ["lang TEXT", "captcha_passed INTEGER DEFAULT 0", "onboarded INTEGER DEFAULT 0", "kick_until INTEGER DEFAULT 0", "clone_style TEXT",
           "streak INTEGER DEFAULT 0", "last_daily INTEGER DEFAULT 0", "last_free_ticket TEXT", "ai_day TEXT", "ai_used INTEGER DEFAULT 0", "banned INTEGER DEFAULT 0",
           "premium_until INTEGER DEFAULT 0", "vip_tier TEXT DEFAULT 'bronze'"]
SEED_TASKS = [("share", "Share the bot", 2, "share"), ("ad", "Watch an ad", 5, "ad")]

async def fetchone(sql, a=()):
    async with aiosqlite.connect(DB_PATH, timeout=15) as db:
        db.row_factory = aiosqlite.Row
        r = await (await db.execute(sql, a)).fetchone()
        return dict(r) if r else None

async def fetchall(sql, a=()):
    async with aiosqlite.connect(DB_PATH, timeout=15) as db:
        db.row_factory = aiosqlite.Row
        return [dict(r) for r in await (await db.execute(sql, a)).fetchall()]

async def execute(sql, a=(), ret="rc"):
    async with aiosqlite.connect(DB_PATH, timeout=15) as db:
        cur = await db.execute(sql, a); await db.commit()
        return cur.rowcount if ret == "rc" else cur.lastrowid

async def init_db():
    parent = os.path.dirname(os.path.abspath(DB_PATH))
    os.makedirs(parent, exist_ok=True)
    async with aiosqlite.connect(DB_PATH, timeout=15) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.executescript(SCHEMA)
        for col in MIGRATE:
            try: await db.execute(f"ALTER TABLE users ADD COLUMN {col}")
            except Exception: pass
        for code, title, rw, kind in SEED_TASKS:
            await db.execute("INSERT OR IGNORE INTO tasks(code,title,reward,kind) VALUES(?,?,?,?)", (code, title, rw, kind))
        await db.commit()

# ---- users ----
async def get_user(uid): return await fetchone("SELECT * FROM users WHERE id=?", (uid,))

async def get_or_create_user(uid, username, first_name, ref=None):
    u = await get_user(uid)
    if u:
        if (u["username"], u["first_name"]) != (username, first_name):
            await execute("UPDATE users SET username=?, first_name=? WHERE id=?", (username, first_name, uid))
        return u
    ref_id = None
    if ref:
        ref = ref[4:] if ref.startswith("ref_") else ref
        r = await fetchone("SELECT id FROM users WHERE referral_code=?", (ref,))
        if r and r["id"] != uid: ref_id = r["id"]
    await execute("INSERT INTO users(id,username,first_name,referral_code,referred_by,created_at) VALUES(?,?,?,?,?,?)",
                  (uid, username, first_name, secrets.token_urlsafe(6)[:8], ref_id, now()))
    await execute("INSERT OR IGNORE INTO broadcast_targets(chat_id,kind,title,added_at) VALUES(?,?,?,?)", (uid, "user", first_name, now()))
    return await get_user(uid)

async def update_user(uid, **kw):
    if kw: await execute(f"UPDATE users SET {', '.join(k + '=?' for k in kw)} WHERE id=?", (*kw.values(), uid))

def is_premium(u): return bool(u and u["is_premium"] and u["premium_until"] > now())

async def credit(uid, amt): await execute("UPDATE users SET stars=stars+? WHERE id=?", (amt, uid))
async def spend(uid, amt): return await execute("UPDATE users SET stars=stars-? WHERE id=? AND stars>=?", (amt, uid, amt)) > 0

async def get_setting(k, d=None):
    r = await fetchone("SELECT value FROM settings WHERE key=?", (k,)); return r["value"] if r else d
async def set_setting(k, v): await execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))

async def ai_gate(uid):
    u = await get_user(uid)
    if uid == OWNER_ID or is_premium(u): return True
    lim = int(await get_setting("free_ai_daily", FREE_AI_DAILY)); day = time.strftime("%Y-%m-%d", time.gmtime())
    used = u["ai_used"] if u["ai_day"] == day else 0
    if used >= lim: return False
    await execute("UPDATE users SET ai_day=?, ai_used=? WHERE id=?", (day, used + 1, uid)); return True

# ---- lottery (BIAS RULE: free tickets can only give 0 or 0.01) ----
PRIZES = [0, 10, 25, 50, 100, 500]; WEIGHTS = [55, 25, 12, 5, 2, 1]   # EV = 15 < 25 ticket price
def roll(is_paid):
    if not is_paid: return 0.01 if random.random() < 0.05 else 0
    return random.choices(PRIZES, WEIGHTS)[0]

async def add_ticket(uid, paid=0): await execute("INSERT INTO lottery_tickets(user_id,is_paid,created_at) VALUES(?,?,?)", (uid, paid, now()))

async def play_ticket(uid):
    async with aiosqlite.connect(DB_PATH, timeout=15) as db:
        await db.execute("BEGIN IMMEDIATE")
        r = await (await db.execute("SELECT id,is_paid FROM lottery_tickets WHERE user_id=? AND played=0 ORDER BY is_paid DESC, id LIMIT 1", (uid,))).fetchone()
        if not r: await db.rollback(); return None
        prize = roll(r[1])
        await db.execute("UPDATE lottery_tickets SET played=1, prize=? WHERE id=?", (prize, r[0]))
        if prize: await db.execute("UPDATE users SET stars=stars+? WHERE id=?", (prize, uid))
        await db.commit(); return {"prize": prize, "paid": bool(r[1])}

async def ticket_counts(uid):
    r = await fetchone("SELECT COALESCE(SUM(is_paid=0),0) f, COALESCE(SUM(is_paid=1),0) p FROM lottery_tickets WHERE user_id=? AND played=0", (uid,))
    return r["f"], r["p"]
