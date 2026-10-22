export const tg = window.Telegram?.WebApp;
export const initData = tg?.initData || "";
export async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", "X-Init-Data": initData, ...(opts.headers || {}) } });
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  return r.json();
}
export const post = (p, body) => api(p, { method: "POST", body: JSON.stringify(body || {}) });
export const fmt = (n) => String(Math.round(Number(n) * 100) / 100);
export function toast(msg) { tg?.showPopup ? tg.showPopup({ message: msg }) : alert(msg); }
