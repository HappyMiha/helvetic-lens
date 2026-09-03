"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Check, FileUp, Globe2, Loader2, Search, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorText, refreshWorkspace, useResource } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Health, Law, Preview, Source, Version } from "@/lib/types";
import { ErrorNote } from "./common";

function documentUrl(value: string) {
  try {
    const parsed = new URL(value.trim());
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return "";
  }
}

function PreviewBox({ preview }: { preview: Preview }) {
  const { t, number } = useI18n();
  const pages = preview.page_count ? t("form.pages", { count: number(preview.page_count) }) : "";
  return (
    <div className="extraction-preview">
      <div className="flex items-center gap-2 mb-2 font-semibold text-sm">
        <Check size={15} />
        {preview.title}
      </div>
      <div className="text-xs muted mb-3">
        {t("form.previewMeta", { type: preview.content_type, characters: number(preview.characters), passages: number(preview.passage_count), pages })}
      </div>
      <div className="preview-text">{preview.excerpt}</div>
    </div>
  );
}

export function AddDocumentDialog({
  open,
  onOpenChange,
  mode,
  initialUrl = "",
  initialName = "",
  sourceId,
  source,
  provider: initialProvider = "native",
  onCreated,
}: {
  open: boolean;
  onOpenChange: (value: boolean) => void;
  mode: "source" | "law";
  initialUrl?: string;
  initialName?: string;
  sourceId?: string;
  source?: Source | null;
  provider?: string;
  onCreated?: (record: Law | Source) => void;
}) {
  const { t } = useI18n();
  const { data: health } = useResource<Health>(open ? "/health" : null);
  const { data: trackedLaws } = useResource<Law[]>(
    open && mode === "law" ? "/laws" : null,
  );
  const [url, setUrl] = useState(""),
    [name, setName] = useState(""),
    [section, setSection] = useState("/");
  const [provider, setProvider] = useState("native"),
    [synthetic, setSynthetic] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null),
    [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  const existingLaw = trackedLaws?.find(
    (law) => documentUrl(law.url) === documentUrl(url),
  );
  useEffect(() => {
    if (open) {
      setUrl(source?.url || initialUrl);
      setName(source?.name || initialName);
      setSection(source?.section || "/");
      setProvider(source?.provider || initialProvider);
      setPreview(null);
      setError("");
      setBusy("");
      setSynthetic(false);
    }
  }, [
    open,
    initialUrl,
    initialName,
    initialProvider,
    source?.id,
    source?.name,
    source?.provider,
    source?.section,
    source?.url,
  ]);
  async function test() {
    setBusy("preview");
    setError("");
    setPreview(null);
    try {
      const data = await api<Preview>("/preview", {
        method: "POST",
        body: JSON.stringify({ url, provider }),
      });
      setPreview(data);
      if (!name.trim())
        setName(data.title.slice(0, mode === "source" ? 250 : 300));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (existingLaw) return;
    if (!preview) {
      await test();
      return;
    }
    setBusy("save");
    setError("");
    try {
      const payload =
        mode === "source"
          ? { url, name, section, provider }
          : { url, name, provider, source_id: sourceId || null, synthetic };
      const path =
        mode === "source"
          ? "/sources" + (source ? "/" + source.id : "")
          : "/laws";
      const result = await api<Law | Source>(path, {
        method: source && mode === "source" ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      refreshWorkspace();
      onOpenChange(false);
      onCreated?.(result);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {mode === "source"
              ? source
                ? t("form.editWebsite")
                : t("form.connectWebsite")
              : t("form.addDocument")}
          </DialogTitle>
          <DialogDescription>
            {mode === "source"
              ? t("form.sourceDescription")
              : t("form.lawDescription")}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={save} className="form-stack">
          <label>
            {mode === "source"
              ? t("form.websiteUrl")
              : t("form.currentUrl")}
            <Input
              type="url"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setPreview(null);
              }}
              placeholder="https://…"
              required
              maxLength={3000}
            />
          </label>
          <label>
            {t("form.displayName")} <span className="muted font-normal">({t("common.optional")})</span>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("form.titlePlaceholder")}
              maxLength={mode === "source" ? 250 : 300}
            />
          </label>
          {mode === "source" && (
            <label>
              {t("form.discoverySection")}
              <Input
                value={section}
                onChange={(e) => setSection(e.target.value)}
                placeholder="/"
              />
              <span className="field-help">
                {t("form.sectionHelp")}
              </span>
            </label>
          )}
          <details className="text-xs muted">
            <summary className="cursor-pointer mb-3">
              {t("form.extraction")}
            </summary>
            <label className="!text-xs">
              {t("form.provider")}
              <select
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  setPreview(null);
                }}
              >
                <option value="native">{t("form.native")}</option>
                <option
                  value="firecrawl"
                  disabled={!health?.firecrawl.configured}
                >
                  {t("form.firecrawl")}{" "}
                  {health?.firecrawl.configured ? "" : t("form.serverKey")}
                </option>
              </select>
            </label>
            <p className="field-help">
              {t("form.providerHelp")}
            </p>
          </details>
          {mode === "law" && (
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={synthetic}
                onChange={(e) => setSynthetic(e.target.checked)}
              />
              {t("form.syntheticSource")}
            </label>
          )}
          <ErrorNote message={error} />
          {existingLaw && (
            <div className="info-note">
              <p>{t("form.alreadyTracked", { name: existingLaw.name })}</p>
              <Button asChild variant="outline" size="sm">
                <Link
                  href={"/laws/" + existingLaw.id}
                  onClick={() => onOpenChange(false)}
                >
                  {t("form.openExisting")}
                </Link>
              </Button>
            </div>
          )}
          {preview && <PreviewBox preview={preview} />}
          <div className="form-actions">
            <Button
              type="button"
              variant="outline"
              onClick={test}
              disabled={!!busy || !url.trim()}
            >
              {busy === "preview" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Search />
              )}
              {mode === "source" ? t("form.testConnection") : t("form.previewDocument")}
            </Button>
            <Button
              type="submit"
              disabled={!!busy || !preview || !!existingLaw}
            >
              {busy === "save" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Globe2 />
              )}
              {mode === "source"
                ? source
                  ? t("form.saveConnection")
                  : t("form.connectWebsite")
                : t("form.addWatchlist")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ImportDialog({
  open,
  onOpenChange,
  law,
  onImported,
}: {
  open: boolean;
  onOpenChange: (value: boolean) => void;
  law: Law;
  onImported: (version: Version, reused: boolean) => void;
}) {
  const { t } = useI18n();
  const [mode, setMode] = useState<"file" | "text" | "url">("file");
  const [file, setFile] = useState<File | null>(null),
    [text, setText] = useState(""),
    [url, setUrl] = useState("");
  const [date, setDate] = useState(""),
    [synthetic, setSynthetic] = useState(false),
    [confirmed, setConfirmed] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null),
    [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setMode("file");
      setFile(null);
      setText("");
      setUrl("");
      setDate("");
      setSynthetic(false);
      setConfirmed(false);
      setPreview(null);
      setError("");
    }
  }, [open]);
  function payload() {
    const data = new FormData();
    if (mode === "file" && file) data.append("file", file);
    if (mode === "text") data.append("text", text);
    if (mode === "url") data.append("url", url);
    data.append("declared_date", date);
    data.append("synthetic", String(synthetic));
    data.append(
      "allow_identity_mismatch",
      String(confirmed && preview?.identity?.status === "mismatch"),
    );
    data.append(
      "confirm_identity",
      String(confirmed && preview?.identity?.status === "unknown"),
    );
    return data;
  }
  async function test() {
    setBusy("preview");
    setError("");
    try {
      if (file && mode === "file" && file.size > 8388608)
        throw new Error(t("error.fileTooLarge"));
      setPreview(
        await api<Preview>("/laws/" + law.id + "/import?preview=true", {
          method: "POST",
          body: payload(),
        }),
      );
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!preview || !confirmed) return;
    setBusy("save");
    setError("");
    try {
      const result = await api<{ version: Version; reused: boolean }>(
        "/laws/" + law.id + "/import",
        { method: "POST", body: payload() },
      );
      refreshWorkspace();
      onOpenChange(false);
      onImported(result.version, result.reused);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy("");
    }
  }
  const hasInput =
    mode === "file" ? !!file : mode === "text" ? !!text.trim() : !!url.trim();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("form.importTitle")}</DialogTitle>
          <DialogDescription>
            {t("form.importDescription", { name: law.name })}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={save} className="form-stack">
          <div className="segmented">
            {(["file", "text", "url"] as const).map((value) => (
              <button
                key={value}
                type="button"
                className={mode === value ? "selected" : ""}
                onClick={() => {
                  setMode(value);
                  setPreview(null);
                  setConfirmed(false);
                  setError("");
                }}
              >
                {value === "file"
                  ? t("form.uploadFile")
                  : value === "text"
                    ? t("form.pasteText")
                    : t("form.historicalUrl")}
              </button>
            ))}
          </div>
          {mode === "file" && (
            <label className="file-drop">
              <FileUp size={28} />
              <strong>{file?.name || t("form.chooseEarlier")}</strong>
              <span className="text-xs muted">
                {t("form.fileHelp")}
              </span>
              <Input
                type="file"
                accept=".pdf,.html,.htm,.txt"
                onChange={(e) => {
                  setFile(e.target.files?.[0] || null);
                  setPreview(null);
                  setConfirmed(false);
                }}
              />
            </label>
          )}
          {mode === "text" && (
            <label>
              {t("form.previousText")}
              <Textarea
                rows={7}
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  setPreview(null);
                  setConfirmed(false);
                }}
                maxLength={1200000}
                placeholder={t("form.pastePlaceholder")}
              />
            </label>
          )}
          {mode === "url" && (
            <label>
              {t("form.olderUrl")}
              <Input
                type="url"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  setPreview(null);
                  setConfirmed(false);
                }}
                placeholder="https://…"
              />
            </label>
          )}
          <label>
            {t("form.versionDate")}{" "}
            <span className="muted font-normal">({t("common.optional")})</span>
            <Input
              type="text"
              aria-label={t("form.versionDate")}
              placeholder="YYYY-MM-DD"
              pattern="[0-9]{4}-[0-9]{2}-[0-9]{2}"
              maxLength={10}
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
            <span className="field-help">
              {t("form.versionDateHelp")}
            </span>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={synthetic}
              onChange={(e) => setSynthetic(e.target.checked)}
            />
            {t("form.syntheticVersion")}
          </label>
          <ErrorNote message={error} />
          {preview && (
            <>
              <PreviewBox preview={preview} />
              {preview.identity &&
                ["unknown", "mismatch"].includes(preview.identity.status) && (
                  <div
                    className={
                      preview.identity.status === "mismatch"
                        ? "identity-warning identity-mismatch"
                        : "identity-warning"
                    }
                  >
                    <strong>
                      {preview.identity.status === "mismatch"
                        ? t("form.differentDocument")
                        : t("form.unknownAssignment")}
                    </strong>
                    <p>{preview.identity.reason}</p>
                    {preview.identity.detected_title && (
                      <p>
                        {t("form.detected", { title: preview.identity.detected_title })}
                      </p>
                    )}
                  </div>
                )}
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />
                {preview.identity?.status === "mismatch"
                  ? t("form.confirmMismatch")
                  : t("form.confirmVersion")}
              </label>
            </>
          )}
          <p className="text-xs muted m-0">
            {t("form.unverifiedHistory")}
          </p>
          <div className="form-actions">
            <Button
              type="button"
              variant="outline"
              onClick={test}
              disabled={!!busy || !hasInput}
            >
              {busy === "preview" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Search />
              )}
              {t("form.previewExtraction")}
            </Button>
            <Button type="submit" disabled={!!busy || !preview || !confirmed}>
              {busy === "save" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Upload />
              )}
              {preview?.identity?.status === "mismatch"
                ? t("form.saveInspection")
                : t("form.importBaseline")}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
