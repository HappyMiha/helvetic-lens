# 02 — Legal Hackathon 2026

[Back to the project map](../../PROJECT_MAP.md)

**Status: main-product preparation space created; connector implementation has not started.**

**Event:** 23 September 2026. [Official event page](https://ai-weeks.ch/2026/events/legal-hackathon) · [User-provided listing](https://www.hackevents.net/ch/events/legal-hackathon-jfvp4wc9).

## Purpose

Prepare Helvetic Lens for the hackathon using the frozen MVP as the starting reference. Connector improvements are part of the main product: **`main` → HappySnowman → helveticlens.ch**, through the existing automatic deployment. This workstream organizes those tasks; it does not introduce a separate hackathon application or long-lived deployment branch.

## What belongs here

- Participation, preparation and reuse rules confirmed with the organizer's published information.
- An inventory of the concrete resources made available to participants, including access conditions and timing.
- Source connectors and AI/provider adapters needed for the chosen hackathon scenario, recorded as separate task types.
- A reproducible demo, permitted fixtures, fallback plan and presentation.

Organizer-listed tools do not by themselves establish API access, quotas, datasets or permission to reuse data. Create implementation tasks only after confirming the actual resource contracts. This entry page does not start those integrations.

## Boundaries

- Preserve [v1.0.0-hackathon-mvp](https://github.com/HappyMiha/helvetic-lens/releases/tag/v1.0.0-hackathon-mvp); develop on current main with one agent, verify complete features and push origin/main. Keep its existing automatic deployment active.
- Do not make the hackathon demo depend on Pollen Watch or the Monitoring v2 environment.
- Do not add hackathon-only tasks to the Monitoring v2 backlog. If a result is useful for v2, add an explicit receiving task there and verify the integration.
- Record the hackathon connector queue here when implementation is selected, with scope, resource contracts and acceptance criteria before coding. It belongs to the main-product channel and does not become a second Monitoring v2 backlog.

**Next step when selected:** confirm the event's preparation rules and actual resource/access list, then agree the hackathon scenario and connector queue.
