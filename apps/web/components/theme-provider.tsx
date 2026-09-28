"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  initializeTheme,
  nextTheme,
  themeCopy,
  type ThemePreference,
} from "@/lib/theme-preference";

const ThemeContext = createContext({
  theme: "dark" as ThemePreference,
  select: (_theme: ThemePreference) => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemePreference>("dark");
  const controller = useRef<ReturnType<typeof initializeTheme> | null>(null);
  useEffect(() => {
    controller.current = initializeTheme(window, setTheme);
    return () => {
      controller.current?.dispose();
      controller.current = null;
    };
  }, []);
  return (
    <ThemeContext.Provider
      value={{ theme, select: (value) => controller.current?.select(value) }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function ThemeControl({
  locale = "en-CH",
  className = "theme-control",
}: {
  locale?: keyof typeof themeCopy;
  className?: string;
}) {
  const { theme, select } = useContext(ThemeContext);
  const copy = themeCopy[locale];
  const next = nextTheme(theme);
  const Icon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;
  return (
    <Button
      type="button"
      variant="outline"
      className={className}
      onClick={() => select(next)}
      aria-label={`${copy.label}: ${copy[theme]}. ${copy.next} ${copy[next]}.`}
    >
      <Icon size={17} aria-hidden="true" />
      <span className="theme-name">{copy[theme]}</span>
    </Button>
  );
}
