const KEY = "cs46-simulated-workspace";
export function currentWorkspace(): string {
  const value = sessionStorage.getItem(KEY) || "all";
  return ["all", "annotations", "genetics"].includes(value) ? value : "all";
}
export function changeWorkspace(value: string) {
  sessionStorage.setItem(KEY, value);
  // Reload to load the selected scope's conversations and clear in-memory credentials.
  window.location.reload();
}
export function scopedFetch(input: RequestInfo | URL, init?: RequestInit) {
  const headers = new Headers(init?.headers);
  headers.set("X-Workspace-ID", currentWorkspace());
  return window.fetch(input, { ...init, headers });
}
