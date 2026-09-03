# Fixed-budget AI analysis planner

Helvetic Lens plans every Impact and Ask run before it contacts a model. The saved `AnalysisPlan` is the audit record for what the application intended to review, why each semantic change was included or excluded, the configured context and output limits, estimated tokens, and the hard provider-call budget.

The deterministic comparison remains complete and is never replaced by the AI dossier. The planner selects material and uncertain legal units, groups related evidence into bounded batches, and records limited coverage when all eligible units cannot fit. Formatting-only and structural noise remains available in **All exact changes**, but it does not spend inference time. A comparison containing only that noise returns a saved low-impact result with zero model calls.

Impact has a hard ceiling of five generation requests, including synthesis and a possible structured-output repair. A complete small dossier uses one request. A larger cloud-backed dossier uses at most three evidence batches and one synthesis request, leaving one request for repair. Local Docker inference reviews at most three bounded batches and combines the validated results deterministically, so it never silently falls back to a cloud provider. Ask retains its separate three-call ceiling.

The reusable general-change layer comes from the persisted semantic diff. Its summary, cluster IDs, classification counts, and fingerprint are independent of the organization profile. The organization-specific Impact plan references that shared layer, then adds the profile revision to its own context fingerprint. This avoids paying for a second generic model explanation while keeping the common legal change set reusable across organizations.

Both complete saved versions are never attached automatically to an Impact request. Ask may use complete versions only when its existing measured character gate admits the serialized saved text; otherwise it uses the complete semantic change set for change questions or bounded targeted passages for a document-content question. Original artifacts always remain downloadable for human review.

Every completed or failed record retains the planned and actual execution data:

- intent, comparison, selected changes/evidence, and inclusion decisions;
- context fingerprint, model, provider, profile revision, and fixed limits;
- estimated input/output tokens and expected generation requests;
- planned and actual coverage plus the hard call ceiling;
- actual provider calls, queue wait, inference duration, provider token counts when supplied, validation result, repair count, and comparison result link.

The comparison page and AI history show these diagnostics in a compact form. The underlying plan remains available in API responses for detailed inspection and future operational reporting.
