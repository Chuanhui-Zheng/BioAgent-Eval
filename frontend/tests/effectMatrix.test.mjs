import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = fs.readFileSync(new URL('../src/effectMatrix.ts', import.meta.url), 'utf8');
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS }}).outputText;
const exports = {};
new Function('exports', output)(exports);
const { effectMatrix } = exports;
test('aligns labels and preserves opposite signs and real zero', () => {
  const effects = [{gene:'B',phenotype:'T2',z:-3,beta:-.2},{gene:'A',phenotype:'T1',z:0,beta:0}];
  assert.deepEqual(effectMatrix(['A','B'],['T1','T2'],effects,'z'), [[0,null],[null,-3]]);
});
test('uses beta independently without replacing missing values with Z', () => {
  const effects = [{gene:'A',phenotype:'T',z:4,beta:.25},{gene:'B',phenotype:'T',z:9}];
  assert.deepEqual(effectMatrix(['A','B'],['T'],effects,'beta'), [[.25,null]]);
});
test('duplicate and nonfinite source cells remain unavailable', () => {
  const effects = [{gene:'A',phenotype:'T',z:4},{gene:'A',phenotype:'T',z:6},{gene:'B',phenotype:'T',z:NaN}];
  assert.deepEqual(effectMatrix(['A','B'],['T'],effects,'z'), [[null,null]]);
});
