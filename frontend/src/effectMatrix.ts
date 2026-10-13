export type Effect = {gene: string; phenotype: string; beta?: number | null; z?: number | null; [key: string]: unknown};
export function effectMatrix(genes: string[], traits: string[], effects: Effect[], metric: "z" | "beta") {
  const lookup = new Map<string, Effect | null>();
  for (const effect of effects) {
    const key = JSON.stringify([effect.gene, effect.phenotype]);
    lookup.set(key, lookup.has(key) ? null : effect);
  }
  return traits.map(trait => genes.map(gene => {
    const effect = lookup.get(JSON.stringify([gene, trait]));
    const value = effect?.[metric];
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }));
}
