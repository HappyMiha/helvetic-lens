"use client";
import {
  createContext,
  Fragment,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { riverCopy } from "@/lib/river-copy";
import { Shell } from "./shell";

export const RiverAccessFailure = createContext<(error: unknown) => void>(
  () => {},
);
export function RiverPrivateBoundary({ children }: { children: ReactNode }) {
  const { locale } = useI18n(),
    c = riverCopy[locale];
  const [denied, setDenied] = useState(false),
    [visible, setVisible] = useState(true),
    [epoch, setEpoch] = useState(0);
  const deny = useCallback((error: unknown) => {
    if (
      error instanceof ApiError &&
      [
        "authentication_required",
        "membership_required",
        "subject_role_denied",
        "river_disabled",
      ].includes(error.code)
    )
      setDenied(true);
  }, []);
  useEffect(() => {
    const hide = () => setVisible(false);
    const show = () => {
      setEpoch((v) => v + 1);
      setVisible(true);
    };
    window.addEventListener("pagehide", hide);
    window.addEventListener("pageshow", show);
    return () => {
      window.removeEventListener("pagehide", hide);
      window.removeEventListener("pageshow", show);
    };
  }, []);
  return (
    <RiverAccessFailure.Provider value={deny}>
      {visible && !denied ? (
        <Fragment key={epoch}>{children}</Fragment>
      ) : (
        <Shell>
          <h1>{c.title}</h1>
          <p role="alert">{c.failed}</p>
          <button
            onClick={() => {
              setDenied(false);
              setEpoch((v) => v + 1);
              setVisible(true);
            }}
          >
            {c.refresh}
          </button>
        </Shell>
      )}
    </RiverAccessFailure.Provider>
  );
}
