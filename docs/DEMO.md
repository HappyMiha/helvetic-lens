# Repeatable demonstration

Use the same forms, network requests, storage, diff engine, and model adapter as normal monitoring. No canned impact responses or simulated progress are shipped.

## 1. Connect a website and choose a document

Open the app and choose **Connect website**. For an actual regulator, start with the [FINMA circulars listing](https://www.finma.ch/en/documentation/circulars/). Set the section to /en/documentation, test the connection, and save it.

Under **Sources → Discover documents**, run the search. Results are direct links, with unverified format hints. Preview a candidate to check the actual extracted text, then add it. Some portals render their content with JavaScript; use a direct PDF or another supported public page when native extraction cannot read it.

For a repeatable, clearly synthetic before/after example, connect this repository's [demo listing](https://raw.githubusercontent.com/HappyMiha/apertus-regwatch/main/demo/index.html), keeping section /. Choose **Synthetic records policy — current version**, preview it, select **This source contains synthetic demo content**, and add it.

You can separately use **Add a law** to add a specific document URL without connecting a website first. For the second synthetic document use [document handling practice](https://raw.githubusercontent.com/HappyMiha/apertus-regwatch/main/demo/practice.txt).

## 2. Import the earlier copy

On the policy's detail page, choose **Import previous version**.

1. Upload [policy-previous.txt](../demo/policy-previous.txt), or use **Paste text** and paste its contents.
2. Optionally enter a stated version date. It is a user-supplied label, not verified legal chronology.
3. Check **This version was edited or created for a synthetic demo**.
4. Preview the extraction, confirm the selected law, and import.

The imported version becomes the selected historical baseline. The live pointer still references the current fetched version. All demo files are authored fictional examples, not modified official laws.

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

Configure the server as described in the README, then open **Company profile**, write a short business description, and select **Test real connection**.

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

## Optional fully local source

The public GitHub fixture URLs above need no private-address exception. For a local source you can run:

~~~sh
npm run demo:source
~~~

It serves only the demo directory at http://127.0.0.1:8765/index.html. A locally running API needs the explicit ALLOW_PRIVATE_SOURCES=true setting and a restart to fetch this address. Keep that exception off in shared deployments. Inside Docker, loopback refers to the API container, not the host; use the public fixture URLs for the simplest Compose demo.
