// Disposable localhost UI fixture; synthetic identities and auction interests, no auction source access.
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { Readable } from "node:stream";
import { resolve } from "node:path";
import { readFile, writeFile, mkdir } from "node:fs/promises";
const root = resolve(import.meta.dirname, ".."),
  id = "00000000-0000-4000-8000-000000000071";
const reserve = createServer();
reserve.listen(0, "127.0.0.1");
await once(reserve, "listening");
const nextPort = reserve.address().port;
await new Promise((done) => reserve.close(done));
const child = spawn(
  process.execPath,
  [
    resolve(root, "node_modules/next/dist/bin/next"),
    "start",
    "-H",
    "127.0.0.1",
    "-p",
    String(nextPort),
  ],
  {
    cwd: resolve(root, "apps/web"),
    env: process.env,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  },
);
child.stdout.on("data", (data) => process.stdout.write(data));
child.stderr.on("data", (data) => process.stderr.write(data));
let state = {
    locale: "en-CH",
    manager: true,
    denied: false,
    conflict: false,
    sourceReady: false,
    revoked: false,
  },
  monitor = null,
  history = [];
const itemId = "00000000-0000-4000-8000-000000000072";
const eventId = "00000000-0000-4000-8000-000000000073";
const reminderId = "00000000-0000-4000-8000-000000000074";
let acknowledged = false,
  reminderVersion = 1,
  email = null;
function reminderView() {
  if (!item?.following || !monitor?.configuration.notify.ending_soon_hours)
    return null;
  return {
    id: reminderId,
    version: reminderVersion,
    state: acknowledged ? "acknowledged" : "ready",
    hours: monitor.configuration.notify.ending_soon_hours,
    eligible: !acknowledged && !state.revoked,
    due_at: state.revoked ? null : "2026-09-19T12:00:00Z",
    ends_at: state.revoked ? null : sourceFacts.ends_at,
    current: itemView(),
    href: `/auction-watch?monitor=${id}&reminder=${reminderId}`,
  };
}
let sourceSequence = 1,
  item = null,
  versions = [],
  sourceFacts = {
    title: "Synthetic vehicle lot",
    description: "PRIVATE-AUCTION-DESCRIPTION",
    canton: "TI",
    auction_id: "185",
    lot_id: "1",
    authority: "Synthetic cantonal office",
    category: "vehicles",
    asset_location: "Lugano",
    brand: "Example",
    prices: [{ kind: "current_bid", currency: "CHF", amount_minor: 850000 }],
    status: "open",
    ends_at: "2026-09-20T12:00:00Z",
    observed_at: "2026-09-14T08:00:00Z",
    source_url: "https://auction.example.invalid/auction/185",
    documents: {
      state: "complete",
      items: [{ official_id: "doc-1", title: "Conditions" }],
    },
  };
function itemView() {
  if (!item) return null;
  const available = !state.revoked && item.sourceSequence === sourceSequence;
  return {
    ...item,
    monitor_id: id,
    state: available ? "available" : "unavailable",
    can_review: available,
    state_hash: available
      ? String(sourceSequence).padStart(64, "0")
      : undefined,
    facts: available ? sourceFacts : null,
    attribution: available ? "Synthetic cantonal office" : undefined,
    assessment: available
      ? {
          status:
            sourceFacts.prices[0]?.amount_minor > 1200050
              ? "excluded"
              : "match",
          reasons: [
            { field: "canton", status: "match" },
            { field: "category", status: "match" },
            {
              field: "prices.current_bid",
              status:
                sourceFacts.prices[0]?.amount_minor > 1200050
                  ? "excluded"
                  : "match",
            },
          ],
        }
      : null,
  };
}
const requests = [],
  audits = [];
const server = createServer(async (req, res) => {
  const url = new URL(req.url, "http://127.0.0.1"),
    path = url.pathname;
  const json = (value, status = 200) => {
    res.writeHead(status, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    res.end(JSON.stringify(value));
  };
  try {
    if (path === "/__qa/axe.js") {
      res.writeHead(200, { "Content-Type": "text/javascript" });
      return res.end(
        await readFile(resolve(root, "node_modules/axe-core/axe.min.js")),
      );
    }
    if (path.startsWith("/api/") || path.startsWith("/__qa/")) {
      let text = "";
      for await (const chunk of req) {
        text += chunk;
        if (text.length > 1024 * 1024) throw Error("Fixture input limit");
      }
      const body = text ? JSON.parse(text) : {};
      if (path === "/__qa/state") {
        state = { ...state, ...body };
        return json(state);
      }
      if (path === "/__qa/source") {
        sourceSequence += 1;
        sourceFacts = { ...sourceFacts, ...body };
        return json({ sequence: sourceSequence });
      }
      if (path === "/__qa/requests") return json(requests);
      if (path === "/__qa/audit") {
        audits.push(body);
        await mkdir(resolve(root, "test-results/accessibility"), {
          recursive: true,
        });
        await writeFile(
          resolve(root, "test-results/accessibility/auction-audit.json"),
          JSON.stringify(audits, null, 2),
        );
        return json({ saved: true });
      }
      if (path === "/__qa/finish") {
        await writeFile(
          resolve(root, ".tmp/auction-browser-requests.json"),
          JSON.stringify(requests, null, 2),
        );
        json({ finished: true });
        server.close();
        child.kill();
        return;
      }
      requests.push({ path, method: req.method, body });
      if (path === "/api/auth/session")
        return json({
          authenticated: true,
          user: {
            id: "auction-qa",
            name: "Auction QA",
            email: "synthetic@example.invalid",
            locale: state.locale,
          },
          organization: { id: "auction-qa-org", name: "Synthetic QA" },
          role: state.manager ? "organization_admin" : "viewer",
          platform_admin: false,
          onboarding_required: false,
        });
      if (path === "/api/health")
        return json({
          status: "ok",
          database: "synthetic",
          apertus: { configured: false },
          firecrawl: { configured: false },
        });
      if (path.startsWith("/api/auction-watch")) {
        if (state.denied) return json({ code: "membership_required" }, 403);
        if (req.method !== "GET" && !state.manager)
          return json({ code: "subject_role_denied" }, 403);
        const route = path.slice("/api/auction-watch".length);
        if (route === "/reminders") {
          const reminder = reminderView();
          return json({
            items: reminder?.eligible ? [reminder] : [],
            next_cursor: null,
            unavailable_count: state.revoked ? 1 : 0,
          });
        }
        if (route === "/capabilities")
          return json({
            drafts_available: true,
            start_available: false,
            live_results_checked: false,
          });
        if (route === "/preview")
          return json({
            start_available: state.sourceReady && !state.revoked,
            source_attributions: ["Synthetic cantonal office"],
            unverified_cantons: [],
            coverage_verified: false,
          });
        if (route === "/today" || route === "/inbox") {
          const available = item && itemView().state === "available";
          return json({
            items:
              available && item.needs_review && monitor.status === "active"
                ? [
                    {
                      id: eventId,
                      name: monitor.configuration.name,
                      title: sourceFacts.title,
                      canton: sourceFacts.canton,
                      auction_id: sourceFacts.auction_id,
                      lot_id: sourceFacts.lot_id,
                      attribution: "Synthetic cantonal office",
                      detected_at: sourceFacts.observed_at,
                      change_codes: [
                        sourceFacts.status === "cancelled"
                          ? "cancelled"
                          : sourceSequence > 1
                            ? "price_above_limit"
                            : "new_match",
                      ],
                      href: `/auction-watch?monitor=${id}&event=${eventId}`,
                    },
                  ]
                : [],
            next_cursor: null,
            has_active_monitors: monitor?.status === "active",
            unavailable_count: item && !available ? 1 : 0,
            coverage_verified: false,
          });
        }
        if (route === "/monitors") {
          if (req.method === "POST") {
            monitor = {
              id,
              status: "draft",
              configuration: body.configuration,
              version: 1,
              revision: 1,
            };
            item = null;
            acknowledged = false;
            reminderVersion = 1;
            email = null;
            versions = [];
            history = [
              {
                revision: 1,
                configuration: structuredClone(body.configuration),
              },
            ];
            return json(monitor, 201);
          }
          return json({ items: monitor ? [monitor] : [], next_cursor: null });
        }
        if (!monitor) return json({ code: "auction_monitor_not_found" }, 404);
        if (route === `/monitors/${id}/reminders`) {
          const reminder = reminderView();
          return json({
            items: reminder ? [reminder] : [],
            next_cursor: null,
            unavailable_count: 0,
          });
        }
        if (route.startsWith(`/monitors/${id}/reminders/${reminderId}`)) {
          if (!reminderView())
            return json({ code: "auction_reminder_not_found" }, 404);
          if (route.endsWith("/acknowledge")) {
            if (body.expected_version !== reminderVersion)
              return json({ code: "auction_version_conflict" }, 409);
            acknowledged = true;
            reminderVersion += 1;
          }
          return json(reminderView());
        }
        if (route === `/monitors/${id}/email/preview`)
          return json({
            status:
              email?.consent_active && !state.revoked ? "ready" : "unavailable",
            quiet_hours: false,
            more_available: false,
            items:
              email?.consent_active && reminderView()?.eligible
                ? [
                    {
                      kind: "ending_soon",
                      detected_at: sourceFacts.observed_at,
                      href: reminderView().href,
                    },
                  ]
                : [],
          });
        if (route === `/monitors/${id}/email`) {
          if (req.method === "PUT") {
            if (body.expected_version !== monitor.version || state.conflict)
              return json({ code: "auction_version_conflict" }, 409);
            email = {
              revision: (email?.revision || 0) + 1,
              configuration: body.configuration,
              consent_active: body.consent,
            };
            monitor.version += 1;
          }
          return json({
            revision: 0,
            configuration: {
              timezone: "Europe/Zurich",
              delivery: { email: "off", digest_at: null, quiet_hours: null },
            },
            consent_active: false,
            ...email,
            monitor_version: monitor.version,
            email_verified: true,
            recipient_email: "synthetic@example.invalid",
            mail_available: true,
            uncertain_deliveries: 0,
          });
        }
        if (route === `/monitors/${id}/events/${eventId}` && item) {
          const snapshot = (v) =>
            !v
              ? null
              : {
                  state: state.revoked ? "unavailable" : "available",
                  facts: state.revoked ? null : v.facts,
                };
          return json({
            id: eventId,
            detected_at: sourceFacts.observed_at,
            change_codes: [
              sourceFacts.status === "cancelled"
                ? "cancelled"
                : sourceSequence > 1
                  ? "price_above_limit"
                  : "new_match",
            ],
            current_configuration: true,
            newer_available: false,
            snapshot: snapshot(versions[0]),
            previous: snapshot(versions[1]),
            current: itemView(),
          });
        }
        if (route === `/monitors/${id}/revisions`)
          return json({ items: history, next_cursor: null });
        if (route === `/monitors/${id}/items`)
          return json({
            items:
              item &&
              (!url.searchParams.get("following_only") ||
                url.searchParams.get("following_only") === "false" ||
                item.following)
                ? [itemView()]
                : [],
            next_cursor: null,
            coverage_verified: false,
          });
        if (route === `/monitors/${id}/items/${itemId}/history`) {
          if (state.revoked)
            return json({ code: "auction_permission_unavailable" }, 409);
          return json({ items: versions, next_cursor: null });
        }
        if (route === `/monitors/${id}/refresh`) {
          if (monitor.status !== "active")
            return json({ code: "auction_monitor_not_active" }, 409);
          if (!state.revoked) {
            if (!item)
              item = {
                id: itemId,
                sourceSequence,
                version: 1,
                following: false,
                decision: null,
                needs_review: true,
              };
            else if (item.sourceSequence !== sourceSequence)
              item = {
                ...item,
                sourceSequence,
                version: item.version + 1,
                needs_review: true,
              };
            if (!versions.some((v) => v.sequence === sourceSequence))
              versions.unshift({
                id: String(sourceSequence),
                sequence: sourceSequence,
                state: "available",
                facts: structuredClone(sourceFacts),
              });
          }
          monitor.runtime = {
            health: state.revoked ? "source_unavailable" : "current",
            last_check_at: sourceFacts.observed_at,
            next_check_at: "2026-09-14T08:01:00Z",
          };
          return json(monitor.runtime);
        }
        if (route.startsWith(`/monitors/${id}/items/${itemId}/`)) {
          if (!item || body.expected_version !== item.version || state.conflict)
            return json({ code: "auction_version_conflict" }, 409);
          if (
            body.following !== false &&
            (state.revoked || item.sourceSequence !== sourceSequence)
          )
            return json({ code: "auction_item_refresh_required" }, 409);
          if (route.endsWith("/follow"))
            item = {
              ...item,
              version: item.version + 1,
              following: body.following,
            };
          else if (route.endsWith("/decision"))
            item = {
              ...item,
              version: item.version + 1,
              decision: body.decision,
              needs_review: false,
            };
          else return json({ code: "fixture_unknown_route" }, 404);
          return json(itemView());
        }
        if (
          req.method !== "GET" &&
          (body.expected_version !== monitor.version || state.conflict)
        )
          return json({ code: "auction_version_conflict" }, 409);
        if (route === `/monitors/${id}/start`) {
          if (!state.sourceReady || state.revoked)
            return json({ code: "auction_source_not_configured" }, 409);
          monitor = {
            ...monitor,
            status: "active",
            version: monitor.version + 1,
            runtime: {
              health: "waiting",
              last_check_at: null,
              next_check_at: sourceFacts.observed_at,
            },
          };
          return json(monitor);
        }
        if (route === `/monitors/${id}/pause`) {
          monitor = {
            ...monitor,
            status: "paused",
            version: monitor.version + 1,
            runtime: { ...monitor.runtime, next_check_at: null },
          };
          return json(monitor);
        }
        if (route === `/monitors/${id}/archive`) {
          monitor = {
            ...monitor,
            status: "archived",
            version: monitor.version + 1,
          };
          return json(monitor);
        }
        if (route === `/monitors/${id}`) {
          if (req.method === "DELETE") {
            monitor = null;
            history = [];
            return json({ deleted: true });
          }
          if (req.method === "PATCH") {
            monitor = {
              ...monitor,
              configuration: body.configuration,
              version: monitor.version + 1,
              revision: monitor.revision + 1,
            };
            history.unshift({
              revision: monitor.revision,
              configuration: structuredClone(body.configuration),
            });
          }
          return json(monitor);
        }
        return json({ code: "fixture_unknown_route" }, 404);
      }
      if (path === "/api/interest-feed")
        return json({
          items: [],
          scanned_event_count: 0,
          has_more: false,
          next_cursor: null,
        });
      return json({ code: "unavailable" }, 503);
    }
    const response = await fetch(`http://127.0.0.1:${nextPort}${req.url}`, {
      redirect: "manual",
      signal: AbortSignal.timeout(15000),
    });
    const headers = Object.fromEntries(response.headers);
    delete headers["content-encoding"];
    delete headers["content-length"];
    res.writeHead(response.status, headers);
    if (response.body) Readable.fromWeb(response.body).pipe(res);
    else res.end();
  } catch (error) {
    json({ code: "fixture_error", detail: String(error) }, 500);
  }
});
server.listen(0, "127.0.0.1");
await once(server, "listening");
console.log(
  JSON.stringify({
    fixture: `http://127.0.0.1:${server.address().port}`,
    nextPort,
    id,
  }),
);
child.once("exit", (code) => {
  server.close();
  process.exitCode = code || 0;
});
