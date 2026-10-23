const BACKEND = 'http://ambassador.seyori.name.ng:2059';
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PATCH,DELETE,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, x-init-data');
  if (req.method === 'OPTIONS') return res.status(200).end();
  const raw = Array.isArray(req.query.path) ? req.query.path.join('/') : String(req.query.path || '');
  const path = '/api/' + raw.split('/').filter(Boolean).join('/');
  const headers = { 'Content-Type': 'application/json' };
  if (req.headers['x-init-data']) headers['x-init-data'] = req.headers['x-init-data'];
  if (req.headers['authorization']) headers['authorization'] = req.headers['authorization'];
  try {
    const options = { method: req.method, headers, signal: AbortSignal.timeout(8000) };
    if (req.method !== 'GET' && req.method !== 'HEAD' && req.body) options.body = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);
    const response = await fetch(BACKEND + path, options);
    res.setHeader('Content-Type', response.headers.get('content-type') || 'application/json');
    res.status(response.status).send(await response.text());
  } catch (e) { res.status(502).json({ error: 'Backend unreachable' }); }
}
