import { api, ApiError } from "@/lib/api";

/** Apply a validated resource automatically and record the actor as system-auto. */
export async function confirmResource(
  submitPath: string,
  approvePath: string,
  projectId: string,
): Promise<void> {
  await api(submitPath, { method: "POST", projectId });
  await api(approvePath, {
    method: "POST",
    projectId,
    body: JSON.stringify({ confirmed_by: "system-auto" }),
  });
}

export async function advancePipeline(projectId: string) {
  return api(`/projects/${projectId}/pipeline/advance`, {
    method: "POST",
    projectId,
    body: JSON.stringify({ confirmed_by: "system-auto" }),
  });
}

/** Best-effort stage advance; ignores gate failures so UI can keep a single CTA. */
export async function tryAdvancePipeline(projectId: string, maxSteps = 3): Promise<number> {
  let advanced = 0;
  for (let i = 0; i < maxSteps; i += 1) {
    try {
      await advancePipeline(projectId);
      advanced += 1;
    } catch (err) {
      if (err instanceof ApiError) break;
      break;
    }
  }
  return advanced;
}
