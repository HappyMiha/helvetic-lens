import type { TemplateId } from "./monitoring-centre-copy";

// Section access is independent of source readiness. A source problem belongs
// inside its section, where the user can still inspect and edit saved settings.
export const monitoringNavigation: ReadonlyArray<{
  id: TemplateId;
  href: string;
}> = [
  { id: "pollen", href: "/pollen-watch" },
  { id: "river", href: "/river-watch" },
  { id: "air", href: "/air-watch" },
  { id: "warnings", href: "/hazard-watch" },
  { id: "commute", href: "/commute-watch" },
  { id: "traffic", href: "/road-watch" },
  { id: "tenders", href: "/tender-watch" },
  { id: "ip", href: "/trademark-watch" },
  { id: "auctions", href: "/auction-watch" },
];
