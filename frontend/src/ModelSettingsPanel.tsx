import { useState } from "react";
import { scopedFetch } from "./api";
import { PROVIDERS, selectProvider, type ModelSettings, type Provider } from "./modelSettings";

type Props = {
  settings: ModelSettings;
  onChange: (settings: ModelSettings) => void;
  busy: boolean;
};

export function ModelSettingsPanel({ settings, onChange, busy }: Props) {
  const [models, setModels] = useState<string[]>([]);
  const [working, setWorking] = useState(false);
  const [notice, setNotice] = useState("");
  const [failed, setFailed] = useState(false);
  function change(next: ModelSettings) {
    setNotice(""); setFailed(false);
    if (next.apiKey !== settings.apiKey || next.provider !== settings.provider) {
      setModels([]);
      next = { ...next, model: "" };
    }
    onChange(next);
  }
  async function check(action: "models" | "test") {
    setWorking(true); setNotice(""); setFailed(false);
    if (action === "models") {
      setModels([]);
      onChange({ ...settings, model: "" });
    }
    try {
      const response = await scopedFetch(`/api/llm/${action}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: settings.provider, api_key: settings.apiKey.trim(), model: settings.model.trim() || undefined }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Unable to check this provider.");
      if (action === "models") {
        setModels(result.models);
        setNotice(result.models.length ? `${result.models.length} model IDs loaded. Choose a text generation model from the list.` : "No model IDs returned. Check your provider and API key, then try again.");
      } else {
        setNotice(result.message);
      }
    } catch (cause) {
      setFailed(true); setNotice(cause instanceof Error ? cause.message : "Provider unavailable.");
    } finally { setWorking(false); }
  }
  return <fieldset className="key-panel model-panel" disabled={busy || working}>
    <legend>Model settings</legend>
    <div className="model-fields">
      <label>Provider<select aria-label="Provider" value={settings.provider} onChange={event => change(selectProvider(event.target.value as Provider))}>
        {Object.entries(PROVIDERS).map(([id, provider]) => <option key={id} value={id}>{provider.label}</option>)}
      </select></label>
      <label>Model ID<select aria-label="Model ID" value={settings.model} disabled={!models.length} onChange={event => change({ ...settings, model: event.target.value })}>
        <option value="" disabled>{models.length ? "Choose a model" : "Load models first"}</option>
        {models.map(model => <option key={model} value={model}>{model}</option>)}
      </select>
      </label>
    </div>
    <label htmlFor="api-key">{PROVIDERS[settings.provider].label} API key</label>
    <input id="api-key" type="password" autoComplete="off" spellCheck={false} value={settings.apiKey} onChange={event => change({ ...settings, apiKey: event.target.value })} placeholder="Leave empty for offline evidence excerpts" />
    <div className="model-actions">
      <button type="button" disabled={!settings.apiKey.trim()} onClick={() => void check("models")}>Load models</button>
      <button type="button" disabled={!settings.apiKey.trim() || !settings.model.trim()} onClick={() => void check("test")}>Test connection</button>
      {settings.apiKey && <button type="button" onClick={() => change({ ...settings, apiKey: "" })}>Clear key · use offline</button>}
    </div>
    <p className="model-notice" role={failed ? "alert" : "status"}>{working ? "Contacting provider…" : notice}</p>
    <small>Key held only in page memory; refresh clears it. Requests go through this app's backend to the selected provider. Questions send retrieved evidence; connection tests send a small test prompt and may incur API charges. A chat subscription is separate from API access.</small>
  </fieldset>;
}
