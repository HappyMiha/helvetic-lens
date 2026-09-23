/** Origin-independent maintenance for the explicitly configured product hosts. */
export const MAINTENANCE_ORIGIN = 'https://helvetic-lens-maintenance.m-shavritskiy.chatgpt.site';
export const PREVIEW_PATH = '/__maintenance/preview';
const PRODUCT_HOSTS = new Set(['helveticlens.ch', 'www.helveticlens.ch']);
const RETURN_AT = 'Thu, 24 Sep 2026 06:00:00 GMT';
const EMERGENCY_HTML = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Helvetic Lens — Maintenance</title><body style="margin:0;padding:10vh 8vw;background:#080f17;color:#fff;font:20px/1.6 system-ui"><h1>Helvetic Lens</h1><p>Sorry for the interruption. We are refreshing the site after Swiss {ai} Weeks.</p><p>Back on <strong>24 September 2026 at 08:00 CEST</strong> (Swiss time).</p><p>Thank you for your patience.</p></body></html>';

function headers(type) {
  return {
    'Content-Type': type,
    'Cache-Control': 'no-store, max-age=0',
    'Retry-After': Date.now() < Date.parse(RETURN_AT) ? RETURN_AT : '120',
    'X-Helvetic-Maintenance': 'edge',
    'X-Robots-Tag': 'noindex, nofollow',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'Content-Security-Policy': `default-src 'none'; img-src ${MAINTENANCE_ORIGIN} data:; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'`,
  };
}

export function createHandler(fetcher = fetch) {
  async function maintenance(request) {
    let body = EMERGENCY_HTML;
    try {
      // Deliberately send no original URL, query, cookies, auth or request body.
      const page = await fetcher(`${MAINTENANCE_ORIGIN}/maintenance.html`, {
        headers: { Accept: 'text/html' },
        cf: { cacheEverything: true, cacheTtl: 3600 },
      });
      if (page.ok && page.headers.get('content-type')?.includes('text/html')) {
        const candidate = await page.text();
        if (candidate.includes('id="maintenance-title"')) body = candidate;
      }
    } catch { /* The edge retains a useful notice even if the asset host fails. */ }
    return new Response(request.method === 'HEAD' ? null : body, {
      status: 503, headers: headers('text/html; charset=utf-8'),
    });
  }
  return {
    async fetch(request) {
      const url = new URL(request.url);
      const safeMethod = request.method === 'GET' || request.method === 'HEAD';
      if (safeMethod && (url.pathname === PREVIEW_PATH || !PRODUCT_HOSTS.has(url.hostname))) {
        return maintenance(request);
      }
      let origin;
      try { origin = await fetcher(request); } catch { /* Unreachable origin. */ }
      if (origin && origin.status < 500) return origin;
      const navigation = safeMethod && !url.pathname.startsWith('/api/') &&
        url.pathname !== '/api' && request.headers.get('accept')?.includes('text/html');
      if (navigation) return maintenance(request);
      // Preserve the API's own errors and never replay unsafe requests.
      if (origin) return origin;
      return new Response(request.method === 'HEAD' ? null : JSON.stringify({
        error: 'maintenance', message: 'Helvetic Lens is temporarily unavailable. Expected back 24 September 2026 at 08:00 CEST.',
      }), { status: 503, headers: headers('application/json; charset=utf-8') });
    },
  };
}
export default createHandler();
