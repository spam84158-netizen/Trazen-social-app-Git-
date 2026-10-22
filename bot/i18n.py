LANGS = [("en", "🇬🇧 English"), ("fr", "🇫🇷 Français"), ("es", "🇪🇸 Español"), ("de", "🇩🇪 Deutsch"), ("ar", "🇸🇦 العربية")]
T = {
 "en": dict(pick="Choose your language", cap="Verify you are human:\n<b>{q} = ?</b>", cap_fail="❌ Wrong answer. Try again in {s}s.",
            cap_ok="✅ Verified", join="Join the channels below, then press the check button.", joined="✅ Welcome aboard!",
            nojoin="❌ You have not joined all channels yet!", check="I Joined", wait="⏳ Too many fails. Wait {s}s."),
 "fr": dict(pick="Choisis ta langue", cap="Prouve que tu es humain :\n<b>{q} = ?</b>", cap_fail="❌ Mauvaise réponse. Réessaie dans {s}s.",
            cap_ok="✅ Vérifié", join="Rejoins les canaux ci-dessous puis appuie sur vérifier.", joined="✅ Bienvenue à bord !",
            nojoin="❌ Tu n'as pas rejoint tous les canaux !", check="J'ai rejoint", wait="⏳ Trop d'échecs. Attends {s}s."),
 "es": dict(pick="Elige tu idioma", cap="Verifica que eres humano:\n<b>{q} = ?</b>", cap_fail="❌ Respuesta incorrecta. Reintenta en {s}s.",
            cap_ok="✅ Verificado", join="Únete a los canales y pulsa verificar.", joined="✅ ¡Bienvenido!",
            nojoin="❌ ¡Aún no te has unido a todos los canales!", check="Ya me uní", wait="⏳ Demasiados fallos. Espera {s}s."),
 "de": dict(pick="Wähle deine Sprache", cap="Bestätige, dass du ein Mensch bist:\n<b>{q} = ?</b>", cap_fail="❌ Falsch. Versuche es in {s}s erneut.",
            cap_ok="✅ Verifiziert", join="Tritt den Kanälen bei und drücke Prüfen.", joined="✅ Willkommen!",
            nojoin="❌ Du bist noch nicht allen Kanälen beigetreten!", check="Beigetreten", wait="⏳ Zu viele Fehler. Warte {s}s."),
 "ar": dict(pick="اختر لغتك", cap="تحقق أنك إنسان:\n<b>{q} = ?</b>", cap_fail="❌ إجابة خاطئة. حاول بعد {s} ثانية.",
            cap_ok="✅ تم التحقق", join="انضم إلى القنوات ثم اضغط تحقق.", joined="✅ أهلاً بك!",
            nojoin="❌ لم تنضم إلى كل القنوات بعد!", check="انضممت", wait="⏳ محاولات كثيرة. انتظر {s} ثانية."),
}
def t(lang, key, **kw): return T.get(lang or "en", T["en"]).get(key, T["en"][key]).format(**kw)
