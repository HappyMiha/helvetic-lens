// Synthetic API transport plus real browser/filesystem download assertions.
// Source authorization is exercised separately by native API/PostgreSQL tests.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readdir, readFile, unlink } from "node:fs/promises";
import { join } from "node:path";
import { evaluate, sleep } from "./browser-cdp.mjs";
import { evidenceExportCopy } from "../apps/web/lib/monitoring-evidence-export-copy.ts";

const prefix = "/api/monitoring-centre/evidence/export/";
const hash = (text) => createHash("sha256").update(text).digest("hex");
export class EvidenceExportFixture {
  constructor() {
    this.mode = "ready";
    this.requests = [];
    this.files = 0;
    this.failures = [];
  }
  async setup(cdp, root) {
    this.cdp = cdp;
    this.directory = await mkdtemp(join(root, ".tmp/evidence-download-"));
    await cdp.send("Browser.setDownloadBehavior", {
      behavior: "allow",
      downloadPath: this.directory,
    });
  }
  async downloadedFiles() {
    // Managed Chrome may update an extension in this disposable directory.
    // Track this application's JSON downloads, including incomplete writes.
    return (await readdir(this.directory)).filter(
      (name) => name.startsWith("helvetic-lens-") || name.endsWith(".json"),
    );
  }
  async respond(id, body, code = 200) {
    await this.cdp
      .send("Fetch.fulfillRequest", {
        requestId: id,
        responseCode: code,
        responseHeaders: [
          { name: "Content-Type", value: "application/json" },
          { name: "Cache-Control", value: "no-store" },
        ],
        body: Buffer.from(JSON.stringify(body)).toString("base64"),
      })
      .catch(() => {});
  }
  async handle({ requestId, request }) {
    const path = new URL(request.url).pathname;
    if (!path.startsWith(prefix)) return false;
    try {
      assert.equal(request.method, "POST");
      const body = JSON.parse(request.postData);
      this.requests.push({ path, body, mode: this.mode });
      let data;
      if (path.endsWith("/preview")) {
        this.selection = body;
        const manifest = {
          format: "helvetic-lens-monitoring-evidence-v1",
          locale: body.locale,
          scope: { organization_id: "org-a", user_id: "owner" },
          selection: {
            domain: body.domain,
            monitor_id: body.monitor_id,
            item_id: body.item_id,
            sequence: body.sequence ?? 2,
            revision_id: body.revision_id ?? "retained-native-version",
          },
          configuration_revision: 1,
        };
        // Preserve decimal and large integer bytes rather than JS reserialization.
        const canonical_json = JSON.stringify({
          manifest,
          native_evidence: {
            before: "Previous source",
            after:
              "Exact selected source <script>window.exportInjected=true</script>",
          },
          private_decisions: [{ comment: "Private comment — Zürich" }],
        }).replace(/}$/, ',"large":9007199254740993,"decimal":1.2500}');
        this.packet = {
          manifest,
          canonical_json,
          bytes: Buffer.byteLength(canonical_json),
          sha256: hash(canonical_json),
          filename: "server-name.json",
        };
        data = {
          ...this.packet,
          canonical_json: undefined,
          expires_at: new Date(
            Date.now() + (this.mode === "expired" ? -1 : 300000),
          ).toISOString(),
          confirmation_token: "synthetic-confirmation",
        };
        if (this.mode === "wrong-preview")
          data.manifest = {
            ...manifest,
            scope: { organization_id: "foreign", user_id: "owner" },
          };
      } else {
        assert.deepEqual(body, {
          confirmation_token: "synthetic-confirmation",
        });
        data = structuredClone(this.packet);
        if (this.mode === "corrupt") data.sha256 = "0".repeat(64);
        if (this.mode === "wrong-bytes") data.canonical_json += " ";
        if (this.mode === "wrong-manifest")
          data.manifest.configuration_revision++;
      }
      if (this.mode === "denied")
        await this.respond(
          requestId,
          { code: "source_permission_revoked" },
          403,
        );
      else if (this.mode === "delayed") this.held = { requestId, data };
      else await this.respond(requestId, data);
    } catch (error) {
      this.failures.push(String(error));
      await this.respond(requestId, { code: "fixture_failure" }, 500);
    }
    return true;
  }
  async wait(check, name) {
    for (let i = 0; i < 200; i++) {
      if (await check()) return;
      await sleep(100);
    }
    throw Error(`Evidence export: ${name}`);
  }
  async button(label, selector) {
    await this.wait(
      () =>
        evaluate(
          this.cdp,
          `(()=>{const b=[...document.querySelector(${JSON.stringify(selector)}).querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)}&&!b.disabled);if(!b)return false;b.click();return true;})()`,
        ),
      label,
    );
  }
  async text(selector) {
    return evaluate(
      this.cdp,
      `document.querySelector(${JSON.stringify(selector)})?.innerText||''`,
    );
  }
  async check({
    domain,
    locale,
    monitor,
    item,
    sequence,
    revision,
    selector = `[data-monitoring-evidence-export="${domain}"]`,
    audit,
    name,
    restore,
    negative = false,
  }) {
    const c = evidenceExportCopy[locale];
    await this.wait(
      () =>
        evaluate(
          this.cdp,
          `!!document.querySelector(${JSON.stringify(selector)})`,
        ),
      `${domain} control missing`,
    );
    this.mode = "ready";
    await this.button(c.prepare, selector);
    await this.wait(
      async () => (await this.text(selector)).includes(c.download),
      "preview missing",
    );
    assert.deepEqual(this.selection, {
      domain,
      monitor_id: monitor,
      item_id: item,
      sequence: sequence ?? null,
      revision_id: revision ?? null,
      locale,
    });
    if (audit) await audit.check(this.cdp, name, selector);
    await this.button(c.download, selector);
    await this.wait(
      async () => (await this.text(selector)).includes(c.complete),
      "download failed",
    );
    await this.wait(
      async () =>
        (await this.downloadedFiles()).some((n) => n.endsWith(".json")),
      "file missing",
    );
    const files = await this.downloadedFiles();
    assert.equal(files.length, 1);
    assert.equal(
      files[0],
      `helvetic-lens-${domain}-${item}-${this.packet.manifest.selection.sequence}.json`,
    );
    const actual = await readFile(join(this.directory, files[0]), "utf8");
    assert.equal(actual, this.packet.canonical_json);
    assert.equal(hash(actual), this.packet.sha256);
    assert.equal(await evaluate(this.cdp, "!!window.exportInjected"), false);
    await unlink(join(this.directory, files[0]));
    this.files++;
    if (!negative) return;
    for (const mode of [
      "wrong-preview",
      "expired",
      "corrupt",
      "wrong-bytes",
      "wrong-manifest",
      "denied",
      "wrong-identity",
    ]) {
      this.mode = ["wrong-preview", "expired"].includes(mode) ? mode : "ready";
      await this.button(c.prepare, selector);
      if (this.mode === "ready") {
        await this.wait(
          async () => (await this.text(selector)).includes(c.download),
          "preview missing",
        );
        this.mode = mode;
        await this.button(c.download, selector);
      }
      await this.wait(
        async () => (await this.text(selector)).includes(c.failed),
        `${mode} not rejected`,
      );
      assert.deepEqual(await this.downloadedFiles(), []);
    }
    for (const phase of ["preview", "download", "pagehide", "today"]) {
      this.mode = phase === "preview" ? "delayed" : "ready";
      this.held = null;
      await this.button(c.prepare, selector);
      if (phase !== "preview") {
        await this.wait(
          async () => (await this.text(selector)).includes(c.download),
          "preview missing",
        );
        this.mode = "delayed";
        await this.button(c.download, selector);
      }
      await this.wait(() => !!this.held, "held request missing");
      if (["pagehide", "today"].includes(phase))
        await evaluate(
          this.cdp,
          `window.dispatchEvent(new Event(${JSON.stringify(phase === "today" ? "helvetic-lens:today-changed" : "pagehide")}))`,
        );
      else await this.button(c.cancel, selector);
      await this.respond(this.held.requestId, this.held.data);
      await sleep(300);
      assert.ok(!(await this.text(selector)).includes(c.complete));
      assert.deepEqual(await this.downloadedFiles(), []);
      if (["pagehide", "today"].includes(phase)) {
        this.mode = "ready";
        await restore();
      }
    }
    this.mode = "ready";
    assert.deepEqual(this.failures, []);
  }
}
