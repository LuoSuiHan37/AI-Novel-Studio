export function extractProjectId(pathname: string): string | null {
  const match = pathname.match(/^\/projects\/([^/]+)/);
  if (!match || match[1] === undefined) return null;
  return match[1];
}

export type NavItem = { href: string; label: string };

export type NavGroup = {
  title: string;
  items: NavItem[];
};

export function getGlobalNav(): NavItem[] {
  return [
    { href: "/", label: "工作台" },
    { href: "/projects", label: "作品库" },
    { href: "/research", label: "参考研究" },
    { href: "/settings", label: "AI 设置" },
  ];
}

/** Primary writing path — keep short. */
export function getProjectPrimaryNav(projectId: string): NavItem[] {
  const base = `/projects/${projectId}`;
  return [
    { href: `${base}/write`, label: "去写小说" },
    { href: `${base}/research`, label: "爆款研究" },
    { href: base, label: "概览" },
  ];
}

/** Canon + runtime reference — secondary library. */
export function getProjectLibraryNav(projectId: string): NavItem[] {
  const base = `/projects/${projectId}`;
  return [
    { href: `${base}/characters`, label: "角色" },
    { href: `${base}/world`, label: "世界观" },
    { href: `${base}/plot`, label: "主线情节" },
    { href: `${base}/arcs`, label: "故事弧" },
    { href: `${base}/memory`, label: "故事记忆" },
    { href: `${base}/timeline`, label: "时间线" },
    { href: `${base}/hooks`, label: "钩子 / 伏笔" },
  ];
}

export function getProjectNavGroups(projectId: string): NavGroup[] {
  return [
    { title: "创作主路径", items: getProjectPrimaryNav(projectId) },
    { title: "资料库", items: getProjectLibraryNav(projectId) },
  ];
}

/** Flat list for overview checklist links (not sidebar). */
export function getProjectNav(projectId: string): NavItem[] {
  return [
    ...getProjectPrimaryNav(projectId),
    ...getProjectLibraryNav(projectId),
  ];
}

export function isNavActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/projects") return pathname === "/projects";
  if (href.endsWith("/write")) {
    return /\/(write|chapters)(\/|$)/.test(pathname);
  }
  if (href.endsWith("/chapters")) return /\/chapters(\/|$)/.test(pathname);
  if (/\/projects\/[^/]+$/.test(href)) {
    return pathname === href;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
