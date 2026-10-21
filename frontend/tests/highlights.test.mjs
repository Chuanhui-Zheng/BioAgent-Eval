import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/highlights.ts", import.meta.url), "utf8");
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { evidenceHighlights } = await import(`data:text/javascript,${encodeURIComponent(js)}`);

test("highlights preserve cited measurements and cap the overview", () => {
  const claims = [
    { text: "ADCY5 has bf_common=45 and strong evidence.", citations: ["common:ADCY5"] },
    { text: "Rare evidence p=0.9796, beta=-1.2218.", citations: ["rare:ADCY5"] },
    { text: "Gene function: cAMP signalling.", citations: ["gene:ADCY5"] },
    { text: "Fourth claim", citations: ["fourth"] },
  ];
  assert.deepEqual(evidenceHighlights(claims).map((point) => point.citations[0]),
    ["common:ADCY5", "rare:ADCY5", "gene:ADCY5"]);
  assert.match(evidenceHighlights(claims)[1].text, /beta=-1\.2218/);
});

test("long tissue claims surface the source's tissue line without adding interpretation", () => {
  const text = "GTEx Tissue Expression for PPARG:\nGene: PPARG\nTop rna tissues among 54 supplied tissues: Liver (median 12); Adipose (median 11).\nExpression does not establish a mechanism.";
  const [point] = evidenceHighlights([{ text, citations: ["gtex:PPARG"] }]);
  assert.match(point.text, /Liver \(median 12\)/);
  assert.match(point.text, /Adipose \(median 11\)/);
  assert.equal(point.text.includes("establish a mechanism"), false);
  assert.deepEqual(evidenceHighlights([{ text: "No citation", citations: [] }]), []);
});
