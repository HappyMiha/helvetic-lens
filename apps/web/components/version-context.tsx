import Link from "next/link";
import type { Version } from "@/lib/types";
import {
  sourceCount,
  sourceFingerprint,
  sourceReference,
  sourceTimestamp,
} from "@/lib/source-reading";
import { sourceReadingCopy } from "@/lib/source-reading-copy";
import { savedEvidenceHref } from "@/lib/saved-evidence-link";
import styles from "./version-context.module.css";

export function VersionContext({
  version,
  side,
  locale,
  formatDate,
  originLabel,
  dateLabel,
  syntheticLabel,
  readingLabel,
}: {
  version: Version;
  side: string;
  locale: keyof typeof sourceReadingCopy;
  formatDate: (value: string) => string;
  originLabel: string;
  dateLabel: string;
  syntheticLabel: string;
  readingLabel?: string;
}) {
  const copy = sourceReadingCopy[locale],
    capture = sourceTimestamp(version.created_at),
    reference = sourceReference(version.source_url, true),
    fingerprint = sourceFingerprint(version.content_hash),
    href = savedEvidenceHref(version.id);
  return (
    <section className={styles.version} data-version-context>
      <h3>{side}</h3>
      <p className={styles.documentDate}>
        {version.declared_date || copy.unknownDate}
      </p>
      <p className={styles.dateLabel}>
        {dateLabel} · {originLabel}
      </p>
      {version.synthetic && <p className="synthetic-label">{syntheticLabel}</p>}
      <dl className={styles.facts}>
        <div>
          <dt>{copy.captured}</dt>
          <dd>
            {capture ? (
              <time dateTime={capture}>{formatDate(capture)}</time>
            ) : (
              copy.unknownDate
            )}
          </dd>
        </div>
        <div>
          <dt>{copy.origin}</dt>
          <dd>{reference?.origin || copy.unknownOrigin}</dd>
        </div>
      </dl>
      <dl className={styles.counts}>
        {(
          [
            [version.passage_count, copy.passages],
            [version.characters, copy.characters],
          ] as const
        ).map(([raw, label]) => {
          const count = sourceCount(raw);
          return (
            <div key={label}>
              <dt>{label}</dt>
              <dd className={count === null ? styles.unknown : undefined}>
                {count === null
                  ? copy.unknown
                  : new Intl.NumberFormat(locale).format(count)}
              </dd>
            </div>
          );
        })}
      </dl>
      {href && (
        <Link className={styles.read} href={href}>
          {readingLabel || copy.reading}
        </Link>
      )}
      <details className={styles.details}>
        <summary>{copy.provenance}</summary>
        <dl className={styles.facts}>
          <div>
            <dt>{copy.identifier}</dt>
            <dd>{version.id || copy.unknown}</dd>
          </div>
          <div>
            <dt>{copy.filename}</dt>
            <dd>{version.filename || copy.unknown}</dd>
          </div>
          <div>
            <dt>{copy.format}</dt>
            <dd>
              {version.content_type && version.content_type !== "unknown"
                ? version.content_type
                : copy.unknown}
            </dd>
          </div>
          <div>
            <dt>{copy.language}</dt>
            <dd>{version.identity_json?.language || copy.unknown}</dd>
          </div>
          <div>
            <dt>{copy.classification}</dt>
            <dd>{copy.unknownClassification}</dd>
          </div>
        </dl>
        <p>{copy.digestHelp}</p>
        <dl>
          <div>
            <dt>{copy.digest}</dt>
            <dd>
              {fingerprint ? (
                <code data-version-fingerprint>
                  {copy.sha} {fingerprint}
                </code>
              ) : (
                copy.unknown
              )}
            </dd>
          </div>
        </dl>
      </details>
    </section>
  );
}

export function ReportVersionReferences({
  before,
  after,
  beforeLabel,
  afterLabel,
  unknown,
}: {
  before: string;
  after: string;
  beforeLabel: string;
  afterLabel: string;
  unknown: string;
}) {
  return (
    <div className={styles.references} data-report-version-references>
      {[
        [before, beforeLabel],
        [after, afterLabel],
      ].map(([id, label], index) => {
        const href = savedEvidenceHref(id);
        return (
          <span key={index}>
            <span>{label}</span>
            {href ? <Link href={href}>{id}</Link> : <span>{unknown}</span>}
          </span>
        );
      })}
    </div>
  );
}
