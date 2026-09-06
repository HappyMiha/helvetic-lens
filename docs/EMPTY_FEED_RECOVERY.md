# Empty Today: explain the state and offer recovery

HL-073 / HL-094, implemented 6 September 2026 on HappyDucky02.

## What users see

An empty Today page no longer has one generic explanation. Nine specific states distinguish an empty **page with more candidates**, an **unavailable linked event**, **active display filters**, **no active interest**, **no enabled package or direct document watch**, **interrupted/unverified history**, **pending history**, **source attention**, and **pending source collection**. Each offers an existing action: continue paging, clear filters, open Getting started, review topics, or review source packages. An empty filtered view does not claim that known matches are hidden; clearing filters lets the user inspect the broader feed. Missing linked evidence does not reveal whether another organization can access it.

The optional details disclose saved operational context and its timestamp, topic-created time, saved-event admission cutoff, processed-through admission time and processed/remaining counts. These dates are not legal publication/effective dates or evidence that the entire website was inspected. Topic links open existing recovery controls. No scan, model call, activation, email subscription or state mutation happens on entry.

## Read projection and limits

`GET /api/interest-feed/readiness` is a passive organization-scoped endpoint. It loads at most 21 scalar topic rows and 21 package IDs to display 20 with explicit `more_topics` / `more_packs`. It joins only the latest saved history job for the current topic revision and checks the evaluator/history idempotency key. Old evaluator results become `superseded`; legacy successes without a complete checkpoint remain `unverified`. Complete current saved history still does not prove live freshness. Job payloads/results are accessed by individual JSON fields: no full jobs, private errors, document bodies or evidence payloads are hydrated.

Source status reuses the saved source-coverage projection with explicit organization selection. Enabled subscription `queued`/`backfilling` and recorded connector runs indicate pending collection; partial/failed runs, paused or late schedules, unknown streams or missing active definitions request review. These are saved observations, not active remote probes or promises of arrival times. A directly watched visible document does not require enabling a source package.

The frontend loads this resource only while the feed is empty, shares the existing organization cache and refresh invalidations, and retains bounded sparse pagination. Operational details are collapsed by default. Both freshness and quiet-period verification remain false: a completed saved-window check cannot justify “nothing relevant happened.”

## Evidence and boundaries

API and disposable PostgreSQL tests cover isolation, current versus old topic/evaluator revisions, scalar query bounds, 24 topics / 21 enabled packages, unknown streams, foreign subscriptions under a privileged session, direct-document visibility, pending collection and no read-time side effects. Browser regression covers nine states in five locales at 390/1440px; all API responses are synthetic intercepted fixtures. Existing populated-feed interactions remain covered separately.

This does not complete HL-073/094 or replace real source-coverage verification. Broad stream-level matching backlog, more-than-20 setup drill-down beyond existing pages, genuinely quiet period evidence, native-language review and observed first value remain separate work. No production migration or deployment is included.
