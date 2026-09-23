# Cloud maintenance after Swiss {ai} Weeks

Status: DONE. H26-09, owner request and live verification on 23 September 2026.

Serve a polished English maintenance page on helveticlens.ch while the owner's
computer and Cloudflare Tunnel are offline. State the expected return as
24 September 2026 at 08:00 CEST (Europe/Zurich). Use original Alpine lens artwork.

The maintenance page and its image must run independently of the origin computer.
An edge Worker should pass healthy origin responses through unchanged and serve
an uncached 503 maintenance page for failed browser navigations. Preserve API
responses, authentication, request methods and user data; never forward private
request headers or URLs to the public maintenance asset host. Restore the normal
site automatically when the origin returns. Do not alter mail DNS records or
weaken domain protections. Retain an explicit preview route for inspection.

Acceptance: original artwork and responsive page; public cloud publication;
scoped routes for the root/www hostname; tests for healthy/authenticated traffic,
HTTP failures, network failures, API and unsafe methods; live proof with the
tunnel briefly stopped and then restored; existing production release healthy.
This is origin-independent outage presentation, not application high availability.

## Active cloud resources

- Preview on the product domain: https://helveticlens.ch/__maintenance/preview
- Public page and original image: https://helvetic-lens-maintenance.m-shavritskiy.chatgpt.site
- Cloudflare Worker: `helvetic-lens-maintenance-fallback`, deployed version
  `34a827e4`, with routes `helveticlens.ch/*` and `www.helveticlens.ch/*`.
- Both routes use fail-open execution limits, so a Worker quota failure does not
  block an otherwise healthy origin. This Worker does not implement authorization.
- Existing proxied tunnel DNS and mail records are unchanged. Neither the artwork
  nor the maintenance page depends on the origin machine or its tunnel.
- Sites project `appgprj_6ab4421cfa8481919a2017421c17e711`, public deployment
  `appgdep_6ab443946d84819184f6483ccb81aa50`, source commit
  `19b2966868bfb3bae4c05cdb9f84cd456d1062cb`. The adjacent development project
  `helvetic-lens-maintenance` contains the page, original image and generation
  prompt. Its independent source repository is hosted by Sites.

## Verified behavior

At 21:39 UTC, the deployment manager was idle and production readiness reported
`git-1357c738021b`. Only `helvetic-lens-cloudflared-1` was briefly stopped; database,
API and worker containers were retained. Anonymous browser requests to the root,
`/monitoring-profiles` and `www` each returned the full artwork page with HTTP 503
and `X-Helvetic-Maintenance: edge`. The 1,967,999-byte PNG independently returned
HTTP 200 while the tunnel was stopped. `/api/ready` retained the origin's HTTP 530
failure, rather than substituting HTML maintenance content for an API response.

The tunnel was restarted in a guaranteed cleanup step. Public readiness returned
HTTP 200 with the same release and healthy PostgreSQL/Redis. Maintenance responses
use `Cache-Control: no-store, max-age=0`, noindex and `Retry-After` for
24 September 2026 at 06:00 UTC / 08:00 CEST. Healthy origin responses, authentication
and cookies pass through unchanged. The asset request uses a constant URL and
only an Accept header; it never forwards visitor URLs, cookies, authorization or
request bodies. An embedded text notice covers failure of the cloud asset host.

Validation: the Sites production build passed; six Worker tests passed for
healthy/authentication responses, origin HTTP/network failure, privacy, API and
unsafe methods, preview/HEAD, asset failure and recovery. The required backlog
integrity check also passed before publication.

## Operation

The computer may be shut down normally. When the server and tunnel start again,
the Worker automatically resumes the application on the next healthy request.
The announced 08:00 return is informational: this change does not power on the
computer. Start the computer and its services before that time.

For future maintenance, update the date and copy in the Sites project, rebuild
the standalone `public/maintenance.html`, and publish that same Site. Update
`RETURN_AT` and emergency copy in `deploy/maintenance/worker.mjs`, run
`node --test deploy/maintenance/worker.test.mjs`, and publish that Worker. The
standalone asset may redirect from `/maintenance.html` to `/maintenance`; standard
fetch follows it. The preview endpoint intentionally returns HTTP 503.

Rollback consists of removing only these two Worker routes. This restores the
previous direct tunnel behavior; it does not delete the Site, Worker or DNS.
