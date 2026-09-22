"use client";

import { useId, useRef, useState } from "react";
import { ArrowUpRight, Building2, GitFork, UserRound } from "lucide-react";
import { influenceCopy } from "@/lib/influence-copy";
import { useI18n } from "@/lib/i18n";
import {
  evidenceStatuses,
  influenceEdgeGeometry,
  INFLUENCE_NODE_WIDTH as NODE_WIDTH,
  INFLUENCE_NODE_HEIGHT as NODE_HEIGHT,
  safeSourceUrl,
  visibleInfluenceEdges,
  type InfluenceDossier,
  type InfluenceEdge,
  type InfluenceEvidence,
  type Perspective,
} from "@/lib/influence-graph";
import styles from "./influence.module.css";

const tones = {
  documented: "#245f97",
  reported: "#806006",
  disputed: "#a44521",
  not_established: "#677083",
};
export function InfluenceReader({ dossier }: { dossier: InfluenceDossier }) {
  const { locale } = useI18n();
  const copy = influenceCopy[locale];
  const [view, setView] = useState<"graph" | "list">("graph");
  const [perspective, setPerspective] = useState<Perspective>("all");
  const [entityId, setEntityId] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const detailRef = useRef<HTMLElement>(null);
  const markerId = useId().replaceAll(":", "-");
  const visible = visibleInfluenceEdges(dossier, perspective, entityId || null);
  const selected = visible.find((edge) => edge.id === selectedId) || visible[0];
  const connectedIds = new Set(visible.flatMap((edge) => [edge.from, edge.to]));
  const nodes =
    perspective === "all" && !entityId
      ? dossier.entities
      : dossier.entities.filter((entity) => connectedIds.has(entity.id));
  const byId = new Map(dossier.entities.map((entity) => [entity.id, entity]));
  const paths = new Map(
    visible.flatMap((edge) => {
      const from = byId.get(edge.from),
        to = byId.get(edge.to);
      return from && to
        ? [
            [
              edge.id,
              influenceEdgeGeometry(from, to, edge, dossier.edges),
            ] as const,
          ]
        : [];
    }),
  );
  const bounds = [...paths.values()];
  const originX = Math.max(0, ...bounds.map((path) => -path.minX));
  const originY = Math.max(0, ...bounds.map((path) => -path.minY));
  const width =
    originX +
    Math.max(
      980,
      ...nodes.map((node) => node.x + NODE_WIDTH + 30),
      ...bounds.map((path) => path.maxX),
    );
  const height =
    Math.max(
      280,
      ...nodes.map((node) => node.y + NODE_HEIGHT + 30),
      ...bounds.map((path) => path.maxY),
    ) + originY;
  const date = (value: string | null) =>
    value
      ? new Intl.DateTimeFormat(locale, {
          dateStyle: "medium",
          timeZone: "UTC",
        }).format(new Date(value))
      : copy.undated;

  function inspect(edge: InfluenceEdge) {
    setSelectedId(edge.id);
    detailRef.current?.focus({ preventScroll: true });
    if (window.matchMedia("(max-width: 1100px)").matches)
      detailRef.current?.scrollIntoView({ block: "start" });
  }

  function connectionLabel(edge: InfluenceEdge) {
    return edge.id.length > 5 ? dossier.edges.indexOf(edge) + 1 : edge.id;
  }

  function EvidenceCard({
    evidence,
    counter = false,
  }: {
    evidence: InfluenceEvidence;
    counter?: boolean;
  }) {
    const source = dossier.sources.find(
      (item) => item.id === evidence.sourceId,
    );
    if (!source) return null;
    return (
      <section
        className={`${styles.evidenceCard} ${counter ? styles.counter : ""}`}
      >
        <strong className={styles.eyebrow}>
          {counter ? copy.disputing : copy.supporting}
        </strong>
        <h4 lang={source.language}>{source.title}</h4>
        <p className={styles.meta}>
          {source.publisher} · {copy.sourceKinds[source.kind]}
        </p>
        <p lang={dossier.summaryLanguage}>{evidence.summary}</p>
        {evidence.quote && (
          <blockquote lang={source.language}>{evidence.quote}</blockquote>
        )}
        <dl className={styles.metadata}>
          <dt>{copy.locator}</dt>
          <dd lang={dossier.summaryLanguage}>{evidence.locator}</dd>
          <dt>{copy.sourceDate}</dt>
          <dd>{date(source.publishedOn)}</dd>
          <dt>{copy.checked}</dt>
          <dd>{date(source.checkedOn)}</dd>
        </dl>
        {safeSourceUrl(source.url) && (
          <a
            className={styles.sourceLink}
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {copy.open}
            <ArrowUpRight size={16} aria-hidden="true" />
          </a>
        )}
        {source.snapshotText ? (
          <details>
            <summary>{copy.extract}</summary>
            <pre lang={source.language}>{source.snapshotText}</pre>
          </details>
        ) : (
          <p className={styles.meta}>{copy.noArchive}</p>
        )}
      </section>
    );
  }

  return (
    <section className={styles.reader}>
      <div className={styles.dossierHeading}>
        <div>
          <h2 lang={dossier.summaryLanguage}>{dossier.title}</h2>
          <p className={styles.meta}>
            {copy.snapshot}: {date(dossier.checkedOn)} · {copy.sourceLanguage}:{" "}
            {dossier.summaryLanguage.toUpperCase()}
          </p>
        </div>
        <div className={styles.stats}>
          <span>
            <b>{dossier.entities.length}</b>
            {copy.entities}
          </span>
          <span>
            <b>{dossier.edges.length}</b>
            {copy.connections}
          </span>
          <span>
            <b>{dossier.sources.length}</b>
            {copy.sources}
          </span>
        </div>
      </div>
      <div className={styles.toolbar}>
        <fieldset className={styles.viewSwitch}>
          <legend className={styles.srOnly}>{copy.perspective}</legend>
          {(["graph", "list"] as const).map((mode) => (
            <label key={mode} className={view === mode ? styles.chosen : ""}>
              <input
                type="radio"
                name={`${markerId}-view`}
                checked={view === mode}
                onChange={() => setView(mode)}
              />
              {copy[mode]}
            </label>
          ))}
        </fieldset>
        <label>
          {copy.perspective}
          <select
            value={perspective}
            onChange={(event) =>
              setPerspective(event.target.value as Perspective)
            }
          >
            {(["all", "documented", "money", "policy"] as const).map((mode) => (
              <option key={mode} value={mode}>
                {copy[mode]}
              </option>
            ))}
          </select>
        </label>
        <label>
          {copy.entity}
          <select
            value={entityId}
            onChange={(event) => setEntityId(event.target.value)}
          >
            <option value="">{copy.allEntities}</option>
            {dossier.entities.map((entity) => (
              <option key={entity.id} value={entity.id}>
                {entity.name}
              </option>
            ))}
          </select>
        </label>
        {(perspective !== "all" || entityId) && (
          <button
            type="button"
            onClick={() => {
              setPerspective("all");
              setEntityId("");
            }}
          >
            {copy.clear}
          </button>
        )}
      </div>
      <p className={styles.helper}>
        {perspective === "money" ? copy.moneyHelp : copy.graphHelp}
      </p>
      <div className={styles.readerGrid}>
        <div className={styles.visualPanel}>
          <div className={styles.panelBar}>
            <span aria-live="polite">
              {visible.length} / {dossier.edges.length}{" "}
              {copy.connections.toLowerCase()} {copy.count}
            </span>
            {view === "graph" && (
              <div className={styles.zoom}>
                <button
                  aria-label={`${copy.graph} −`}
                  onClick={() => setZoom(Math.max(0.6, zoom - 0.1))}
                >
                  −
                </button>
                <button onClick={() => setZoom(1)}>
                  {Math.round(zoom * 100)}%
                </button>
                <button
                  aria-label={`${copy.graph} +`}
                  onClick={() => setZoom(Math.min(1.6, zoom + 0.1))}
                >
                  +
                </button>
              </div>
            )}
          </div>
          {view === "graph" && nodes.length > 0 ? (
            <div
              className={styles.graphScroll}
              tabIndex={0}
              role="region"
              aria-label={copy.graph}
            >
              <div style={{ width: width * zoom, height: height * zoom }}>
                <div
                  className={styles.canvas}
                  style={{ width, height, transform: `scale(${zoom})` }}
                >
                  <svg
                    width={width}
                    height={height}
                    role="group"
                    aria-label={copy.connections}
                  >
                    <defs>
                      {evidenceStatuses.map((status) => (
                        <marker
                          key={status}
                          id={`${markerId}-${status}`}
                          viewBox="0 0 10 10"
                          refX="9"
                          refY="5"
                          markerWidth="7"
                          markerHeight="7"
                          orient="auto-start-reverse"
                        >
                          <path
                            d="M 0 0 L 10 5 L 0 10 z"
                            fill={tones[status]}
                          />
                        </marker>
                      ))}
                    </defs>
                    <g transform={`translate(${originX} ${originY})`}>
                      {visible.map((edge) => {
                        const from = byId.get(edge.from),
                          to = byId.get(edge.to);
                        if (!from || !to) return null;
                        const geometry = paths.get(edge.id)!;
                        const active = selected?.id === edge.id;
                        return (
                          <g
                            key={edge.id}
                            className={styles.graphEdge}
                            role="button"
                            tabIndex={0}
                            aria-pressed={active}
                            aria-label={`${from.name} → ${to.name}: ${edge.label}. ${copy.statuses[edge.status]}`}
                            onClick={() => inspect(edge)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                inspect(edge);
                              }
                            }}
                          >
                            <title>
                              {edge.label} · {copy.statuses[edge.status]}
                            </title>
                            <path
                              d={geometry.path}
                              stroke="transparent"
                              strokeWidth="26"
                              fill="none"
                            />
                            <path
                              className={styles.visibleEdge}
                              d={geometry.path}
                              stroke={tones[edge.status]}
                              strokeWidth={active ? 3 : 1.7}
                              strokeDasharray={
                                edge.status === "documented"
                                  ? undefined
                                  : edge.status === "not_established"
                                    ? "3 6"
                                    : "9 5"
                              }
                              markerEnd={`url(#${markerId}-${edge.status})`}
                              fill="none"
                            />
                            <rect
                              x={geometry.x - 24}
                              y={geometry.y - 15}
                              width="48"
                              height="30"
                              rx="6"
                              fill={active ? tones[edge.status] : "#fff"}
                              stroke={tones[edge.status]}
                            />
                            <text
                              x={geometry.x}
                              y={geometry.y + 5}
                              textAnchor="middle"
                              fill={active ? "#fff" : tones[edge.status]}
                              fontSize="14"
                              fontWeight="650"
                            >
                              {connectionLabel(edge)}
                            </text>
                          </g>
                        );
                      })}
                    </g>
                  </svg>
                  {nodes.map((entity) => (
                    <button
                      type="button"
                      key={entity.id}
                      title={entity.name}
                      className={`${styles.node} ${entityId === entity.id ? styles.nodeSelected : ""}`}
                      style={{
                        left: entity.x + originX,
                        top: entity.y + originY,
                        width: NODE_WIDTH,
                        minHeight: NODE_HEIGHT,
                      }}
                      onClick={() =>
                        setEntityId(entityId === entity.id ? "" : entity.id)
                      }
                      aria-pressed={entityId === entity.id}
                    >
                      <span className={styles.nodeMeta}>
                        {entity.kind === "person" ? (
                          <UserRound size={15} />
                        ) : entity.kind === "company" ? (
                          <Building2 size={15} />
                        ) : (
                          <GitFork size={15} />
                        )}
                        {copy.entityKinds[entity.kind]}
                        {entity.country ? ` · ${entity.country}` : ""}
                      </span>
                      <strong lang={dossier.summaryLanguage}>
                        {entity.name}
                      </strong>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : view === "list" && visible.length ? (
            <ol className={styles.edgeList}>
              {visible.map((edge) => (
                <li key={edge.id}>
                  <button
                    aria-pressed={selected?.id === edge.id}
                    onClick={() => inspect(edge)}
                    className={
                      selected?.id === edge.id ? styles.selectedRow : ""
                    }
                  >
                    <span className={styles.rowNumber}>
                      {connectionLabel(edge)}
                    </span>
                    <span className={styles.rowBody}>
                      <strong lang={dossier.summaryLanguage}>
                        {byId.get(edge.from)?.name} → {byId.get(edge.to)?.name}
                      </strong>
                      <span lang={dossier.summaryLanguage}>{edge.label}</span>
                      <small>{date(edge.asOf)}</small>
                    </span>
                    <span className={styles.badge} data-status={edge.status}>
                      {copy.statuses[edge.status]}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <p className={styles.empty}>{copy.empty}</p>
          )}
          <div className={styles.legend}>
            {evidenceStatuses.map((status) => (
              <span key={status}>
                <i
                  style={{
                    borderColor: tones[status],
                    borderStyle:
                      status === "documented"
                        ? "solid"
                        : status === "not_established"
                          ? "dotted"
                          : "dashed",
                  }}
                />
                {copy.statuses[status]}
              </span>
            ))}
          </div>
        </div>
        <aside
          className={styles.evidencePanel}
          ref={detailRef}
          tabIndex={-1}
          aria-label={copy.evidence}
        >
          {selected ? (
            <>
              <span className={styles.eyebrow}>{copy.selected}</span>
              <h3 lang={dossier.summaryLanguage}>
                {byId.get(selected.from)?.name}
                <span className={styles.direction}>↓</span>
                {byId.get(selected.to)?.name}
              </h3>
              <span className={styles.badge} data-status={selected.status}>
                {copy.statuses[selected.status]}
              </span>
              <p className={styles.claim} lang={dossier.summaryLanguage}>
                {selected.statement}
              </p>
              <dl className={styles.metadata}>
                <dt>{copy.kind}</dt>
                <dd>{copy.relationKinds[selected.kind]}</dd>
                <dt>{copy.effective}</dt>
                <dd>{date(selected.asOf)}</dd>
              </dl>
              {selected.money && (
                <div className={styles.moneyBlock}>
                  <span>{copy[selected.money.basis]}</span>
                  <strong>
                    {new Intl.NumberFormat(locale, {
                      style: "currency",
                      currency: selected.money.currency,
                      maximumFractionDigits: 2,
                    }).format(selected.money.amount)}
                  </strong>
                  <small>
                    {date(selected.money.periodStart)} –{" "}
                    {date(selected.money.periodEnd)}
                  </small>
                </div>
              )}
              {selected.supporting.map((evidence, index) => (
                <EvidenceCard key={`s-${index}`} evidence={evidence} />
              ))}
              {selected.disputing.map((evidence, index) => (
                <EvidenceCard key={`d-${index}`} evidence={evidence} counter />
              ))}
              <section className={styles.limitBox}>
                <strong>{copy.scope}</strong>
                <ul lang={dossier.summaryLanguage}>
                  {selected.limits.map((limit, index) => (
                    <li key={index}>{limit}</li>
                  ))}
                </ul>
              </section>
            </>
          ) : (
            <p>{copy.noSelection}</p>
          )}
        </aside>
      </div>
      {!!dossier.gaps.length && (
        <section className={styles.gaps}>
          <h3>{copy.gaps}</h3>
          <ul lang={dossier.summaryLanguage}>
            {dossier.gaps.map((gap, index) => (
              <li key={index}>{gap}</li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}
