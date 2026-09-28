import {
  sourceCount,
  sourceFingerprint,
  sourceReference,
  sourceTimestamp,
} from "@/lib/source-reading";
import { sourceReadingCopy } from "@/lib/source-reading-copy";
import type { Version } from "@/lib/types";
import styles from "./source-reading.module.css";

type Source = Pick<
  Version,
  | "id"
  | "source_url"
  | "created_at"
  | "declared_date"
  | "filename"
  | "content_type"
  | "content_hash"
  | "characters"
  | "passage_count"
  | "identity_json"
>;
export function SourceReadingMetadata({
  source,
  locale,
  savedAt,
  statedLabel,
}: {
  source: Source;
  locale: keyof typeof sourceReadingCopy;
  savedAt: string;
  statedLabel: string;
}) {
  const copy = sourceReadingCopy[locale];
  const reference = sourceReference(source.source_url, true);
  const captured = sourceTimestamp(source.created_at);
  const fingerprint = sourceFingerprint(source.content_hash);
  const metrics = [
    [sourceCount(source.passage_count), copy.passages],
    [sourceCount(source.characters), copy.characters],
  ] as const;
  return (
    <section
      className={styles.provenance}
      data-source-reading
      aria-label={copy.provenance}
    >
      <dl className={styles.facts}>
        <div>
          <dt>{copy.origin}</dt>
          <dd className={styles.origin}>
            {reference?.origin || copy.unknownOrigin}
          </dd>
        </div>
        <div>
          <dt>{copy.captured}</dt>
          <dd>
            {captured ? (
              <time dateTime={captured}>{savedAt}</time>
            ) : (
              copy.unknownDate
            )}
          </dd>
        </div>
        <div>
          <dt>{statedLabel}</dt>
          <dd>{source.declared_date || copy.unknownDate}</dd>
        </div>
        <div>
          <dt>{copy.classification}</dt>
          <dd>{copy.unknownClassification}</dd>
        </div>
      </dl>
      <dl className={styles.metrics}>
        {metrics.map(([value, title]) => (
          <div key={title}>
            <dt>{title}</dt>
            <dd className={value === null ? styles.unknownMetric : undefined}>
              {value === null
                ? copy.unknown
                : new Intl.NumberFormat(locale).format(value)}
            </dd>
          </div>
        ))}
      </dl>
      <details className={styles.details}>
        <summary>{copy.provenance}</summary>
        <dl className={styles.facts}>
          <div>
            <dt>{copy.identifier}</dt>
            <dd>{source.id}</dd>
          </div>
          <div>
            <dt>{copy.filename}</dt>
            <dd>{source.filename || copy.unknown}</dd>
          </div>
          <div>
            <dt>{copy.format}</dt>
            <dd>
              {source.content_type && source.content_type !== "unknown"
                ? source.content_type
                : copy.unknown}
            </dd>
          </div>
          <div>
            <dt>{copy.language}</dt>
            <dd>{source.identity_json?.language || copy.unknown}</dd>
          </div>
        </dl>
        <p>{copy.digestHelp}</p>
        <dl>
          <div>
            <dt>{copy.digest}</dt>
            <dd>
              {fingerprint ? (
                <code data-source-fingerprint>
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
