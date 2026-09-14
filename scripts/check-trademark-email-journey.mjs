import assert from "node:assert/strict";
import { roadEmailCopy } from "../apps/web/lib/road-email-copy.ts";

export async function checkEmail({ click, fill, until, evaluate, json, record, audit, navigate }) {
  const scope = "[data-trademark-email]";
  const open = async () => {
    if (!(await evaluate("!!document.querySelector('[data-trademark-detail]')"))) {
      const button = "[...document.querySelectorAll('[data-trademark-watch] aside button')].find(b=>b.textContent.startsWith('Revised IP fixture'))";
      await until(`!!(${button})`);
      await evaluate(`(${button}).click()`);
    }
    await until(`!!document.querySelector('${scope}')`);
    await evaluate(`document.querySelector('${scope}').open=true`);
    await until(`!!document.querySelector('${scope} select')`);
  };
  const e = roadEmailCopy["en-CH"];
  await open();
  assert.equal(await evaluate(`document.querySelector('${scope} select').value`), "off");
  await fill(scope + " select", "daily_digest");
  assert.ok(await evaluate(`document.querySelector('${scope} button[type=submit]').disabled`));
  await fill(scope + " input[type=time]", "09:30");
  await evaluate(`document.querySelector('${scope} input[type=checkbox]').click()`);
  await evaluate(`document.querySelector('${scope} input[type=checkbox][required]').click()`);
  await click(e.save, scope);
  await until(`!document.querySelector('${scope} select')`);
  await open();
  assert.equal(await evaluate(`document.querySelector('${scope} select').value`), "daily_digest");
  assert.equal(await evaluate(`document.querySelector('${scope} input[type=time]').value`), "09:30");
  assert.ok(!(await evaluate(`document.querySelector('${scope} input[required][type=checkbox]').checked`)));
  const puts = (await json("/__qa/requests")).filter(r => r.method === "PUT" && r.path.endsWith("/email"));
  assert.equal(puts.length, 1);
  assert.equal(puts[0].body.consent, true);
  assert.deepEqual(puts[0].body.configuration.delivery.quiet_hours, { start: "22:00", end: "07:00" });
  record("ip-email-explicit-consent-digest-and-quiet-hours-survive-save");
  await click(e.preview, scope);
  await until(`!!document.querySelector('${scope} a[href*="event="]')`);
  await json("/__qa/state", { sourceRevoked: true });
  await click(e.preview, scope);
  await until(`!document.querySelector('${scope} a[href*="event="]')`);
  record("ip-email-preview-rechecks-source-without-sending");
  await json("/__qa/state", { sourceRevoked: false, manager: false });
  await navigate();
  await open();
  assert.ok(await evaluate(`document.querySelector('${scope} fieldset').disabled`));
  assert.ok(!(await evaluate(`!!document.querySelector('${scope} button[type=submit]')`)));
  record("ip-email-viewer-cannot-change-consent");
  await json("/__qa/state", { manager: true });
  const translated = {"en-CH":"A candidate is not a confirmed infringement.","de-CH":"Ein Kandidat ist keine bestätigte Rechtsverletzung.","fr-CH":"Un candidat ne constitue pas une contrefaçon confirmée.","it-CH":"Un candidato non costituisce una violazione accertata.","rm-CH":"In candidat n’è betg ina violaziun confermada."};
  for (const locale of ["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]) {
    await navigate(locale);
    await open();
    assert.ok(await evaluate(`document.querySelector('${scope}').textContent.includes(${JSON.stringify(translated[locale])})`));
    assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"), locale);
    record(`ip-email-translated:${locale}`);
  }
  await audit("email");
  await fill(scope + " select", "off");
  await click(e.save, scope);
  await until(`!document.querySelector('${scope} select')`);
  await open();
  assert.equal(await evaluate(`document.querySelector('${scope} select').value`), "off");
  record("ip-email-opt-out-does-not-require-consent");
  await json("/__qa/state", { emailDenied: true });
  await click(e.preview, scope);
  await until("!document.querySelector('[data-trademark-detail]')");
  assert.ok(!(await evaluate("document.body.textContent.includes('synthetic@example.invalid')")));
  record("ip-email-membership-denial-redacts-portfolio");
  await json("/__qa/state", { emailDenied: false });
  await navigate();
  await open();
}
