import type { SavedLegalUnit } from "./types";

export type UnitLabel = {type: string; label: string};
const kinds = new Set(["title", "chapter", "section", "article", "paragraph", "littera", "number"]);

// Only the saved parser hierarchy is used. Passage positions and opaque IDs are
// never promoted to legal numbers. Validate attachment to this exact diff side.
export function materialLabels(ids: string[], units: Map<string, SavedLegalUnit>, passageIds: Set<string>) {
  const paths: {full: UnitLabel[]; short: UnitLabel[]}[] = [];
  const seen = new Set<string>();
  for (const id of ids) {
    const unit = units.get(id);
    if (!unit || !Array.isArray(unit.passage_ids) || !unit.passage_ids.some(id => passageIds.has(id)) || !Array.isArray(unit.path)) continue;
    const path = unit.path.flatMap(value => {
      if (typeof value !== "string") return [];
      const colon = value.indexOf(":");
      const type = value.slice(0,colon), label = value.slice(colon+1).trim();
      if (colon < 1 || !kinds.has(type) || !label || label.length > 80) return [];
      return [{type,label}];
    });
    // An article plus its subdivisions is more useful than the full title tree.
    const article = path.findLastIndex(item => item.type === "article");
    const short = article >= 0 ? path.slice(article) : path.slice(-2);
    const signature = JSON.stringify(path);
    if (short.length && !seen.has(signature)) {seen.add(signature); paths.push({full:path,short});}
  }
  // Repeated article numbers in different chapters/annex-like hierarchies must
  // not collapse into one misleading label. Keep distinguishing saved ancestors.
  const counts = new Map<string,number>();
  for (const path of paths) {const key=JSON.stringify(path.short); counts.set(key,(counts.get(key)||0)+1);}
  const labels = paths.map(path => (counts.get(JSON.stringify(path.short)) || 0) > 1 ? path.full : path.short);
  return {all:labels, items:labels.slice(0,3), additional:Math.max(0,labels.length-3)};
}
