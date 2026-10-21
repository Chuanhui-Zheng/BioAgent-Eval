import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/modelSettings.ts", import.meta.url), "utf8");
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { selectProvider, generationSettings, PROVIDERS } = await import(`data:text/javascript,${encodeURIComponent(js)}`);

test("provider switches clear credentials and all five providers are selectable", () => {
  assert.deepEqual(Object.keys(PROVIDERS), ["aihubmix", "openai", "anthropic", "gemini", "custom"]);
  for (const provider of Object.keys(PROVIDERS)) {
    assert.equal(selectProvider(provider).apiKey, "");
    assert.equal(selectProvider(provider).model, "");
    assert.equal(selectProvider(provider).baseUrl, "");
    assert.deepEqual(generationSettings(selectProvider(provider)), {});
  }
});

test("hosted requests pair the selected provider, model and key; no key means offline", () => {
  assert.deepEqual(generationSettings({ provider: "gemini", apiKey: " key ", model: " model-id " }),
    { provider: "gemini", api_key: "key", model: "model-id" });
  assert.throws(() => generationSettings({ provider: "gemini", apiKey: "key", model: " " }), /model ID/);
  assert.deepEqual(generationSettings({ provider: "gemini", apiKey: " ", model: "model-id" }), {});
});

test("custom provider sends its base URL and requires one", () => {
  assert.deepEqual(generationSettings({ provider: "custom", apiKey: " k ", model: " m ", baseUrl: " https://relay.example/v1 " }),
    { provider: "custom", api_key: "k", model: "m", base_url: "https://relay.example/v1" });
  assert.throws(() => generationSettings({ provider: "custom", apiKey: "k", model: "m", baseUrl: " " }), /base URL/);
  assert.equal("base_url" in generationSettings({ provider: "openai", apiKey: "k", model: "m", baseUrl: "https://x" }), false);
});
