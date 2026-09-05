import { EvidenceView } from "@/components/evidence-view";

export default async function EvidencePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ passage?: string | string[] }>;
}) {
  const { id } = await params;
  const { passage } = await searchParams;
  const passageId = typeof passage === "string" ? passage : "";
  return <EvidenceView native key={id + passageId} id={id} passageId={passageId} />;
}
