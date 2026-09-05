# Browser QA fixtures

`comparison-synthetic.json` is a populated API-shaped comparison generated from
`services/api/tests/conftest.py` (`harness`, `add_law`, `import_old`), using a
throwaway SQLite database, FakeFetcher and ScriptedModel. It compares the fictional
retention policy's 10/30-day passages and includes a scripted saved report with
citations. All records, organizations, source content and conclusions are synthetic.
It is not real legislation, a model-quality evaluation or evidence of legal advice.

The browser harness intercepts every application API call. No running backend,
production account, source fetch, paid model or real message is used. Required
comparison/citation fixtures fail the run if absent; there is no optional ID that
silently skips the populated journey.
