import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/modelSettings.ts", import.meta.url), "utf8");
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { selectProvider, generationSettings, PROVIDERS } = await import(`data:text/javascript,${encodeURIComponent(js)}`);

test("provider switches clear credentials and all four providers are selectable", () => {
  assert.deepEqual(Object.keys(PROVIDERS), ["aihubmix", "openai", "anthropic", "gemini"]);
  for (const provider of Object.keys(PROVIDERS)) {
    assert.equal(selectProvider(provider).apiKey, "");
    assert.equal(selectProvider(provider).model, "");
    assert.deepEqual(generationSettings(selectProvider(provider)), {});
  }
});

test("hosted requests pair the selected provider, model and key; no key means offline", () => {
  assert.deepEqual(generationSettings({ provider: "gemini", apiKey: " key ", model: " model-id " }),
    { provider: "gemini", api_key: "key", model: "model-id" });
  assert.throws(() => generationSettings({ provider: "gemini", apiKey: "key", model: " " }), /model ID/);
  assert.deepEqual(generationSettings({ provider: "gemini", apiKey: " ", model: "model-id" }), {});
});
