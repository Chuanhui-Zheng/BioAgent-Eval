export const PROVIDERS = {
  aihubmix: { label: "AIHubMix" },
  openai: { label: "OpenAI" },
  anthropic: { label: "Anthropic (Claude)" },
  gemini: { label: "Google (Gemini)" },
  custom: { label: "Custom (OpenAI-compatible URL)" },
};
export type Provider = keyof typeof PROVIDERS;
export type ModelSettings = { provider: Provider; apiKey: string; model: string; baseUrl: string };

export function selectProvider(provider: Provider): ModelSettings {
  // Never carry credentials or endpoints across providers. These settings stay in React memory.
  return { provider, apiKey: "", model: "", baseUrl: "" };
}

export function generationSettings(settings: ModelSettings) {
  const apiKey = settings.apiKey.trim();
  if (!apiKey) return {};
  const model = settings.model.trim();
  if (!model) throw new Error("Load models and choose a model ID in Model settings.");
  if (settings.provider !== "custom") return { provider: settings.provider, api_key: apiKey, model };
  const baseUrl = settings.baseUrl.trim();
  if (!baseUrl) throw new Error("Enter the provider's OpenAI-compatible base URL in Model settings.");
  return { provider: settings.provider, api_key: apiKey, model, base_url: baseUrl };
}
