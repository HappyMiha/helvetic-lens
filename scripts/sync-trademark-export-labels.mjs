// Shared authored UI translations are copied into the API distribution for offline documents.
import { readFile, writeFile } from "node:fs/promises";
import { trademarkReviewCopy } from "../apps/web/lib/trademark-review-copy.ts";
import { trademarkExportCopy } from "../apps/web/lib/trademark-export-copy.ts";
import { trademarkDeadlineCopy } from "../apps/web/lib/trademark-deadline-copy.ts";
const path = new URL(
  "../services/api/helvetic_lens/trademark_export_labels.json",
  import.meta.url,
);
const content =
  JSON.stringify(
    {
      review: trademarkReviewCopy,
      packet: trademarkExportCopy,
      deadline: trademarkDeadlineCopy,
    },
    null,
    2,
  ) + "\n";
if (process.argv.includes("--check")) {
  if ((await readFile(path, "utf8")) !== content)
    throw Error(
      "Run scripts/sync-trademark-export-labels.mjs to synchronize document labels.",
    );
} else await writeFile(path, content);
