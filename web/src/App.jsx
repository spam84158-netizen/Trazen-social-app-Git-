import { useEffect, useState, useCallback } from "react";
import { api, initData, tg } from "./api.js";
import { Landing, Wallet, Lottery, DreamMap, CRM, Earn } from "./pages.jsx";
import Logo from "./Logo.jsx";

const TABS = [["wallet", "💰", "Wallet"], ["lottery", "🎰", "Lottery"], ["dream", "🌙", "Dreams"], ["crm", "🧠", "CRM"], ["earn", "📺", "Earn"]];

export default function App() {
  const initial = new URLSearchParams(location.search).get("p") || "wallet";
  const [page, setPage] = useState(initial), [me, setMe] = useState(null), [err, setErr] = useState("");
  const reload = useCallback(() => api("/api/me").then(setMe).catch((e) => setErr(e.message)), []);
  useEffect(() => { tg?.ready(); tg?.expand(); tg?.setHeaderColor?.("#0a0a0f"); tg?.setBackgroundColor?.("#0a0a0f"); if (initData) reload(); }, [reload]);

  if (!initData || page === "landing") return <Landing />;          // opened in a normal browser
  if (err) return <div className="page center"><Logo size={56} /><p className="muted">{err}</p></div>;
  if (!me) return <div className="page center muted">Loading…</div>;
  const P = { wallet: Wallet, lottery: Lottery, dream: DreamMap, crm: CRM, earn: Earn }[page] || Wallet;
  return (
    <>
      <header className="top"><Logo size={28} /><b>Trazen Society</b><span className="chip">{me.stars}⭐</span></header>
      <P me={me} reload={reload} />
      <nav className="tabs">{TABS.map(([k, i, l]) => <button key={k} className={page === k ? "on" : ""} onClick={() => setPage(k)}><span>{i}</span>{l}</button>)}</nav>
    </>
  );
}
