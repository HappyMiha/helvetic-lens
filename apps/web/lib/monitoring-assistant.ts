import help from "../../../services/api/helvetic_lens/monitoring_assistant_help.json";
import { centreCopy } from "./monitoring-centre-copy";
import { monitoringNavigation } from "./monitoring-navigation";
import type { Locale } from "./i18n";

export type MonitoringAssistantRoute = keyof typeof help.locales["en-CH"]["routes"];

// Only exact section paths enter this context. Query values, private monitor
// identities and forms never become part of a companion conversation.
export function monitoringAssistantRoute(pathname: string): MonitoringAssistantRoute | null {
  if (pathname === "/monitoring/email") return "/monitoring";
  return Object.hasOwn(help.locales["en-CH"].routes, pathname)
    ? pathname as MonitoringAssistantRoute
    : null;
}

export function monitoringAssistantMessages(locale: Locale): Record<string, string> {
  const copy = help.locales[locale];
  const messages: Record<string, string> = {
    "companion.monitoring.action": centreCopy[locale].title,
    "companion.monitoring.help": copy.button,
    "companion.monitoring.question": copy.question,
    "companion.monitoring.boundary": copy.boundary,
  };
  for (const route of Object.keys(copy.routes) as MonitoringAssistantRoute[]) {
    const direction = monitoringNavigation.find(item => item.href === route);
    messages[`companion.monitoring.${route}.title`] = direction
      ? centreCopy[locale].templates[direction.id][0] : centreCopy[locale].title;
    messages[`companion.monitoring.${route}.description`] = copy.routes[route];
  }
  return messages;
}
