export const tg = window.Telegram?.WebApp;
export const initData = tg?.initData || "";
export const API_BASE = "/api/proxy";
export async function api(path, opts = {}) {
  const ctl = new AbortController(); const to = setTimeout(() => ctl.abort(), 20000);
  let r;
  try { r = await fetch(API_BASE + String(path).replace(/^\/api/, ""), { ...opts, signal: ctl.signal, headers: { "Content-Type": "application/json", "X-Init-Data": initData, ...(opts.headers || {}) } }); }
  catch (e) { throw new Error(e.name === "AbortError" ? "Server timeout" : "Network error"); }
  finally { clearTimeout(to); }
  if (!r.ok) { let m = r.statusText || "Error " + r.status; try { const j = await r.json(); m = j.detail || j.error || m; } catch {} throw new Error(m); }
  try { return await r.json(); } catch { throw new Error("Bad server response"); }
}
export const post = (p, body) => api(p, { method: "POST", body: JSON.stringify(body || {}) });
export const fmt = (n) => String(Math.round(Number(n) * 100) / 100);
export function toast(msg) { tg?.showPopup ? tg.showPopup({ message: msg }) : alert(msg); }
