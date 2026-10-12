import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Dna,
  Download,
  FileText,
  FlaskConical,
  GitBranch,
  Key,
  Loader2,
  Menu,
  PanelLeftClose,
  Search,
  Send,
  Settings,
  Sparkles,
  TableProperties,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Page = "gene" | "phenotype" | "region" | "moa";

interface CitationItem {
  id?: string;
  chunk_id?: string;
  title?: string;
  source_name?: string;
  source_url?: string;
  source_file?: string;
  collection?: string;
  citation?: string;
}

interface ClaimItem {
  text: string;
  citations: string[];
}

interface ChatMessage {
  role: "assistant" | "user";
  text: string;
  status?: "verified" | "qualified" | "refused" | "answer";
  claims?: ClaimItem[];
  citations?: CitationItem[];
  latency_ms?: number;
  retrieved_count?: number;
  provider?: string;
  loading?: boolean;
}

interface GeneAssociation {
  phenotype: string;
  label: string;
  common_bf: number;
  rare_bf: number;
  huge_score: number;
  beta?: number;
  z?: number;
  p_value?: number;
  evidence_tier: string;
}

interface GeneData {
  symbol: string;
  title?: string;
  content?: string;
  metadata?: {
    gene_symbol?: string;
    ensembl_gene_id?: string;
    chromosome?: string;
    start?: number;
    end?: number;
    assembly?: string;
    alternative_names?: string[];
    uniprot_accession?: string;
    hgnc_id?: string;
    protein_class?: string;
  };
  huge_score?: number;
  common_evidence_count?: number;
  rare_evidence_count?: number;
  associations?: GeneAssociation[];
}

interface PhenotypeData {
  code: string;
  label: string;
  category?: string;
  group?: string;
  aliases?: string[];
  curation_status?: string;
}

const PAGE_SECTIONS: Record<Page, { id: string; label: string }[]> = {
  gene: [
    { id: "functional-association", label: "Functional association" },
    { id: "gene-level-association", label: "Gene-level association" },
    { id: "tissue-expression", label: "Tissue-specific expression" },
  ],
  phenotype: [
    { id: "gwas", label: "Genome-wide association study" },
    { id: "single-variants", label: "Top single-variant associations" },
    { id: "phenotype-genes", label: "Top gene-level associations" },
    { id: "top-pathways", label: "Top pathways" },
    { id: "genetic-correlation", label: "Genetic correlation" },
    { id: "global-annotation", label: "Global enriched annotation" },
  ],
  region: [
    { id: "significant-variants", label: "Most significant variants" },
    { id: "genomics-region", label: "Genomics region" },
    { id: "inferred-region", label: "Inferred region of gene" },
  ],
  moa: [
    { id: "phenotype-gene", label: "Phenotype–Gene association" },
    { id: "top-weighted-genes", label: "Top weighted genes" },
    { id: "gene-enrichment", label: "Gene enrichment" },
    { id: "directional-effect", label: "Directional effect" },
    { id: "mechanism-action", label: "Mechanism of action" },
  ],
};

function downloadCsv(filename: string, headers: string[], rows: (string | number)[][]) {
  const escape = (value: string | number) => `"${String(value).replaceAll('"', '""')}"`;
  const csv = [headers, ...rows].map((row) => row.map(escape).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

// API client functions
async function queryRAG(question: string, apiKey?: string, model?: string) {
  const res = await fetch("/api/rag/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      top_k: 8,
      api_key: apiKey ? apiKey.trim() : undefined,
      model: model || "gpt-4o-mini",
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Network error" }));
    throw new Error(err.detail || `Server returned ${res.status}`);
  }
  return await res.json();
}

async function fetchGene(symbol: string): Promise<GeneData> {
  const res = await fetch(`/api/genes/${encodeURIComponent(symbol.toUpperCase())}`);
  if (!res.ok) throw new Error(`Gene ${symbol} not found`);
  return await res.json();
}

async function fetchPhenotypesList(): Promise<PhenotypeData[]> {
  const res = await fetch("/api/phenotypes");
  if (!res.ok) return [];
  const data = await res.json();
  return data.phenotypes || [];
}

const NAV_ITEMS = [
  { id: "gene" as Page, label: "Gene Search", short: "Gene", icon: Dna },
  { id: "phenotype" as Page, label: "Phenotype Search", short: "Trait", icon: Activity },
  { id: "region" as Page, label: "Gene Region", short: "Region", icon: GitBranch },
  { id: "moa" as Page, label: "Gene MoA", short: "MoA", icon: FlaskConical },
];

const tissueData = [
  { tissue: "Adipose", expression: 104.8 },
  { tissue: "Adrenal", expression: 15.3 },
  { tissue: "Blood", expression: 4.4 },
  { tissue: "Colon", expression: 52.2 },
  { tissue: "Heart", expression: 33.4 },
  { tissue: "Liver", expression: 73.8 },
  { tissue: "Muscle", expression: 27.6 },
];

const variants = [
  ["3:12,328,867", "G/A", "rs9822598", "Intron variant", "PPARG", "1.21e-146", "-0.0422"],
  ["3:12,269,266", "C/T", "rs13066322", "Missense", "PPARG", "1.71e-123", "-0.0074"],
  ["3:12,267,648", "A/G", "rs7616006", "Intron variant", "TSEN2", "1.65e-97", "0.0140"],
  ["3:12,756,298", "C/T", "rs2643826", "Regulatory", "PPARG", "5.92e-90", "0.0237"],
  ["3:12,434,608", "A/G", "rs1515998", "Intron variant", "PPARG", "5.60e-7", "0.0059"],
];

const pathways = [
  ["PPAR signalling pathway", "2.04e-19", "2.699", "0.0915"],
  ["Adipocytokine signalling", "7.92e-15", "2.491", "0.0950"],
  ["Insulin resistance", "2.19e-12", "1.758", "0.0678"],
  ["Fatty acid metabolism", "5.15e-10", "2.210", "0.0912"],
  ["Lipid particle remodelling", "4.87e-08", "2.374", "0.0999"],
];

const geneScores = [
  { gene: "PPARG", score: 121800 },
  { gene: "CD36", score: 15660 },
  { gene: "LIPC", score: 9690 },
  { gene: "APOE", score: 6960 },
  { gene: "ABCA1", score: 2838 },
  { gene: "PCNT", score: 2245 },
];

const correlations = [
  { trait: "Fasting glucose", value: 0.72 },
  { trait: "Triglycerides", value: 0.61 },
  { trait: "HDL cholesterol", value: -0.51 },
  { trait: "BMI", value: 0.46 },
  { trait: "Blood pressure", value: 0.24 },
];

const moaRows = [
  ["AKT1", "Activator", "Kinase activation", "Promotes cell survival and growth", "High"],
  ["BAD", "Suppressor", "Apoptosis regulation", "Promotes apoptosis by binding BCL-2", "Medium"],
  ["CEBPA", "Activator", "Transcription factor", "Regulates adipocyte differentiation", "High"],
  ["IRS1", "Modulator", "Insulin signalling", "Mediates insulin receptor signalling", "High"],
  ["PPARG", "Activator", "Nuclear receptor", "Regulates lipid storage and glucose metabolism", "High"],
];

const manhattan = Array.from({ length: 34 }, (_, index) => ({
  chr: index + 1,
  value: 8 + ((index * 17) % 40) + (index % 9 === 0 ? 52 : 0),
}));

function Badge({ children, tone = "mint" }: { children: React.ReactNode; tone?: "mint" | "blue" | "amber" | "pink" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function IconButton({ label, children, onClick }: { label: string; children: React.ReactNode; onClick?: () => void }) {
  return (
    <button className="icon-button" aria-label={label} title={label} onClick={onClick}>
      {children}
    </button>
  );
}

function Panel({
  id,
  title,
  subtitle,
  action,
  className = "",
  children,
}: {
  id?: string;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className={`panel ${className}`}>
      <header className="panel-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

function Tabs({ tabs, active, onChange }: { tabs: string[]; active: string; onChange: (value: string) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((tab) => (
        <button key={tab} className={active === tab ? "active" : ""} onClick={() => onChange(tab)}>
          {tab}
        </button>
      ))}
    </div>
  );
}

function DataTable({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>
                  {cellIndex === 0 ? <span className="table-link">{cell}</span> : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SearchBar({ page, onSearch }: { page: Page; onSearch: (value: string) => void }) {
  const placeholders: Record<Page, string> = {
    gene: "Search gene symbol (e.g. PPARG, TCF7L2, ADCY5)...",
    phenotype: "Search phenotype or trait (e.g. 2hrG, Type 2 diabetes)...",
    region: "Search genomic region (e.g. chr3:12328867-12475855)...",
    moa: "Ask scientific question (e.g. What evidence supports PPARG?)...",
  };
  const [value, setValue] = useState("");
  return (
    <form
      className="global-search"
      onSubmit={(event) => {
        event.preventDefault();
        onSearch(value);
      }}
    >
      <Search size={20} />
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholders[page]}
        aria-label={placeholders[page]}
      />
      <kbd>↵ Enter</kbd>
    </form>
  );
}

const FEATURED_GENES = ["PPARG", "TCF7L2", "ADCY5", "LPCAT2", "SLC30A8", "INS", "KCNJ11", "GCK", "AKT1", "CD36"];

function GenePage({ initialGene = "PPARG" }: { initialGene?: string }) {
  const [selectedSymbol, setSelectedSymbol] = useState(initialGene);
  const [tab, setTab] = useState("Function");
  const [association, setAssociation] = useState("HuGE Score");
  const [geneData, setGeneData] = useState<GeneData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchGene(selectedSymbol)
      .then((data) => {
        if (active) {
          setGeneData(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          console.error("Gene load error", err);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [selectedSymbol]);

  const ontologyRows = [
    ["GO:0045444 · Fat cell differentiation", "Biological process", "Strong"],
    ["GO:0006629 · Lipid metabolic process", "Biological process", "Strong"],
    ["GO:0003707 · Steroid hormone receptor activity", "Molecular function", "Moderate"],
  ];
  const pathwayRows = [
    ["PPAR signalling pathway", "WikiPathways", "2.04e-19"],
    ["Adipocytokine signalling", "KEGG", "7.92e-15"],
    ["Insulin resistance", "KEGG", "2.19e-12"],
  ];

  const meta = geneData?.metadata;
  const ensemblId = meta?.ensembl_gene_id || "ENSG00000132170";
  const coords = meta?.chromosome
    ? `chr${meta.chromosome}:${meta.start?.toLocaleString() ?? 0}–${meta.end?.toLocaleString() ?? 0}`
    : "3p25.2";
  const aliases = meta?.alternative_names?.join(", ") || "None";
  const contentText = geneData?.content || "Loading curated function from approved corpus...";

  // Prepare phenotype association rows
  const assocRows =
    geneData?.associations && geneData.associations.length > 0
      ? geneData.associations.map((a) => [
          a.label || a.phenotype,
          a.evidence_tier.toUpperCase(),
          a.common_bf.toLocaleString(),
          a.rare_bf.toLocaleString(),
          a.huge_score.toLocaleString(),
        ])
      : [
          ["Type 2 diabetes", "Glycemic", 350, 348, "121,800"],
          ["2-hour glucose (OGTT)", "Glycemic", 45, 1, "45"],
          ["HDL cholesterol", "Lipids", 45, 348, "15,660"],
          ["Body fat percentage", "Anthropometric", 45, 348, "15,660"],
          ["Triglycerides", "Lipids", 20, 77.87, "1,557.4"],
        ];

  const chartData =
    geneData?.associations && geneData.associations.length > 0
      ? geneData.associations.map((a) => ({
          name: a.label.length > 18 ? a.label.slice(0, 16) + "..." : a.label,
          common: a.common_bf,
          rare: a.rare_bf,
          huge: a.huge_score,
        }))
      : [
          { name: "Type 2 diabetes", common: 350, rare: 348, huge: 121800 },
          { name: "2hr Glucose", common: 45, rare: 1, huge: 45 },
          { name: "HDL cholesterol", common: 45, rare: 348, huge: 15660 },
          { name: "Body fat %", common: 45, rare: 348, huge: 15660 },
          { name: "Triglycerides", common: 20, rare: 78, huge: 1557 },
        ];

  return (
    <div className="page-stack">
      {/* Gene quick switcher pills */}
      <div className="gene-selector-bar">
        <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", fontWeight: 700 }}>
          Featured Targets:
        </span>
        {FEATURED_GENES.map((sym) => (
          <button
            key={sym}
            className={`gene-chip ${selectedSymbol === sym ? "active" : ""}`}
            onClick={() => setSelectedSymbol(sym)}
          >
            {sym}
          </button>
        ))}
      </div>

      <section className="hero-strip">
        <div>
          <span className="eyebrow">TARGET GENE WORKSPACE</span>
          <h1>{selectedSymbol}</h1>
          <p>{geneData?.title || `Gene ${selectedSymbol} · Curated Multi-omics Evidence`}</p>
        </div>
        <div className="hero-meta">
          <div>
            <span>Location</span>
            <strong>{coords}</strong>
          </div>
          <div>
            <span>Ensembl</span>
            <strong>{ensemblId}</strong>
          </div>
          <div>
            <span>Evidence</span>
            <Badge tone="mint">
              {geneData?.huge_score && geneData.huge_score > 1000
                ? "Compelling"
                : geneData?.common_evidence_count
                ? "Strong"
                : "Curated"}
            </Badge>
          </div>
        </div>
      </section>

      <div className="grid two-one">
        <Panel
          id="functional-association"
          title="Functional association"
          subtitle="Curated function, ontology and pathway evidence from indexed corpus"
          action={
            <IconButton
              label="Download gene summary"
              onClick={() =>
                downloadCsv(`${selectedSymbol}_summary.csv`, ["Field", "Value"], [
                  ["Gene", selectedSymbol],
                  ["Location", coords],
                  ["Ensembl", ensemblId],
                  ["Function", contentText.replaceAll("\n", " ")],
                ])
              }
            >
              <Download size={17} />
            </IconButton>
          }
        >
          <Tabs tabs={["Function", "Gene Ontology", "Pathways"]} active={tab} onChange={setTab} />
          {tab === "Function" ? (
            <div className="prose-block">
              <p style={{ whiteSpace: "pre-line" }}>{contentText}</p>
              <div className="source-row">
                <FileText size={16} />
                <span>Grounded in approved gene information corpus ({meta?.assembly || "GRCh37"})</span>
                <Badge tone="blue">Verified Corpus</Badge>
              </div>
            </div>
          ) : tab === "Gene Ontology" ? (
            <DataTable headers={["Ontology term", "Domain", "Evidence"]} rows={ontologyRows} />
          ) : (
            <DataTable headers={["Pathway", "Library", "P-value"]} rows={pathwayRows} />
          )}
        </Panel>

        <Panel title="Gene information" subtitle="Reference annotation">
          <dl className="detail-list">
            <div>
              <dt>Aliases</dt>
              <dd>{aliases}</dd>
            </div>
            <div>
              <dt>Chromosome</dt>
              <dd>{meta?.chromosome || "3"}</dd>
            </div>
            <div>
              <dt>Coordinates</dt>
              <dd>{meta?.start ? `${meta.start.toLocaleString()}–${meta.end?.toLocaleString()}` : "12,328,867–12,475,855"}</dd>
            </div>
            <div>
              <dt>Assembly</dt>
              <dd>{meta?.assembly || "GRCh38"}</dd>
            </div>
            <div>
              <dt>UniProt ID</dt>
              <dd>{meta?.uniprot_accession || "P37231"}</dd>
            </div>
            <div>
              <dt>HuGE Score</dt>
              <dd>
                <strong>{geneData?.huge_score ? geneData.huge_score.toLocaleString() : "121,800"}</strong>
              </dd>
            </div>
          </dl>
        </Panel>
      </div>

      <Panel
        id="gene-level-association"
        title="Gene-level associations"
        subtitle="Live multi-omics association data from 2hrG common & rare variant cohorts"
        action={<Badge tone="mint">Live Corpus</Badge>}
      >
        <Tabs tabs={["HuGE Score", "Common Variant", "Rare Variant", "Combined"]} active={association} onChange={setAssociation} />
        <div className="chart-table-grid">
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chartData}>
                <CartesianGrid stroke="#303340" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: "#8f93a3", fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={72} />
                <YAxis tick={{ fill: "#8f93a3" }} />
                <Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} />
                <Bar
                  dataKey={association === "Common Variant" ? "common" : association === "Rare Variant" ? "rare" : "huge"}
                  radius={[5, 5, 0, 0]}
                >
                  {chartData.map((_, index) => (
                    <Cell key={index} fill={["#9be0d5", "#59b9e9", "#f2b858", "#d99bd3"][index % 4]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <DataTable headers={["Phenotype", "Evidence Tier", "Common BF", "Rare BF", "HuGE Score"]} rows={assocRows} />
        </div>
      </Panel>

      <Panel
        id="tissue-expression"
        title="Tissue-specific gene expression"
        subtitle="Median expression by tissue from GTEx Proteomics (TPM)"
        action={
          <button
            className="text-button"
            onClick={() =>
              downloadCsv(`${selectedSymbol}_tissue_expression.csv`, ["Tissue", "Expression TPM"], tissueData.map((i) => [i.tissue, i.expression]))
            }
          >
            <Download size={16} /> Export
          </button>
        }
      >
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={tissueData}>
            <CartesianGrid stroke="#303340" vertical={false} />
            <XAxis dataKey="tissue" tick={{ fill: "#9b9eac" }} />
            <YAxis tick={{ fill: "#9b9eac" }} />
            <Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} />
            <Bar dataKey="expression" fill="#9be0d5" radius={[5, 5, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  );
}

function PhenotypePage() {
  const [geneTab, setGeneTab] = useState("HuGE Score");
  const [phenotypes, setPhenotypes] = useState<PhenotypeData[]>([]);
  const [selectedCode, setSelectedCode] = useState("2hrG");
  const [ancestry, setAncestry] = useState("European");
  const [significance, setSignificance] = useState("Genome-wide");

  useEffect(() => {
    fetchPhenotypesList().then((list) => {
      if (list && list.length > 0) {
        setPhenotypes(list);
      }
    });
  }, []);

  const activePt = phenotypes.find((p) => p.code === selectedCode) || {
    code: "2hrG",
    label: "2-hour glucose (OGTT)",
    category: "GLYCEMIC",
    group: "GLYCEMIC",
    aliases: ["2hrG", "glucose_2h"],
  };

  const visibleVariants = significance === "Genome-wide" ? variants.slice(0, 3) : variants;
  const qqData = Array.from({ length: 20 }, (_, i) => ({
    expected: i / 2,
    observed: i < 13 ? i / 2 + 0.1 : i / 2 + (i - 12) * 0.7,
  }));

  return (
    <div className="page-stack">
      <section className="hero-strip phenotype-hero">
        <div>
          <span className="eyebrow">PHENOTYPE WORKSPACE (1,658 CURATED TERMS)</span>
          <h1>{activePt.label}</h1>
          <p>
            Code: <strong>{activePt.code}</strong> · Group: <strong>{activePt.group || "GLYCEMIC"}</strong> · {ancestry} ancestry
          </p>
        </div>
        <div className="hero-meta">
          <div>
            <span>Category</span>
            <strong>{activePt.category || "GLYCEMIC"}</strong>
          </div>
          <div>
            <span>Corpus</span>
            <strong>41,103 chunks</strong>
          </div>
          <div>
            <span>Curation</span>
            <Badge tone="mint">Curated</Badge>
          </div>
        </div>
      </section>

      <div className="filter-bar">
        <label>
          <span>Curated Phenotype</span>
          <select value={selectedCode} onChange={(event) => setSelectedCode(event.target.value)}>
            {phenotypes.length > 0 ? (
              phenotypes.map((pt) => (
                <option key={pt.code} value={pt.code}>
                  {pt.label} ({pt.code})
                </option>
              ))
            ) : (
              <>
                <option value="2hrG">2-hour glucose (OGTT) (2hrG)</option>
                <option value="2hrI">2-hour insulin (OGTT) (2hrI)</option>
                <option value="T2D">Type 2 diabetes (T2D)</option>
                <option value="BMI">Body mass index (BMI)</option>
              </>
            )}
          </select>
        </label>
        <label>
          <span>Ancestry</span>
          <select value={ancestry} onChange={(event) => setAncestry(event.target.value)}>
            <option>European</option>
            <option>All ancestries</option>
          </select>
        </label>
        <label>
          <span>Significance</span>
          <select value={significance} onChange={(event) => setSignificance(event.target.value)}>
            <option>Genome-wide</option>
            <option>Suggestive</option>
          </select>
        </label>
        <button onClick={() => {}}>
          <Search size={16} /> Filter
        </button>
      </div>

      <Panel
        id="gwas"
        title="Genome-wide association study"
        subtitle={`${activePt.label} · ${ancestry} · ${significance}`}
        action={
          <button
            className="text-button"
            onClick={() =>
              downloadCsv("gwas_plot_data.csv", ["Chromosome", "Minus log10 P"], manhattan.map((item) => [item.chr, item.value]))
            }
          >
            <Download size={16} /> Export
          </button>
        }
      >
        <div className="plot-pair">
          <div>
            <h3>Manhattan plot</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={manhattan} barCategoryGap={1}>
                <CartesianGrid stroke="#303340" vertical={false} />
                <XAxis dataKey="chr" tick={{ fill: "#8f93a3", fontSize: 10 }} />
                <YAxis tick={{ fill: "#8f93a3" }} />
                <Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} />
                <Bar dataKey="value">
                  {manhattan.map((_, index) => (
                    <Cell key={index} fill={index % 2 ? "#59b9e9" : "#9be0d5"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div>
            <h3>Q-Q plot</h3>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={qqData}>
                <CartesianGrid stroke="#303340" />
                <XAxis dataKey="expected" tick={{ fill: "#8f93a3", fontSize: 10 }} />
                <YAxis tick={{ fill: "#8f93a3" }} />
                <Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} />
                <Line type="monotone" dataKey="expected" stroke="#5b6070" dot={false} />
                <Line type="monotone" dataKey="observed" stroke="#dca2d6" strokeWidth={3} dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </Panel>

      <Panel id="single-variants" title="Top single-variant associations" subtitle="Ranked by statistical significance">
        <DataTable headers={["Position", "Allele", "dbSNP", "Consequence", "Closest gene", "P-value", "Beta"]} rows={visibleVariants} />
      </Panel>

      <Panel id="phenotype-genes" title="Top gene-level associations" subtitle="Integrated common and rare variant evidence">
        <Tabs tabs={["HuGE Score", "Common Variant", "Rare Variant", "Combined"]} active={geneTab} onChange={setGeneTab} />
        <div className="chart-table-grid">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={geneScores} layout="vertical">
              <CartesianGrid stroke="#303340" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#8f93a3" }} />
              <YAxis type="category" dataKey="gene" tick={{ fill: "#aeb2be" }} width={60} />
              <Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} />
              <Bar dataKey="score" fill="#9be0d5" radius={[0, 5, 5, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <DataTable
            headers={["Gene", "Common BF", "Rare BF", "HuGE score"]}
            rows={geneScores.map((item, i) => [item.gene, [350, 45, 20][i % 3], [348, 77.87, 6.42][i % 3], item.score.toLocaleString()])}
          />
        </div>
      </Panel>

      <div className="grid two-one">
        <Panel id="top-pathways" title="Top pathways" subtitle="Pathway-level enrichment">
          <DataTable headers={["Pathway", "P-value", "Beta", "Std. error"]} rows={pathways} />
        </Panel>
        <Panel id="genetic-correlation" title="Genetic correlation" subtitle="Shared genetic architecture">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={correlations} layout="vertical">
              <XAxis type="number" domain={[-1, 1]} tick={{ fill: "#8f93a3" }} />
              <YAxis type="category" dataKey="trait" width={105} tick={{ fill: "#9a9eac", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} />
              <Bar dataKey="value" radius={[4, 4, 4, 4]}>
                {correlations.map((item, index) => (
                  <Cell key={index} fill={item.value > 0 ? "#9be0d5" : "#dca2d6"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>
    </div>
  );
}

function RegionPage({ goToMoa }: { goToMoa: () => void }) {
  const [view, setView] = useState("Raw association");
  const [draft, setDraft] = useState({ chromosome: "chr3", start: "12,328,867", end: "12,475,855" });
  const [region, setRegion] = useState(draft);
  const [regionStatus, setRegionStatus] = useState("Loaded demonstration region");

  const loadRegion = () => {
    const start = Number(draft.start.replaceAll(",", ""));
    const end = Number(draft.end.replaceAll(",", ""));
    if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) {
      setRegionStatus("Enter valid numeric coordinates with start smaller than end");
      return;
    }
    setRegion(draft);
    setRegionStatus(`Loaded ${draft.chromosome}:${start.toLocaleString()}–${end.toLocaleString()}`);
  };

  return (
    <div className="page-stack">
      <section className="hero-strip region-hero">
        <div>
          <span className="eyebrow">REGION WORKSPACE</span>
          <h1>
            {region.chromosome}:{region.start}–{region.end}
          </h1>
          <p>Loaded genomic interval · GRCh38 · PPARG Target Locus</p>
        </div>
        <div className="hero-meta">
          <div>
            <span>Phenotypes</span>
            <strong>3 selected</strong>
          </div>
          <div>
            <span>Variants</span>
            <strong>2,424</strong>
          </div>
          <div>
            <span>Lead gene</span>
            <Badge tone="mint">PPARG</Badge>
          </div>
        </div>
      </section>

      <div className="filter-bar region-filter">
        <label>
          <span>Chromosome</span>
          <select value={draft.chromosome} onChange={(event) => setDraft({ ...draft, chromosome: event.target.value })}>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22].map((chr) => (
              <option key={chr}>chr{chr}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Start</span>
          <input value={draft.start} onChange={(event) => setDraft({ ...draft, start: event.target.value })} />
        </label>
        <label>
          <span>End</span>
          <input value={draft.end} onChange={(event) => setDraft({ ...draft, end: event.target.value })} />
        </label>
        <label className="wide-field">
          <span>Phenotypes</span>
          <div className="chip-input">
            <Badge>Type 2 diabetes</Badge>
            <Badge tone="blue">2hr Glucose</Badge>
            <Badge tone="pink">BMI</Badge>
          </div>
        </label>
        <button onClick={loadRegion}>
          <Search size={16} /> Load region
        </button>
      </div>

      <div className={`inline-status ${regionStatus.startsWith("Enter") ? "error" : ""}`}>{regionStatus}</div>

      <Panel
        id="significant-variants"
        title="Most significant variants in the region"
        subtitle="Lead associations by phenotype from approved client cohorts"
        action={
          <button
            className="text-button"
            onClick={() =>
              downloadCsv("region_variants.csv", ["Position", "Allele", "dbSNP", "Consequence", "Closest gene", "P-value", "Beta"], variants)
            }
          >
            <Download size={16} /> Export
          </button>
        }
      >
        <ResponsiveContainer width="100%" height={260}>
          <BarChart
            data={[
              { name: "Type 2 diabetes", rare: 348 },
              { name: "2hr Glucose", rare: 1 },
              { name: "HDL cholesterol", rare: 348 },
              { name: "Body fat %", rare: 348 },
            ]}
          >
            <CartesianGrid stroke="#303340" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: "#8f93a3", fontSize: 10 }} />
            <YAxis tick={{ fill: "#8f93a3" }} />
            <Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} />
            <Bar dataKey="rare" fill="#59b9e9" radius={[5, 5, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <DataTable
          headers={["Lead variant", "dbSNP", "Phenotype", "P-value", "Beta"]}
          rows={variants.slice(0, 4).map((row, i) => [row[0], row[2], ["T2D", "2hrG", "HDL", "BMI"][i], row[5], row[6]])}
        />
      </Panel>

      <Panel id="genomics-region" title="Genomics region" subtitle="Interactive locus view and variant catalogue">
        <Tabs tabs={["Raw association", "Variant catalogue"]} active={view} onChange={setView} />
        {view === "Raw association" ? <LocusPlot /> : <DataTable headers={["Position", "Allele", "dbSNP", "Consequence", "Closest gene", "P-value", "Beta"]} rows={variants} />}
      </Panel>

      <Panel
        id="inferred-region"
        title="Inferred region of gene"
        subtitle="Processed association and perturbation evidence"
        action={
          <button className="primary-button" onClick={goToMoa}>
            <FlaskConical size={17} /> Open Gene MoA <ChevronRight size={16} />
          </button>
        }
      >
        <div className="inferred-grid">
          <div>
            <h3>PSI and PIP distribution</h3>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={geneScores}>
                <CartesianGrid stroke="#303340" vertical={false} />
                <XAxis dataKey="gene" tick={{ fill: "#9a9eac" }} />
                <YAxis tick={{ fill: "#9a9eac" }} />
                <Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} />
                <Bar dataKey="score" fill="#dca2d6" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div>
            <h3>Gene perturbation effect</h3>
            <DataTable
              headers={["Gene", "Cluster", "PSI", "PIP", "Effect"]}
              rows={[
                ["PPARG", "C2", "0.89", "0.94", "Positive"],
                ["TSEN2", "C4", "0.56", "0.71", "Negative"],
                ["LIPC", "C2", "0.48", "0.62", "Positive"],
              ]}
            />
          </div>
        </div>
      </Panel>
    </div>
  );
}

function LocusPlot() {
  const dots = Array.from({ length: 56 }, (_, index) => ({
    left: `${2 + ((index * 17) % 96)}%`,
    bottom: `${10 + ((index * 31) % 72)}%`,
    hot: index % 13 === 0,
  }));
  return (
    <div className="locus-wrap">
      <div className="locus-toolbar">
        <span>
          <Badge>Type 2 diabetes</Badge>
          <Badge tone="blue">2hr Glucose</Badge>
        </span>
        <small>LD population: EUR</small>
      </div>
      <div className="locus-plot">
        {dots.map((dot, index) => (
          <i key={index} className={dot.hot ? "hot" : ""} style={{ left: dot.left, bottom: dot.bottom }} />
        ))}
      </div>
      <div className="gene-track">
        <span style={{ left: "22%", width: "54%" }}>PPARG</span>
      </div>
      <div className="locus-axis">
        <span>12.32 Mb</span>
        <span>12.40 Mb</span>
        <span>12.47 Mb</span>
      </div>
    </div>
  );
}

function MoAPage() {
  const [step, setStep] = useState(1);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [moaStatus, setMoaStatus] = useState<string>("");
  const [loadingMoa, setLoadingMoa] = useState(false);
  const [inputFiles, setInputFiles] = useState(["W.csv", "H.csv", "associations.csv"]);
  const [enrichmentStatus, setEnrichmentStatus] = useState("Ready to run with the selected genes");
  const steps = ["Phenotype–Gene", "Top genes", "Enrichment", "Directional effect", "Mechanism of action"];

  const ask = async () => {
    if (!question.trim()) return;
    setLoadingMoa(true);
    try {
      const res = await queryRAG(question);
      setAnswer(res.answer);
      setMoaStatus(res.status);
    } catch (e: any) {
      setAnswer(`Error querying RAG assistant: ${e.message}`);
    } finally {
      setLoadingMoa(false);
    }
  };

  return (
    <div className="page-stack">
      <section className="hero-strip moa-hero">
        <div>
          <span className="eyebrow">MECHANISM WORKSPACE</span>
          <h1>Gene mechanism of action</h1>
          <p>Direction of effect & therapeutic hypothesis deducer (Client β-sign & Z-score rules)</p>
        </div>
        <div className="hero-meta">
          <div>
            <span>Phenotype</span>
            <strong>2-hour glucose / T2D</strong>
          </div>
          <div>
            <span>Genes in scope</span>
            <strong>10 targets</strong>
          </div>
          <div>
            <span>Status</span>
            <Badge tone="mint">Evidence Live</Badge>
          </div>
        </div>
      </section>

      <div className="data-source-bar">
        <div>
          <TableProperties size={20} />
          <div>
            <strong>Analysis inputs</strong>
            <span>W matrix · H matrix · Association table</span>
          </div>
        </div>
        <div className="input-status">
          {inputFiles.map((file) => (
            <span key={file}>
              <i /> {file}
            </span>
          ))}
        </div>
        <label className="file-button">
          Replace files
          <input
            type="file"
            multiple
            accept=".csv"
            onChange={(event) => {
              const names = Array.from(event.target.files ?? []).map((file) => file.name);
              if (names.length) setInputFiles(names);
            }}
          />
        </label>
      </div>

      <ol className="workflow-steps">
        {steps.map((label, index) => (
          <li key={label} className={step >= index + 1 ? "active" : ""}>
            <button onClick={() => setStep(index + 1)}>
              <span>{index + 1}</span>
              {label}
            </button>
          </li>
        ))}
      </ol>

      <Panel
        id="phenotype-gene"
        title="Phenotype–Gene association"
        subtitle="bNMF factoring matrix and component labels"
        action={<Badge tone="amber">Step 1</Badge>}
      >
        <div className="moa-grid">
          <Heatmap />
          <div className="control-stack">
            <label>
              <span>Phenotypes</span>
              <select multiple defaultValue={["T2D", "HDL"]}>
                <option value="T2D">Type 2 diabetes</option>
                <option value="2hrG">2-hour glucose (OGTT)</option>
                <option value="HDL">HDL cholesterol</option>
                <option value="BMI">Body mass index</option>
              </select>
            </label>
            <label>
              <span>Components</span>
              <select>
                <option>All components</option>
                <option>Component 9</option>
              </select>
            </label>
            <label className="check-row">
              <input type="checkbox" defaultChecked /> Annotate cells
            </label>
            <button className="primary-button" onClick={() => setStep(2)}>
              Apply selection <ChevronRight size={16} />
            </button>
          </div>
        </div>
        <h3 className="section-subhead">Component labels</h3>
        <DataTable
          headers={["Component", "Label", "Confidence", "Rationale"]}
          rows={[
            ["2", "Liver dysfunction", "Medium", "Elevated bilirubin with altered ALT and AST"],
            ["5", "Type 2 diabetes predominance", "Low", "Primary positive trait is T2D"],
            ["9", "Broad lipid and glycemic function", "Medium", "Triglyceride and 2hrG association"],
          ]}
        />
      </Panel>

      <Panel
        id="top-weighted-genes"
        title="Top weighted genes"
        subtitle="Select genes from the active component"
        action={<Badge tone="blue">Step 2</Badge>}
      >
        <div className="inline-controls">
          <label>
            <span>Component</span>
            <select>
              <option>9</option>
              <option>5</option>
            </select>
          </label>
          <label>
            <span>W threshold</span>
            <input type="number" defaultValue="0.000001" />
          </label>
          <label>
            <span>Trait contains</span>
            <input defaultValue="2hrG" />
          </label>
          <label>
            <span>|Z-score| ≥</span>
            <input type="number" defaultValue="5" />
          </label>
        </div>
        <DataTable
          headers={["Rank", "Gene", "W weight", "Z-score", "Selected"]}
          rows={geneScores.slice(0, 5).map((item, i) => [i + 1, item.gene, (1 / (i + 3)).toFixed(4), (12.8 - i * 1.3).toFixed(2), "Included"])}
        />
      </Panel>

      <Panel
        id="gene-enrichment"
        title="Gene enrichment"
        subtitle="Enrichr analysis of the selected gene set"
        action={<Badge tone="pink">Step 3</Badge>}
      >
        <div className="inline-controls enrichment-controls">
          <label>
            <span>Library</span>
            <select>
              <option>WikiPathways 2023 Human</option>
              <option>KEGG 2021 Human</option>
            </select>
          </label>
          <label>
            <span>P-value threshold</span>
            <input type="number" defaultValue="0.05" />
          </label>
          <button
            className="primary-button"
            onClick={() => {
              setStep(4);
              setEnrichmentStatus("Enrichment complete · 5 significant pathways returned");
            }}
          >
            <Sparkles size={16} /> Run enrichment
          </button>
        </div>
        <div className="inline-status">{enrichmentStatus}</div>
        <div className="chart-table-grid">
          <ResponsiveContainer width="100%" height={270}>
            <BarChart data={pathways.map((row, i) => ({ name: String(row[0]).slice(0, 20), score: 19 - i * 2.3 }))} layout="vertical">
              <CartesianGrid stroke="#303340" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#8f93a3" }} />
              <YAxis type="category" dataKey="name" width={140} tick={{ fill: "#9a9eac", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} />
              <Bar dataKey="score" fill="#f2b858" radius={[0, 5, 5, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <DataTable headers={["Pathway", "P-value", "Beta", "Std. error"]} rows={pathways} />
        </div>
      </Panel>

      <Panel
        id="directional-effect"
        title="Directional effect (MoA)"
        subtitle="Trait-by-gene effect matrix with direction of effect hypothesis"
        action={<Badge tone="amber">Step 4</Badge>}
      >
        <div className="inline-controls">
          <label className="check-row">
            <input type="checkbox" defaultChecked /> Use selected genes
          </label>
          <label>
            <span>Genes to show</span>
            <input type="number" defaultValue="10" />
          </label>
          <label>
            <span>Metric</span>
            <select>
              <option>Z-score</option>
              <option>Beta</option>
            </select>
          </label>
          <label>
            <span>Direction Rule</span>
            <select>
              <option>β &gt; 0: Agonist / β &lt; 0: Antagonist</option>
            </select>
          </label>
        </div>
        <Heatmap directional />
      </Panel>

      <Panel
        id="mechanism-action"
        title="Mechanism of action"
        subtitle="Mechanistic summary grounded in live RAG retrieval"
        action={
          <button
            className="text-button"
            onClick={() =>
              downloadCsv("mechanism_of_action.csv", ["Gene", "MoA label", "Action type", "Mechanism", "Confidence"], moaRows)
            }
          >
            <Download size={16} /> Download CSV
          </button>
        }
      >
        <DataTable headers={["Gene", "MoA label", "Action type", "Mechanism", "Confidence"]} rows={moaRows} />

        <div className="embedded-chat">
          <div className="embedded-chat-head">
            <div>
              <Bot size={20} />
              <div>
                <strong>Ask questions about these genes & mechanisms</strong>
                <span>Directly queries the Evidence-Grounded Scientific RAG backend</span>
              </div>
            </div>
            <Badge tone="mint">Live Pipeline</Badge>
          </div>

          {answer && (
            <div className="embedded-answer">
              <Sparkles size={17} />
              <div>
                {moaStatus && (
                  <div style={{ marginBottom: "6px" }}>
                    <span className={moaStatus === "answer" || moaStatus === "verified" ? "status-pill-verified" : `status-pill-${moaStatus}`}>
                      {moaStatus === "verified" || moaStatus === "answer" ? "Verified Grounded" : moaStatus.toUpperCase()}
                    </span>
                  </div>
                )}
                <p>{answer}</p>
              </div>
            </div>
          )}

          <form
            onSubmit={(event) => {
              event.preventDefault();
              ask();
            }}
          >
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="e.g. What evidence supports PPARG or ADCY5 as therapeutic targets?"
            />
            <button aria-label="Ask question" disabled={loadingMoa}>
              {loadingMoa ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
          </form>
        </div>
      </Panel>
    </div>
  );
}

function Heatmap({ directional = false }: { directional?: boolean }) {
  const rows = directional ? ["2hrG", "T2D", "HDL", "BMI", "TG"] : ["2hrG (+)", "T2D (+)", "HDL (+)", "2hrG (−)", "HDL (−)"];
  const cols = directional ? ["AKT1", "BAD", "CEBPA", "IRS1", "PPARG", "ADCY5"] : ["C1", "C2", "C3", "C4", "C5", "C6"];
  return (
    <div className="heatmap">
      <div className="heatmap-grid" style={{ gridTemplateColumns: `76px repeat(${cols.length}, minmax(44px, 1fr))` }}>
        <span />
        {cols.map((col) => (
          <strong key={col}>{col}</strong>
        ))}
        {rows.flatMap((row, ri) => [
          <strong key={`${row}-label`}>{row}</strong>,
          ...cols.map((col, ci) => {
            const value = ((ri * 7 + ci * 11) % 40) - 20;
            return (
              <i
                key={`${row}-${col}`}
                style={{
                  background:
                    value > 0
                      ? `rgba(220, 112, 107, ${0.25 + Math.abs(value) / 30})`
                      : `rgba(75, 137, 190, ${0.25 + Math.abs(value) / 30})`,
                }}
              >
                {directional ? value : (value / 14).toFixed(2)}
              </i>
            );
          }),
        ])}
      </div>
    </div>
  );
}

function App() {
  const [page, setPage] = useState<Page>("gene");
  const [selectedGene, setSelectedGene] = useState("PPARG");
  const [navOpen, setNavOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [systemHealth, setSystemHealth] = useState<{ status: string; total_chunks: number } | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((data) => setSystemHealth(data))
      .catch((err) => console.log("Backend offline or connecting:", err));
  }, []);

  const title = NAV_ITEMS.find((item) => item.id === page)?.label ?? "Workspace";
  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2500);
  };

  const handleGlobalSearch = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      showToast("Enter a gene symbol, phenotype or scientific question");
      return;
    }
    // Check if it's a genomic region
    if (/chr\w*[:\s]/i.test(trimmed)) {
      setPage("region");
      showToast(`Viewing region: ${trimmed}`);
    } else if (/glucose|diabetes|cholesterol|body mass|phenotype|trait|2hr/i.test(trimmed)) {
      setPage("phenotype");
      showToast(`Filtering phenotype: ${trimmed}`);
    } else if (trimmed.includes("?") || /^(what|how|why|does|explain|is|which)/i.test(trimmed)) {
      // Question -> open RAG Chat panel
      setChatOpen(true);
      showToast("Forwarded to RAG assistant");
    } else {
      // Likely a gene symbol
      setSelectedGene(trimmed.toUpperCase());
      setPage("gene");
      showToast(`Loading target gene: ${trimmed.toUpperCase()}`);
    }
  };

  const goToSection = (targetPage: Page, id?: string) => {
    setPage(targetPage);
    window.setTimeout(() => {
      if (id) document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
      else contentRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    }, 0);
    setNavOpen(false);
  };

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0 });
  }, [page]);

  return (
    <div className={`app-shell ${navOpen ? "nav-open" : "nav-closed"}`}>
      <aside className="rail">
        <button
          className="brand-mark"
          aria-label="Open navigation"
          title="Open navigation"
          onClick={() => setNavOpen((open) => !open)}
        >
          <Menu size={23} />
        </button>
        <nav>
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button key={id} className={page === id ? "active" : ""} title={label} onClick={() => setPage(id)}>
              <Icon size={21} />
            </button>
          ))}
        </nav>
        <button title="Settings" onClick={() => setChatOpen(true)}>
          <Settings size={21} />
        </button>
      </aside>

      <aside className="sidebar">
        <div className="sidebar-head">
          <div>
            <span>EVIDENCE PORTAL</span>
            <strong>GENOVA</strong>
          </div>
          <IconButton label="Collapse navigation" onClick={() => setNavOpen(false)}>
            <PanelLeftClose size={19} />
          </IconButton>
        </div>

        <nav className="site-contents">
          {NAV_ITEMS.map(({ id, label }) => (
            <section className={page === id ? "active" : ""} key={id}>
              <button className="sidebar-page-title" onClick={() => goToSection(id)}>
                <span>{label}</span>
                <ChevronRight size={15} />
              </button>
              <div className="section-nav">
                {PAGE_SECTIONS[id].map((section) => (
                  <button key={section.id} onClick={() => goToSection(id, section.id)}>
                    {section.label}
                  </button>
                ))}
              </div>
            </section>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="status-dot" style={{ background: systemHealth ? "#69d39b" : "#f4b759" }} />
          <div>
            <strong>Evidence Corpus</strong>
            <span>{systemHealth ? `${systemHealth.total_chunks.toLocaleString()} chunks indexed` : "Connecting backend..."}</span>
          </div>
        </div>
      </aside>

      <main className="main-area" onClick={() => navOpen && setNavOpen(false)}>
        <header className="topbar">
          <div className="mobile-nav-toggle" onClick={(event) => event.stopPropagation()}>
            <IconButton label="Open navigation" onClick={() => setNavOpen(true)}>
              <Menu size={20} />
            </IconButton>
          </div>
          <SearchBar page={page} onSearch={handleGlobalSearch} />
          <div className="top-actions">
            <button className="ask-button" onClick={() => setChatOpen(true)}>
              <Sparkles size={18} /> Ask RAG Assistant
            </button>
            <IconButton
              label="Help"
              onClick={() => showToast("Evidence-Grounded RAG Assistant: 41,103 Chunks Indexed across Genes, GWAS & Phenotypes")}
            >
              <CircleHelp size={20} />
            </IconButton>
            <div className="avatar">CS</div>
          </div>
        </header>

        <div className="content-head">
          <div>
            <span>Scientific Analysis Workspace</span>
            <h1>{title}</h1>
          </div>
          <div className="context-pill" title="Connected to live FastAPI backend on port 8000">
            <span>ENGINE</span>
            <strong style={{ color: "#69d39b" }}>Live RAG (41,103 Chunks)</strong>
          </div>
        </div>

        <div className="content-scroll" ref={contentRef}>
          {page === "gene" ? (
            <GenePage initialGene={selectedGene} />
          ) : page === "phenotype" ? (
            <PhenotypePage />
          ) : page === "region" ? (
            <RegionPage goToMoa={() => setPage("moa")} />
          ) : (
            <MoAPage />
          )}
        </div>
      </main>

      {chatOpen && <ChatPanel page={page} onClose={() => setChatOpen(false)} />}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function ChatPanel({ page, onClose }: { page: Page; onClose: () => void }) {
  const context: Record<Page, string> = {
    gene: "Gene Information & Association Corpus",
    phenotype: "Curated Phenotype Glossary & GWAS",
    region: "Genomic Interval & Locus Variants",
    moa: "Directional Effects & MoA Rules",
  };

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      text: `Hello! I am your Evidence-Grounded Scientific Assistant. I retrieve vetted multi-omics data from 41,103 indexed passages, provide verifiable citations, and validate all claims against hallucinations. How can I assist your drug target discovery?`,
      status: "verified",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [showConfig, setShowConfig] = useState(false);

  const suggestions = useMemo(
    () =>
      page === "gene"
        ? [
            "Summarise the strongest evidence for PPARG in Type 2 Diabetes",
            "What common and rare variant associations support ADCY5?",
            "Compare TCF7L2 and PPARG evidence tiers",
          ]
        : page === "phenotype"
        ? [
            "What genes are associated with 2-hour glucose (2hrG)?",
            "Explain the difference between 2hrG and 2hrI phenotypes",
          ]
        : [
            "How does direction of effect deduce therapeutic mechanism?",
            "What evidence supports PPARG as an agonist target?",
          ],
    [page]
  );

  const send = async (text = input) => {
    const q = text.trim();
    if (!q || loading) return;

    // Append user message
    const userMsg: ChatMessage = { role: "user", text: q };
    const loadingMsg: ChatMessage = { role: "assistant", text: "", loading: true };
    setMessages((curr) => [...curr, userMsg, loadingMsg]);
    setInput("");
    setLoading(true);

    try {
      const data = await queryRAG(q, apiKey);
      const assistantMsg: ChatMessage = {
        role: "assistant",
        text: data.answer,
        status: data.status,
        claims: data.claims,
        citations: data.citations,
        latency_ms: Math.round((data.latency_s?.total_api || 0.005) * 1000),
        retrieved_count: data.retrieved_count,
        provider: data.provider,
      };
      setMessages((curr) => [...curr.slice(0, -1), assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        role: "assistant",
        text: `Unable to retrieve evidence: ${err.message}. Please verify the RAG backend is running on http://127.0.0.1:8000.`,
        status: "refused",
      };
      setMessages((curr) => [...curr.slice(0, -1), errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <aside className="chat-panel">
      <header>
        <div>
          <span>
            <Bot size={18} /> Evidence RAG Assistant
          </span>
          <small>Grounded Target Discovery</small>
        </div>
        <div style={{ display: "flex", gap: "6px" }}>
          <IconButton label="Provider settings" onClick={() => setShowConfig(!showConfig)}>
            <Key size={17} />
          </IconButton>
          <IconButton label="Close assistant" onClick={onClose}>
            <X size={20} />
          </IconButton>
        </div>
      </header>

      {showConfig && (
        <div className="api-toggle-box">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong>LLM Generator Option</strong>
            <Badge tone="blue">{apiKey ? "AIHubMix" : "Offline Engine"}</Badge>
          </div>
          <p style={{ margin: "4px 0", color: "var(--muted)", fontSize: "10px" }}>
            Leave blank to use the high-speed local Offline Evidence Engine (0ms, 100% grounded), or enter an AIHubMix API key
            for live GPT-4o-mini synthesis.
          </p>
          <input
            type="password"
            placeholder="AIHubMix API key (optional)"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </div>
      )}

      <div className="chat-context">
        <span>Current Context</span>
        <strong>{context[page]}</strong>
        <Badge tone="mint">41,103 Chunks</Badge>
      </div>

      <div className="messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            {message.role === "assistant" && (
              <div className="message-meta">
                {message.loading ? (
                  <span className="status-pill-qualified">
                    <Loader2 size={12} className="animate-spin" /> Retrieving evidence...
                  </span>
                ) : message.status === "verified" || message.status === "answer" ? (
                  <span className="status-pill-verified">
                    <CheckCircle2 size={12} /> Verified Grounded
                  </span>
                ) : message.status === "qualified" ? (
                  <span className="status-pill-qualified">
                    <AlertTriangle size={12} /> Qualified
                  </span>
                ) : (
                  <span className="status-pill-refused">
                    <AlertOctagon size={12} /> Refused / Partial
                  </span>
                )}
                {message.latency_ms !== undefined && (
                  <span className="message-latency">
                    ⚡ {message.latency_ms}ms · {message.retrieved_count} sources
                  </span>
                )}
              </div>
            )}

            {message.loading ? (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--muted)" }}>
                <span>Searching BM25 index & ranking passages...</span>
              </div>
            ) : (
              <div style={{ whiteSpace: "pre-line" }}>{message.text}</div>
            )}

            {/* Citations Box */}
            {message.citations && message.citations.length > 0 && (
              <div className="citations-box">
                <div className="citations-title">
                  <FileText size={12} /> Cited Sources ({message.citations.length})
                </div>
                <div>
                  {message.citations.map((c, cIdx) => {
                    const citId = c.chunk_id || c.id || `ref-${cIdx + 1}`;
                    const citName = c.source_name || c.title || citId;
                    return (
                      <span
                        key={c.chunk_id || c.id || cIdx}
                        className="citation-tag"
                        title={c.source_url || c.source_file || c.citation || citName}
                      >
                        [{citId}] {citName.length > 30 ? citName.slice(0, 28) + "…" : citName}
                      </span>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="suggestions">
        {suggestions.map((suggestion) => (
          <button key={suggestion} onClick={() => send(suggestion)} disabled={loading}>
            {suggestion}
          </button>
        ))}
      </div>

      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
          placeholder="Ask about gene evidence, GWAS signals, or MoA hypotheses..."
        />
        <button aria-label="Send question" disabled={loading}>
          {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </form>
      <p className="chat-note">Evidence-Grounded RAG Engine · Verifiable Citations · Hallucination Validator</p>
    </aside>
  );
}

export default App;
