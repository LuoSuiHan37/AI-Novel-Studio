import { redirect } from "next/navigation";

export default async function BibleRedirect({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  redirect(`/projects/${projectId}/story`);
}
