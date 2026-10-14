// Pure URL rules shared by the app shell and its tests. The shell shows the
// Helvetic Lens site itself; everything else opens outside the web view.

export const SITE_ORIGIN = "https://helveticlens.ch";
export const APP_SCHEME = "helveticlens";

const SITE_HOSTS = new Set(["helveticlens.ch", "www.helveticlens.ch"]);

export type LinkTarget = "app" | "browser" | "system" | "ignore";

/** Decide where a navigation requested by the page should go. */
export function classifyNavigation(rawUrl: string): LinkTarget {
  if (rawUrl === "about:blank" || rawUrl.startsWith("about:srcdoc")) return "app";
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    return "ignore";
  }
  switch (url.protocol) {
    case "https:":
      return SITE_HOSTS.has(url.hostname) ? "app" : "browser";
    case "http:":
      return "browser";
    case "mailto:":
    case "tel:":
    case "sms:":
      return "system";
    case "blob:":
    case "data:":
      return "app";
    default:
      return "ignore";
  }
}

/**
 * Map an incoming deep link (helveticlens://registry, or an https link to the
 * site) to a site URL, or null when the link is not ours. Only the path, query
 * and fragment are kept so a link can never point the shell at another origin.
 */
export function deepLinkToSiteUrl(rawUrl: string | null | undefined): string | null {
  if (!rawUrl) return null;
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    return null;
  }
  let path: string;
  if (url.protocol === `${APP_SCHEME}:`) {
    // helveticlens://registry/x parses with host "registry"; helveticlens:///x has no host.
    path = `/${url.hostname}${url.pathname}`.replace(/\/{2,}/g, "/");
  } else if (url.protocol === "https:" && SITE_HOSTS.has(url.hostname)) {
    path = url.pathname;
  } else {
    return null;
  }
  if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
  return `${SITE_ORIGIN}${path}${url.search}${url.hash}`;
}
