export const PROVIDERS = {
  aihubmix: { label: "AIHubMix" },
  openai: { label: "OpenAI" },
  anthropic: { label: "Anthropic (Claude)" },
  gemini: { label: "Google (Gemini)" },
};
export type Provider = keyof typeof PROVIDERS;
export type ModelSettings = { provider: Provider; apiKey: string; model: string };

export function selectProvider(provider: Provider): ModelSettings {
  // Never carry credentials across providers. These settings stay in React memory.
  return { provider, apiKey: "", model: "" };
}

export function generationSettings(settings: ModelSettings) {
  const apiKey = settings.apiKey.trim();
  if (!apiKey) return {};
  const model = settings.model.trim();
  if (!model) throw new Error("Load models and choose a model ID in Model settings.");
  return { provider: settings.provider, api_key: apiKey, model };
}
