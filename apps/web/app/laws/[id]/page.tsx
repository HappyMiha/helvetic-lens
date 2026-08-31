import { LawDetail } from "@/components/law-detail";

export default async function LawPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <LawDetail key={id} id={id} />;
}
