// Synthetic HTTP contract for the built UI. Real reconstruction/rights are covered by API tests.
import { createHash, randomUUID } from "node:crypto";
import { trademarkExportCopy } from "../apps/web/lib/trademark-export-copy.ts";
export function trademarkExportFixture() {
  const prepared = new Map();
  return (route, method, body, { monitor, candidate, events, state }) => {
    const path = `/monitors/${monitor.id}/candidates/${candidate.id}/exports`;
    if (!route.startsWith(path)) return;
    const fail = (code) => ({ value: { code }, status: 409 }),
      ok = (value) => ({ value, status: 200 });
    if (!state.exportAllowed || state.sourceRevoked)
      return fail("trademark_source_use_denied");
    if (route === path && method === "POST") {
      if (body.expected_version !== candidate.version)
        return fail("trademark_version_conflict");
      const c = trademarkExportCopy[body.locale],
        escape = (s) =>
          String(s)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll('"', "&quot;");
      const event = events.find((e) => e.id === body.event_id),
        id = randomUUID();
      const document = `<!doctype html><html lang="${body.locale}"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'"><title>${escape(c.title)}</title></head><body><main><h1>${escape(c.title)}</h1><p>${escape(c.warning)}</p><h2>${escape(c.current)}</h2><p>${escape(candidate.facts.owners[0])}</p>${event?.previous ? `<h2>${escape(c.previous)}</h2><p>${escape(event.previous.facts.owners[0])}</p>` : ""}<p>${escape(c.deadlineUnavailable)}</p></main></body></html>`;
      const value = {
        id,
        document,
        content_sha256: createHash("sha256").update(document).digest("hex"),
        expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
        filename: `trademark-evidence-${id}.html`,
      };
      prepared.set(id, { value, version: candidate.version });
      return ok(value);
    }
    const id = route.slice(path.length + 1).split("/")[0],
      row = prepared.get(id);
    if (!row) return fail("trademark_export_not_found");
    if (row.version !== candidate.version || state.exportExpired)
      return fail("trademark_export_changed");
    if (
      route.endsWith("/download") &&
      body.expected_content_sha256 !== row.value.content_sha256
    )
      return fail("trademark_export_changed");
    return ok(row.value);
  };
}
