"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from "react";
import { ArrowUpRight, Search } from "lucide-react";
import { useAuth } from "./auth-gate";
import { useI18n } from "@/lib/i18n";
import { api } from "@/lib/api";
import {
  askBoundary,
  isAskShortcut,
  type AskDraftDecision,
} from "@/lib/ask-interaction";
import { nativeAskCopy } from "@/lib/native-ask-copy";
import {
  searchNativeAsk,
  type NativeSearchGroup,
  type NativeSearchMode,
} from "@/lib/native-ask-search";
import {
  productDestinations,
  productNavigationCopy,
} from "@/lib/product-navigation";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { ProductDestinations } from "./product-destinations";
import styles from "./native-ask-search.module.css";

export type NativeAskContext = {
  boundary: string;
  prepare: (question: string) => AskDraftDecision;
  open: () => void;
  close: () => void;
};
const AskContext = createContext<{
  register: (context: NativeAskContext) => () => void;
}>({ register: () => () => {} });
export const useNativeAsk = () => useContext(AskContext);

export function NativeAskTrigger({
  label,
  open,
  controls,
  onOpen,
  buttonRef,
}: {
  label: string;
  open: boolean;
  controls: string;
  onOpen: () => void;
  buttonRef?: React.Ref<HTMLButtonElement>;
}) {
  return (
    <button
      type="button"
      className={styles.trigger}
      data-native-ask-trigger
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls={controls}
      aria-keyshortcuts="Meta+K Control+K"
      onClick={onOpen}
      ref={buttonRef}
    >
      <Search size={18} aria-hidden="true" />
      <span>{label}</span>
      <kbd>{nativeAskCopy["en-CH"].shortcut}</kbd>
    </button>
  );
}

export function NativeAskSearchProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { session } = useAuth();
  const { locale } = useI18n();
  const boundary = askBoundary(
    pathname,
    session?.organization?.id,
    session?.user?.id,
    locale,
    JSON.stringify([
      session?.authenticated,
      session?.anonymous_development,
      session?.role,
      session?.platform_admin,
    ]),
  );
  const privateAccess = Boolean(
    session?.authenticated || session?.anonymous_development,
  );
  const [context, setContext] = useState<NativeAskContext | null>(null);
  const registered = useRef<NativeAskContext | null>(null);
  const register = useCallback((next: NativeAskContext) => {
    registered.current = next;
    setContext(next);
    return () => {
      if (registered.current === next) registered.current = null;
      setContext((value) => (value === next ? null : value));
    };
  }, []);
  return (
    <AskContext.Provider value={{ register }}>
      {children}
      <NativeAskDialog
        key={boundary}
        boundary={boundary}
        privateAccess={privateAccess}
        context={context}
        registered={registered}
        locale={locale}
      />
    </AskContext.Provider>
  );
}

function NativeAskDialog({
  boundary,
  privateAccess,
  context,
  registered,
  locale,
}: {
  boundary: string;
  privateAccess: boolean;
  context: NativeAskContext | null;
  registered: RefObject<NativeAskContext | null>;
  locale: keyof typeof nativeAskCopy;
}) {
  const copy = nativeAskCopy[locale];
  const currentBoundary = useRef(boundary);
  const available = context?.boundary === boundary ? context : null;
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ boundary, value: "" });
  const query = draft.boundary === boundary ? draft.value : "";
  const [result, setResult] = useState<{
    boundary: string;
    query: string;
    groups: NativeSearchGroup[];
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<
    "conflict" | "unavailable" | "invalid" | null
  >(null);
  const controller = useRef<AbortController | null>(null);
  const epoch = useRef(0);
  const mounted = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const handoff = useRef<string | null>(null);
  const panelId = useId();
  const invalidate = useCallback(() => {
    epoch.current++;
    controller.current?.abort();
    controller.current = null;
  }, []);
  const close = useCallback(() => {
    invalidate();
    setOpen(false);
    setBusy(false);
    setResult(null);
    setNotice(null);
  }, [invalidate]);
  const openAsk = useCallback(() => {
    if (open) {
      input.current?.focus();
      return;
    }
    opener.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    if (registered.current?.boundary === currentBoundary.current)
      registered.current.close();
    setOpen(true);
  }, [open]);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      invalidate();
    };
  }, [invalidate]);

  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      const dialog =
        event.target instanceof Element
          ? event.target.closest(
              'dialog[open], [role="dialog"], [role="alertdialog"]',
            )
          : null;
      if (!isAskShortcut(event, dialog)) return;
      event.preventDefault();
      openAsk();
    };
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [openAsk]);

  async function search(mode: NativeSearchMode) {
    if (busy || (mode === "sources" && !privateAccess)) return;
    invalidate();
    const attempt = epoch.current;
    const scope = boundary;
    const next = new AbortController();
    controller.current = next;
    setBusy(true);
    setNotice(null);
    setResult(null);
    try {
      const groups = await searchNativeAsk(
        query,
        mode,
        (path, init) => api(path, init),
        next.signal,
      );
      if (attempt === epoch.current && scope === currentBoundary.current)
        setResult({ boundary: scope, query: query.trim(), groups });
    } catch {
      if (attempt === epoch.current && !next.signal.aborted)
        setNotice("invalid");
    } finally {
      if (attempt === epoch.current) setBusy(false);
    }
  }
  function prepare(existing = false) {
    const active = registered.current;
    if (!active || active.boundary !== boundary) {
      setNotice("unavailable");
      return;
    }
    const decision = existing ? "ready" : active.prepare(query);
    if (decision !== "ready") {
      setNotice(decision);
      return;
    }
    if (!existing) setDraft({ boundary, value: "" });
    handoff.current = boundary;
    close();
  }
  const groups = result?.boundary === boundary ? result.groups : null;
  const groupTitle = (id: NativeSearchGroup["id"]) =>
    id === "monitored" || id === "events"
      ? copy[id]
      : productDestinations.find((item) => item.id === id)!.name;
  return (
    <>
      <NativeAskTrigger
        label={copy.trigger}
        open={open}
        controls={panelId}
        onOpen={openAsk}
        buttonRef={trigger}
      />
      <Dialog open={open} onOpenChange={(next) => (next ? openAsk() : close())}>
        <DialogContent
          id={panelId}
          className={styles.dialog}
          data-helvetic-ask="true"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            input.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            const transfer = handoff.current;
            handoff.current = null;
            if (transfer) {
              requestAnimationFrame(() => {
                if (
                  mounted.current &&
                  transfer === currentBoundary.current &&
                  registered.current?.boundary === transfer
                )
                  registered.current.open();
              });
            } else if (
              opener.current?.isConnected &&
              opener.current.getClientRects().length
            )
              opener.current.focus({ preventScroll: true });
            else trigger.current?.focus({ preventScroll: true });
          }}
        >
          <DialogHeader>
            <DialogTitle>{copy.title}</DialogTitle>
            <DialogDescription>{copy.intro}</DialogDescription>
          </DialogHeader>
          <form
            className={styles.form}
            onSubmit={(event) => {
              event.preventDefault();
              void search(privateAccess ? "sources" : "public");
            }}
          >
            <label htmlFor={panelId + "-query"}>{copy.trigger}</label>
            <input
              id={panelId + "-query"}
              ref={input}
              value={query}
              placeholder={copy.placeholder}
              maxLength={300}
              autoComplete="off"
              onChange={(event) => {
                invalidate();
                setBusy(false);
                setDraft({ boundary, value: event.target.value });
                setResult(null);
                setNotice(null);
              }}
            />
            <div className={styles.actions}>
              {privateAccess && (
                <button
                  type="submit"
                  disabled={busy || query.trim().length < 2}
                >
                  {copy.sources}
                </button>
              )}
              <button
                type={privateAccess ? "button" : "submit"}
                disabled={busy || query.trim().length < 2}
                onClick={
                  privateAccess ? () => void search("public") : undefined
                }
              >
                {copy.public}
              </button>
              {available && (
                <button
                  type="button"
                  disabled={busy || !query.trim()}
                  onClick={() => prepare()}
                >
                  {copy.prepare}
                </button>
              )}
            </div>
            <p>
              {available
                ? copy.prepareHelp
                : privateAccess
                  ? copy.intro
                  : copy.signIn}
            </p>
          </form>
          <p className={styles.note}>{copy.privacy}</p>
          {notice && (
            <div role="alert">
              <p>{copy[notice]}</p>
              {available && notice !== "invalid" && (
                <button type="button" onClick={() => prepare(true)}>
                  {copy.openMarvin}
                </button>
              )}
            </div>
          )}
          {busy && <p role="status">{copy.searching}</p>}
          {groups && (
            <div className={styles.results} aria-live="polite">
              <p className={styles.searched}>“{result?.query}”</p>
              {groups.map((group) => (
                <section key={group.id} aria-label={groupTitle(group.id)}>
                  <h3>{groupTitle(group.id)}</h3>
                  {group.failed ? (
                    <p role="alert">{copy.failed}</p>
                  ) : (
                    <>
                      <p className={styles.note}>
                        {group.items.length} {copy.shown}
                        {group.total !== null
                          ? ` · ${new Intl.NumberFormat(locale).format(group.total)} ${copy.total}`
                          : ""}
                        {group.more ? ` · ${copy.more}` : ""}
                      </p>
                      {!group.items.length && <p>{copy.empty}</p>}
                      {group.items.map((item, index) => (
                        <article key={`${item.href}:${index}`}>
                          {item.href ? (
                            item.external ? (
                              <a
                                href={item.href}
                                target="_blank"
                                rel="noopener noreferrer"
                                referrerPolicy="no-referrer"
                              >
                                <strong>{item.title}</strong>
                                <ArrowUpRight size={15} aria-hidden="true" />
                              </a>
                            ) : (
                              <Link href={item.href} onNavigate={close}>
                                <strong>{item.title}</strong>
                              </Link>
                            )
                          ) : (
                            <>
                              <strong>{item.title}</strong>
                              <small>{copy.noReader}</small>
                            </>
                          )}
                          <p>{item.detail}</p>
                        </article>
                      ))}
                      {group.next &&
                        (group.id === "pharma" || group.id === "legal" ? (
                          <a
                            href={group.next}
                            target="_blank"
                            rel="noopener noreferrer"
                            referrerPolicy="no-referrer"
                          >
                            {copy.openCollection}
                            <ArrowUpRight size={15} aria-hidden="true" />
                          </a>
                        ) : (
                          <Link href={group.next} onNavigate={close}>
                            {copy.openCollection}
                          </Link>
                        ))}
                    </>
                  )}
                </section>
              ))}
            </div>
          )}
          <ProductDestinations
            current="platform"
            copy={productNavigationCopy[locale]}
          />
          <p className={styles.note}>{copy.retained}</p>
        </DialogContent>
      </Dialog>
    </>
  );
}
