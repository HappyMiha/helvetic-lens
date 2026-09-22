import type { Metadata } from "next";
import { InfluencePage } from "@/components/influence-page";

export const metadata: Metadata = {
  title: "Influence Graph · Helvetic Lens",
  description:
    "Inspect source-backed relationships, contested claims and documented money flows in workspace dossiers.",
};

export default function Page() {
  return <InfluencePage />;
}
