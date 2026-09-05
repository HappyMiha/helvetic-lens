// Navigation changes are explicit; stale cursors never survive a new filter.
const keys = ["source", "severity", "item_type", "watched_law", "state", "candidate", "cursor", "limit"];
export function inboxQuery(query: string, changes: Record<string, string> = {}): string {
  const current = new URLSearchParams(query);
  const result = new URLSearchParams();
  for (const key of keys) {
    const value = current.get(key);
    if (value) result.set(key, value);
  }
  if (Object.keys(changes).some(key => key !== "cursor")) result.delete("cursor");
  if (Object.keys(changes).some(key => !["cursor", "candidate", "limit"].includes(key))) result.delete("candidate");
  for (const [key, value] of Object.entries(changes)) {
    if (!keys.includes(key)) continue;
    if (value) result.set(key, value); else result.delete(key);
  }
  return result.toString();
}
