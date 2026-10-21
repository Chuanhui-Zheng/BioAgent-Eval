export type CitedClaim = { text: string; citations: string[] };

export function evidenceHighlights(claims: CitedClaim[], limit = 3): CitedClaim[] {
  return claims
    .filter((claim) => claim.text.trim() && claim.citations.length)
    .slice(0, limit)
    .map((claim) => {
      const lines = claim.text.split("\n").map((line) => line.trim()).filter(Boolean);
      const metricLine = lines.find((line) => /^(Top rna tissues|Top protein tissues|pValue=|Bayes factor)/i.test(line));
      const shortMetricLine = metricLine?.startsWith("Top ")
        ? `${metricLine.split(";").slice(0, 2).join(";")}${metricLine.split(";").length > 2 ? "; …" : ""}`
        : metricLine;
      const excerpt = shortMetricLine && shortMetricLine !== lines[0]
        ? `${lines[0]} ${shortMetricLine}`
        : claim.text.replace(/\s+/g, " ").trim();
      const cut = excerpt.length > 260 ? excerpt.lastIndexOf(" ", 260) : -1;
      return {
        text: cut > 0 ? `${excerpt.slice(0, cut)}…` : excerpt,
        citations: claim.citations,
      };
    });
}
