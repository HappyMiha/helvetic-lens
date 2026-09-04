# Saved Impact matrix

The `/matrix` page is a read-only organization view of saved Impact reports. It does not call a model, create a second assessment, or infer that a missing assessment means low impact.

Rows are active monitored laws. Columns are the current company-profile business areas. Every row points to the latest saved comparison for that law, and every assessed cell points back to that same comparison and its evidence.

## Cell states

- `assessed`: a current, validated Impact report explicitly names the business area and contains a valid high, medium, or low rating.
- `unknown`: a current report exists but does not assess that business area. No rating is invented.
- `stale`: the last valid report was produced with an earlier company profile, prompt, model/runtime setting, or output locale. The old value may be shown as historical context but is not presented as current.
- `unanalysed`: no saved valid Impact report exists for the latest comparison.
- `failed`: the latest analysis attempt failed and no earlier valid report can be shown.

The matrix reuses the same cache fingerprint as comparison Impact analysis. A profile revision therefore invalidates displayed values consistently with the comparison page. Changing the interface language requests matching saved output-locale results and does not silently reuse an assessment in another language.

## Scope and access

The API reads through the active organization-scoped database session. It returns active watches, their latest comparisons, and existing analysis records only for that organization. Viewers can inspect the matrix; mutations continue to use the existing comparison, profile, and monitoring permissions.

The feature does not change scanning, version creation, comparison, or AI-analysis workflows. Users review or rerun an assessment from the linked comparison page.
