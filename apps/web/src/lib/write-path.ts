import { api } from "@/lib/api";
import { DEFAULT_CHARACTER, defaultPlan } from "@/lib/defaults";
import { confirmResource, tryAdvancePipeline } from "@/lib/hitl";
import type { Chapter, Character, StoryArc } from "@/lib/types";

export function writeHref(projectId: string, chapterNumber = 1): string {
  return `/projects/${projectId}/chapters/${chapterNumber}`;
}

type CharacterDraft = Omit<Character, "id" | "project_id" | "aliases" | "status" | "updated_at">;

async function ensureCharacter(projectId: string, people: Character[], draft: CharacterDraft) {
    const existing = people.find((item) =>
      [item.name, ...(item.aliases ?? [])].some((name) => name.toLowerCase() === draft.name.toLowerCase()),
    );
  if (existing) {
    if (existing.status !== "approved") {
      await confirmResource(
        `/projects/${projectId}/characters/${existing.id}/submit`,
        `/projects/${projectId}/characters/${existing.id}/approve`,
        projectId,
      );
    }
    return;
  }
  const created = await api<Character>(`/projects/${projectId}/characters`, {
    method: "POST",
    projectId,
    body: JSON.stringify(draft),
  });
  if (created.status !== "approved") {
    await confirmResource(
      `/projects/${projectId}/characters/${created.id}/submit`,
      `/projects/${projectId}/characters/${created.id}/approve`,
      projectId,
    );
  }
}

/** Ensure the names used by a chapter plan are present in the project canon. */
export async function ensureCharactersForPlan(projectId: string, names: string[]): Promise<void> {
  let people = await api<Character[]>(`/projects/${projectId}/characters`).catch(() => [] as Character[]);
  const required = [...new Set(names.map((name) => name.trim()).filter(Boolean))];

  for (const name of required) {
    const normalized = name.toLocaleLowerCase();
    let existing = people.find((item) =>
      [item.name, ...(item.aliases ?? [])].some((candidate) => candidate.trim().toLocaleLowerCase() === normalized),
    );
    if (!existing) {
      // Titles such as "Alpha" are ways of addressing a character, not separate identities.
      const withoutTitle = name.replace(/^(?:alpha|beta|omega|luna|king|queen|prince|princess)\s+/i, "").trim();
      const matches = people.filter((item) => item.name.toLocaleLowerCase() === withoutTitle.toLocaleLowerCase());
      if (matches.length === 1) {
        existing = matches[0];
        const aliases = [...new Set([...(existing.aliases ?? []), name])];
        await api<Character>(`/projects/${projectId}/characters/${existing.id}`, {
          method: "PATCH",
          projectId,
          body: JSON.stringify({ aliases }),
        });
        people = people.map((item) => item.id === existing!.id ? { ...item, aliases } : item);
      }
    }
    if (existing) {
      if (existing.status !== "approved") {
        await confirmResource(
          `/projects/${projectId}/characters/${existing.id}/submit`,
          `/projects/${projectId}/characters/${existing.id}/approve`,
          projectId,
        );
      }
      continue;
    }

    // A chapter plan may introduce a new supporting character. Add only this character
    // to this book's cast; approval remains an explicit user confirmation.
    const draft = {
      ...DEFAULT_CHARACTER,
      name,
      role: "supporting",
      personality: "待完善（根据章节计划补充）",
      background: "在章节计划中首次出现，背景待完善。",
      goal: "待完善",
      motivation: "待完善",
      fear: "待完善",
      secret: "待完善",
      strength: "待完善",
      weakness: "待完善",
      internal_conflict: "待完善",
      external_conflict: "待完善",
      speech_style: "待完善",
      character_arc: "待完善",
      species: null,
      rank: null,
      tropes: [],
    };
    await ensureCharacter(projectId, people, draft);
    people = await api<Character[]>(`/projects/${projectId}/characters`);
  }
}

async function ensureActiveArcApproved(projectId: string, chapterNumber: number): Promise<void> {
  const arcs = await api<StoryArc[]>(`/projects/${projectId}/arcs`).catch(() => [] as StoryArc[]);
  const covering = arcs
    .filter((arc) =>
      (arc.start_chapter_number ?? 1) <= chapterNumber &&
      (arc.end_chapter_number ?? Number.MAX_SAFE_INTEGER) >= chapterNumber,
    )
    .sort((left, right) => left.sequence - right.sequence);
  const active = covering[0] ?? [...arcs].sort((left, right) => left.sequence - right.sequence)[0];
  if (active && active.status !== "approved") {
    await confirmResource(
      `/projects/${projectId}/arcs/${active.id}/submit`,
      `/projects/${projectId}/arcs/${active.id}/approve`,
      projectId,
    );
  }
}

/** Fill the minimum canon needed to write, then return the chapter editor path. */
export async function ensureWriteReady(projectId: string, chapterNumber = 1): Promise<string> {
  const people = await api<Character[]>(`/projects/${projectId}/characters`).catch(() => [] as Character[]);
  if (!people.some((item) => item.status === "approved")) {
    for (const person of people) {
      if (person.status !== "approved") {
        await confirmResource(
          `/projects/${projectId}/characters/${person.id}/submit`,
          `/projects/${projectId}/characters/${person.id}/approve`,
          projectId,
        );
      }
    }
    if (people.length) await tryAdvancePipeline(projectId);
  }

  // The chapter pipeline uses the lowest-sequence arc covering this chapter.
  // Confirm that exact arc so a newer, unrelated approved arc cannot leave the
  // current chapter blocked by the active-arc gate.
  await ensureActiveArcApproved(projectId, chapterNumber);

  const chapters = await api<Chapter[]>(`/projects/${projectId}/chapters`).catch(() => [] as Chapter[]);
  if (!chapters.length) {
    await api(`/projects/${projectId}/chapters/plan`, {
      method: "POST",
      projectId,
      body: JSON.stringify(defaultPlan(1)),
    });
    return writeHref(projectId, 1);
  }

  const latest = [...chapters].sort((a, b) => b.chapter_number - a.chapter_number)[0];
  const target = latest.content?.trim() ? latest.chapter_number : latest.chapter_number;
  return writeHref(projectId, target || 1);
}
