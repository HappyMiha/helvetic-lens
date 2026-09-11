"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { pollenBackupCopy } from "@/lib/pollen-backup-copy";
import {
  decodePollenBackup,
  encodePollenBackup,
  POLLEN_BACKUP_MAX_BYTES,
  PollenBackupError,
} from "@/lib/pollen-edit";
import {
  draftFailure,
  type PollenConfiguration,
  type PollenDraft,
} from "@/lib/pollen-drafts";
import styles from "./pollen-draft-reader.module.css";

export function PollenDraftExport({
  id,
  disabled,
  onDenied,
}: {
  id: string;
  disabled: boolean;
  onDenied: (error: unknown) => void;
}) {
  const { locale } = useI18n(),
    copy = pollenBackupCopy[locale];
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<
    "downloaded" | "failed" | "unsupported" | null
  >(null);
  const request = useRef<AbortController | null>(null);
  const objectUrl = useRef<string | null>(null);
  function release() {
    request.current?.abort();
    request.current = null;
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
  }
  useEffect(() => () => release(), []);
  useEffect(() => {
    if (disabled) {
      release();
      setBusy(false);
      setNotice(null);
    }
  }, [disabled]);

  async function download() {
    if (disabled || request.current) return;
    release();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setNotice(null);
    try {
      // Recheck owner/workspace access and current settings, never export the
      // selected cached revision. No filename embeds personal configuration.
      const current = await api<PollenDraft>(
        `/monitoring-subjects/${encodeURIComponent(id)}`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      const contents = encodePollenBackup(current.configuration);
      objectUrl.current = URL.createObjectURL(
        new Blob([contents], { type: "application/json" }),
      );
      const link = document.createElement("a");
      link.href = objectUrl.current;
      link.download = "pollen-watch-settings.json";
      document.body.append(link);
      link.click();
      link.remove();
      setNotice("downloaded");
    } catch (error) {
      if (controller.signal.aborted) return;
      if (error instanceof ApiError && draftFailure(error.code) !== "failed")
        onDenied(error);
      else
        setNotice(
          error instanceof PollenBackupError &&
            error.code === "unsupported_backup"
            ? "unsupported"
            : "failed",
        );
    } finally {
      if (!controller.signal.aborted) {
        request.current = null;
        setBusy(false);
      }
    }
  }
  return (
    <div data-pollen-backup>
      <p id="pollen-backup-privacy">{copy.privacy}</p>
      <button
        type="button"
        className={styles.button}
        data-pollen-export
        disabled={disabled || busy}
        aria-describedby="pollen-backup-privacy"
        onClick={() => void download()}
      >
        {copy.export}
      </button>
      {busy && <p role="status">{copy.busy}</p>}
      {notice && (
        <p role={notice === "downloaded" ? "status" : "alert"}>
          {copy[notice]}
        </p>
      )}
    </div>
  );
}

export function PollenDraftImport({
  onLoaded,
}: {
  onLoaded: (configuration: PollenConfiguration) => void;
}) {
  const { locale } = useI18n(),
    copy = pollenBackupCopy[locale];
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<"invalid" | "unsupported" | null>(null);
  const alive = useRef(true);
  const reading = useRef(false);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  async function read(file: File) {
    if (reading.current) return;
    setNotice(null);
    if (!file.size || file.size > POLLEN_BACKUP_MAX_BYTES) {
      setNotice("invalid");
      return;
    }
    reading.current = true;
    setBusy(true);
    try {
      const bytes = await file.arrayBuffer();
      if (!alive.current) return;
      const configuration = decodePollenBackup(
        new TextDecoder("utf-8", { fatal: true }).decode(bytes),
      );
      onLoaded(configuration);
    } catch (error) {
      if (alive.current)
        setNotice(
          error instanceof PollenBackupError &&
            error.code === "unsupported_backup"
            ? "unsupported"
            : "invalid",
        );
    } finally {
      reading.current = false;
      if (alive.current) setBusy(false);
    }
  }
  return (
    <details className={styles.history} data-pollen-import>
      <summary>{copy.import}</summary>
      <p id="pollen-import-notice">{copy.restore}</p>
      <label className={styles.backupFile}>
        {copy.file}
        <input
          type="file"
          accept=".json,application/json"
          disabled={busy}
          aria-describedby="pollen-import-notice"
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = "";
            if (file) void read(file);
          }}
        />
      </label>
      {busy && <p role="status">{copy.busy}</p>}
      {notice && <p role="alert">{copy[notice]}</p>}
    </details>
  );
}
