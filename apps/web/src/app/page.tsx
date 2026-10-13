"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { projectMetaLine } from "@/lib/labels";
import type { Project } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Project[]>("/projects")
      .then(setProjects)
      .catch((err: ApiError) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">工作台</h1>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">可以直接写作，也可以先蒸馏参考小说，提取爆款结构和文案规律。</p>
        <Link href="/research" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "inline-flex")}>蒸馏小说</Link>
      </div>
      <StatusBanner loading={loading} error={error} />
      <div className="space-y-3">
        {projects.map((project) => (
          <article key={project.id} className="rounded-xl border px-4 py-4">
            <div className="font-medium">{project.title}</div>
            <div className="mt-1 text-xs text-muted-foreground">{projectMetaLine(project)}</div>
            <div className="mt-3">
              <Link
                href={`/projects/${project.id}/write`}
                className={cn(buttonVariants({ size: "sm" }), "inline-flex")}
              >
                去写小说
              </Link>
              <Link
                href={`/projects/${project.id}/research`}
                className={cn(buttonVariants({ variant: "outline", size: "sm" }), "ml-2 inline-flex")}
              >
                蒸馏参考小说
              </Link>
            </div>
          </article>
        ))}
      </div>
      {!loading && projects.length === 0 && !error ? (
        <p className="text-sm text-muted-foreground">还没有项目。先去创建一本。</p>
      ) : null}
      <Link href="/projects" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "inline-flex")}>
        管理项目
      </Link>
    </section>
  );
}
