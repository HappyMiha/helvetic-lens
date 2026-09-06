import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { evaluate } from "./browser-cdp.mjs";

const require = createRequire(import.meta.url);
const source = await readFile(require.resolve("axe-core/axe.min.js"), "utf8");

// Full rendered documents only: no rule exclusions, element exclusions, or
// severity downgrades. Incomplete checks remain visible for manual review.
export class AccessibilityAudit {
  constructor(suite) {
    assert.match(suite, /^[a-z-]+$/);
    this.suite = suite;
    this.checkpoints = [];
  }

  async check(cdp, name, requiredSelector) {
    assert.ok(!this.checkpoints.some(point => point.name === name), `Duplicate accessibility checkpoint: ${name}`);
    assert.ok(await evaluate(cdp, `!!document.querySelector(${JSON.stringify(requiredSelector)})?.getClientRects().length`), `Missing required accessibility fixture: ${name}`);
    if (!(await evaluate(cdp, "!!window.axe"))) await evaluate(cdp, source);
    const result = await evaluate(cdp, `(async () => {
      await document.fonts.ready;
      const result = await axe.run(document);
      return {engine:result.testEngine, url:location.pathname, locale:document.documentElement.lang,
        width:innerWidth, height:innerHeight, violations:result.violations,
        incomplete:result.incomplete, passedRules:result.passes.length};
    })()`);
    this.checkpoints.push({name, ...result});
    const dir = resolve(import.meta.dirname, "../test-results/accessibility");
    await mkdir(dir, {recursive:true});
    await writeFile(resolve(dir, `${this.suite}.json`), JSON.stringify({suite:this.suite, checkpoints:this.checkpoints}, null, 2));
    const blocking = result.violations.filter(rule => ["critical", "serious"].includes(rule.impact));
    assert.deepEqual(blocking.map(rule => ({id:rule.id, impact:rule.impact, nodes:rule.nodes.map(node => ({target:node.target, failure:node.failureSummary}))})), [], `Accessibility findings at ${this.suite}/${name}; full results: test-results/accessibility/${this.suite}.json`);
  }

  finish(expected) {
    assert.equal(this.checkpoints.length, expected, `Missing required accessibility checkpoints: ${this.suite}`);
    console.log(`${this.suite}: ${this.checkpoints.length} full-document axe checkpoints passed critical/serious gate; lesser findings and incomplete checks retained in JSON, not certified accessible.`);
  }
}
