import { redirect } from "next/navigation";

export default async function ProjectSettingsRedirect({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  void projectId;
  redirect("/settings");
}
