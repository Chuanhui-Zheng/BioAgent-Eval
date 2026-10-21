import { useEffect, useState } from "react";
import { scopedFetch as fetch } from "./api";

export type LlmProvider = {
  id: string;
  label: string;
  base_url: string | null;
  default_model: string;
  requires_key: boolean;
};

/** Hosted generation settings. provider "offline" means the local evidence engine. */
export type LlmSettings = {
  provider: string;
  apiKey: string;
  model: string;
  baseUrl: string;
};

export const OFFLINE_SETTINGS: LlmSettings = { provider: "offline", apiKey: "", model: "", baseUrl: "" };

let catalogPromise: Promise<LlmProvider[]> | null = null;

function loadCatalog(): Promise<LlmProvider[]> {
  catalogPromise ??= fetch("/api/llm/providers")
    .then((res) => (res.ok ? res.json() : { providers: [] }))
    .then((body) => body.providers as LlmProvider[])
    .catch(() => []);
  return catalogPromise;
}

/** Request fields understood by /api/rag/query and /api/analysis/evaluate. */
export function llmRequestFields(settings: LlmSettings) {
  if (settings.provider === "offline") return {};
  return {
    llm_provider: settings.provider,
    api_key: settings.apiKey.trim() || undefined,
    model: settings.model.trim() || undefined,
    base_url: settings.baseUrl.trim() || undefined,
  };
}

export function llmLabel(settings: LlmSettings, providers: LlmProvider[]) {
  if (settings.provider === "offline") return "Offline Engine";
  return providers.find((p) => p.id === settings.provider)?.label ?? settings.provider;
}

export function useLlmProviders() {
  const [providers, setProviders] = useState<LlmProvider[]>([]);
  useEffect(() => {
    let active = true;
    loadCatalog().then((items) => active && setProviders(items));
    return () => {
      active = false;
    };
  }, []);
  return providers;
}

export function LlmSettingsForm({
  value,
  onChange,
  providers,
}: {
  value: LlmSettings;
  onChange: (next: LlmSettings) => void;
  providers: LlmProvider[];
}) {
  const preset = providers.find((p) => p.id === value.provider);
  return (
    <div className="llm-settings">
      <label>
        <span>Generator</span>
        <select
          value={value.provider}
          onChange={(e) => onChange({ ...value, provider: e.target.value, model: "", baseUrl: "" })}
        >
          <option value="offline">Offline engine (no API call)</option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      {value.provider !== "offline" && (
        <>
          <label>
            <span>Model</span>
            <input
              value={value.model}
              placeholder={preset?.default_model || "model name"}
              onChange={(e) => onChange({ ...value, model: e.target.value })}
            />
          </label>
          <label>
            <span>Base URL (OpenAI-compatible)</span>
            <input
              value={value.baseUrl}
              placeholder={preset?.base_url || "https://your-endpoint/v1"}
              onChange={(e) => onChange({ ...value, baseUrl: e.target.value })}
            />
          </label>
          <label>
            <span>API key{preset && !preset.requires_key ? " (optional)" : ""}</span>
            <input
              type="password"
              autoComplete="off"
              value={value.apiKey}
              placeholder="sk-..."
              onChange={(e) => onChange({ ...value, apiKey: e.target.value })}
            />
          </label>
        </>
      )}
    </div>
  );
}
