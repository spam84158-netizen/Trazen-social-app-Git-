import { useEffect, useMemo, useRef, useState } from "react";
import { api, post, tg, fmt, toast } from "./api.js";
import Logo from "./Logo.jsx";

const BOT = "MordrexHood_bot";
const IMG = (id) => `https://images.unsplash.com/${id}?w=900&q=80`;

/* ---------------- Landing ---------------- */
export function Landing() {
  const features = [["🧬", "Clone", "Teach the AI your writing style from your chat export."], ["🌙", "Dream Map", "Decode dreams and watch them form a constellation."],
    ["🧠", "CRM", "Birthdays and relations pulled out of your chats."], ["🐋", "Whale radar", "Live crypto moves, straight to Telegram."],
    ["🎰", "Lottery", "Spin the wheel with Stars tickets."], ["📺", "Earn", "Watch ads, collect credits every day."]];
  return (
    <div className="page">
      <section className="hero" style={{ backgroundImage: `linear-gradient(180deg,rgba(10,10,15,.35),#0a0a0f), url(${IMG("photo-1451187580459-43490279c0fa")})` }}>
        <Logo size={72} />
        <h1>Trazen <span className="grad">Society</span></h1>
        <p>The AI-powered Telegram ecosystem: clone, dream, earn, win.</p>
        <a className="btn primary" href={`https://t.me/${BOT}`}>Open in Telegram</a>
      </section>
      <h2>Features</h2>
      <div className="grid2">{features.map(([i, t, d]) => <div className="glass" key={t}><div className="ico">{i}</div><b>{t}</b><p className="muted">{d}</p></div>)}</div>
      <h2>Pricing</h2>
      <div className="grid3">
        {[["1 Month", 50, "Unlimited AI"], ["3 Months", 120, "+5 tickets · +50⭐"], ["1 Year", 400, "+20 tickets · +200⭐ · Diamond VIP"]].map(([n, s, d], i) => (
          <div key={n} className={"glass price" + (i === 2 ? " best" : "")}><b>{n}</b><div className="big">{s}⭐</div><p className="muted">{d}</p></div>
        ))}
      </div>
      <p className="muted center">© Trazen Society</p>
    </div>
  );
}

/* ---------------- Wallet ---------------- */
export function Wallet({ me, reload }) {
  const pay = async (kind, key) => {
    try {
      const { link } = await post("/api/invoice", { kind, key });
      tg.openInvoice(link, (s) => { if (s === "paid") { toast("✅ Payment received"); setTimeout(reload, 1500); } });
    } catch (e) { toast(e.message); }
  };
  return (
    <div className="page">
      <div className="glass balance"><span className="muted">Balance</span><div className="big">{fmt(me.stars)}⭐</div>
        <div className="row"><span className={"chip tier-" + me.vip_tier}>{me.vip_tier.toUpperCase()}</span>
          {me.premium && <span className="chip ok">Premium until {new Date(me.premium_until * 1000).toLocaleDateString()}</span>}<span className="chip">🔥 {me.streak}</span></div></div>
      <h3>Top up</h3>
      <div className="grid3">{Object.entries(me.packs).map(([k, v]) => <button key={k} className="glass pick" onClick={() => pay("pack", k)}><b>{v}⭐</b><small>credits</small></button>)}</div>
      <h3>Premium</h3>
      <div className="grid3">{Object.entries(me.plans).map(([k, p]) => <button key={k} className="glass pick" onClick={() => pay("plan", k)}><b>{p.label}</b><small>{p.stars}⭐</small></button>)}</div>
    </div>
  );
}

/* ---------------- Lottery ---------------- */
const SEG = [0, 10, 0.01, 25, 0, 50, 100, 500];
const COL = ["#1f2937", "#7c3aed", "#374151", "#0891b2", "#1f2937", "#db2777", "#d97706", "#16a34a"];
export function Lottery({ me, reload }) {
  const [rot, setRot] = useState(0), [busy, setBusy] = useState(false), [res, setRes] = useState(null);
  const grad = SEG.map((_, i) => `${COL[i]} ${i * 45}deg ${(i + 1) * 45}deg`).join(",");
  const spin = async () => {
    if (busy) return; setBusy(true); setRes(null);
    try {
      const r = await post("/api/lottery/spin");
      const idxs = SEG.map((v, i) => (v === r.prize ? i : -1)).filter((i) => i >= 0); const i = idxs[Math.floor(Math.random() * idxs.length)];
      setRot((p) => p + 360 * 6 + ((360 - (i * 45 + 22.5)) - (p % 360) + 360) % 360);
      setTimeout(() => { setRes(r); setBusy(false); reload(); }, 4200);
    } catch (e) { toast(e.message); setBusy(false); }
  };
  const act = async (p) => { try { await post(p); reload(); } catch (e) { toast(e.message); } };
  return (
    <div className="page center">
      <div className="wheelwrap"><div className="pointer">▼</div>
        <div className="wheel" style={{ background: `conic-gradient(${grad})`, transform: `rotate(${rot}deg)` }}>
          {SEG.map((v, i) => <span key={i} style={{ transform: `rotate(${i * 45 + 22.5}deg) translateY(-112px)` }}>{v}</span>)}
        </div></div>
      <p className="muted">🎟 {me.tickets_free} free · {me.tickets_paid} paid · ⭐ {fmt(me.stars)}</p>
      {res && <div className="glass result">{res.prize ? `🎉 You won ${fmt(res.prize)}⭐` : "💨 No prize"}</div>}
      <button className="btn primary" disabled={busy || me.tickets_free + me.tickets_paid === 0} onClick={spin}>{busy ? "Spinning…" : "SPIN"}</button>
      <div className="row"><button className="btn" onClick={() => act("/api/lottery/free")}>Free ticket</button><button className="btn" onClick={() => act("/api/lottery/buy")}>Buy · {me.ticket_price}⭐</button></div>
      <p className="muted small">Free tickets only win the 0.01⭐ consolation. Paid tickets can win up to 500⭐.</p>
    </div>
  );
}

/* ---------------- Dream Map (constellation) ---------------- */
const hash = (s) => { let h = 2166136261; for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967295; };
export function DreamMap() {
  const [dreams, setDreams] = useState(null), [sel, setSel] = useState(null);
  useEffect(() => { api("/api/dreams").then(setDreams).catch((e) => toast(e.message)); }, []);
  const nodes = useMemo(() => (dreams || []).map((d) => ({ ...d, x: 30 + hash("x" + d.id) * 300, y: 30 + hash("y" + d.id) * 340, r: 4 + Math.min(d.symbols.length, 6) })), [dreams]);
  const edges = useMemo(() => { const e = []; nodes.forEach((a, i) => nodes.slice(i + 1).forEach((b) => { const s = a.symbols.filter((x) => b.symbols.includes(x)); if (s.length) e.push([a, b, s.length]); })); return e; }, [nodes]);
  if (!dreams) return <div className="page center muted">Loading…</div>;
  if (!dreams.length) return <div className="page center"><p className="muted">No dreams yet. Send /dream to the bot.</p></div>;
  return (
    <div className="page">
      <svg viewBox="0 0 360 400" className="sky">
        {edges.map(([a, b, w], i) => <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#8b5cf6" strokeOpacity={0.25 + w * 0.2} strokeWidth={w} />)}
        {nodes.map((n) => <g key={n.id} onClick={() => setSel(n)} style={{ cursor: "pointer" }}>
          <circle cx={n.x} cy={n.y} r={n.r * 2.4} fill="#22d3ee" opacity=".08" /><circle cx={n.x} cy={n.y} r={n.r} fill={sel?.id === n.id ? "#fff" : "#a5f3fc"} />
        </g>)}
      </svg>
      {sel ? <div className="glass"><b>{sel.mood}</b> · <span className="muted">{new Date(sel.created_at * 1000).toLocaleDateString()}</span><p>{sel.analysis}</p><div className="row wrap">{sel.symbols.map((s) => <span className="chip" key={s}>{s}</span>)}</div></div>
        : <p className="muted center">Tap a star to read the dream. Linked stars share symbols.</p>}
    </div>
  );
}

/* ---------------- CRM Kanban ---------------- */
function nextOccurrence(d) {
  const m = (d || "").match(/^(?:\d{4}-)?(\d{2})-(\d{2})$/); if (!m) return null;
  const now = new Date(), today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  let t = new Date(now.getFullYear(), +m[1] - 1, +m[2]);
  if (t < today) t = new Date(now.getFullYear() + 1, +m[1] - 1, +m[2]);
  return t;
}
export function CRM() {
  const [rows, setRows] = useState(null);
  const load = () => api("/api/crm").then(setRows).catch((e) => toast(e.message));
  useEffect(() => { load(); }, []);
  const setStatus = async (id, status) => { await api(`/api/crm/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }); load(); };
  const del = async (id) => { await api(`/api/crm/${id}`, { method: "DELETE" }); load(); };
  if (!rows) return <div className="page center muted">Loading…</div>;
  const soon = Date.now() + 30 * 864e5;
  const cols = { "This month": [], Upcoming: [], Done: [] };
  rows.forEach((r) => { const t = nextOccurrence(r.date); (r.status === "done" ? cols.Done : t && t.getTime() <= soon ? cols["This month"] : cols.Upcoming).push({ ...r, t }); });
  cols["This month"].sort((a, b) => a.t - b.t);
  return (
    <div className="page"><div className="kanban">
      {Object.entries(cols).map(([name, items]) => (
        <div className="col" key={name}><h4>{name} <span className="muted">{items.length}</span></h4>
          {items.map((r) => <div className="glass card" key={r.id}><b>{r.name}</b><div className="muted small">{r.kind || "event"} · {r.relation || "—"}</div><div className="small">📅 {r.date || "no date"}</div>{r.note && <div className="muted small">{r.note}</div>}
            <div className="row"><button className="mini" onClick={() => setStatus(r.id, r.status === "done" ? "upcoming" : "done")}>{r.status === "done" ? "↩︎" : "✓"}</button><button className="mini" onClick={() => del(r.id)}>🗑</button></div></div>)}
        </div>))}
    </div>{!rows.length && <p className="muted center">Empty. Send /crm to the bot and paste a chat.</p>}</div>
  );
}

/* ---------------- Earn (Monetag rewarded ads) ---------------- */
export function Earn({ me, reload }) {
  const [busy, setBusy] = useState(false); const loaded = useRef(false);
  useEffect(() => {
    if (!me.monetag_zone || loaded.current) return; loaded.current = true;
    const s = document.createElement("script"); s.src = "//libtl.com/sdk.js"; s.dataset.zone = me.monetag_zone; s.dataset.sdk = `show_${me.monetag_zone}`; document.head.appendChild(s);
  }, [me.monetag_zone]);
  const watch = async () => {
    const show = window[`show_${me.monetag_zone}`];
    if (!show) return toast("Ad network not configured yet (set MONETAG_ZONE).");
    setBusy(true);
    try {
      const { token } = await post("/api/ad/start");
      await show({ ymid: token });                                    // resolves when the viewer watched the whole ad
      const r = await post("/api/ad/complete", { token });
      toast(r.reward ? `+${r.reward}⭐` : "Reward pending…"); reload();
    } catch (e) { toast(e.message || "Ad closed early"); }
    setBusy(false);
  };
  return (
    <div className="page center">
      <div className="glass balance"><span className="muted">Today</span><div className="big">{me.ads_today}/{me.ad_cap}</div><p className="muted">+{me.ad_reward}⭐ per ad</p></div>
      <button className="btn primary" disabled={busy || me.ads_today >= me.ad_cap} onClick={watch}>{busy ? "Loading ad…" : "📺 Watch ad"}</button>
      <p className="muted small">Watch the whole ad to get your reward. Resets daily.</p>
    </div>
  );
}
