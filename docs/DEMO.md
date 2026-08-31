# Repeatable demonstration

Use the same forms, network requests, storage, diff engine, and model adapter as normal monitoring. No canned impact responses or simulated progress are shipped.

## 1. Connect a website and choose a document

Open the app and choose **Connect website**. For an actual regulator, start with the [FINMA circulars listing](https://www.finma.ch/en/documentation/circulars/). Set the section to /en/documentation, test the connection, and save it.

Under **Sources → Discover documents**, run the search. The app inspects at most 50 direct documents and shows actual extraction previews, verified types, individual errors, and the coverage limits. Filter titles, URLs, or preview text, then choose **Preview & add**. Some portals render their content with JavaScript; use a direct PDF or another supported public page when native extraction cannot read it.

For a repeatable, clearly synthetic before/after example, connect this repository's [demo listing](https://raw.githubusercontent.com/HappyMiha/apertus-regwatch/main/demo/index.html), keeping section /. Choose **Synthetic records policy — current version**, preview it, select **This source contains synthetic demo content**, and add it.

You can separately use **Add a law** to add a specific document URL without connecting a website first. For the second synthetic document use [document handling practice](https://raw.githubusercontent.com/HappyMiha/apertus-regwatch/main/demo/practice.txt).

## 2. Import the earlier copy

On the policy's detail page, choose **Import previous version**.

1. Upload [policy-previous.txt](../demo/policy-previous.txt), or use **Paste text** and paste its contents.
2. Optionally enter a stated version date in YYYY-MM-DD format. It is a user-supplied label, not verified legal chronology.
3. Check **This version was edited or created for a synthetic demo**.
4. Preview the extraction, confirm the selected law, and import.

The imported version becomes the selected historical baseline. The live pointer still references the current fetched version. All demo files are authored fictional examples, not modified official laws.

Re-importing identical text reuses its immutable snapshot. A different filename or stated date belongs to the new import observation and is shown under **Fetch & import observations**; the original snapshot metadata is not overwritten.

## 3. Fetch and inspect exact changes

Choose **Fetch & compare with history**. The API downloads the actual current URL, extracts its content, saves an observation, and compares the selected pair. Open the result when the scan finishes.

Expected changes in the supplied fixture:

- The retention period changes from **30** to **60** days; the individual numbers are highlighted.
- The owner changes from the operations team to the data protection lead.
- A quarterly spreadsheet report is removed.
- A new evidence heading and record-keeping paragraph are added.

The result is labeled **Historical comparison**. The ordinary live outcome is **Unchanged** if the current file is the same as the initial fetch.

Use the filters and **Jump to a change**, then open an old or new passage reference. The evidence page shows that exact saved version and highlights the referenced passage. For PDFs, page references open the stored PDF.

Repeat the historical scan without editing the source or deleting anything. The same snapshots and comparison are reused, with a new observation for each fetch. Switch the baseline back to **Last live version** and run **Scan now** to see a separate ordinary unchanged result.

## 4. Review Apertus output when a real endpoint is connected

Open **Settings → Apertus**, enter the endpoint and served model ID, and choose key handling. Adjust limits if needed. **Test connection** checks the current form without saving; **Save settings** applies it immediately and persists it across restarts. Open **Edit company profile** and write a short business description.

Generate an impact analysis or let the scan request it. Review the summary, impact reason, suggested actions, and passage citations.

Try:

- “What changed about the retention period?”
- “What did the earlier version say, and which passage supports that?”
- “Who signed this policy?” — the fixtures do not contain a signatory; a supported answer must not invent one.

Citations must resolve to the correct before/after version. A failed, malformed, or unsupported response is shown explicitly. Until a real endpoint passes these checks, the full Apertus MVP remains unaccepted.

## 5. Honest fallback and persistence checks

- Without a model endpoint, the app shows **Connect Apertus**, with no generated answer or impact rating.
- Without network access to the source, use **Compare saved versions**. This does not claim a live check or change monitoring state.
- Pause and resume a document. A paused law stays available in history and is excluded from ordinary scans.
- Restart the API and PostgreSQL without deleting their data. Sources, snapshots, scans, comparisons, and profile should remain. Running scans become interrupted and can be retried.
- Do not remove database volumes when rehearsing a normal repeat run.

## Repeat the core HTTP check

For development verification, run this only against a disposable local workspace. It creates or reuses two clearly synthetic tracked documents and pauses the secondary one. It does not reset history or substitute model responses. A configured endpoint may be called by the normal scan pipeline.

~~~sh
uv run --project services/api python scripts/smoke_http.py --api http://127.0.0.1:8000 --record data/smoke-check.json
~~~

Restart the app and database without removing volumes, then verify the saved record:

~~~sh
uv run --project services/api python scripts/smoke_http.py --api http://127.0.0.1:8000 --verify-record data/smoke-check.json
~~~

This check covers real HTTP fetching, repeated historical comparisons, ordinary unchanged scans, saved evidence, and persistence. It deliberately does not establish live Apertus acceptance.

## Optional fully local source

The public GitHub fixture URLs above need no private-address exception. For a local source you can run:

~~~sh
npm run demo:source
~~~

It serves only the demo directory at http://127.0.0.1:8765/index.html. A locally running API needs the explicit ALLOW_PRIVATE_SOURCES=true setting and a restart to fetch this address. Keep that exception off in shared deployments. Inside Docker, loopback refers to the API container, not the host; use the public fixture URLs for the simplest Compose demo.
