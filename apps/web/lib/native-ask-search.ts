export type NativeSearchMode = "sources" | "public";
export type NativeSearchGroup = {
  id: "monitored" | "events" | "pharma" | "loyer";
  failed: boolean;
  items: {
    title: string;
    detail: string;
    href: string | null;
    external: boolean;
  }[];
  more: boolean;
  total: number | null;
  next: string | null;
};
type Request = (path: string, init: RequestInit) => Promise<unknown>;
type RecordValue = Record<string, unknown>;
/** Internal failure codes are mapped to localized interface states by the caller. */
class NativeSearchError extends Error {
  constructor(readonly code: "invalid_query" | "invalid_response") {
    super(code);
  }
}
const record = (value: unknown): RecordValue => {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new NativeSearchError("invalid_response");
  return value as RecordValue;
};
const string = (value: unknown) => (typeof value === "string" ? value : "");

/** Only links to the existing evidence readers or a canonical public dossier. */
export function nativeSearchHref(value: unknown, product?: "pharma" | "loyer") {
  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    /[\\\u0000-\u0020]/.test(value)
  )
    return null;
  const base = product
    ? `https://${product}.helveticlens.ch`
    : "https://helveticlens.ch";
  try {
    const url = new URL(value, base);
    const allowed = product
      ? /^\/public-dossiers\/[^/]+$/
      : /^\/(?:laws|compare|evidence|corpus-evidence|native-comparison)\/[^/]+$/;
    if (url.origin !== base || !allowed.test(url.pathname)) return null;
    return product ? url.href : url.pathname + url.search + url.hash;
  } catch {
    return null;
  }
}

export async function searchNativeAsk(
  question: string,
  mode: NativeSearchMode,
  request: Request,
  signal: AbortSignal,
): Promise<NativeSearchGroup[]> {
  const query = question.trim();
  if (
    query.length < 2 ||
    query.length > 300 ||
    (mode === "public" && new Set(query.toLowerCase().split(/\s+/)).size > 12)
  )
    throw new NativeSearchError("invalid_query");
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  const ids =
    mode === "sources"
      ? (["monitored", "events"] as const)
      : (["pharma", "loyer"] as const);
  const groups = await Promise.all(
    ids.map(async (id): Promise<NativeSearchGroup> => {
      const product = id === "pharma" || id === "loyer" ? id : undefined;
      const params = new URLSearchParams({ q: query });
      if (!product) {
        params.set("view", id);
        params.set("limit", "20");
      }
      const path = product
        ? `/products/${product}/public-knowledge?${params}`
        : `/registry?${params}`;
      try {
        const page = record(await request(path, { signal }));
        if (signal.aborted) throw new DOMException("Aborted", "AbortError");
        if (!Array.isArray(page.items) || page.items.length > 20)
          throw new NativeSearchError("invalid_response");
        const items = page.items.map((value) => {
          const item = record(value);
          const title = string(product ? item.label : item.title);
          if (!title) throw new NativeSearchError("invalid_response");
          const href = product
            ? nativeSearchHref(item.href, product)
            : [item.comparison_url, item.evidence_url, item.timeline_url]
                .map((value) => nativeSearchHref(value))
                .find(Boolean) || null;
          return {
            title,
            detail: product
              ? [string(item.dossier_title), string(item.text)]
                  .filter(Boolean)
                  .join(" · ")
              : [string(item.authority), string(item.why)]
                  .filter(Boolean)
                  .join(" · "),
            href,
            external: Boolean(product),
          };
        });
        const total =
          product &&
          Number.isSafeInteger(page.total) &&
          (page.total as number) >= items.length
            ? (page.total as number)
            : null;
        if (product && total === null)
          throw new NativeSearchError("invalid_response");
        const more = product
          ? total! > items.length
          : Boolean(page.next_cursor);
        const next = product
          ? more
            ? `https://${product}.helveticlens.ch/public-dossiers?${new URLSearchParams({ q: query })}`
            : null
          : `${id === "monitored" ? "/registry" : "/discover"}?${new URLSearchParams({ q: query })}`;
        return { id, failed: false, items, more, total, next };
      } catch (error) {
        if (signal.aborted) throw error;
        return {
          id,
          failed: true,
          items: [],
          more: false,
          total: null,
          next: null,
        };
      }
    }),
  );
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  return groups;
}
