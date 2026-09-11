// The fragment is a locator, never an authorization token or a saved configuration.
export function pollenDraftIdFromHash(hash: string): string | null {
  const match = /^#draft=([A-Za-z0-9_-]{1,128})$/.exec(hash);
  return match?.[1] ?? null;
}

export function replacePollenDraftLocation(id: string | null) {
  const url = new URL(window.location.href);
  url.hash = id ? `draft=${encodeURIComponent(id)}` : "";
  window.history.replaceState(window.history.state, "", url);
}
