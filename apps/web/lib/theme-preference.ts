/** Device-local appearance only. Never store research, identity or session data. */
export type ThemePreference = "dark" | "light" | "system";
export const THEME_STORAGE_KEY = "helvetic-lens-theme";

export function readTheme(value: unknown): ThemePreference | null {
  return value === "dark" || value === "light" || value === "system"
    ? value
    : null;
}

export function nextTheme(theme: ThemePreference): ThemePreference {
  return theme === "dark" ? "system" : theme === "system" ? "light" : "dark";
}

// Static, first-party head script. No request, cookie, account or user text input.
// Keep its first-paint behavior equivalent to initializeTheme (tested together).
export const THEME_BOOTSTRAP = `(function(){var t='dark';try{var s=localStorage.getItem('helvetic-lens-theme');if(s==='light'||s==='dark'||s==='system')t=s}catch(e){}var d=t==='dark';if(t==='system'){try{d=matchMedia('(prefers-color-scheme: dark)').matches}catch(e){d=false}}var r=document.documentElement;r.dataset.theme=t;r.classList.toggle('dark',d);r.style.colorScheme=d?'dark':'light'})();`;

export function initializeTheme(
  host: Window,
  changed: (theme: ThemePreference) => void,
) {
  const root = host.document.documentElement;
  let selected = readTheme(root.dataset.theme) ?? "dark";
  try {
    selected =
      readTheme(host.localStorage.getItem(THEME_STORAGE_KEY)) ?? "dark";
  } catch {
    // The bootstrap choice remains usable if storage is blocked.
  }
  let media: MediaQueryList | undefined;
  try {
    media = host.matchMedia("(prefers-color-scheme: dark)");
  } catch {
    /* Light system fallback. */
  }
  let disposed = false;
  const apply = () => {
    if (disposed) return;
    const dark =
      selected === "dark" || (selected === "system" && Boolean(media?.matches));
    root.dataset.theme = selected;
    root.classList.toggle("dark", dark);
    root.style.colorScheme = dark ? "dark" : "light";
    changed(selected);
  };
  const storageChanged = (event: StorageEvent) => {
    if (event.key !== THEME_STORAGE_KEY && event.key !== null) return;
    try {
      if (event.storageArea !== host.localStorage) return;
    } catch {
      return;
    }
    selected = readTheme(event.newValue) ?? "dark";
    apply();
  };
  media?.addEventListener("change", apply);
  host.addEventListener("storage", storageChanged);
  apply();
  return {
    select(value: ThemePreference) {
      if (disposed || !readTheme(value)) return;
      selected = value;
      try {
        host.localStorage.setItem(THEME_STORAGE_KEY, value);
      } catch {
        /* Retain this page's choice. */
      }
      apply();
    },
    dispose() {
      disposed = true;
      media?.removeEventListener("change", apply);
      host.removeEventListener("storage", storageChanged);
    },
  };
}

export const themeCopy = {
  "en-CH": {
    label: "Theme",
    dark: "Dark",
    light: "Light",
    system: "System",
    next: "Switch to",
  },
  "de-CH": {
    label: "Darstellung",
    dark: "Dunkel",
    light: "Hell",
    system: "System",
    next: "Wechseln zu",
  },
  "fr-CH": {
    label: "Apparence",
    dark: "Sombre",
    light: "Clair",
    system: "Système",
    next: "Passer à",
  },
  "it-CH": {
    label: "Aspetto",
    dark: "Scuro",
    light: "Chiaro",
    system: "Sistema",
    next: "Passa a",
  },
  "rm-CH": {
    label: "Cumparsa",
    dark: "Stgir",
    light: "Cler",
    system: "Sistem",
    next: "Midar a",
  },
} as const;
