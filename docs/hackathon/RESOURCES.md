# Legal Hackathon resource contracts

Verified on 19 September 2026. Scope: the **23 September Legal Hackathon at Novu
Campus**, not the separate Swisscom hackathon on 24–25 September or the 2025 event.

## Event and access

- [Official event](https://ai-weeks.ch/events/legal-hackathon): 23 September,
  Novu Campus, The Circle 60, 8058 Zürich/Kloten; English; free.
- [Organizer registration and detailed agenda](https://luma.com/hack-kloten-23Sep26):
  registration requires host approval. Arrival 09:00, welcome 09:20, hacking
  10:00–16:00, pre-evaluation from 16:00, top six announced 17:25, pitches
  17:30–18:05. The detailed agenda ends at 20:00; the overview says 19:30.
  Confirm the final timing in the participant message.
- Selected track: **Vibe Coding Track: Regulatory Change Monitor**.
- Luma names **Anthropic, Lovable, ElevenLabs, Swisscom, Supertext and others**.
  It does not publish redeemable codes, exact credits, team budgets, model IDs,
  dedicated GPU allocations, datasets, retention agreements or reuse rules.

No claim here establishes free access, registration approval or an organizer
entitlement. The 2025 Swisscom Apertus announcement is historical context, not
proof of a 2026 allocation. Existing code reuse and any required event-time delta
must be confirmed before entering this project in the competition.

## Coverage of the named resources

| Resource | Implemented integration | Still needed from the participant/provider |
|---|---|---|
| Anthropic | Native Messages adapter in the existing impact/Ask pipeline; model discovery; fixed official HTTPS origin; bounded existing request budget; incomplete/refused outputs rejected | Console API key scoped to one workspace, permitted model ID, quota; a Claude subscription alone does not establish API credits |
| Swisscom | Explicit Swisscom provider using its documented bearer-authenticated Chat Completions protocol; issued endpoint entered in Settings | Exact 2026 endpoint, served model and key; which plan/model and limits the organizer grants |
| Supertext | Encrypted organization configuration; feature-access probe; AI text translation of a reviewed briefing | API key from Supertext cockpit, supported language pair, usable credits |
| ElevenLabs | Encrypted organization configuration; configured-voice access probe; MP3 speech from reviewed text | API key with voice-read and speech permissions, permitted voice ID/model, usable credits |
| Lovable | Development handoff below; existing GitHub repository remains authoritative | Organizer workspace/credits and a Lovable-created project if used for UI exploration |
| Other tools, data or compute | Existing custom compatible endpoint and local model-manager paths can be configured when contracts are known | Names, documentation, license/rights, credentials, endpoints and allocations; no invented connectors |

## Verified protocols and setup

**Anthropic:** [Messages reference](https://platform.claude.com/docs/en/api/messages/create)
and [authentication](https://platform.claude.com/docs/en/manage-claude/authentication).
`POST https://api.anthropic.com/v1/messages`, bearer API key,
`anthropic-version: 2023-06-01`, top-level `system`, user `messages`, `model`,
`max_tokens`, `stream: false`. Read text blocks only. OpenAI-specific sampling
fields are omitted; server-side JSON/schema and evidence validation still apply.
The shipped connector uses a single-workspace key. Multi-workspace identity keys
that require an extra workspace header are not configured by this UI.

Open **Settings → Inference provider → Anthropic Claude**. Select Replace key,
enter the issued key, Load models, choose a permitted model, Test connection, Save.
Discovery works before choosing a model. The connection test must return the
requested `{"status":"ok"}` object; this is not an answer-quality evaluation.

**Swisscom:** [official product and example](https://digital.swisscom.com/products/swiss-ai-platform/info)
and [Swisscom quickstart](https://docs.cloud.swisscom.ch/guide/cloud-services/aip/use/inference-endpoints/).
The official example uses a bearer-authenticated OpenAI client with a
model-specific base URL under `https://api.swisscom.com/layer/swiss-ai-platform/`.
Select Swisscom AI, enter the **issued** base URL ending in `/v1`, replace the key
and enter the exact served model ID. Load models if the issued route exposes it;
manual entry is available. Test and save. Do not append `/chat/completions`.
The connector also permits the `/layer/swiss-ai-weeks/` route family for an
organizer-issued endpoint; no historical endpoint or model is preselected.

**Supertext:** [official API](https://www.supertext.com/en/documentation/api).
`Authorization: Supertext-Auth-Key <key>`, base `https://api.supertext.com/v1`.
Probe `GET /features`; translate `POST /translate/ai/text` with
`{"text":["reviewed text"],"target_lang":"de-CH"}` and optional `source_lang`.
Response: `translated_text` array with one result per submitted segment.
This connector submits one segment and requires one nonempty result.
It does not order the separate human-assisted Fused service.

**ElevenLabs:** [speech reference](https://elevenlabs.io/docs/api-reference/text-to-speech/convert).
`xi-api-key`, base `https://api.elevenlabs.io/v1`; voice probe
`GET /voices/{voice_id}`; speech `POST /text-to-speech/{voice_id}` with
`text`, `model_id` and `output_format=mp3_44100_128` in the query.
The editable default is `eleven_multilingual_v2`. No voice is silently chosen.
This uses standard provider retention; it does not claim enterprise zero retention.

Open **Settings → Partner tools** (`/settings/partners`). Replace the provider's
key, explicitly enable it, and save. For ElevenLabs also enter an accessible voice
ID. Test saved access. In **Review and present**, paste a short reviewed excerpt,
approve the named destination and click Translate or Speak. To speak a translation,
copy it with **Review this translation for speech**, review and approve it again.

## Processing and operating boundaries

- Partner integrations start disabled, without keys; migrations make no network calls.
- Keys use the existing AES-GCM credential cipher. Configurations are organization
  scoped with optimistic revision checks. Viewers cannot mutate settings or call
  providers; authenticated mutations retain CSRF protection.
- Translation/speech submit at most 3,000 characters after an explicit action.
  There is no automatic upload of documents, company profiles or source history.
- Calls have a 45-second deadline and 4 MiB response bound, reject redirects, and
  do not automatically replay ambiguous billable requests. API actions are rate limited.
- Briefing logs store operation/status/character counts, without keys or source text.
  Translation/audio results are page-session outputs, not new authoritative evidence.
- The existing inference pipeline retains its bounded evidence and retry budgets,
  immutable comparisons and citation validators. Optional cloud use stays explicit.
- Local CPU/GPU inference, Public AI, Hugging Face and Infomaniak remain available
  through existing settings. They are not claimed as 2026 organizer grants.
- Public partner API documentation verifies a protocol, not account activation,
  sufficient credits, live quality, legal correctness or production release.

## Lovable and compute handoff

[Lovable's GitHub documentation](https://docs.lovable.dev/integrations/github)
states that an existing GitHub repository cannot be imported into Lovable.
Do not replace this Next.js/FastAPI repository with a generated scaffold to work
around that limit. If organizers provide Lovable, use a separate Lovable-created
prototype with public synthetic data, export it through its documented GitHub
workflow and port reviewed UI ideas into this repository's normal development cycle.
Do not connect production credentials or private source documents to a prototype.

Suggested prompt for the granted Lovable workspace:

> Prototype one accessible Regulatory Change Monitor briefing view. Use fictional
> records-policy data, clearly marked DEMO ONLY: deletion deadline changes from
> 30 to 60 days; the data protection lead becomes responsible; request and completion
> dates become required in the deletion record. Show old and new text, source
> references, a human-review action, and optional translation/audio buttons with
> an explicit data-sharing preview. Use mocked data only in this disposable UI
> prototype. Do not claim legal accuracy or actual provider connectivity. Produce
> reusable layout ideas, not a replacement backend or authentication system.

For granted hosted inference, collect base URL, authentication, model ID, context
limit, requests/tokens per minute and expiry, then use the matching adapter.
For genuinely allocated GPUs, collect SSH/VPN/container access, GPU model/VRAM,
driver/runtime constraints, storage and permitted model license. Use the existing
documented model manager only on supported hardware; keep the current serving
deployment untouched. No GPU allocation is documented for this specific event.

See [verification](VERIFICATION.md) and the existing [technical demo setup](../DEMO.md).
Participant coaching and presentation materials are delivered separately from the repository.
