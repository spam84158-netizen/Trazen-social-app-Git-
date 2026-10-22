import httpx, json, re, logging
from bot.config import OPENROUTER_KEY, OPENROUTER_MODEL
log = logging.getLogger("ai")
LANGNAME = {"en": "English", "fr": "French", "es": "Spanish", "de": "German", "ar": "Arabic"}

async def ask(system, user, *, max_tokens=700, temperature=0.8, history=None):
    if not OPENROUTER_KEY: return "⚠️ OPENROUTER_API_KEY is missing."
    msgs = [{"role": "system", "content": system}] + (history or []) + [{"role": "user", "content": user}]
    try:
        async with httpx.AsyncClient(timeout=90) as c:
            r = await c.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "X-Title": "Trazen Society"},
                json={"model": OPENROUTER_MODEL, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning("AI error: %s", e); return "⚠️ AI is unavailable right now, try again soon."

async def ask_json(system, user, **kw):
    t = await ask(system + "\nReturn ONLY valid JSON. No markdown, no commentary.", user, temperature=0.3, **kw)
    m = re.search(r"[\[{].*[\]}]", t, re.S)
    try: return json.loads(m.group(0)) if m else None
    except Exception: return None
