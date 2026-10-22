import html
_S = dict(zip("abcdefghijklmnopqrstuvwxyz", "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"))
def sc(x) -> str:
    return "".join(_S.get(c.lower(), c) for c in str(x))
def em(eid, fb): return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>'
def mention(uid, name): return f'<a href="tg://user?id={uid}">{html.escape(str(name or uid))}</a>'
def fmt(n): return f"{round(float(n), 2):g}"
