# Intent-routed Ask

Ask classifies a question before assembling document context. The deterministic router sees only the question, makes no provider call, and records its version, detected locale, selected intent, and zero document characters inspected.

The supported intents are:

| Intent | Context and behavior |
| --- | --- |
| `explain_changes` | Reuse the current validated Impact report in the same locale when available; otherwise use the complete bounded semantic-change dossier. |
| `organization_impact` | Reuse validated applicability and evidence when available; otherwise use the semantic-change dossier plus the organization profile. |
| `actions` | Reuse the validated review plan when available; otherwise ask against the semantic-change dossier. Zero actions remains a useful answer. |
| `specific_unit` | Select the requested article/section plus adjacent saved passages from both versions. It never sends both complete documents merely because they are small. |
| `whole_document` | Send both complete saved versions only when the serialized prompt and output reservation fit the configured context. Otherwise retrieve a bounded set with neighbours and state that scope. |
| `vague` | Return clarification and four useful choices with no model or document-context call. |
| `off_topic` | Explain the document-review boundary and offer relevant choices with no model or document-context call. |

The four quick intents are available in German, French, Italian, Romansh, and English based on the browser language. The router also recognizes the existing Ukrainian and Russian clarification paths. Complete interface localization remains tracked by `HL-057`.

Every answer persists its intent, context mode, scope, selected change and evidence IDs, coverage, locale, model/runtime provenance, latency, citations, cache reuse, and exact comparison. The hard limit remains three provider requests including any repair or synthesis. A canonical answer reused from the current validated report uses zero provider calls.

Follow-up requests include the previous validated answer and citations, not only the prior question text. These records remain untrusted prompt evidence and are limited to the four most recent successful answers. If exact evidence is absent or the request is too broad for the available context, Ask states the missing scope and suggests a narrower question instead of scanning passages indefinitely.

## Response origin is separate from context

`response_mode` records `selected_evidence`, `generated_explanation` or `deterministic` independently of `context_mode`. It survives history, repeated requests and zero-call reuse. The small-model selector provides inspectable saved quotations, not an impact explanation. Actions/applicability remain explicitly unassessed in that mode; no-action advice cannot be inferred from an empty action list. A one-sided citation is not proof that wording was added/removed. Earlier records lacking mode metadata are labelled historical; they are not rewritten. See [report modes](IMPACT_REPORT.md#explicit-response-modes-hl-091).
