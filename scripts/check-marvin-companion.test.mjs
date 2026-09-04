import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");
const companion = read("apps/web/components/marvin-companion.tsx");
const comparison = read("apps/web/components/comparison-view.tsx");
const events = read("apps/web/lib/assistant-events.ts");
const shell = read("apps/web/components/shell.tsx");
const css = read("apps/web/app/globals.css");
const i18n = read("apps/web/lib/i18n.tsx");

test("the contextual companion is mounted for signed-in and local development workspaces", () => {
  assert.match(
    shell,
    /\{\(session\?\.authenticated \|\| session\?\.anonymous_development\) && \(\s*<MarvinCompanion/,
  );
  assert.match(
    shell,
    /localAiReady=\{Boolean\(health\?\.apertus\.configured\)\}/,
  );
  assert.match(shell, /assistant-open/);
});

test("spontaneous observations are bounded and never inspect form content", () => {
  assert.match(companion, /15 \* 60 \* 1000/);
  assert.match(companion, /document\.visibilityState !== "visible"/);
  assert.match(companion, /target\.closest\("button, a\[href\], summary"\)/);
  assert.match(companion, /control\.closest\("form"\)/);
  assert.match(companion, /main\?\.addEventListener\("scroll"/);
  assert.match(
    companion,
    /api<AssistantContextResponse>\("\/assistant\/context"/,
  );
  assert.match(companion, /api<AssistantRuntime>\("\/assistant\/runtime"\)/);
  assert.match(companion, /api<AssistantRemarkResponse>/);
  assert.match(companion, /provenance\.cloud_fallback === false/);
  assert.match(companion, /GENERATED_REMARK_KEYS\.has\(response\.key\)/);
  assert.match(companion, /remarkRequestId/);
  assert.match(companion, /runtime\.selected_model\.display_name/);
  assert.match(companion, /schema_version: "assistant-context\.v1"/);
  assert.match(companion, /!serverQuipAllowed/);
  assert.doesNotMatch(
    companion,
    /textContent|innerText|MutationObserver|FormData|querySelector(?:All)?<[^>]*>\(["'][^"']*(?:input|textarea)|fetch\(|\bapi\(/,
  );
});

test("tone and spontaneous controls stay on-device", () => {
  assert.match(companion, /window\.localStorage/);
  assert.match(companion, /window\.sessionStorage/);
  assert.match(companion, /tone: "very_dry"/);
  assert.match(companion, /spontaneous: true/);
  assert.match(companion, /type="checkbox"/);
});

test("comparison questions use a private draft and the existing cited Ask flow", () => {
  assert.match(companion, /DRAFT_KEY_PREFIX \+ comparisonId/);
  assert.match(companion, /window\.sessionStorage/);
  assert.match(companion, /new CustomEvent\(ASSISTANT_QUESTION_EVENT/);
  assert.doesNotMatch(companion, /\/ask-jobs/);
  assert.match(events, /question\.trim\(\)\.slice\(0, 2000\)/);
  assert.match(comparison, /setCompanionTab\("ask"\)/);
  assert.match(comparison, /setQuestion\(detail\.question\)/);
  assert.match(comparison, /getElementById\("apertus-question"\)\?\.focus/);
  assert.match(companion, /setContextAttached\(\(value\) => !value\)/);
  assert.match(
    companion,
    /contextAttached\s*\?\s*api<AssistantContextResponse>/,
  );
  assert.match(companion, /comparisonId && contextAttached/);
  assert.match(companion, /useResource<Job\[]>\(resources\.assistantJobs\(\)/);
  assert.match(companion, /ASSISTANT_JOB_TYPES/);
  assert.match(companion, /job\.progress\.current/);
  assert.match(companion, /jobResultHref\(job\)/);
  assert.match(companion, /actionHref: `\$\{pathname\}\?task=impact`/);
  assert.match(companion, /function routeEntity\(pathname: string\)/);
  assert.match(companion, /\.\.\.\(entity \? \{ entity \} : \{\}\)/);
  assert.match(companion, /contextLabel \|\| t\(context\.titleKey\)/);
  assert.match(companion, /\/assistant\/conversations/);
  assert.match(companion, /conversationResult\.value\.draft/);
  assert.match(companion, /recentQuestions/);
  assert.doesNotMatch(companion, /setQuestionDraft\(\s*comparisonId\s*\?/);
});

test("the companion remains keyboard, mobile, and reduced-motion aware", () => {
  assert.match(companion, /event\.key !== "Escape"/);
  assert.match(companion, /aria-expanded=\{open\}/);
  assert.match(companion, /aria-label=\{t\("companion\.panelLabel"\)\}/);
  assert.match(
    css,
    /@media \(max-width: 900px\)[\s\S]*\.marvin-drawer[\s\S]*width: 100%/,
  );
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /\.shell\.assistant-open \.main/);
});

test("all five product locales define the companion contract", () => {
  for (const locale of ["en-CH", "de-CH", "fr-CH", "it-CH", "rm-CH"]) {
    assert.match(
      i18n,
      new RegExp(`"${locale}": \\{[\\s\\S]*?"companion\\.panelLabel"`),
      `missing companion messages for ${locale}`,
    );
  }
  for (const key of [
    "companion.contextBoundary",
    "companion.spontaneousHelp",
    "companion.quip.compare",
    "companion.quip.busy",
    "companion.runtimeProfile",
    "companion.generated.bureaucracy",
    "companion.generated.evidence",
    "companion.generated.queue",
    "companion.generated.progress",
    "companion.askLabel",
    "companion.askPlaceholder",
    "companion.draftPrivacy",
    "companion.openCitedAsk",
    "companion.detachContext",
    "companion.attachContext",
    "companion.noContext",
    "companion.aiWork",
    "companion.activeJobs",
    "companion.latestJob",
    "companion.jobSaved",
    "companion.queuePosition",
    "companion.jobProgress",
    "companion.openJob",
    "companion.openJobResult",
    "companion.jobComplete",
    "companion.jobEnded",
    "companion.action.reviewCitedImpact",
  ]) {
    assert.equal(
      i18n.match(new RegExp(`"${key.replaceAll(".", "\\.")}"`, "g"))?.length,
      5,
      `${key} must exist in every locale`,
    );
  }
});
