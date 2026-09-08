import { NativeComparisonWorkspace } from "@/components/native-comparison-page";

export default async function NativeComparisonRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <NativeComparisonWorkspace eventId={id} />;
}
