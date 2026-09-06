"use client";

import { useMemo, useRef } from "react";
import { Button } from "./ui/button";
import { useI18n } from "@/lib/i18n";
import { materialLabels } from "@/lib/material-headings";
import type { Change, Comparison } from "@/lib/types";

type Cluster = NonNullable<Comparison["diff"]["change_clusters"]>[number];
type Position = {query: string; page: number};
const SIZE = 5;

export function MaterialChanges({clusters, changes, units, state, onStateChange, onEvidence}: {
  clusters: Cluster[]; changes: Change[]; units?: Comparison["diff"]["legal_units"]; state: Position;
  onStateChange: (state: Position) => void; onEvidence: (id: string) => void;
}) {
  const {t, number} = useI18n();
  const classifications: Record<string, string> = {
    substantive:t("materialPage.substantive"), uncertain:t("materialPage.uncertain"),
    structural:t("materialPage.structural"), formatting_only:t("materialPage.formatting_only"),
    moved:t("materialPage.moved"), renumbered:t("materialPage.renumbered"),
    added:t("materialPage.added"), removed:t("materialPage.removed"),
  };
  const unitNames: Record<string,string> = {
    title:t("materialUnit.title"), chapter:t("materialUnit.chapter"), section:t("materialUnit.section"),
    article:t("materialUnit.article"), paragraph:t("materialUnit.paragraph"),
    littera:t("materialUnit.littera"), number:t("materialUnit.number"),
  };
  function names(value: ReturnType<typeof materialLabels>) {
    const text = value.items.map(path => path.map(item => `${unitNames[item.type]} ${item.label}`).join(" · ")).join("; ");
    return value.additional ? `${text} (+${number(value.additional)})` : text;
  }
  const heading = useRef<HTMLHeadingElement>(null);
  const rows = useMemo(() => {
    const byId = new Map(changes.map(change => [change.id, change]));
    const oldUnits = new Map((units?.old || []).map(unit => [unit.id,unit]));
    const newUnits = new Map((units?.new || []).map(unit => [unit.id,unit]));
    return clusters.map((cluster, index) => {
      const items = cluster.change_ids.map(id => byId.get(id)).filter((item): item is Change => !!item);
      const before = materialLabels(cluster.old_unit_ids, oldUnits, new Set(items.flatMap(item => item.old ? [item.old.id] : [])));
      const after = materialLabels(cluster.new_unit_ids, newUnits, new Set(items.flatMap(item => item.new ? [item.new.id] : [])));
      return {cluster, index, items, before, after, search: items.flatMap(item => [item.old?.text || "", item.new?.text || ""]).join(" ").normalize("NFKC").toLocaleLowerCase()};
    });
  }, [clusters, changes, units]);
  const query = state.query.trim().normalize("NFKC").toLocaleLowerCase();
  const matching = query ? rows.filter(row => `${row.search} ${names({...row.before,items:row.before.all,additional:0})} ${names({...row.after,items:row.after.all,additional:0})}`.normalize("NFKC").toLocaleLowerCase().includes(query)) : rows;
  const pages = Math.max(1, Math.ceil(matching.length / SIZE));
  const page = Math.min(state.page, pages - 1);
  const shown = matching.slice(page * SIZE, (page + 1) * SIZE);
  function move(next: number) {
    onStateChange({...state, page: next});
    heading.current?.focus();
    heading.current?.scrollIntoView({block: "start"});
  }
  return <section className="material-reader" data-material-reader aria-label={t("materialPage.title")}>
    <div className="material-reader-controls">
      <h3 ref={heading} tabIndex={-1}>{t("materialPage.title")}</h3>
      <p className="muted">{t("materialPage.help")}</p>
      <label className="grid gap-2">{t("materialPage.search")}
        <input className="input" type="search" data-material-search value={state.query}
          onChange={event => onStateChange({query: event.target.value, page: 0})} />
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <p role="status" data-material-range>{t("materialPage.range", {start: number(matching.length ? page * SIZE + 1 : 0), end: number(Math.min((page + 1) * SIZE, matching.length)), total: number(matching.length), all: number(rows.length)})}</p>
        {state.query && <Button variant="outline" data-material-clear onClick={() => {onStateChange({query:"",page:0}); heading.current?.focus();}}>{t("materialPage.clear")}</Button>}
      </div>
      <nav className="flex flex-wrap gap-2 items-center" aria-label={t("materialPage.pages")}>
        <Button variant="outline" data-material-previous disabled={page === 0} onClick={() => move(page - 1)}>{t("materialPage.previous")}</Button>
        <label>{t("materialPage.page")}{" "}<select className="input !w-auto" data-material-page value={page} onChange={event => move(Number(event.target.value))}>
          {Array.from({length:pages}, (_, index) => <option value={index} key={index}>{number(index + 1)} / {number(pages)}</option>)}
        </select></label>
        <Button variant="outline" data-material-next disabled={page === pages - 1} onClick={() => move(page + 1)}>{t("materialPage.next")}</Button>
      </nav>
    </div>
    {!matching.length && <p className="p-5" data-material-empty>{t("materialPage.empty")}</p>}
    <div className="semantic-clusters">
      {shown.map(({cluster,index,items,before,after}) => {
        const first = items[0];
        const oldName = names(before), newName = names(after);
        const unitHeading = oldName && newName && oldName !== newName ? `${oldName} → ${newName}` : newName || oldName;
        return <article key={cluster.id} data-material-group={cluster.id}>
          <div className="semantic-cluster-heading"><h4 data-material-heading>{unitHeading || t("compare.changeGroup", {number:number(index + 1)})}</h4><span>{t("compare.exactChangeCount", {count:number(cluster.change_ids.length)})}</span></div>
          {unitHeading && <p className="muted">{t("materialUnit.provenance")}</p>}
          <p>{cluster.classifications.map(value => classifications[value] || t("materialPage.uncertain")).join(" · ")}</p>
          <p className="muted">{t("materialPage.sample")}</p>
          <div className="material-delta">
            <div><strong>{t("compare.before")}</strong><p>{first?.old?.text.slice(0,260) || t("compare.noEarlierUnit")}</p></div>
            <div><strong>{t("compare.after")}</strong><p>{first?.new?.text.slice(0,260) || t("compare.noCurrentUnit")}</p></div>
          </div>
          {cluster.ambiguous && <span className="needs-review-label">{t("compare.needsReview")}</span>}
          <details><summary>{t("materialPage.technical")}</summary><p className="semantic-cluster-units">{cluster.id} · {cluster.old_unit_ids.join(", ")} → {cluster.new_unit_ids.join(", ")}</p></details>
          {first && <Button variant="outline" data-material-evidence onClick={() => onEvidence(first.id)}>{t("compare.viewEvidence")}</Button>}
          {items.length > 1 && <label className="grid gap-2">{t("materialPage.exact")}
            <select className="input" value="" onChange={event => event.target.value && onEvidence(event.target.value)}>
              <option value="">{t("compare.jump")}</option>
              {items.map((item,i) => <option key={item.id} value={item.id}>{number(i+1)} · {(item.new?.text || item.old?.text || t("compare.savedUnitChange")).slice(0,100)}</option>)}
            </select>
          </label>}
        </article>;
      })}
    </div>
  </section>;
}
