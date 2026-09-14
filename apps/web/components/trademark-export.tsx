"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { trademarkCopy } from "@/lib/trademark-copy";
import { trademarkExportCopy } from "@/lib/trademark-export-copy";
import { useData, useMutation } from "./trademark-client";

type Preparation = {
  id: string;
  document: string;
  content_sha256: string;
  expires_at: string;
};

function Prepared({ path, id }: { path: string; id: string }) {
  const { locale } = useI18n(),
    c = trademarkExportCopy[locale],
    b = trademarkCopy[locale];
  const [revision, setRevision] = useState(0),
    mutation = useMutation();
  const result = useData<Preparation>(`${path}/${id}`, revision);
  const downloadUrl = useRef<string | null>(null);
  useEffect(() => {
    const timer = window.setInterval(() => setRevision((v) => v + 1), 30_000);
    return () => {
      window.clearInterval(timer);
      if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current);
    };
  }, []);
  if (result.error || mutation.error)
    return (
      <p data-trademark-export-unavailable role="alert">
        {c.unavailable}
      </p>
    );
  if (!result.data) return <p role="status">{b.loading}</p>;
  const prepared = result.data;
  function download(value: Preparation) {
    if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current);
    const url = URL.createObjectURL(
      new Blob([value.document], { type: "text/html;charset=utf-8" }),
    );
    downloadUrl.current = url;
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `trademark-evidence-${id}.html`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  }
  return (
    <div data-trademark-export-preview>
      <p>
        {c.expires}:{" "}
        <time dateTime={prepared.expires_at}>
          {new Date(prepared.expires_at).toLocaleString(
            locale === "rm-CH" ? "de-CH" : locale,
          )}
        </time>
      </p>
      <iframe
        title={c.preview}
        sandbox=""
        referrerPolicy="no-referrer"
        srcDoc={prepared.document}
        className="w-full h-[600px] border rounded-lg bg-white"
      />
      <p>{c.static}</p>
      <button
        disabled={mutation.busy}
        onClick={() =>
          void mutation.run<Preparation>(
            `${path}/${id}/download`,
            { expected_content_sha256: prepared.content_sha256 },
            download,
          )
        }
      >
        {c.download}
      </button>
      <button
        disabled={mutation.busy}
        onClick={() => setRevision((v) => v + 1)}
      >
        {b.refresh}
      </button>
    </div>
  );
}

export function TrademarkExport({
  path,
  version,
  evaluationHash,
  event,
  canManage,
}: {
  path: string;
  version?: number;
  evaluationHash?: string;
  event?: string;
  canManage: boolean;
}) {
  const { locale } = useI18n(),
    c = trademarkExportCopy[locale],
    mutation = useMutation();
  const [include, setInclude] = useState(!!event),
    [prepared, setPrepared] = useState<{
      id: string;
      version: number;
      hash: string;
    } | null>(null);
  const request = useRef<{ body: string; key: string } | null>(null);
  function prepare() {
    if (!version || !evaluationHash) return;
    setPrepared(null);
    const body = {
      expected_version: version,
      expected_evaluation_hash: evaluationHash,
      event_id: include && event ? event : null,
      locale,
    };
    const serialized = JSON.stringify(body);
    if (!request.current || request.current.body !== serialized)
      request.current = { body: serialized, key: crypto.randomUUID() };
    void mutation.run<Preparation>(
      `${path}/exports`,
      { ...body, request_key: request.current.key },
      (value) => {
        setPrepared({ id: value.id, version, hash: evaluationHash });
        // An explicit later preparation must not be trapped by an expired/changed earlier request.
        request.current = null;
      },
    );
  }
  return (
    <section data-trademark-export>
      <h4>{c.title}</h4>
      <p>{c.help}</p>
      {event ? (
        <label className="!flex-row items-center gap-2">
          <input
            type="checkbox"
            checked={include}
            onChange={(e) => {
              setInclude(e.target.checked);
              setPrepared(null);
            }}
          />
          {c.include}
        </label>
      ) : (
        <p>{c.currentOnly}</p>
      )}
      <button
        disabled={!canManage || !evaluationHash || mutation.busy}
        onClick={prepare}
      >
        {c.prepare}
      </button>
      {mutation.error && (
        <p data-trademark-export-unavailable role="alert">
          {c.unavailable}
        </p>
      )}
      {prepared &&
        prepared.version === version &&
        prepared.hash === evaluationHash && (
          <Prepared
            key={prepared.id}
            path={`${path}/exports`}
            id={prepared.id}
          />
        )}
    </section>
  );
}
