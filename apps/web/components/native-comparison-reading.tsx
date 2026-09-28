import Link from "next/link";
import type {
  NativeComparisonPage,
  NativeSnapshot,
} from "@/lib/native-baseline";
import { nativeBaselineCopy } from "@/lib/native-baseline";
import { comparisonReadingCopy } from "@/lib/comparison-reading-copy";
import { nativeSnapshotHref } from "@/lib/comparison-selection";
import { sourceCount, sourceTimestamp } from "@/lib/source-reading";
import styles from "./comparison-reading.module.css";

type Locale = keyof typeof comparisonReadingCopy;
export function ComparisonVersion({
  snapshot,
  label,
  locale,
  formatDate,
}: {
  snapshot: NativeSnapshot | null;
  label: string;
  locale: Locale;
  formatDate: (value: string) => string;
}) {
  const copy = comparisonReadingCopy[locale],
    captured = sourceTimestamp(snapshot?.saved_at),
    href = nativeSnapshotHref(snapshot);
  return (
    <section className={styles.version}>
      <h3>{label}</h3>
      {snapshot ? (
        <>
          <p className={styles.versionName}>{snapshot.version_key}</p>
          <dl>
            <div>
              <dt>{copy.captured}</dt>
              <dd>
                {captured ? (
                  <time dateTime={captured}>{formatDate(captured)}</time>
                ) : (
                  copy.unknown
                )}
              </dd>
            </div>
          </dl>
          {href && <Link href={href}>{copy.open}</Link>}
          <details>
            <summary>{copy.details}</summary>
            <dl>
              <div>
                <dt>{copy.version}</dt>
                <dd>{snapshot.id}</dd>
              </div>
            </dl>
          </details>
        </>
      ) : (
        <p>{copy.unknown}</p>
      )}
    </section>
  );
}
export function SavedComparisonSummary({
  data,
  locale,
  formatDate,
}: {
  data: NativeComparisonPage;
  locale: Locale;
  formatDate: (value: string) => string;
}) {
  if (data.status !== "ready") return null;
  const copy = comparisonReadingCopy[locale],
    old = nativeBaselineCopy[locale],
    count = sourceCount(data.material_count);
  return (
    <div className={styles.summary} data-saved-comparison>
      <h2>{copy.savedPair}</h2>
      <div className={styles.summaryFacts}>
        <dl className={styles.metric}>
          <dt>{copy.material}</dt>
          <dd className={count === null ? styles.unknownMetric : undefined}>
            {count === null
              ? copy.unknown
              : new Intl.NumberFormat(locale).format(count)}
          </dd>
        </dl>
        <p className={styles.context}>
          {copy.revision} {data.revision}
          <br />
          {copy.limits}
        </p>
      </div>
      <div className={styles.pair}>
        <ComparisonVersion
          snapshot={data.before}
          label={old.before}
          locale={locale}
          formatDate={formatDate}
        />
        <ComparisonVersion
          snapshot={data.after}
          label={old.after}
          locale={locale}
          formatDate={formatDate}
        />
      </div>
    </div>
  );
}
export function ComparisonPassages({
  data,
  item,
  locale,
  evidenceLabel,
}: {
  data: NativeComparisonPage;
  item: NativeComparisonPage["items"][number];
  locale: Locale;
  evidenceLabel: string;
}) {
  if (data.status !== "ready") return null;
  const copy = nativeBaselineCopy[locale];
  return (
    <div className={styles.pair} data-comparison-passages>
      {(["old", "new"] as const).map((side) => {
        const passage = item[side],
          href = passage
            ? nativeSnapshotHref(
                side === "old" ? data.before : data.after,
                passage.id,
              )
            : null;
        return (
          <section key={side}>
            <h4>{side === "old" ? copy.before : copy.after}</h4>
            <p
              className={styles.passage}
              lang={passage ? data.language : undefined}
            >
              {passage?.text || copy.none}
            </p>
            {href && (
              <Link className={styles.reference} href={href}>
                {evidenceLabel} · {passage?.id}
              </Link>
            )}
          </section>
        );
      })}
    </div>
  );
}
