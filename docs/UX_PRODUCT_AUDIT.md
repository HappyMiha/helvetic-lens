# Daily-use UX and product audit

This audit translates observed product friction into the `HL-065`–`HL-088` roadmap. It is based on the current browser experience, responsive CSS, navigation, comparison/Ask implementation, onboarding, registry, Impact inbox, digest flow, official connector contracts, and local-model architecture.

## Product conclusion

Helvetic Lens already has strong evidence, versioning, source, tenancy, and local-AI foundations. Its main usability problem is information architecture: the UI exposes technical modules and long records, while the user arrives with a simpler job — follow an issue, learn what deserves attention, understand why, inspect proof, and decide what to do.

The next product iteration should make Helvetic Lens an **interest-centred daily intelligence workspace**. Connector operation belongs to platform administration. An organization user should primarily see monitored laws and topics, new relevant events, possible impact, and evidence-backed next actions.

## Observed friction

### Shell and navigation

- The desktop sidebar is sticky and exactly `100vh`, but its long navigation has no reliable internal scroll region. Low-height screens, browser zoom, long translations, and platform-admin controls can make lower routes unreachable.
- The mobile replacement is a long horizontally scrolling row. It has incomplete route coverage, weak active-state orientation, and no clear overflow affordance.
- Navigation mixes daily work, organization configuration, ingestion operations, model management, diagnostics, and prompts in one list.

### Company profile

- Company profile is invoked from the workspace selector and a separate navigation item; Settings contains another instance, and Organization reaches it through a DOM-click workaround.
- The modal mixes company facts used for relevance with an AI connection test. It has no canonical URL, browser history, dependable unsaved-change protection, or space for a growing organization profile.
- The workspace selector should select an organization. Company profile should be an ordinary organization page. Model/provider tests belong in AI settings.

### Comparison and AI

- On desktop, the full Impact report, Ask, and AI history are stacked in a narrow column beside the diff. A long report determines the page height and produces large unused space under shorter evidence.
- At tablet widths the AI modules move below the evidence, and on mobile users must traverse the diff before reaching the most frequently used explanation and question controls.
- Detailed provenance, dates, uncertainties, repeated evidence labels, and action state compete with the central answer: what changed, why it matters, and what should be reviewed.
- Ask waits synchronously for a durable job while showing mainly a disabled form and spinner. It has no pending message, real processing stage, background continuation, or completion notification.
- A successful question triggers the global workspace refresh event. Every `useResource` listener may reload, creating unnecessary requests, perceived page refresh, and possible scroll instability.

### First value and discovery

- Onboarding explains three product ideas but does not guide a user through a saved interest, trusted sources, notification choice, and first real evidence item.
- Empty states lead primarily to adding a URL. A new user should not need to know a precise ELI or publication URL before the product becomes useful.
- The shared regulatory corpus already includes Fedlex, Parliament, federal court, official federal news, consultation, and FINMA streams. Organizations cannot yet activate these as understandable source packages.
- There is no durable monitoring-topic object. The system can relate a new event to a watched law, but it cannot represent “follow simplified naturalisation” as a user-owned, reviewable interest.

## Target information architecture

Primary work:

1. **Today** — new and important items that may need attention.
2. **Monitoring** — the organization's laws and topics.
3. **Impact inbox** — external events connected to those interests.
4. **Discover** — the broader time-based registry of laws, proposals, decisions, consultations, and notices.
5. **Sources** — trusted starter/cantonal packages and advanced custom sources.

Workspace:

- Company profile
- Team and roles
- Digests and notifications

Administration, visible only to the relevant role:

- Local AI and models
- Connectors and schedules
- Prompt defaults
- Integration diagnostics
- Platform health

Desktop comparison becomes a decision workspace: evidence on the left and a viewport-stable 420–480 px assistant panel with **Summary**, **Actions**, **Ask**, and **History** tabs on the right. Tablet uses a drawer. Mobile uses task tabs and a full-screen assistant sheet rather than placing AI after the complete diff.

## Target first-value journey

1. Register or accept an organization invitation.
2. Choose an intent: monitor a topic, follow a law, or explore current events.
3. Review and activate the Swiss Federal Starter package with visible source health, languages, cadence, and coverage limits.
4. Describe an interest naturally or select a law. Local AI may draft a monitoring plan, but the user reviews its concepts, jurisdictions, document types, languages, and sources before saving.
5. Preview a bounded set of already-saved matching events and open exact evidence.
6. Receive one grouped item when a new event relates to one or more monitored topics/laws.
7. See what happened, why the item appeared, its legal status, possible significance, and a useful next step.
8. Confirm, mute, refine, follow a related law, or configure a digest.

## Source-package model

Global connector jobs continue to ingest one shared public corpus. Enabling a package for an organization creates a subscription and feed scope; it must not duplicate downloads, connector cursors, artifacts, or AI work per organization.

The first starter package is composed of visible subpackages:

- Federal legislation and consultations — Fedlex.
- Parliament — initiatives, bills, affairs, and official notices.
- Federal courts — supported court sources with their actual historical windows.
- Official policy and regulator notices — News Service Bund and FINMA.

Coverage is contractual, never promotional shorthand. Federal Criminal Court support is a bounded latest-list window. Cantonal sources are unavailable until each canton passes its own source contract. Independent media and politician statements are a separately labelled, opt-in public-discourse signal; they never imply a change in law.

## Local assistant concept

The working persona is **Marvin**, inspired by an exceptionally capable, dry, pessimistic robot who still helps. Public artwork, wording, and final identity must be original unless separate rights are obtained. The desired character is expressed through optional tone, not copied character art or canonical quotations.

Marvin is a global interface to Helvetic Lens rather than a second autonomous legal system. It should:

- explain the current screen and state;
- find a saved law, event, comparison, or evidence item;
- answer legal/change questions through the existing cited Ask/Impact planners;
- draft and refine a monitoring topic;
- propose a bounded navigation or monitoring action for explicit confirmation;
- show the real status of local AI work and return to a completed job later.

The assistant uses the existing private gateway, `ai_interactive` queue, model manager, authorization, evidence, cache, and history. The default `assistant-lite` profile should use a small verified Apertus quantization. It must not keep a competing model process in VRAM unless hardware benchmarks prove capacity. There is no silent cloud fallback.

Model output cannot execute arbitrary routes, URLs, SQL, connector changes, user/role changes, credential changes, model downloads, prompt edits, deletion, or external communication. It may return a typed proposal with server-validated IDs. Any shared-data mutation opens a human-readable preview and requires an authorized user action.

The factual answer stays neutral. A separate optional `quip` can provide dry humour, but humour is suppressed for failures, uncertainty, high-impact alerts, access/security guidance, and destructive decisions. Users can choose Off/Neutral, Dry, or Very dry.

## Success measures

- A new organization saves its first law or topic and opens one real/cached evidence item in under five minutes without knowing a source URL.
- A returning user identifies why an alert appeared and its official legal status without external instructions.
- The key AI control is discoverable within ten seconds on desktop and mobile.
- Asking a question never reloads the diff or loses scroll/tab state; a queued job survives navigation.
- Topic-match usefulness is measured by precision/noise, evidence-open, confirm/reject, mute, and refinement rates. Volume of alerts or chat length is not success.
- All critical journeys pass at 390×844, 768×1024, 1024×768 with 200% zoom, and 1440×900 in DE/FR/IT/RM/EN.
- Source and AI wording never exceeds verified coverage or evidence.

## Scope discipline

This roadmap does not justify an unbounded web crawler, per-organization connector fleets, autonomous legal decisions, a second vector database, a separate assistant microservice, silent cloud execution, or an ornamental character that blocks core work. The first useful release improves navigation, first value, topic monitoring, evidence-linked alerts, and asynchronous local-AI interaction on the existing single-server architecture.
