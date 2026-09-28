/** A source reference identifies an origin; it does not classify its authority. */
export function sourceReference(value: unknown, allowHttp = false) {
  if (
    typeof value !== "string" ||
    value.length > 8192 ||
    value.includes("\\") ||
    Array.from(value).some((character) => character.charCodeAt(0) <= 32)
  )
    return null;
  try {
    const url = new URL(value);
    if (
      (url.protocol !== "https:" && !(allowHttp && url.protocol === "http:")) ||
      url.username ||
      url.password
    )
      return null;
    return { href: url.href, origin: url.host };
  } catch {
    return null;
  }
}

/** Unknown is distinct from a measured zero. */
export function sourceCount(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0
    ? value
    : null;
}

export function sourceFingerprint(value: unknown): string | null {
  return typeof value === "string" && /^[a-f0-9]{64}$/i.test(value)
    ? value.toLowerCase()
    : null;
}

/** Only an explicit, parseable timestamp can receive a machine-readable time. */
export function sourceTimestamp(value: unknown): string | null {
  return typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(
      value,
    ) &&
    Number.isFinite(Date.parse(value))
    ? value
    : null;
}
