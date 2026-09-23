# 02 — Legal Hackathon 2026

[Back to the project map](../../PROJECT_MAP.md)

**Status: VERIFYING — software integration delivered; participant access, live activation and event eligibility remain open.**

## Selected delivery and acceptance

Track: Regulatory Change Monitor. Retain the existing saved-source → immutable
versions → exact comparison → cited impact workflow. Keep local inference as the
default and remote processing explicitly selected. Public partner mentions are
not proof of participant credentials, credits, model access or allocated GPUs.

| Task | Scope and dependency | Acceptance | State |
|---|---|---|---|
| H26-01 | Verify current official event and provider contracts | Dated resource inventory distinguishes announced tools, documented APIs and unconfirmed participant entitlements | DONE — public contract research; private allocation open |
| H26-02 | Anthropic Messages and Swisscom-compatible inference through existing analysis/settings | Explicit selection, safe credentials, bounded retries, cited workflow retained and regression tests | VERIFYING — software checked; granted access and answer quality open |
| H26-03 | Supertext AI text translation and ElevenLabs speech | Encrypted organization credentials, explicit reviewed text submission, bounded responses, safe errors, usable UI and tenant/role tests | VERIFYING — software checked; live generation and language review open |
| H26-04 | Lovable development handoff, compute activation instructions | Document supported integration paths; no invented import API, credits or server allocation | DONE — documented; no allocation claimed |
| H26-05 | Participant preparation delivered outside Git | Presentation and personal coaching are excluded from main at the user's request | Delivered separately; participant rehearsal remains open |
| H26-06 | Activate the participant's OpenAI, Swisscom Apertus 1.5 70B and Supertext access in production | Official organizer contracts; current Swisscom route; fixed OpenAI origin; independently stored encrypted inference connections; administrator activation; no credential disclosure; provider/tenant tests; live checks and verified deployment | IN PROGRESS — user authorized production activation on 23 September; personal access is being obtained |

H26-06 preserves the existing inference and translation workflows. Separate saved
connections let the organization retain both OpenAI and Swisscom credentials;
activating one remains an explicit administrator action. The organizer publishes
the `/products/swiss-ai-weeks/apertus-1.5-70b/v1` endpoint and the exact
`swiss-ai/Apertus-v1.5-70B` model. API keys, redemption links and participant contact
details stay outside Git. OpenAI credit redemption is distinct from an API key
and must target the participant's intended API organization. Supertext human
verification is excluded from this grant. No account entitlement, lasting token
validity or answer quality is inferred from documentation or a connection test.

Published contracts: [Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create),
[Supertext](https://www.supertext.com/en/documentation/api),
[ElevenLabs speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert),
[Lovable GitHub](https://docs.lovable.dev/integrations/github).
The [Swisscom participant guide](https://zh.ai-weeks.ch/tools/swisscom-hacker-guide)
now confirms the event endpoint, model and bearer authentication. Reuse eligibility
and continued participant entitlement remain separate organizer checks.
These tasks belong here, not in the Monitoring v2 backlog.

**Event:** 23 September 2026. [Official event page](https://ai-weeks.ch/events/legal-hackathon) · [User-provided listing](https://www.hackevents.net/ch/events/legal-hackathon-jfvp4wc9).

## Purpose

Prepare Helvetic Lens for the hackathon using the frozen MVP as the starting reference. Connector improvements are part of the main product: **`main` → HappySnowman → helveticlens.ch**, through the existing automatic deployment. This workstream organizes those tasks; it does not introduce a separate hackathon application or long-lived deployment branch.

## What belongs here

- Participation, preparation and reuse rules confirmed with the organizer's published information.
- An inventory of the concrete resources made available to participants, including access conditions and timing.
- Source connectors and AI/provider adapters needed for the chosen hackathon scenario, recorded as separate task types.
- Technical acceptance, permitted fixtures and operating instructions. Personal presentation materials stay outside Git.

Organizer-listed tools do not by themselves establish API access, quotas, datasets or permission to reuse data. The implemented adapters use published provider contracts recorded in [RESOURCES.md](../hackathon/RESOURCES.md). Their code and activation boundaries are recorded in [VERIFICATION.md](../hackathon/VERIFICATION.md).

## Boundaries

- Preserve [v1.0.0-hackathon-mvp](https://github.com/HappyMiha/helvetic-lens/releases/tag/v1.0.0-hackathon-mvp); develop on current main with one agent, verify complete features and push origin/main. Keep its existing automatic deployment active.
- Do not make the hackathon demo depend on Pollen Watch or the Monitoring v2 environment.
- Do not add hackathon-only tasks to the Monitoring v2 backlog. If a result is useful for v2, add an explicit receiving task there and verify the integration.
- Record the hackathon connector queue here when implementation is selected, with scope, resource contracts and acceptance criteria before coding. It belongs to the main-product channel and does not become a second Monitoring v2 backlog.

**Remaining participant steps:** confirm registration/reuse rules, obtain issued resource access, run explicit connection and generation checks, then review output quality using synthetic data. Verify the main-site release independently of Git publication.
