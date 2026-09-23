import { LegalProfilesPage } from "@/components/legal-profiles-page";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <LegalProfilesPage profileId={id} />;
}
