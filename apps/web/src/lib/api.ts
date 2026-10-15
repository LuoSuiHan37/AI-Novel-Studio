export function getApiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const KEY_STORAGE = "ai-novel-studio.llm-key";
const KEYS_BY_PROVIDER = "ai-novel-studio.llm-keys";
const PROJECT_LLM_PREFS = "ai-novel-studio.llm-project-prefs";
const GLOBAL_LLM_PREFS = "ai-novel-studio.llm-global-prefs";

export type ProjectLlmPrefs = {
  provider: string;
  model: string;
  baseUrl: string;
  reviewProvider?: string;
  reviewModel?: string;
  reviewBaseUrl?: string;
};

export type GlobalLlmPrefs = ProjectLlmPrefs;

const SUPPORTED_LLM_PROVIDERS = new Set([
  "deepseek",
  "gemini",
  "grok",
  "openai",
  "anthropic",
]);

function normalizeLlmPrefs(prefs: ProjectLlmPrefs): ProjectLlmPrefs {
  // Older builds used the generic openai_compatible provider. The settings UI
  // now exposes concrete providers, so migrate that stale browser value to
  // DeepSeek (the previous default for this app).
  const provider =
    prefs.provider === "openai_compatible"
      ? "deepseek"
      : SUPPORTED_LLM_PROVIDERS.has(prefs.provider)
        ? prefs.provider
        : "deepseek";
  return { ...prefs, provider };
}

function readJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

export function getStoredLlmKeys(): Record<string, string> {
  const map = readJson<Record<string, string>>(KEYS_BY_PROVIDER, {});
  return map;
}

export function getStoredLlmKey(provider?: string): string {
  const keys = getStoredLlmKeys();
  if (typeof window === "undefined") return "";
  if (provider) {
    if (keys[provider]) return keys[provider];
    // Only migrate the legacy unscoped key to the historical default provider.
    // Never show a generation key in another provider's input.
    return provider === "deepseek"
      ? window.localStorage.getItem(KEY_STORAGE) || ""
      : "";
  }
  return window.localStorage.getItem(KEY_STORAGE) || "";
}

export function setStoredLlmKey(value: string, provider?: string): void {
  if (typeof window === "undefined") return;
  if (provider) {
    const keys = getStoredLlmKeys();
    if (value) keys[provider] = value;
    else delete keys[provider];
    writeJson(KEYS_BY_PROVIDER, keys);
    // The legacy unscoped key is still used as a fallback for DeepSeek.
    // Remove it together with the provider key, otherwise clearing the
    // DeepSeek input makes the old value reappear on the next render.
    if (!value && provider === "deepseek") {
      window.localStorage.removeItem(KEY_STORAGE);
    }
    return;
  }
  if (value) window.localStorage.setItem(KEY_STORAGE, value);
  else window.localStorage.removeItem(KEY_STORAGE);
}

export function getProjectLlmPrefs(projectId: string): ProjectLlmPrefs | null {
  const all = readJson<Record<string, ProjectLlmPrefs>>(PROJECT_LLM_PREFS, {});
  return all[projectId] ? normalizeLlmPrefs(all[projectId]) : null;
}

export function setProjectLlmPrefs(projectId: string, prefs: ProjectLlmPrefs): void {
  const all = readJson<Record<string, ProjectLlmPrefs>>(PROJECT_LLM_PREFS, {});
  all[projectId] = normalizeLlmPrefs(prefs);
  writeJson(PROJECT_LLM_PREFS, all);
}

export function getGlobalLlmPrefs(): GlobalLlmPrefs | null {
  const prefs = readJson<GlobalLlmPrefs | null>(GLOBAL_LLM_PREFS, null);
  return prefs ? normalizeLlmPrefs(prefs) : null;
}

export function setGlobalLlmPrefs(prefs: GlobalLlmPrefs): void {
  writeJson(GLOBAL_LLM_PREFS, normalizeLlmPrefs(prefs));
}

export async function api<T>(
  path: string,
  options: RequestInit & { projectId?: string } = {},
): Promise<T> {
  const { projectId, headers, ...rest } = options;
  const merged = new Headers(headers);
  merged.set("Content-Type", "application/json");
  merged.set("X-Actor", "studio-user");
  if (projectId) {
    merged.set("X-Project-Id", projectId);
    const prefs = getGlobalLlmPrefs() || getProjectLlmPrefs(projectId);
    if (prefs) {
      if (prefs.provider && !merged.has("X-LLM-Provider")) merged.set("X-LLM-Provider", prefs.provider);
      if (prefs.model && !merged.has("X-LLM-Model")) merged.set("X-LLM-Model", prefs.model);
      if (prefs.baseUrl && !merged.has("X-LLM-Base-Url")) merged.set("X-LLM-Base-Url", prefs.baseUrl);
      const key = getStoredLlmKey(prefs.provider);
      if (key && !merged.has("X-LLM-Api-Key")) merged.set("X-LLM-Api-Key", key);
      if (prefs.reviewProvider && !merged.has("X-Review-Provider")) merged.set("X-Review-Provider", prefs.reviewProvider);
      if (prefs.reviewModel && !merged.has("X-Review-Model")) merged.set("X-Review-Model", prefs.reviewModel);
      if (prefs.reviewBaseUrl && !merged.has("X-Review-Base-Url")) merged.set("X-Review-Base-Url", prefs.reviewBaseUrl);
      const reviewKey = getStoredLlmKey(prefs.reviewProvider);
      if (reviewKey && !merged.has("X-Review-Api-Key")) merged.set("X-Review-Api-Key", reviewKey);
    } else {
      const key = getStoredLlmKey();
      if (key && !merged.has("X-LLM-Api-Key")) merged.set("X-LLM-Api-Key", key);
    }
  } else {
    const prefs = getGlobalLlmPrefs();
    if (prefs) {
      if (prefs.provider && !merged.has("X-LLM-Provider")) merged.set("X-LLM-Provider", prefs.provider);
      if (prefs.model && !merged.has("X-LLM-Model")) merged.set("X-LLM-Model", prefs.model);
      if (prefs.baseUrl && !merged.has("X-LLM-Base-Url")) merged.set("X-LLM-Base-Url", prefs.baseUrl);
      if (prefs.reviewProvider && !merged.has("X-Review-Provider")) merged.set("X-Review-Provider", prefs.reviewProvider);
      if (prefs.reviewModel && !merged.has("X-Review-Model")) merged.set("X-Review-Model", prefs.reviewModel);
      if (prefs.reviewBaseUrl && !merged.has("X-Review-Base-Url")) merged.set("X-Review-Base-Url", prefs.reviewBaseUrl);
    }
    const key = getStoredLlmKey(merged.get("X-LLM-Provider") || prefs?.provider);
    if (key && !merged.has("X-LLM-Api-Key")) merged.set("X-LLM-Api-Key", key);
    const reviewKey = getStoredLlmKey(prefs?.reviewProvider);
    if (reviewKey && !merged.has("X-Review-Api-Key")) merged.set("X-Review-Api-Key", reviewKey);
  }
  const requestPath = path.endsWith("/generate") ? `${path}/stream` : path;
  const url = `${getApiBase()}${requestPath}`;
  let response: Response;
  try {
    response = await fetch(url, { ...rest, headers: merged });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      "network_error",
      `无法连接 API（${getApiBase()}）。请确认后端已启动，并用同一主机名打开前端（localhost 与 127.0.0.1 不要混用）。`,
    );
  }
  if (response.status === 204) return undefined as T;
  if (response.headers.get("content-type")?.includes("text/event-stream")) {
    const reader = response.body?.getReader();
    if (!reader) throw new ApiError(0, "stream_error", "流式响应不可用");
    const decoder = new TextDecoder();
    let buffer = "";
    let donePayload: unknown;
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";
      for (const frame of frames) {
        const eventName = frame.match(/^event:\s*(.+)$/m)?.[1]?.trim() || "message";
        const dataLine = frame.match(/^data:\s*(.+)$/m)?.[1];
        if (!dataLine) continue;
        const data = JSON.parse(dataLine) as Record<string, unknown>;
        if (eventName === "error") throw new ApiError(500, "generation_error", String(data.message || "正文生成失败"));
        if (eventName === "done") donePayload = data;
        if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("chapter-generation-event", { detail: { type: eventName, ...data } }));
      }
      if (chunk.done) break;
    }
    return donePayload as T;
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = payload.error || {};
    throw new ApiError(
      response.status,
      err.code || "http_error",
      err.message || response.statusText,
      err.request_id,
    );
  }
  return payload as T;
}
