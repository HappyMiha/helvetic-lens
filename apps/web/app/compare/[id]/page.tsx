import { ComparisonView } from "@/components/comparison-view";

export default async function ComparePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ComparisonView key={id} id={id} />;
}
