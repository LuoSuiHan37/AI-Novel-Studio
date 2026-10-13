"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { StatusBanner } from "@/components/ui-bits";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { Project } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function DistillationLandingPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Project[]>("/projects")
      .then(setProjects)
      .catch((err: ApiError) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="mx-auto max-w-5xl space-y-6">
      <header className="max-w-3xl space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Research Lab</p>
        <h1 className="text-2xl font-semibold tracking-tight">蒸馏小说</h1>
        <p className="text-sm leading-6 text-muted-foreground">
          先导入参考作品，提取结构、节奏、人物、文案和表达规律，再把抽象结果用于原创项目。
          每条规律都保留来源证据，不直接复制任何一本小说。
        </p>
      </header>

      <div className="grid gap-3 md:grid-cols-3">
        {["导入参考作品", "交叉分析爆款规律", "注入原创项目"].map((item, index) => (
          <div key={item} className="rounded-xl border bg-muted/20 p-4">
            <span className="text-xs text-muted-foreground">0{index + 1}</span>
            <p className="mt-2 text-sm font-medium">{item}</p>
          </div>
        ))}
      </div>

      <StatusBanner loading={loading} error={error} />

      {projects.length ? (
        <div className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold">选择一个原创项目</h2>
            <p className="mt-1 text-sm text-muted-foreground">蒸馏结果会保存到对应项目，确认后才能注入 Story Bible 和主线情节。</p>
          </div>
          <div className="divide-y rounded-xl border">
            {projects.map((project) => (
              <div key={project.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-4">
                <div>
                  <p className="font-medium">{project.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{project.genre} · {project.language}</p>
                </div>
                <Link href={`/projects/${project.id}/research`} className={cn(buttonVariants(), "inline-flex")}>进入蒸馏工作台</Link>
              </div>
            ))}
          </div>
        </div>
      ) : !loading && !error ? (
        <div className="rounded-xl border border-dashed p-6">
          <p className="font-medium">还没有原创项目</p>
          <p className="mt-1 text-sm text-muted-foreground">先创建一本书，蒸馏结果才有落点。</p>
          <Link href="/projects" className={cn(buttonVariants(), "mt-4 inline-flex")}>创建新书</Link>
        </div>
      ) : null}
    </section>
  );
}
