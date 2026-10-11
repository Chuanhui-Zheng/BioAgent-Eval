import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  Atom,
  Bot,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Dna,
  Download,
  FileText,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
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
type ChatMessage = { role: "assistant" | "user"; text: string };

const PAGE_SECTIONS: Record<Page, { id: string; label: string }[]> = {
  gene: [{ id: "functional-association", label: "Functional association" }, { id: "gene-level-association", label: "Gene-level association" }, { id: "tissue-expression", label: "Tissue-specific expression" }],
  phenotype: [{ id: "gwas", label: "Genome-wide association study" }, { id: "single-variants", label: "Top single-variant associations" }, { id: "phenotype-genes", label: "Top gene-level associations" }, { id: "top-pathways", label: "Top pathways" }, { id: "genetic-correlation", label: "Genetic correlation" }, { id: "global-annotation", label: "Global enriched annotation" }],
  region: [{ id: "significant-variants", label: "Most significant variants" }, { id: "genomics-region", label: "Genomics region" }, { id: "inferred-region", label: "Inferred region of gene" }],
  moa: [{ id: "phenotype-gene", label: "Phenotype–Gene association" }, { id: "top-weighted-genes", label: "Top weighted genes" }, { id: "gene-enrichment", label: "Gene enrichment" }, { id: "directional-effect", label: "Directional effect" }, { id: "mechanism-action", label: "Mechanism of action" }],
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

function localAssistantAnswer(question: string, page: Page) {
  const q = question.toLowerCase();
  if (q.includes("pparg")) return "PPARG is prioritised because common-variant, functional and directional-effect evidence converge on adipocyte differentiation, lipid metabolism and insulin signalling. In this demo, the supporting records are the HuGE association table, tissue-expression panel and MoA summary [Gene evidence 1–3].";
  if (q.includes("citation") || q.includes("source")) return "This prototype marks the gene-information corpus, association results and MoA table as evidence sources. Exact document titles, passages and citation IDs require the backend RAG response schema; they are not fabricated by the frontend.";
  if (q.includes("common") && q.includes("rare")) return "Common-variant evidence reflects population-level association, while rare-variant evidence captures lower-frequency effects. The HuGE view combines both evidence streams; the demo score is common BF × rare BF.";
  if (q.includes("pathway") || q.includes("enrichment")) return "The current results highlight PPAR signalling, adipocytokine signalling, insulin resistance and fatty-acid metabolism. Page 4 carries selected genes into enrichment before calculating directional effects.";
  if (q.includes("region") || q.includes("variant") || q.includes("locus")) return "The region workspace covers chr3:12,328,867–12,475,855 in the demo. It combines lead variants, a locus view, PSI/PIP distributions and gene perturbation evidence before opening Gene MoA.";
  if (q.includes("mechanism") || q.includes("moa") || q.includes("direction")) return "The MoA workflow moves from phenotype–gene components to weighted genes, pathway enrichment, directional effects and a final mechanism table. Positive and negative heatmap values indicate the inferred direction of gene effects.";
  if (q.includes("what can") || q.includes("help")) return "I can explain PPARG, common versus rare evidence, pathways, genomic-region results and the Page 4 MoA workflow. Open-ended biomedical answers and verified citations will become available after the frontend connects to the RAG API.";
  return `I cannot reliably answer that open-ended question in the local demo. This assistant is not connected to an LLM yet. On the ${page} page, try asking about PPARG, evidence sources, pathways, variants, the genomic region or mechanism of action.`;
}

const NAV_ITEMS = [
  { id: "gene" as Page, label: "Gene Search", short: "Gene", icon: Dna },
  { id: "phenotype" as Page, label: "Phenotype Search", short: "Trait", icon: Activity },
  { id: "region" as Page, label: "Gene Region", short: "Region", icon: GitBranch },
  { id: "moa" as Page, label: "Gene MoA", short: "MoA", icon: FlaskConical },
];

const phenotypes = [
  { name: "Type 2 diabetes", group: "Glycemic", common: 350, rare: 348, huge: 121800 },
  { name: "HDL cholesterol", group: "Lipids", common: 45, rare: 348, huge: 15660 },
  { name: "Body fat percentage", group: "Anthropometric", common: 45, rare: 348, huge: 15660 },
  { name: "Pulse pressure", group: "Cardiovascular", common: 350, rare: 1, huge: 350 },
  { name: "Triglycerides", group: "Lipids", common: 20, rare: 77.87, huge: 1557.4 },
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
  { gene: "PPARG", score: 121800 }, { gene: "CD36", score: 15660 },
  { gene: "LIPC", score: 9690 }, { gene: "APOE", score: 6960 },
  { gene: "ABCA1", score: 2838 }, { gene: "PCNT", score: 2245 },
];

const correlations = [
  { trait: "Fasting glucose", value: .72 }, { trait: "Triglycerides", value: .61 },
  { trait: "HDL cholesterol", value: -.51 }, { trait: "BMI", value: .46 },
  { trait: "Blood pressure", value: .24 },
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
  return <button className="icon-button" aria-label={label} title={label} onClick={onClick}>{children}</button>;
}

function Panel({ id, title, subtitle, action, className = "", children }: { id?: string; title: string; subtitle?: string; action?: React.ReactNode; className?: string; children: React.ReactNode }) {
  return (
    <section id={id} className={`panel ${className}`}>
      <header className="panel-head">
        <div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
        {action}
      </header>
      {children}
    </section>
  );
}

function Tabs({ tabs, active, onChange }: { tabs: string[]; active: string; onChange: (value: string) => void }) {
  return <div className="tabs" role="tablist">{tabs.map((tab) => <button key={tab} className={active === tab ? "active" : ""} onClick={() => onChange(tab)}>{tab}</button>)}</div>;
}

function DataTable({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  return (
    <div className="table-wrap">
      <table><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cellIndex === 0 ? <span className="table-link">{cell}</span> : cell}</td>)}</tr>)}</tbody></table>
    </div>
  );
}

function SearchBar({ page, onSearch }: { page: Page; onSearch: (value: string) => void }) {
  const placeholders: Record<Page, string> = {
    gene: "Search gene symbol or Ensembl ID...",
    phenotype: "Search a phenotype or trait...",
    region: "Search region, e.g. chr3:12328867-12475855...",
    moa: "Search genes, pathways or mechanisms...",
  };
  const [value, setValue] = useState("");
  return (
    <form className="global-search" onSubmit={(event) => { event.preventDefault(); onSearch(value); }}>
      <Search size={20} />
      <input value={value} onChange={(event) => setValue(event.target.value)} placeholder={placeholders[page]} aria-label={placeholders[page]} />
      <kbd>⌘ K</kbd>
    </form>
  );
}

function GenePage() {
  const [tab, setTab] = useState("Function");
  const [association, setAssociation] = useState("HuGE Score");
  const ontologyRows = [["GO:0045444 · Fat cell differentiation", "Biological process", "Strong"], ["GO:0006629 · Lipid metabolic process", "Biological process", "Strong"], ["GO:0003707 · Steroid hormone receptor activity", "Molecular function", "Moderate"]];
  const pathwayRows = [["PPAR signalling pathway", "WikiPathways", "2.04e-19"], ["Adipocytokine signalling", "KEGG", "7.92e-15"], ["Insulin resistance", "KEGG", "2.19e-12"]];
  return (
    <div className="page-stack">
      <section className="hero-strip">
        <div><span className="eyebrow">GENE WORKSPACE</span><h1>PPARG</h1><p>Peroxisome proliferator activated receptor gamma</p></div>
        <div className="hero-meta"><div><span>Location</span><strong>3p25.2</strong></div><div><span>Ensembl</span><strong>ENSG00000132170</strong></div><div><span>Evidence</span><Badge>Compelling</Badge></div></div>
      </section>
      <div className="grid two-one">
        <Panel id="functional-association" title="Functional association" subtitle="Curated function, ontology and pathway evidence" action={<IconButton label="Download gene summary" onClick={() => downloadCsv("PPARG_gene_summary.csv", ["Field", "Value"], [["Gene", "PPARG"], ["Location", "3p25.2"], ["Function", "Adipocyte differentiation and lipid metabolism"]])}><Download size={17} /></IconButton>}>
          <Tabs tabs={["Function", "Gene Ontology", "Pathways"]} active={tab} onChange={setTab} />
          {tab === "Function" ? <div className="prose-block"><p>PPARG is a ligand-activated nuclear receptor that regulates adipocyte differentiation, lipid storage, glucose metabolism and inflammatory responses.</p><div className="source-row"><FileText size={16} /><span>Grounded in approved gene information corpus</span><Badge tone="blue">3 sources</Badge></div></div> : tab === "Gene Ontology" ? <DataTable headers={["Ontology term", "Domain", "Evidence"]} rows={ontologyRows} /> : <DataTable headers={["Pathway", "Library", "P-value"]} rows={pathwayRows} />}
        </Panel>
        <Panel title="Gene information" subtitle="Reference annotation">
          <dl className="detail-list"><div><dt>Aliases</dt><dd>PPARG1, PPARG2, NR1C3</dd></div><div><dt>Chromosome</dt><dd>3</dd></div><div><dt>Coordinates</dt><dd>12,328,867–12,475,855</dd></div><div><dt>Assembly</dt><dd>GRCh38</dd></div><div><dt>Protein class</dt><dd>Nuclear receptor</dd></div></dl>
        </Panel>
      </div>
      <Panel id="gene-level-association" title="Gene-level associations" subtitle="Evidence across diseases and traits" action={<Badge tone="amber">Mock data</Badge>}>
        <Tabs tabs={["HuGE Score", "Common Variant", "Rare Variant", "Combined"]} active={association} onChange={setAssociation} />
        <div className="chart-table-grid">
          <div className="chart-box"><ResponsiveContainer width="100%" height={250}><BarChart data={phenotypes}><CartesianGrid stroke="#303340" vertical={false} /><XAxis dataKey="name" tick={{ fill: "#8f93a3", fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={72} /><YAxis tick={{ fill: "#8f93a3" }} /><Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} /><Bar dataKey={association === "Common Variant" ? "common" : association === "Rare Variant" ? "rare" : "huge"} radius={[5, 5, 0, 0]}>{phenotypes.map((_, index) => <Cell key={index} fill={["#9be0d5", "#59b9e9", "#f2b858", "#d99bd3"][index % 4]} />)}</Bar></BarChart></ResponsiveContainer></div>
          <DataTable headers={["Phenotype", "Group", "Common BF", "Rare BF", "HuGE"]} rows={phenotypes.map((item) => [item.name, item.group, item.common, item.rare, item.huge.toLocaleString()])} />
        </div>
      </Panel>
      <Panel id="tissue-expression" title="Tissue-specific gene expression" subtitle="Median expression by tissue (TPM)" action={<button className="text-button" onClick={() => downloadCsv("PPARG_tissue_expression.csv", ["Tissue", "Expression TPM"], tissueData.map((item) => [item.tissue, item.expression]))}><Download size={16} /> Export</button>}>
        <ResponsiveContainer width="100%" height={280}><BarChart data={tissueData}><CartesianGrid stroke="#303340" vertical={false} /><XAxis dataKey="tissue" tick={{ fill: "#9b9eac" }} /><YAxis tick={{ fill: "#9b9eac" }} /><Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} /><Bar dataKey="expression" fill="#9be0d5" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer>
      </Panel>
    </div>
  );
}

function PhenotypePage() {
  const [geneTab, setGeneTab] = useState("HuGE Score");
  const [draftPhenotype, setDraftPhenotype] = useState("Type 2 diabetes");
  const [draftAncestry, setDraftAncestry] = useState("European");
  const [draftSignificance, setDraftSignificance] = useState("Genome-wide");
  const [filters, setFilters] = useState({ phenotype: "Type 2 diabetes", ancestry: "European", significance: "Genome-wide" });
  const visibleVariants = filters.significance === "Genome-wide" ? variants.slice(0, 3) : variants;
  const traitMeta: Record<string, { group: string; samples: string; signals: string }> = { "Type 2 diabetes": { group: "Glycemic", samples: "1.42 million", signals: "560 variants" }, "HDL cholesterol": { group: "Lipids", samples: "1.18 million", signals: "472 variants" }, "Body mass index": { group: "Anthropometric", samples: "2.06 million", signals: "684 variants" } };
  const meta = traitMeta[filters.phenotype];
  const qqData = Array.from({ length: 20 }, (_, i) => ({ expected: i / 2, observed: i < 13 ? i / 2 + .1 : i / 2 + (i - 12) * .7 }));
  return (
    <div className="page-stack">
      <section className="hero-strip phenotype-hero">
        <div><span className="eyebrow">PHENOTYPE WORKSPACE</span><h1>{filters.phenotype}</h1><p>{meta.group} · Dichotomous trait · {filters.ancestry} ancestry</p></div>
        <div className="hero-meta"><div><span>Datasets</span><strong>18 cohorts</strong></div><div><span>Sample size</span><strong>{meta.samples}</strong></div><div><span>Lead signals</span><Badge tone="amber">{meta.signals}</Badge></div></div>
      </section>
      <div className="filter-bar">
        <label><span>Phenotype</span><select value={draftPhenotype} onChange={(event) => setDraftPhenotype(event.target.value)}><option>Type 2 diabetes</option><option>HDL cholesterol</option><option>Body mass index</option></select></label>
        <label><span>Ancestry</span><select value={draftAncestry} onChange={(event) => setDraftAncestry(event.target.value)}><option>European</option><option>All ancestries</option></select></label>
        <label><span>Significance</span><select value={draftSignificance} onChange={(event) => setDraftSignificance(event.target.value)}><option>Genome-wide</option><option>Suggestive</option></select></label>
        <button onClick={() => setFilters({ phenotype: draftPhenotype, ancestry: draftAncestry, significance: draftSignificance })}><Search size={16} /> Apply filters</button>
      </div>
      <Panel id="gwas" title="Genome-wide association study" subtitle={`${filters.phenotype} · ${filters.ancestry} · ${filters.significance}`} action={<button className="text-button" onClick={() => downloadCsv("gwas_plot_data.csv", ["Chromosome", "Minus log10 P"], manhattan.map((item) => [item.chr, item.value]))}><Download size={16} /> Export data</button>}>
        <div className="plot-pair">
          <div><h3>Manhattan plot</h3><ResponsiveContainer width="100%" height={260}><BarChart data={manhattan} barCategoryGap={1}><CartesianGrid stroke="#303340" vertical={false} /><XAxis dataKey="chr" tick={{ fill: "#8f93a3", fontSize: 10 }} /><YAxis tick={{ fill: "#8f93a3" }} /><Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} /><Bar dataKey="value">{manhattan.map((_, index) => <Cell key={index} fill={index % 2 ? "#59b9e9" : "#9be0d5"} />)}</Bar></BarChart></ResponsiveContainer></div>
          <div><h3>Q-Q plot</h3><ResponsiveContainer width="100%" height={260}><LineChart data={qqData}><CartesianGrid stroke="#303340" /><XAxis dataKey="expected" tick={{ fill: "#8f93a3", fontSize: 10 }} /><YAxis tick={{ fill: "#8f93a3" }} /><Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} /><Line type="monotone" dataKey="expected" stroke="#5b6070" dot={false} /><Line type="monotone" dataKey="observed" stroke="#dca2d6" strokeWidth={3} dot={{ r: 2 }} /></LineChart></ResponsiveContainer></div>
        </div>
      </Panel>
      <Panel id="single-variants" title="Top single-variant associations" subtitle="Ranked by statistical significance" action={<Badge tone="amber">Mock data</Badge>}>
        <DataTable headers={["Position", "Allele", "dbSNP", "Consequence", "Closest gene", "P-value", "Beta"]} rows={visibleVariants} />
      </Panel>
      <Panel id="phenotype-genes" title="Top gene-level associations" subtitle="Integrated common and rare variant evidence">
        <Tabs tabs={["HuGE Score", "Common Variant", "Rare Variant", "Combined"]} active={geneTab} onChange={setGeneTab} />
        <div className="chart-table-grid"><ResponsiveContainer width="100%" height={250}><BarChart data={geneScores} layout="vertical"><CartesianGrid stroke="#303340" horizontal={false} /><XAxis type="number" tick={{ fill: "#8f93a3" }} /><YAxis type="category" dataKey="gene" tick={{ fill: "#aeb2be" }} width={60} /><Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} /><Bar dataKey="score" fill="#9be0d5" radius={[0, 5, 5, 0]} /></BarChart></ResponsiveContainer><DataTable headers={["Gene", "Common BF", "Rare BF", "HuGE score"]} rows={geneScores.map((item, i) => [item.gene, [350, 45, 20][i % 3], [348, 77.87, 6.42][i % 3], item.score.toLocaleString()])} /></div>
      </Panel>
      <div className="grid two-one">
        <Panel id="top-pathways" title="Top pathways" subtitle="Pathway-level enrichment"><DataTable headers={["Pathway", "P-value", "Beta", "Std. error"]} rows={pathways} /></Panel>
        <Panel id="genetic-correlation" title="Genetic correlation" subtitle="Shared genetic architecture"><ResponsiveContainer width="100%" height={280}><BarChart data={correlations} layout="vertical"><XAxis type="number" domain={[-1, 1]} tick={{ fill: "#8f93a3" }} /><YAxis type="category" dataKey="trait" width={105} tick={{ fill: "#9a9eac", fontSize: 10 }} /><Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} /><Bar dataKey="value" radius={[4,4,4,4]}>{correlations.map((item, index) => <Cell key={index} fill={item.value > 0 ? "#9be0d5" : "#dca2d6"} />)}</Bar></BarChart></ResponsiveContainer></Panel>
      </div>
      <Panel id="global-annotation" title="Global enriched annotation" subtitle="Tissue and cell-type enrichment">
        <DataTable headers={["Tissue", "Annotation", "Ancestry", "P-value", "Fold"]} rows={[["Adipose tissue", "Enhancer", "European", "2.27e-12", "4.77"], ["Liver", "Promoter", "European", "1.35e-9", "6.69"], ["Pancreas", "Enhancer", "European", "2.24e-9", "9.80"], ["Skeletal muscle", "Binding site", "European", "6.23e-8", "3.14"]]} />
      </Panel>
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
      <section className="hero-strip region-hero"><div><span className="eyebrow">REGION WORKSPACE</span><h1>{region.chromosome}:{region.start}–{region.end}</h1><p>Loaded genomic interval · GRCh38</p></div><div className="hero-meta"><div><span>Phenotypes</span><strong>3 selected</strong></div><div><span>Variants</span><strong>2,424</strong></div><div><span>Lead gene</span><Badge>PPARG</Badge></div></div></section>
      <div className="filter-bar region-filter"><label><span>Chromosome</span><select value={draft.chromosome} onChange={(event) => setDraft({ ...draft, chromosome: event.target.value })}>{[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22].map((chr) => <option key={chr}>chr{chr}</option>)}</select></label><label><span>Start</span><input value={draft.start} onChange={(event) => setDraft({ ...draft, start: event.target.value })} /></label><label><span>End</span><input value={draft.end} onChange={(event) => setDraft({ ...draft, end: event.target.value })} /></label><label className="wide-field"><span>Phenotypes</span><div className="chip-input"><Badge>Type 2 diabetes</Badge><Badge tone="blue">HDL</Badge><Badge tone="pink">BMI</Badge></div></label><button onClick={loadRegion}><Search size={16} /> Load region</button></div>
      <div className={`inline-status ${regionStatus.startsWith("Enter") ? "error" : ""}`}>{regionStatus}</div>
      <Panel id="significant-variants" title="Most significant variants in the region" subtitle="Lead associations by phenotype" action={<button className="text-button" onClick={() => downloadCsv("region_variants.csv", ["Position", "Allele", "dbSNP", "Consequence", "Closest gene", "P-value", "Beta"], variants)}><Download size={16} /> Export</button>}>
        <ResponsiveContainer width="100%" height={260}><BarChart data={phenotypes}><CartesianGrid stroke="#303340" vertical={false} /><XAxis dataKey="name" tick={{ fill: "#8f93a3", fontSize: 10 }} /><YAxis tick={{ fill: "#8f93a3" }} /><Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} /><Bar dataKey="rare" fill="#59b9e9" radius={[5,5,0,0]} /></BarChart></ResponsiveContainer>
        <DataTable headers={["Lead variant", "dbSNP", "Phenotype", "Group", "P-value", "Beta"]} rows={variants.slice(0,4).map((row, i) => [row[0], row[2], phenotypes[i].name, phenotypes[i].group, row[5], row[6]])} />
      </Panel>
      <Panel id="genomics-region" title="Genomics region" subtitle="Interactive locus view and variant catalogue">
        <Tabs tabs={["Raw association", "Variant catalogue"]} active={view} onChange={setView} />
        {view === "Raw association" ? <LocusPlot /> : <DataTable headers={["Position", "Allele", "dbSNP", "Consequence", "Closest gene", "P-value", "Beta"]} rows={variants} />}
      </Panel>
      <Panel id="inferred-region" title="Inferred region of gene" subtitle="Processed association and perturbation evidence" action={<button className="primary-button" onClick={goToMoa}><FlaskConical size={17} /> Open Gene MoA <ChevronRight size={16} /></button>}>
        <div className="inferred-grid"><div><h3>PSI and PIP distribution</h3><ResponsiveContainer width="100%" height={230}><BarChart data={geneScores}><CartesianGrid stroke="#303340" vertical={false} /><XAxis dataKey="gene" tick={{ fill: "#9a9eac" }} /><YAxis tick={{ fill: "#9a9eac" }} /><Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} /><Bar dataKey="score" fill="#dca2d6" radius={[5,5,0,0]} /></BarChart></ResponsiveContainer></div><div><h3>Gene perturbation effect</h3><DataTable headers={["Gene", "Cluster", "PSI", "PIP", "Effect"]} rows={[["PPARG", "C2", "0.89", "0.94", "Positive"], ["TSEN2", "C4", "0.56", "0.71", "Negative"], ["LIPC", "C2", "0.48", "0.62", "Positive"]]} /></div></div>
      </Panel>
    </div>
  );
}

function LocusPlot() {
  const dots = Array.from({ length: 56 }, (_, index) => ({ left: `${2 + (index * 17) % 96}%`, bottom: `${10 + (index * 31) % 72}%`, hot: index % 13 === 0 }));
  return (
    <div className="locus-wrap">
      <div className="locus-toolbar">
        <span><Badge>Type 2 diabetes</Badge><Badge tone="blue">HDL cholesterol</Badge></span>
        <small>LD population: EUR</small>
      </div>
      <div className="locus-plot">
        {dots.map((dot, index) => <i key={index} className={dot.hot ? "hot" : ""} style={{ left: dot.left, bottom: dot.bottom }} />)}
      </div>
      <div className="gene-track"><span style={{ left: "22%", width: "54%" }}>PPARG</span></div>
      <div className="locus-axis"><span>12.32 Mb</span><span>12.40 Mb</span><span>12.47 Mb</span></div>
    </div>
  );
}

function MoAPage() {
  const [step, setStep] = useState(1);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [inputFiles, setInputFiles] = useState(["W.csv", "H.csv", "associations.csv"]);
  const [enrichmentStatus, setEnrichmentStatus] = useState("Ready to run with the selected genes");
  const steps = ["Phenotype–Gene", "Top genes", "Enrichment", "Directional effect", "Mechanism of action"];
  const ask = () => { if (question.trim()) setAnswer(localAssistantAnswer(question, "moa")); };
  return (
    <div className="page-stack">
      <section className="hero-strip moa-hero"><div><span className="eyebrow">MECHANISM WORKSPACE</span><h1>Gene mechanism of action</h1><p>From phenotype association to evidence-grounded interpretation</p></div><div className="hero-meta"><div><span>Phenotype</span><strong>Type 2 diabetes</strong></div><div><span>Genes in scope</span><strong>10</strong></div><div><span>Status</span><Badge>Analysis ready</Badge></div></div></section>
      <div className="data-source-bar"><div><TableProperties size={20} /><div><strong>Analysis inputs</strong><span>W matrix · H matrix · Association table</span></div></div><div className="input-status">{inputFiles.map((file) => <span key={file}><i /> {file}</span>)}</div><label className="file-button">Replace files<input type="file" multiple accept=".csv" onChange={(event) => { const names = Array.from(event.target.files ?? []).map((file) => file.name); if (names.length) setInputFiles(names); }} /></label></div>
      <ol className="workflow-steps">{steps.map((label, index) => <li key={label} className={step >= index + 1 ? "active" : ""}><button onClick={() => setStep(index + 1)}><span>{index + 1}</span>{label}</button></li>)}</ol>
      <Panel id="phenotype-gene" title="Phenotype–Gene association" subtitle="bNMF factoring matrix and component labels" action={<Badge tone="amber">Step 1</Badge>}>
        <div className="moa-grid"><Heatmap /><div className="control-stack"><label><span>Phenotypes</span><select multiple defaultValue={["T2D", "HDL"]}><option value="T2D">Type 2 diabetes</option><option value="HDL">HDL cholesterol</option><option value="BMI">Body mass index</option></select></label><label><span>Components</span><select><option>All components</option><option>Component 9</option></select></label><label className="check-row"><input type="checkbox" defaultChecked /> Annotate cells</label><button className="primary-button" onClick={() => setStep(2)}>Apply selection <ChevronRight size={16} /></button></div></div>
        <h3 className="section-subhead">Component labels</h3><DataTable headers={["Component", "Label", "Confidence", "Rationale"]} rows={[["2", "Liver dysfunction", "Medium", "Elevated bilirubin with altered ALT and AST"], ["5", "Type 2 diabetes predominance", "Low", "Primary positive trait is T2D"], ["9", "Broad lipid and liver function", "Medium", "Triglyceride and bilirubin association"]]} />
      </Panel>
      <Panel id="top-weighted-genes" title="Top weighted genes" subtitle="Select genes from the active component" action={<Badge tone="blue">Step 2</Badge>}>
        <div className="inline-controls"><label><span>Component</span><select><option>9</option><option>5</option></select></label><label><span>W threshold</span><input type="number" defaultValue="0.000001" /></label><label><span>Trait contains</span><input defaultValue="T2D" /></label><label><span>|Z-score| ≥</span><input type="number" defaultValue="5" /></label></div>
        <DataTable headers={["Rank", "Gene", "W weight", "Z-score", "Selected"]} rows={geneScores.slice(0,5).map((item, i) => [i + 1, item.gene, (1 / (i + 3)).toFixed(4), (12.8 - i * 1.3).toFixed(2), "Included"])} />
      </Panel>
      <Panel id="gene-enrichment" title="Gene enrichment" subtitle="Enrichr analysis of the selected gene set" action={<Badge tone="pink">Step 3</Badge>}>
        <div className="inline-controls enrichment-controls"><label><span>Library</span><select><option>WikiPathways 2023 Human</option><option>KEGG 2021 Human</option></select></label><label><span>P-value threshold</span><input type="number" defaultValue="0.05" /></label><button className="primary-button" onClick={() => { setStep(4); setEnrichmentStatus("Enrichment complete · 5 significant pathways returned"); }}><Sparkles size={16} /> Run enrichment</button></div>
        <div className="inline-status">{enrichmentStatus}</div>
        <div className="chart-table-grid"><ResponsiveContainer width="100%" height={270}><BarChart data={pathways.map((row, i) => ({ name: String(row[0]).slice(0, 20), score: 19 - i * 2.3 }))} layout="vertical"><CartesianGrid stroke="#303340" horizontal={false} /><XAxis type="number" tick={{ fill: "#8f93a3" }} /><YAxis type="category" dataKey="name" width={140} tick={{ fill: "#9a9eac", fontSize: 10 }} /><Tooltip contentStyle={{ background: "#191c27", border: "1px solid #343744" }} /><Bar dataKey="score" fill="#f2b858" radius={[0,5,5,0]} /></BarChart></ResponsiveContainer><DataTable headers={["Pathway", "P-value", "Beta", "Std. error"]} rows={pathways} /></div>
      </Panel>
      <Panel id="directional-effect" title="Directional effect" subtitle="Trait-by-gene effect matrix" action={<Badge tone="amber">Step 4</Badge>}>
        <div className="inline-controls"><label className="check-row"><input type="checkbox" defaultChecked /> Use selected genes</label><label><span>Genes to show</span><input type="number" defaultValue="10" /></label><label><span>Metric</span><select><option>Z-score</option><option>Beta</option></select></label><label><span>Combine pathways</span><select><option>Union</option><option>Intersection</option></select></label></div>
        <Heatmap directional />
      </Panel>
      <Panel id="mechanism-action" title="Mechanism of action" subtitle="Mechanistic summary grounded in selected evidence" action={<button className="text-button" onClick={() => downloadCsv("mechanism_of_action.csv", ["Gene", "MoA label", "Action type", "Mechanism", "Confidence"], moaRows)}><Download size={16} /> Download CSV</button>}>
        <DataTable headers={["Gene", "MoA label", "Action type", "Mechanism", "Confidence"]} rows={moaRows} />
        <div className="embedded-chat"><div className="embedded-chat-head"><div><Bot size={20} /><div><strong>Ask questions about these genes</strong><span>Scoped to selected genes, directional effects and MoA results</span></div></div><Badge>Evidence context ready</Badge></div>{answer && <div className="embedded-answer"><Sparkles size={17} /><p>{answer}</p></div>}<form onSubmit={(event) => { event.preventDefault(); ask(); }}><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="e.g. What evidence supports PPARG as a therapeutic target?" /><button aria-label="Ask question"><Send size={18} /></button></form></div>
      </Panel>
    </div>
  );
}

function Heatmap({ directional = false }: { directional?: boolean }) {
  const rows = directional ? ["T2D", "HDL", "BMI", "TG", "WHR"] : ["T2D (+)", "HDL (+)", "BMI (+)", "T2D (−)", "HDL (−)"];
  const cols = directional ? ["AKT1", "BAD", "CEBPA", "IRS1", "PPARG", "CD36"] : ["C1", "C2", "C3", "C4", "C5", "C6"];
  return <div className="heatmap"><div className="heatmap-grid" style={{ gridTemplateColumns: `76px repeat(${cols.length}, minmax(44px, 1fr))` }}><span />{cols.map((col) => <strong key={col}>{col}</strong>)}{rows.flatMap((row, ri) => [<strong key={`${row}-label`}>{row}</strong>, ...cols.map((col, ci) => { const value = ((ri * 7 + ci * 11) % 40) - 20; return <i key={`${row}-${col}`} style={{ background: value > 0 ? `rgba(220, 112, 107, ${.25 + Math.abs(value) / 30})` : `rgba(75, 137, 190, ${.25 + Math.abs(value) / 30})` }}>{directional ? value : (value / 14).toFixed(2)}</i>; })])}</div></div>;
}

function App() {
  const [page, setPage] = useState<Page>("gene");
  const [navOpen, setNavOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [toast, setToast] = useState("");
  const contentRef = useRef<HTMLDivElement>(null);

  const title = NAV_ITEMS.find((item) => item.id === page)?.label ?? "Workspace";
  const showToast = (message: string) => { setToast(message); window.setTimeout(() => setToast(""), 2200); };
  const handleGlobalSearch = (value: string) => {
    if (!value.trim()) { showToast("Enter a gene, phenotype or genomic region"); return; }
    if (/chr\w*[:\s]/i.test(value)) setPage("region");
    else if (/diabetes|cholesterol|body mass|phenotype|trait/i.test(value)) setPage("phenotype");
    else setPage("gene");
    showToast(`Loaded demonstration results for “${value}”`);
  };
  const goToSection = (targetPage: Page, id?: string) => {
    setPage(targetPage);
    window.setTimeout(() => {
      if (id) document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
      else contentRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    }, 0);
    setNavOpen(false);
  };
  useEffect(() => { contentRef.current?.scrollTo({ top: 0 }); }, [page]);

  return (
    <div className={`app-shell ${navOpen ? "nav-open" : "nav-closed"}`}>
      <aside className="rail">
        <button className="brand-mark" aria-label="Open navigation" title="Open navigation" onClick={() => setNavOpen((open) => !open)}><Menu size={23} /></button>
        <nav>{NAV_ITEMS.map(({ id, label, icon: Icon }) => <button key={id} className={page === id ? "active" : ""} title={label} onClick={() => setPage(id)}><Icon size={21} /></button>)}</nav>
        <button title="Settings"><Settings size={21} /></button>
      </aside>
      <aside className="sidebar">
        <div className="sidebar-head"><div><span>PAGE CONTENTS</span><strong>GENOVA</strong></div><IconButton label="Collapse navigation" onClick={() => setNavOpen(false)}><PanelLeftClose size={19} /></IconButton></div>
        <nav className="site-contents">
          {NAV_ITEMS.map(({ id, label }) => (
            <section className={page === id ? "active" : ""} key={id}>
              <button className="sidebar-page-title" onClick={() => goToSection(id)}><span>{label}</span><ChevronRight size={15} /></button>
              <div className="section-nav">
                {PAGE_SECTIONS[id].map((section) => <button key={section.id} onClick={() => goToSection(id, section.id)}>{section.label}</button>)}
              </div>
            </section>
          ))}
        </nav>
        <div className="sidebar-foot"><div className="status-dot" /><div><strong>Evidence corpus</strong><span>25,606 indexed chunks</span></div></div>
      </aside>
      <main className="main-area" onClick={() => navOpen && setNavOpen(false)}>
        <header className="topbar">
          <div className="mobile-nav-toggle" onClick={(event) => event.stopPropagation()}><IconButton label="Open navigation" onClick={() => setNavOpen(true)}><Menu size={20} /></IconButton></div>
          <SearchBar page={page} onSearch={handleGlobalSearch} />
          <div className="top-actions"><button className="ask-button" onClick={() => setChatOpen(true)}><Sparkles size={18} /> Ask assistant</button><IconButton label="Help" onClick={() => showToast("Use the left navigation to open Gene, Phenotype, Region or Gene MoA workspaces")}><CircleHelp size={20} /></IconButton><div className="avatar">CZ</div></div>
        </header>
        <div className="content-head"><div><span>Analysis workspace</span><h1>{title}</h1></div><div className="context-pill" title="The interface is using local demonstration data until the backend APIs are connected"><span>DATA MODE</span><strong>Demo data</strong></div></div>
        <div className="content-scroll" ref={contentRef}>{page === "gene" ? <GenePage /> : page === "phenotype" ? <PhenotypePage /> : page === "region" ? <RegionPage goToMoa={() => setPage("moa")} /> : <MoAPage />}</div>
      </main>
      {chatOpen && <ChatPanel page={page} onClose={() => setChatOpen(false)} />}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function ChatPanel({ page, onClose }: { page: Page; onClose: () => void }) {
  const context: Record<Page, string> = { gene: "PPARG gene evidence", phenotype: "Type 2 diabetes", region: "chr3:12.32–12.47 Mb", moa: "10 selected genes and MoA results" };
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: "assistant", text: `I can answer questions using the current ${context[page]} context and cite the supporting evidence.` }]);
  const [input, setInput] = useState("");
  const suggestions = useMemo(() => page === "gene" ? ["Summarise the strongest evidence", "How is PPARG linked to diabetes?"] : ["Explain the current results", "What evidence supports this finding?"], [page]);
  const send = (text = input) => {
    if (!text.trim()) return;
    setMessages((current) => [...current, { role: "user", text }, { role: "assistant", text: localAssistantAnswer(text, page) }]);
    setInput("");
  };
  return (
    <aside className="chat-panel">
      <header><div><span><Bot size={18} /> Evidence assistant</span><small>Context-aware RAG</small></div><IconButton label="Close assistant" onClick={onClose}><X size={20} /></IconButton></header>
      <div className="chat-context"><span>Current context</span><strong>{context[page]}</strong><Badge>Grounded</Badge></div>
      <div className="messages">{messages.map((message, index) => <div key={index} className={`message ${message.role}`}>{message.text}</div>)}</div>
      <div className="suggestions">{suggestions.map((suggestion) => <button key={suggestion} onClick={() => send(suggestion)}>{suggestion}</button>)}</div>
      <form className="chat-composer" onSubmit={(event) => { event.preventDefault(); send(); }}><textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask about these results..." /><button aria-label="Send question"><Send size={18} /></button></form>
      <p className="chat-note">Mock response · API connection pending</p>
    </aside>
  );
}

export default App;
