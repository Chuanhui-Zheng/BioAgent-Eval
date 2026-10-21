import { effectMatrix } from "./effectMatrix";
import { scopedFetch as fetch, currentWorkspace, changeWorkspace } from "./api";
import { useEffect, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Bot,
  ChevronRight,
  Download,
  FileText,
  Loader2,
  Search,
  Send,
  Sparkles,
  TableProperties,
} from "lucide-react";

type Row = Record<string, any>;

export async function api(path: string, body?: unknown): Promise<any> {
  const response = await fetch(
    "/api/analysis" + path,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const value = await response.json().catch(() => ({
    detail: `Backend returned ${response.status}; please check the server status.`,
  }));
  if (!response.ok)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : "Request rejected; check the file format and input values.",
    );
  return value;
}

function useLoad(path: string) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    setLoading(true);
    api(path)
      .then((value) => {
        if (active) setData(value);
      })
      .catch((err) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path]);
  return { data, error, loading };
}

function display(value: any): string {
  if (value == null || value === "") return "Unavailable";
  if (typeof value === "number")
    return Number.isInteger(value)
      ? value.toLocaleString()
      : value.toPrecision(5);
  return String(value);
}

function exportFile(name: string, text: string, type = "text/csv") {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([text], { type }));
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 0);
}

function exportRows(name: string, rows: Row[]) {
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  const quote = (value: any) =>
    '"' +
    String(
      typeof value === "object" && value !== null
        ? JSON.stringify(value)
        : (value ?? ""),
    ).replaceAll('"', '""') +
    '"';
  exportFile(
    name,
    [
      columns.map(quote).join(","),
      ...rows.map((row) => columns.map((key) => quote(row[key])).join(",")),
    ].join(String.fromCharCode(10)),
  );
}

function Badge({
  children,
  tone = "mint",
}: {
  children: React.ReactNode;
  tone?: "mint" | "blue" | "amber" | "pink";
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function IconButton({
  label,
  children,
  onClick,
}: {
  label: string;
  children: React.ReactNode;
  onClick?: () => void;
}) {
  return (
    <button
      className="icon-button"
      aria-label={label}
      title={label}
      onClick={onClick}
    >
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

function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: string[];
  active: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab}
          className={active === tab ? "active" : ""}
          onClick={() => onChange(tab)}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}

function DataTable({
  headers,
  rows,
  pageSize = 10,
  searchPlaceholder = "Search records...",
  maxHeight = 360,
}: {
  headers: string[];
  rows: (string | number)[][];
  pageSize?: number;
  searchPlaceholder?: string;
  maxHeight?: number;
}) {
  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);

  // Reset to first page if search term changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm]);

  const filteredRows = rows.filter((row) =>
    searchTerm.trim() === ""
      ? true
      : row.some((cell) =>
          String(cell).toLowerCase().includes(searchTerm.toLowerCase().trim()),
        ),
  );

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const currentFilteredPage = Math.min(currentPage, totalPages);
  const startIndex = (currentFilteredPage - 1) * pageSize;
  const pageRows = filteredRows.slice(startIndex, startIndex + pageSize);

  const shouldShowControls = rows.length > pageSize || searchTerm.length > 0;

  return (
    <div style={{ width: "100%", margin: "8px 0" }}>
      {shouldShowControls && (
        <div className="table-toolbar">
          <div className="table-search-input">
            <Search size={14} style={{ color: "var(--muted)" }} />
            <input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={searchPlaceholder}
            />
          </div>
          <span style={{ fontSize: "11px", color: "var(--muted)" }}>
            Showing {filteredRows.length > 0 ? startIndex + 1 : 0}-
            {Math.min(startIndex + pageSize, filteredRows.length)} of{" "}
            {filteredRows.length.toLocaleString()} items
          </span>
        </div>
      )}

      <div
        className="table-wrap table-scroll-container"
        style={{
          maxHeight: `${maxHeight}px`,
          borderTopLeftRadius: shouldShowControls ? 0 : 6,
          borderTopRightRadius: shouldShowControls ? 0 : 6,
          borderBottomLeftRadius: shouldShowControls ? 0 : 6,
          borderBottomRightRadius: shouldShowControls ? 0 : 6,
        }}
      >
        <table>
          <thead>
            <tr>
              {headers.map((header) => (
                <th key={header}>{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length > 0 ? (
              pageRows.map((row, index) => (
                <tr key={index}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>
                      {cellIndex === 0 ? (
                        <span className="table-link">{cell}</span>
                      ) : (
                        cell
                      )}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td
                  colSpan={headers.length}
                  style={{
                    textAlign: "center",
                    color: "var(--muted)",
                    padding: "24px",
                  }}
                >
                  No matching records found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {shouldShowControls && (
        <div className="table-pagination-bar">
          <span>
            Page {currentFilteredPage} of {totalPages}
          </span>
          <div className="table-pagination-controls">
            <button
              className="table-page-btn"
              disabled={currentFilteredPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </button>
            <button
              className="table-page-btn"
              disabled={currentFilteredPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Notice({ loading, error }: { loading?: boolean; error?: string }) {
  return (
    <>
      {loading && <p role="status">Loading source data...</p>}
      {error && (
        <p className="prototype-notice" role="alert">
          {error}
        </p>
      )}
    </>
  );
}

function Limits({ data }: { data: any }) {
  return (
    <>
      {data?.limitations?.length > 0 && (
        <div className="answer-limitations">
          <strong>Interpretation and coverage</strong>
          <ul>
            {data.limitations.map((item: string, i: number) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {data?.sources && (
        <details>
          <summary>Source files and checksums</summary>
          <pre className="source-json">
            {JSON.stringify(data.sources, null, 2)}
          </pre>
        </details>
      )}
    </>
  );
}

function SourcePlots({ data }: { data: any }) {
  if (!data?.total_records)
    return <p>No variant statistics match this selection.</p>;
  return (
    <>
      <p style={{ color: "var(--muted)", fontSize: "12px", marginBottom: "12px" }}>
        {data.total_records.toLocaleString()} source records ·{" "}
        {data.significant_records.toLocaleString()} pass threshold ·{" "}
        {data.manhattan.length.toLocaleString()} plotted points
      </p>
      <div className="plot-pair">
        <div>
          <h3>Manhattan plot</h3>
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart>
              <CartesianGrid stroke="#303340" />
              <XAxis
                type="number"
                dataKey="x"
                name="Position"
                tick={{ fill: "#8f93a3", fontSize: 10 }}
                tickFormatter={(v) => `${Math.round(v / 1e6)}M`}
              />
              <YAxis
                type="number"
                dataKey="minus_log10_p"
                name="-log10 P"
                tick={{ fill: "#8f93a3", fontSize: 10 }}
              />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                contentStyle={{
                  background: "#191c27",
                  border: "1px solid #343744",
                  color: "#f0f2f8",
                  borderRadius: "6px",
                }}
                itemStyle={{ color: "#f0f2f8" }}
                labelStyle={{
                  color: "#9be0d5",
                  fontWeight: 600,
                  marginBottom: "4px",
                }}
              />
              <Scatter
                data={data.manhattan}
                fill="#9be0d5"
                isAnimationActive={false}
              />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div>
          <h3>Q-Q plot</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={[...data.qq].reverse()}>
              <CartesianGrid stroke="#303340" />
              <XAxis
                type="number"
                dataKey="expected"
                name="Expected -log10 P"
                tick={{ fill: "#8f93a3", fontSize: 10 }}
              />
              <YAxis
                type="number"
                tick={{ fill: "#8f93a3", fontSize: 10 }}
              />
              <Tooltip
                contentStyle={{
                  background: "#191c27",
                  border: "1px solid #343744",
                  color: "#f0f2f8",
                  borderRadius: "6px",
                }}
                itemStyle={{ color: "#f0f2f8" }}
                labelStyle={{
                  color: "#9be0d5",
                  fontWeight: 600,
                  marginBottom: "4px",
                }}
              />
              <Line
                type="linear"
                dataKey="expected"
                stroke="#5b6070"
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="linear"
                dataKey="observed"
                stroke="#dca2d6"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div style={{ display: "flex", gap: "12px", marginTop: "12px" }}>
        <button
          className="text-button"
          onClick={() => exportRows("gwas_plot_points.csv", data.manhattan)}
        >
          <Download size={14} /> Export Manhattan points
        </button>
        <button
          className="text-button"
          onClick={() => exportRows("qq_quantiles.csv", data.qq)}
        >
          <Download size={14} /> Export QQ quantiles
        </button>
      </div>
      <Limits data={data} />
    </>
  );
}

const FEATURED_GENES = [
  "PPARG",
  "TCF7L2",
  "ADCY5",
  "LPCAT2",
  "SLC30A8",
  "INS",
  "KCNJ11",
  "GCK",
  "AKT1",
  "CD36",
];

export function GeneAnalysis({
  initialGene = "PPARG",
}: {
  initialGene?: string;
}) {
  const [selectedSymbol, setSelectedSymbol] = useState(initialGene);
  const [tab, setTab] = useState("Function");
  const [association, setAssociation] = useState("HuGE Score");
  const [kind, setKind] = useState("rna");
  const [stat, setStat] = useState("50%");
  const [comparison, setComparison] = useState("PPARG,TCF7L2");
  const [dossiers, setDossiers] = useState<any>(null);
  const [compareError, setCompareError] = useState("");
  const [details, setDetails] = useState<any>(null);
  const [geneError, setGeneError] = useState("");

  useEffect(() => {
    setSelectedSymbol(initialGene);
  }, [initialGene]);

  useEffect(() => {
    let active = true;
    setDetails(null);
    setGeneError("");
    fetch("/api/genes/" + encodeURIComponent(selectedSymbol))
      .then(async (r) => {
        if (!r.ok) throw new Error("No gene annotation found in the corpus.");
        return r.json();
      })
      .then((d) => {
        if (active) setDetails(d);
      })
      .catch((e) => {
        if (active) setGeneError(e.message);
      });
    return () => {
      active = false;
    };
  }, [selectedSymbol]);

  const expression = useLoad(
    "/expression/" + encodeURIComponent(selectedSymbol) + "?kind=" + kind,
  );
  const annotation = useLoad(
    "/annotations/" + encodeURIComponent(selectedSymbol),
  );
  const reference = useLoad(
    "/references?gene=" + encodeURIComponent(selectedSymbol),
  );

  const meta = details?.metadata;
  const ensemblId = meta?.ensembl_gene_id || "ENSG00000132170";
  const coords = meta?.chromosome
    ? `chr${meta.chromosome}:${meta.start?.toLocaleString() ?? 0}-${meta.end?.toLocaleString() ?? 0}`
    : "3p25.2";
  const aliases = Array.isArray(meta?.alternative_names)
    ? meta.alternative_names.join(", ")
    : meta?.alternative_names || "None";
  const contentText = details?.content || "Loading curated function from approved corpus...";

  const rawAssocs = details?.associations || [];
  const assocRows =
    rawAssocs.length > 0
      ? rawAssocs.map((a: any) => [
          a.label || a.phenotype,
          (a.evidence_tier || "CURATED").toUpperCase(),
          a.common_bf != null ? a.common_bf.toLocaleString() : "N/A",
          a.rare_bf != null ? a.rare_bf.toLocaleString() : "N/A",
          a.huge_score != null ? a.huge_score.toLocaleString() : "N/A",
        ])
      : [];

  const chartData =
    rawAssocs.length > 0
      ? rawAssocs.map((a: any) => ({
          name:
            (a.label || a.phenotype).length > 18
              ? (a.label || a.phenotype).slice(0, 16) + "..."
              : a.label || a.phenotype,
          common: a.common_bf ?? 0,
          rare: a.rare_bf ?? 0,
          huge: a.huge_score ?? 0,
        }))
      : [];

  const rnaChartRows =
    kind === "rna"
      ? (expression.data?.records || []).filter((r: Row) => r[stat] != null)
      : (expression.data?.records || []).filter((r: Row) => r.value != null);

  const goAnnotations = (annotation.data?.annotations || []).filter((a: any) =>
    a.library?.includes("GO"),
  );
  const pathwayAnnotations = (annotation.data?.annotations || []).filter(
    (a: any) => !a.library?.includes("GO"),
  );

  return (
    <div className="page-stack">
      <div className="gene-selector-bar">
        <span
          style={{
            fontSize: "11px",
            color: "var(--muted)",
            textTransform: "uppercase",
            fontWeight: 700,
          }}
        >
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
          <p>
            {details?.title ||
              `Gene ${selectedSymbol} · Curated Multi-omics Evidence`}
          </p>
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
              {details?.huge_score && details.huge_score > 1000
                ? "Compelling"
                : details?.common_evidence_count
                ? "Strong"
                : "Curated"}
            </Badge>
          </div>
        </div>
      </section>

      <Notice error={geneError} />

      <div className="grid two-one">
        <Panel
          id="functional-association"
          title="Functional association"
          subtitle="Curated function, ontology and pathway evidence from indexed corpus"
          action={
            <IconButton
              label="Download gene summary"
              onClick={() =>
                exportRows(`${selectedSymbol}_summary.csv`, [
                  {
                    Gene: selectedSymbol,
                    Location: coords,
                    Ensembl: ensemblId,
                    Function: contentText.replaceAll("\n", " "),
                  },
                ])
              }
            >
              <Download size={17} />
            </IconButton>
          }
        >
          <Tabs
            tabs={["Function", "Gene Ontology", "Pathways"]}
            active={tab}
            onChange={setTab}
          />
          {tab === "Function" ? (
            <div className="prose-block">
              <p style={{ whiteSpace: "pre-line" }}>{contentText}</p>
              <div className="source-row">
                <FileText size={16} />
                <span>
                  Grounded in approved gene information corpus (
                  {meta?.assembly || "GRCh37"})
                </span>
                <Badge tone="blue">Approved Corpus</Badge>
              </div>
            </div>
          ) : tab === "Gene Ontology" ? (
            <DataTable
              headers={["Ontology Term", "Library", "Source"]}
              rows={
                goAnnotations.length > 0
                  ? goAnnotations.map((a: any) => [
                      a.term,
                      a.library,
                      a.source?.source_file || "Reference",
                    ])
                  : [["No GO annotations found in reference library.", "-", "-"]]
              }
            />
          ) : (
            <DataTable
              headers={["Pathway", "Library", "Source"]}
              rows={
                pathwayAnnotations.length > 0
                  ? pathwayAnnotations.map((a: any) => [
                      a.term,
                      a.library,
                      a.source?.source_file || "Reference",
                    ])
                  : [["No pathway annotations found in reference library.", "-", "-"]]
              }
            />
          )}
          <Notice {...annotation} />
          <Limits data={annotation.data} />
        </Panel>

        <Panel title="Gene information" subtitle="Reference annotation">
          <dl className="detail-list">
            <div>
              <dt>Aliases</dt>
              <dd>{aliases}</dd>
            </div>
            <div>
              <dt>Chromosome</dt>
              <dd>{meta?.chromosome || "N/A"}</dd>
            </div>
            <div>
              <dt>Coordinates</dt>
              <dd>
                {meta?.start
                  ? `${meta.start.toLocaleString()}-${meta.end?.toLocaleString()}`
                  : coords}
              </dd>
            </div>
            <div>
              <dt>Assembly</dt>
              <dd>{meta?.assembly || "GRCh38"}</dd>
            </div>
            <div>
              <dt>UniProt ID</dt>
              <dd>{meta?.uniprot_accession || "N/A"}</dd>
            </div>
            <div>
              <dt>HuGE Score</dt>
              <dd>
                <strong>
                  {details?.huge_score
                    ? details.huge_score.toLocaleString()
                    : "N/A"}
                </strong>
              </dd>
            </div>
          </dl>
        </Panel>
      </div>

      <Panel
        id="gene-level-association"
        title="Gene-level associations"
        subtitle="Live multi-omics association data from 2hrG common & rare variant cohorts"
        action={
          <button
            className="text-button"
            onClick={() =>
              exportRows(
                `${selectedSymbol}_associations.csv`,
                rawAssocs,
              )
            }
          >
            <Download size={16} /> Export
          </button>
        }
      >
        <Tabs
          tabs={["HuGE Score", "Common Variant", "Rare Variant", "Combined"]}
          active={association}
          onChange={setAssociation}
        />
        <div className="chart-table-grid">
          <div className="chart-box">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={chartData}>
                  <CartesianGrid stroke="#303340" vertical={false} />
                  <XAxis
                    dataKey="name"
                    tick={{ fill: "#8f93a3", fontSize: 11 }}
                    interval={0}
                    angle={-20}
                    textAnchor="end"
                    height={72}
                  />
                  <YAxis tick={{ fill: "#8f93a3" }} />
                  <Tooltip
                    contentStyle={{
                      background: "#191c27",
                      border: "1px solid #343744",
                      color: "#f0f2f8",
                      borderRadius: "6px",
                    }}
                    itemStyle={{ color: "#f0f2f8" }}
                    labelStyle={{
                      color: "#9be0d5",
                      fontWeight: 600,
                      marginBottom: "4px",
                    }}
                  />
                  <Bar
                    dataKey={
                      association === "Common Variant"
                        ? "common"
                        : association === "Rare Variant"
                        ? "rare"
                        : "huge"
                    }
                    radius={[5, 5, 0, 0]}
                  >
                    {chartData.map((_: any, index: number) => (
                      <Cell
                        key={index}
                        fill={
                          ["#9be0d5", "#59b9e9", "#f2b858", "#d99bd3"][
                            index % 4
                          ]
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p style={{ color: "var(--muted)", padding: "20px" }}>
                No association charts available for {selectedSymbol}.
              </p>
            )}
          </div>
          <DataTable
            headers={[
              "Phenotype",
              "Evidence Tier",
              "Common BF",
              "Rare BF",
              "HuGE Score",
            ]}
            rows={
              assocRows.length > 0
                ? assocRows
                : [["No associated phenotypes found.", "-", "-", "-", "-"]]
            }
          />
        </div>
      </Panel>

      <Panel
        id="tissue-expression"
        title="Tissue-specific gene expression"
        subtitle={`Measured ${kind.toUpperCase()} expression by tissue (${kind === "rna" ? "GTEx RNA-seq" : "GTEx Proteomics"})`}
        action={
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              className="text-button"
              onClick={() =>
                exportRows(
                  `${selectedSymbol}_${kind}_expression.csv`,
                  expression.data?.records || [],
                )
              }
            >
              <Download size={16} /> Export
            </button>
          </div>
        }
      >
        <div
          className="inline-controls"
          style={{ marginBottom: "16px", display: "flex", gap: "12px" }}
        >
          <label>
            <span>Source</span>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="rna">RNA source summaries</option>
              <option value="protein">Protein individual observations</option>
            </select>
          </label>
          {kind === "rna" && (
            <label>
              <span>Statistic</span>
              <select value={stat} onChange={(e) => setStat(e.target.value)}>
                {["count", "mean", "std", "min", "25%", "50%", "75%", "max"].map(
                  (s) => (
                    <option key={s}>{s}</option>
                  ),
                )}
              </select>
            </label>
          )}
        </div>
        <Notice {...expression} />
        {kind === "rna" ? (
          rnaChartRows.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={rnaChartRows.slice(0, 32)} margin={{ bottom: 90 }}>
                <CartesianGrid stroke="#303340" vertical={false} />
                <XAxis
                  dataKey="tissue"
                  tick={{ fill: "#9b9eac", fontSize: 10 }}
                  interval={0}
                  angle={-45}
                  textAnchor="end"
                  height={90}
                />
                <YAxis tick={{ fill: "#9b9eac" }} />
                <Tooltip
                  contentStyle={{
                    background: "#191c27",
                    border: "1px solid #343744",
                    color: "#f0f2f8",
                    borderRadius: "6px",
                  }}
                  itemStyle={{ color: "#f0f2f8" }}
                  labelStyle={{
                    color: "#9be0d5",
                    fontWeight: 600,
                    marginBottom: "4px",
                  }}
                />
                <Bar dataKey={stat} fill="#9be0d5" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ color: "var(--muted)", padding: "20px" }}>
              No RNA expression records observed for {selectedSymbol}.
            </p>
          )
        ) : rnaChartRows.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <ScatterChart margin={{ bottom: 90 }}>
              <CartesianGrid stroke="#303340" />
              <XAxis
                type="category"
                dataKey="tissue"
                allowDuplicatedCategory={false}
                angle={-45}
                height={90}
                textAnchor="end"
                tick={{ fill: "#9b9eac", fontSize: 10 }}
              />
              <YAxis
                dataKey="value"
                type="number"
                name="Value"
                tick={{ fill: "#9b9eac" }}
              />
              <Tooltip
                contentStyle={{
                  background: "#191c27",
                  border: "1px solid #343744",
                  color: "#f0f2f8",
                  borderRadius: "6px",
                }}
                itemStyle={{ color: "#f0f2f8" }}
                labelStyle={{
                  color: "#9be0d5",
                  fontWeight: 600,
                  marginBottom: "4px",
                }}
              />
              <Scatter
                data={rnaChartRows}
                fill="#9be0d5"
                isAnimationActive={false}
              />
            </ScatterChart>
          </ResponsiveContainer>
        ) : (
          <p style={{ color: "var(--muted)", padding: "20px" }}>
            No protein expression observations found for {selectedSymbol}.
          </p>
        )}
        <Limits data={expression.data} />
      </Panel>

      <Panel
        title="SNP-to-gene reference links"
        subtitle="cS2G mappings and variant annotations"
      >
        <Notice {...reference} />
        <DataTable
          headers={["rsID", "Gene", "cS2G Score", "Source"]}
          rows={
            (reference.data?.links || []).length > 0
              ? (reference.data?.links || []).map((r: any) => [
                  r.snp,
                  r.gene,
                  display(r.score),
                  r.source,
                ])
              : [["No cS2G reference links available.", "-", "-", "-"]]
          }
        />
        <Limits data={reference.data} />
      </Panel>

      <Panel
        title="Compare targets"
        subtitle="Multi-gene evidence dossier comparison for 2hrG"
      >
        <form
          className="inline-controls"
          onSubmit={async (e) => {
            e.preventDefault();
            setCompareError("");
            setDossiers(null);
            try {
              setDossiers(
                await api("/compare", {
                  genes: comparison.split(/[\s,]+/).filter(Boolean),
                  phenotype: "2hrG",
                }),
              );
            } catch (err: any) {
              setCompareError(err.message);
            }
          }}
          style={{ display: "flex", gap: "12px", marginBottom: "16px" }}
        >
          <label style={{ flex: 1 }}>
            <span>Gene symbols</span>
            <input
              value={comparison}
              onChange={(e) => setComparison(e.target.value)}
              placeholder="e.g. PPARG, TCF7L2, ADCY5"
            />
          </label>
          <button className="primary-button" style={{ alignSelf: "flex-end" }}>
            Compare evidence
          </button>
        </form>
        <Notice error={compareError} />
        {dossiers?.genes.map((d: any) => (
          <div key={d.gene} style={{ marginBottom: "20px" }}>
            <h3 style={{ color: "var(--mint)", marginBottom: "8px" }}>
              {d.gene}
            </h3>
            <DataTable
              headers={[
                "Phenotype",
                "Common BF",
                "Rare BF",
                "HuGE Score",
                "Beta",
                "P-value",
              ]}
              rows={
                (d.associations || []).length > 0
                  ? d.associations.map((a: any) => [
                      a.phenotype,
                      display(a.common_bf),
                      display(a.rare_bf),
                      display(a.huge_score),
                      display(a.beta),
                      display(a.p_value),
                    ])
                  : [["No records", "-", "-", "-", "-", "-"]]
              }
            />
            <Limits data={d} />
          </div>
        ))}
        <Limits data={dossiers} />
        {dossiers && (
          <button
            className="text-button"
            onClick={() =>
              exportFile(
                "target_comparison.json",
                JSON.stringify(dossiers, null, 2),
                "application/json",
              )
            }
          >
            <Download size={14} /> Export dossier JSON
          </button>
        )}
      </Panel>
    </div>
  );
}

export function PhenotypeAnalysis({
  initialPhenotype = "2hrG",
}: {
  initialPhenotype?: string;
}) {
  const catalog = useLoad("/catalog");
  const glossary = useLoad("/phenotypes");
  const [code, setCode] = useState(initialPhenotype);
  const [threshold, setThreshold] = useState("1");
  const [geneTab, setGeneTab] = useState("HuGE Score");
  const [query, setQuery] = useState(
    "/gwas?phenotype=" + encodeURIComponent(initialPhenotype) + "&threshold=1",
  );

  // Searchable combobox states
  const [comboSearch, setComboSearch] = useState("2-hour glucose (OGTT) (2hrG)");
  const [isOpen, setIsOpen] = useState(false);
  const comboRef = useRef<HTMLDivElement>(null);

  const featuredPhenotypes = [
    { code: "2hrG", label: "2-hour glucose (OGTT)", records: "197k GWAS" },
    { code: "2hrFFA", label: "2-hour free fatty acids", records: "448k GWAS" },
    { code: "2hrI", label: "2-hour insulin (OGTT)", records: "LDSC Cohort" },
    { code: "T2D", label: "Type 2 diabetes", records: "Standardized" },
  ];

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (comboRef.current && !comboRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const allPhenotypesList = glossary.data?.phenotypes || [
    { code: "2hrG", label: "2-hour glucose (OGTT)" },
  ];

  const filteredPhenotypesList = allPhenotypesList.filter((item: Row) => {
    if (!comboSearch.trim()) return true;
    const term = comboSearch.toLowerCase();
    return (
      item.code.toLowerCase().includes(term) ||
      (item.label && item.label.toLowerCase().includes(term))
    );
  });

  useEffect(() => {
    setCode(initialPhenotype);
    const matched = (glossary.data?.phenotypes || []).find(
      (p: Row) => p.code === initialPhenotype,
    );
    if (matched) {
      setComboSearch(`${matched.label} (${matched.code})`);
    } else if (initialPhenotype === "2hrG") {
      setComboSearch("2-hour glucose (OGTT) (2hrG)");
    } else {
      setComboSearch(initialPhenotype);
    }
    setQuery(
      "/gwas?phenotype=" +
        encodeURIComponent(initialPhenotype) +
        "&threshold=1",
    );
  }, [initialPhenotype, glossary.data]);

  const gwas = useLoad(query);
  const evidence = useLoad("/phenotype-evidence/" + encodeURIComponent(code));

  const activeTerm =
    (glossary.data?.phenotypes || []).find((p: Row) => p.code === code) || {
      code,
      label: code === "2hrG" ? "2-hour glucose (OGTT)" : code,
      category: "GLYCEMIC",
      group: "GLYCEMIC",
    };

  const gwasList = gwas.data?.variants || [];
  const variantRows = gwasList.map((v: Row) => [
    `${v.chromosome}:${v.position}`,
    `${v.reference}/${v.alt}`,
    v.var_id,
    display(v.p_value),
    display(v.beta),
    display(v.std_err),
    display(v.n),
  ]);

  const geneEvidenceList = evidence.data?.genes || [];
  const geneRows = geneEvidenceList.map((g: Row) => [
    g.gene,
    display(g.common_bf),
    display(g.rare_bf),
    display(g.huge_score),
    display(g.p_value),
    display(g.beta),
  ]);

  const geneChartScores = geneEvidenceList.slice(0, 10).map((g: Row) => ({
    gene: g.gene,
    score:
      geneTab === "Common Variant"
        ? g.common_bf ?? 0
        : geneTab === "Rare Variant"
        ? g.rare_bf ?? 0
        : g.huge_score ?? 0,
  }));

  const correlations = (evidence.data?.correlations || []).map((c: Row) => ({
    trait: c.other_phenotype_label || c.other_phenotype || "Other",
    value: c.mixed_rg ?? 0,
  }));

  return (
    <div className="page-stack">
      <section className="hero-strip phenotype-hero">
        <div>
          <span className="eyebrow">
            PHENOTYPE WORKSPACE ({glossary.data?.phenotypes?.length ?? 1658} CURATED TERMS)
          </span>
          <h1>{activeTerm.label}</h1>
          <p>
            Code: <strong>{activeTerm.code}</strong> · Group:{" "}
            <strong>{activeTerm.group || "GLYCEMIC"}</strong> · European (EU)
            ancestry
          </p>
        </div>
        <div className="hero-meta">
          <div>
            <span>Category</span>
            <strong>{activeTerm.category || "GLYCEMIC"}</strong>
          </div>
          <div>
            <span>Available GWAS</span>
            <strong>
              {catalog.data?.gwas?.find((g: Row) => g.phenotype === code)
                ? `${catalog.data.gwas.find((g: Row) => g.phenotype === code).count.toLocaleString()} variants`
                : "No summary stats"}
            </strong>
          </div>
          <div>
            <span>Curation</span>
            <Badge tone="mint">Curated</Badge>
          </div>
        </div>
      </section>

      <Notice {...catalog} />
      <Notice {...glossary} />

      <div className="filter-bar" style={{ gridTemplateColumns: "1.8fr 1fr 1fr auto" }}>
        <div className="combobox-wrap" ref={comboRef}>
          <label>
            <span>Phenotype</span>
            <div style={{ position: "relative" }}>
              <input
                value={comboSearch}
                onChange={(e) => {
                  setComboSearch(e.target.value);
                  setIsOpen(true);
                }}
                onFocus={() => setIsOpen(true)}
                placeholder="Search code or trait (e.g. 2hrG, glucose, T2D)..."
              />
              <Search
                size={14}
                style={{
                  position: "absolute",
                  right: "12px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--muted)",
                  pointerEvents: "none",
                }}
              />
            </div>
          </label>

          {isOpen && (
            <div className="combobox-dropdown">
              {!comboSearch.trim() && (
                <>
                  <div className="combobox-group-title">
                    ⭐ Featured / Live Datasets
                  </div>
                  {featuredPhenotypes.map((item) => (
                    <div
                      key={item.code}
                      className={`combobox-item ${code === item.code ? "active" : ""}`}
                      onClick={() => {
                        setCode(item.code);
                        setComboSearch(`${item.label} (${item.code})`);
                        setIsOpen(false);
                      }}
                    >
                      <div>
                        <strong>{item.label}</strong>{" "}
                        <span style={{ color: "var(--muted)", fontSize: "10px" }}>
                          ({item.code})
                        </span>
                      </div>
                      <span className="combobox-item-badge">
                        {item.records}
                      </span>
                    </div>
                  ))}
                  <div className="combobox-group-title">
                    All Standardized Terms ({allPhenotypesList.length})
                  </div>
                </>
              )}

              {filteredPhenotypesList.slice(0, 15).map((item: Row) => (
                <div
                  key={item.code}
                  className={`combobox-item ${code === item.code ? "active" : ""}`}
                  onClick={() => {
                    setCode(item.code);
                    setComboSearch(`${item.label} (${item.code})`);
                    setIsOpen(false);
                  }}
                >
                  <div>
                    <span>{item.label}</span>{" "}
                    <span style={{ color: "var(--muted)", fontSize: "10px" }}>
                      ({item.code})
                    </span>
                  </div>
                  <span style={{ color: "var(--muted)", fontSize: "10px" }}>
                    {item.group || item.category || "CURATED"}
                  </span>
                </div>
              ))}

              {filteredPhenotypesList.length === 0 && (
                <div
                  style={{
                    padding: "16px",
                    color: "var(--muted)",
                    fontSize: "11px",
                    textAlign: "center",
                  }}
                >
                  No matching phenotypes found.
                </div>
              )}
            </div>
          )}
        </div>

        <label>
          <span>Ancestry</span>
          <select>
            <option>European (EU)</option>
          </select>
        </label>
        <label>
          <span>P-value Threshold</span>
          <select
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
          >
            <option value="1">All valid p-values</option>
            <option value="0.00001">p ≤ 1e-5</option>
            <option value="0.00000005">p ≤ 5e-8</option>
          </select>
        </label>
        <button
          onClick={() =>
            setQuery(
              `/gwas?phenotype=${encodeURIComponent(code)}&threshold=${threshold}`,
            )
          }
        >
          <Search size={16} /> Filter
        </button>
      </div>

      <Panel
        id="gwas"
        title="Genome-wide association study"
        subtitle={`${activeTerm.label} · European ancestry (EU)`}
        action={
          <button
            className="text-button"
            onClick={() =>
              exportRows(
                `${code}_gwas_variants.csv`,
                gwas.data?.variants || [],
              )
            }
          >
            <Download size={16} /> Export
          </button>
        }
      >
        <Notice {...gwas} />
        <SourcePlots data={gwas.data} />
      </Panel>

      <Panel
        id="single-variants"
        title="Top single-variant associations"
        subtitle="Ranked by statistical significance from source GWAS"
      >
        <DataTable
          headers={[
            "Position",
            "Allele",
            "Variant ID",
            "P-value",
            "Beta",
            "Std. Error",
            "N",
          ]}
          rows={
            variantRows.length > 0
              ? variantRows
              : [["No variants observed for this selection.", "-", "-", "-", "-", "-", "-"]]
          }
          pageSize={10}
          searchPlaceholder="Search by rsID, chr, allele..."
          maxHeight={340}
        />
      </Panel>

      <Panel
        id="phenotype-genes"
        title="Top gene-level associations"
        subtitle={`Integrated common and rare variant evidence for ${code}`}
      >
        <Tabs
          tabs={["HuGE Score", "Common Variant", "Rare Variant", "Combined"]}
          active={geneTab}
          onChange={setGeneTab}
        />
        <Notice {...evidence} />
        <div className="chart-table-grid">
          {geneChartScores.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={geneChartScores} layout="vertical">
                <CartesianGrid stroke="#303340" horizontal={false} />
                <XAxis type="number" tick={{ fill: "#8f93a3" }} />
                <YAxis
                  type="category"
                  dataKey="gene"
                  tick={{ fill: "#aeb2be" }}
                  width={60}
                />
                <Tooltip
                  contentStyle={{
                    background: "#191c27",
                    border: "1px solid #343744",
                    color: "#f0f2f8",
                    borderRadius: "6px",
                  }}
                  itemStyle={{ color: "#f0f2f8" }}
                  labelStyle={{
                    color: "#9be0d5",
                    fontWeight: 600,
                    marginBottom: "4px",
                  }}
                />
                <Bar dataKey="score" fill="#9be0d5" radius={[0, 5, 5, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ color: "var(--muted)", padding: "20px" }}>
              No gene-level scores found for {code}.
            </p>
          )}
          <DataTable
            headers={[
              "Gene",
              "Common BF",
              "Rare BF",
              "HuGE Score",
              "Rare P-value",
              "Beta",
            ]}
            rows={
              geneRows.length > 0
                ? geneRows
                : [["No associated genes found.", "-", "-", "-", "-", "-"]]
            }
            pageSize={8}
            searchPlaceholder="Filter gene symbol..."
            maxHeight={260}
          />
        </div>
        <Limits data={evidence.data} />
      </Panel>

      <div className="grid two-one">
        <Panel
          id="genetic-correlation"
          title="Genetic correlation"
          subtitle="Shared genetic architecture across anchor traits"
        >
          {correlations.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={correlations} layout="vertical">
                <XAxis
                  type="number"
                  domain={[-1, 1]}
                  tick={{ fill: "#8f93a3" }}
                />
                <YAxis
                  type="category"
                  dataKey="trait"
                  width={110}
                  tick={{ fill: "#9a9eac", fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={{
                    background: "#191c27",
                    border: "1px solid #343744",
                    color: "#f0f2f8",
                    borderRadius: "6px",
                  }}
                  itemStyle={{ color: "#f0f2f8" }}
                  labelStyle={{
                    color: "#9be0d5",
                    fontWeight: 600,
                    marginBottom: "4px",
                  }}
                />
                <Bar dataKey="value" radius={[4, 4, 4, 4]}>
                  {correlations.map((item: any, index: number) => (
                    <Cell
                      key={index}
                      fill={item.value > 0 ? "#9be0d5" : "#dca2d6"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ color: "var(--muted)", padding: "20px" }}>
              No LDSC genetic correlation records for {code}.
            </p>
          )}
        </Panel>

        <Panel
          id="global-annotation"
          title="Partitioned heritability"
          subtitle="Tissue & cell-type enrichment estimates"
        >
          <DataTable
            headers={[
              "Annotation",
              "Tissue",
              "Ancestry",
              "Enrichment",
              "P-value",
            ]}
            rows={
              (evidence.data?.partitioned || []).length > 0
                ? (evidence.data?.partitioned || []).map((p: any) => [
                    p.annotation,
                    p.tissue,
                    p.ancestry,
                    display(p.enrichment_beta),
                    display(p.pValue),
                  ])
                : [["No partitioned heritability records.", "-", "-", "-", "-"]]
            }
            pageSize={6}
            searchPlaceholder="Search tissue or annotation..."
            maxHeight={260}
          />
        </Panel>
      </div>
    </div>
  );
}

export function RegionAnalysis({
  goToMoa,
  initialRegion,
}: {
  goToMoa: () => void;
  initialRegion?: { chromosome: string; start: string; end: string };
}) {
  const [phenotype, setPhenotype] = useState("2hrG");
  const [view, setView] = useState("Raw association");
  const [chr, setChr] = useState("3");
  const [start, setStart] = useState("12328867");
  const [end, setEnd] = useState("12475855");
  const [query, setQuery] = useState(
    "/gwas?phenotype=2hrG&chromosome=3&start=12328867&end=12475855",
  );
  const [variant, setVariant] = useState("");

  useEffect(() => {
    if (initialRegion) {
      setChr(initialRegion.chromosome.replace(/\D/g, "") || "3");
      setStart(initialRegion.start.replaceAll(",", ""));
      setEnd(initialRegion.end.replaceAll(",", ""));
      setVariant("");
      setQuery(
        `/gwas?phenotype=2hrG&chromosome=${encodeURIComponent(
          initialRegion.chromosome.replace(/\D/g, "") || "3",
        )}&start=${initialRegion.start.replaceAll(",", "")}&end=${initialRegion.end.replaceAll(",", "")}`,
      );
    }
  }, [initialRegion]);

  const data = useLoad(query);
  const refs = useLoad(
    "/references?variant=" +
      encodeURIComponent(variant || "__no_variant_selected__"),
  );

  const startNum = parseInt(start) || 12328867;
  const endNum = parseInt(end) || 12475855;
  const spanKb = Math.max(1, Math.round((endNum - startNum) / 1000));
  const variantsList = data.data?.variants || [];

  const handleLoadRegion = () => {
    setVariant("");
    setQuery(
      `/gwas?phenotype=${phenotype}&chromosome=${encodeURIComponent(chr)}&start=${start}&end=${end}`,
    );
  };

  const dots = variantsList.map((v: any, index: number) => {
    const pos = v.position || startNum;
    const pct = Math.max(
      2,
      Math.min(96, ((pos - startNum) / (endNum - startNum || 1)) * 100),
    );
    const pVal = v.p_value ?? 1;
    const logP = -Math.log10(Math.max(pVal, 1e-300));
    const bottomPct = Math.max(5, Math.min(85, (logP / 30) * 100));
    return {
      left: `${pct.toFixed(1)}%`,
      bottom: `${bottomPct.toFixed(1)}%`,
      hot: logP > 7.3,
      id: v.var_id,
      pVal,
    };
  });

  return (
    <div className="page-stack">
      <section className="hero-strip region-hero">
        <div>
          <span className="eyebrow">REGION WORKSPACE</span>
          <h1>
            chr{chr}:{parseInt(start).toLocaleString()}-{parseInt(end).toLocaleString()}
          </h1>
          <p>
            Loaded genomic interval · GRCh38 · {chr === "3" ? "PPARG Target Locus" : `chr${chr} Locus`} ({spanKb} kb span)
          </p>
        </div>
        <div className="hero-meta">
          <div>
            <span>Phenotype</span>
            <strong>{phenotype}</strong>
          </div>
          <div>
            <span>Variants</span>
            <strong>{variantsList.length} observed</strong>
          </div>
          <div>
            <span>Lead Gene</span>
            <Badge tone="mint">{chr === "3" ? "PPARG" : `chr${chr}`}</Badge>
          </div>
        </div>
      </section>

      <div className="filter-bar region-filter">
        <label>
          <span>Phenotype</span>
          <select
            value={phenotype}
            onChange={(e) => setPhenotype(e.target.value)}
          >
            <option>2hrG</option>
            <option>2hrFFA</option>
          </select>
        </label>
        <label>
          <span>Chromosome</span>
          <select value={chr} onChange={(e) => setChr(e.target.value)}>
            {[
              1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18,
              19, 20, 21, 22,
            ].map((c) => (
              <option key={c} value={String(c)}>
                chr{c}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Start</span>
          <input
            type="number"
            min={1}
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          <span>End</span>
          <input
            type="number"
            min={Number(start)}
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <button onClick={handleLoadRegion}>
          <Search size={16} /> Load region
        </button>
      </div>

      <Notice {...data} />

      <Panel
        id="significant-variants"
        title="Most significant variants in the region"
        subtitle={`Observed variant statistics for ${phenotype} in interval`}
        action={
          <button
            className="text-button"
            onClick={() =>
              exportRows("region_variants.csv", variantsList)
            }
          >
            <Download size={16} /> Export
          </button>
        }
      >
        <SourcePlots data={data.data} />
        <DataTable
          headers={[
            "Variant ID",
            "Chr",
            "Position",
            "Allele",
            "P-value",
            "Beta",
            "Std. Error",
          ]}
          rows={
            variantsList.length > 0
              ? variantsList.map((v: Row) => [
                  v.var_id,
                  v.chromosome,
                  v.position?.toLocaleString(),
                  `${v.reference}/${v.alt}`,
                  display(v.p_value),
                  display(v.beta),
                  display(v.std_err),
                ])
              : [["No variants found in this interval.", "-", "-", "-", "-", "-", "-"]]
          }
        />
      </Panel>

      <Panel
        id="genomics-region"
        title="Genomics region"
        subtitle="Interactive regional locus view and variant catalogue"
      >
        <Tabs
          tabs={["Raw association", "Variant catalogue"]}
          active={view}
          onChange={setView}
        />
        {view === "Raw association" ? (
          <div className="locus-wrap">
            <div className="locus-toolbar">
              <span>
                <Badge>{phenotype}</Badge>
                <Badge tone="blue">EUR Cohort</Badge>
              </span>
              <small>Observed in interval</small>
            </div>
            <div className="locus-plot">
              {dots.map((dot: any, index: number) => (
                <i
                  key={index}
                  className={dot.hot ? "hot" : ""}
                  style={{ left: dot.left, bottom: dot.bottom }}
                  title={`${dot.id} (p=${dot.pVal})`}
                  onClick={() => setVariant(dot.id)}
                />
              ))}
            </div>
            <div className="gene-track">
              <span style={{ left: "20%", width: "60%" }}>
                {chr === "3" ? "PPARG" : `Target Locus chr${chr}`}
              </span>
            </div>
            <div className="locus-axis">
              <span>{(startNum / 1e6).toFixed(2)} Mb</span>
              <span>{(((startNum + endNum) / 2) / 1e6).toFixed(2)} Mb</span>
              <span>{(endNum / 1e6).toFixed(2)} Mb</span>
            </div>
          </div>
        ) : (
          <DataTable
            headers={[
              "Variant",
              "Position",
              "Allele",
              "P-value",
              "Beta",
              "Std. Error",
            ]}
            rows={
              variantsList.length > 0
                ? variantsList.map((v: Row) => [
                    v.var_id,
                    v.position?.toLocaleString(),
                    `${v.reference}/${v.alt}`,
                    display(v.p_value),
                    display(v.beta),
                    display(v.std_err),
                  ])
                : [["No variants in catalogue.", "-", "-", "-", "-", "-"]]
            }
          />
        )}
      </Panel>

      <Panel
        id="inferred-region"
        title="Reference annotation for exact variant"
        subtitle="Lookup nearest Ensembl gene and functional annotations"
        action={
          <button className="primary-button" onClick={goToMoa}>
            Open MoA Analysis <ChevronRight size={16} />
          </button>
        }
      >
        <div style={{ marginBottom: "14px" }}>
          <label>
            <span>Inspect Variant</span>
            <select
              value={variant}
              onChange={(e) => setVariant(e.target.value)}
              style={{
                width: "100%",
                background: "#1c1f2a",
                border: "1px solid #303340",
                color: "#e2e4ec",
                padding: "8px 12px",
                borderRadius: "6px",
                marginTop: "4px",
              }}
            >
              <option value="">Choose a variant from this interval...</option>
              {variantsList.map((r: Row) => (
                <option key={r.var_id} value={r.var_id}>
                  {r.var_id} (p={display(r.p_value)})
                </option>
              ))}
            </select>
          </label>
        </div>
        {variant ? (
          <>
            <Notice {...refs} />
            <DataTable
              headers={["Variant ID", "Nearest Ensembl ID", "Mapped Gene", "Source"]}
              rows={
                (refs.data?.nearest_genes || []).length > 0
                  ? (refs.data?.nearest_genes || []).map((r: any) => [
                      r.var_id,
                      r.gene_id,
                      r.gene,
                      r.source,
                    ])
                  : [["No nearest gene mapping found.", "-", "-", "-"]]
              }
            />
            <div style={{ marginTop: "12px" }}>
              <DataTable
                headers={["Variant ID", "Gene", "Annotation Detail"]}
                rows={
                  (refs.data?.annotations || []).length > 0
                    ? (refs.data?.annotations || []).map((r: any) => [
                        r.var_id,
                        r.gene,
                        r.record,
                      ])
                    : [["No specific annotations found.", "-", "-"]]
                }
              />
            </div>
            <Limits data={refs.data} />
          </>
        ) : (
          <p style={{ color: "var(--muted)" }}>
            Select a variant from the dropdown above to inspect supplied nearest-gene and burden annotations.
          </p>
        )}
      </Panel>
    </div>
  );
}

function Heatmap({ rows = [], cols = [], values = [], annotate = true, signed = false, onSelect }: {
  rows?: string[]; cols?: string[]; values?: (number | null)[][]; annotate?: boolean;
  signed?: boolean; onSelect?: (row: string, col: string, value: number | null) => void;
}) {
  const maximum = values.reduce((maximum, row) => row.reduce<number>((m, v) => typeof v === "number" && Number.isFinite(v) ? Math.max(m, Math.abs(v)) : m, maximum), 0);
  return <div className="evidence-heatmap">
    <div className="heatmap-legend">
      <span>{signed ? "Blue: negative · Red: positive" : "Green: larger weight"}</span>
      <span>{signed ? "Symmetric scale: ±" : "Scale: 0–"}{display(maximum)} · Grey: unavailable</span>
    </div>
    <div className="heatmap-scroll" tabIndex={0} aria-label="Scrollable evidence heatmap">
      <table className="evidence-heatmap-table">
        <thead><tr><th scope="col">{signed ? "Trait / Gene" : "Component / Trait"}</th>{cols.map(c => <th scope="col" key={c}>{c}</th>)}</tr></thead>
        <tbody>{rows.map((row, ri) => <tr key={row}><th scope="row">{row}</th>{cols.map((col, ci) => {
          const raw = values[ri]?.[ci];
          const value = typeof raw === "number" && Number.isFinite(raw) ? raw : null;
          const intensity = value === null || maximum === 0 ? 0 : Math.abs(value) / maximum;
          const background = value === null ? "#30333c" : value === 0 ? "#212633" : signed
            ? value > 0 ? "rgba(196,65,60," + (0.15 + intensity * 0.7) + ")" : "rgba(48,105,177," + (0.15 + intensity * 0.7) + ")"
            : "rgba(39,125,101," + (0.15 + intensity * 0.7) + ")";
          const label = row + " / " + col + ": " + (value === null ? "Unavailable" : value);
          return <td key={col} style={{background}}>
            {onSelect ? <button title={label} aria-label={label} onClick={() => onSelect(row,col,value)}>
              {value === null ? "N/A" : annotate ? display(value) : <span aria-hidden="true">·</span>}
            </button> : <span title={label}>{value === null ? "N/A" : annotate ? display(value) : "·"}</span>}
          </td>;
        })}</tr>)}</tbody>
      </table>
    </div>
  </div>;
}

function EvaluationPanel() {
  const [key, setKey] = useState("");
  const [text, setText] = useState("");
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Panel id="quality-evaluation" title="Independent annotated evaluation">
      <p style={{ color: "var(--muted)", fontSize: "12px", marginBottom: "10px" }}>
        Upload JSONL questions labelled by an independent reviewer. Each row
        needs question, expected_status and gold_citations; optional
        required_facts, required_numbers and forbidden_phrases. Human scientific
        review remains separate.
      </p>
      <div style={{ display: "flex", gap: "12px", alignItems: "center", marginBottom: "14px" }}>
        <a
          href="/api/analysis/templates/benchmark"
          className="text-button"
          download
        >
          <Download size={14} /> Download annotation format
        </a>
        <input
          type="file"
          accept=".jsonl,.json,.txt"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            if (file.size > 2000000) {
              setError("Benchmark exceeds 2 MB.");
              return;
            }
            setText(await file.text());
            setReport(null);
          }}
        />
      </div>
      <div style={{ marginBottom: "14px" }}>
        <label>
          <span>Optional AIHubMix API Key</span>
          <input
            type="password"
            autoComplete="off"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="sk-..."
            style={{
              width: "100%",
              background: "#1c1f2a",
              border: "1px solid #303340",
              color: "#e2e4ec",
              padding: "8px 12px",
              borderRadius: "6px",
              marginTop: "4px",
            }}
          />
        </label>
      </div>
      <button
        className="primary-button"
        disabled={!text || busy}
        onClick={async () => {
          setBusy(true);
          setError("");
          setReport(null);
          try {
            setReport(
              await api("/evaluate", {
                benchmark_jsonl: text,
                api_key: key || undefined,
              }),
            );
          } catch (e: any) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Sparkles size={16} /> Run annotated offline evaluation
      </button>
      <Notice error={error} loading={busy} />
      {report && (
        <div style={{ marginTop: "16px" }}>
          <DataTable
            headers={["Metric", "Value"]}
            rows={Object.entries(report)
              .filter(([k]) => k !== "results" && k !== "limitations")
              .map(([field, value]) => [field, display(value)])}
          />
          <Limits data={report} />
          <button
            className="text-button"
            style={{ marginTop: "10px" }}
            onClick={() =>
              exportFile(
                "evaluation_with_human_review.json",
                JSON.stringify(report, null, 2),
                "application/json",
              )
            }
          >
            <Download size={14} /> Export results and human-review rubric
          </button>
        </div>
      )}
    </Panel>
  );
}

export function MoAAnalysis({ requestedSection }: { requestedSection?: { id: string; tick: number } }) {
  const catalog = useLoad("/catalog");
  const [step, setStep] = useState(1);
  const [files, setFiles] = useState<Record<string, string>>({});
  const [run, setRun] = useState<any>(null);
  const [selection, setSelection] = useState<any>(null);
  const [enriched, setEnriched] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [components, setComponents] = useState(2);
  const [component, setComponent] = useState(0);
  const [weight, setWeight] = useState(0);
  const [cutoff, setCutoff] = useState(0);
  const [trait, setTrait] = useState("");
  const [library, setLibrary] = useState("");
  const [q, setQ] = useState(0.05);
  const [algorithm, setAlgorithm] = useState("nmf");
  const [iterations, setIterations] = useState(500);
  const [seed, setSeed] = useState(46);
  const [fileVersion, setFileVersion] = useState(0);
  const [inputFiles, setInputFiles] = useState<string[]>([]);
  const [annotateCells, setAnnotateCells] = useState(true);
  const [effectMetric, setEffectMetric] = useState<"z" | "beta">("z");
  const [genesToShow, setGenesToShow] = useState(12);
  const [activeCell, setActiveCell] = useState<{gene: string; trait: string; value: number | null} | null>(null);

  // Embedded RAG chat state
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [answerDetails, setAnswerDetails] = useState<any>(null);
  const [moaStatus, setMoaStatus] = useState<string>("");
  const [loadingMoa, setLoadingMoa] = useState(false);

  const generation = useRef(0);
  const steps = ["Choose data", "Explore genes", "Explain results"];
  const moveStep = (next: number) => {
    setStep(next);
    document.querySelector(".content-scroll")?.scrollTo({ top: 0, behavior: "smooth" });
  };
  useEffect(() => {
    if (!requestedSection) return;
    const target = requestedSection.id;
    setStep(target === "phenotype-gene" || !run ? 1 : target === "mechanism-action" || target === "quality-evaluation" ? 3 : 2);
  }, [requestedSection]);


  useEffect(() => {
    if (catalog.data?.libraries.length && !library)
      setLibrary(
        catalog.data.libraries.find((r: Row) =>
          r.name.startsWith("WikiPathways"),
        )?.name || catalog.data.libraries[0].name,
      );
  }, [catalog.data, library]);

  useEffect(() => {
    setAnswer("");
    setMoaStatus("");
    setAnswerDetails(null);
    setActiveCell(null);
    const ticket = ++generation.current;
    if (!run) return;
    setSelection(null);
    setEnriched(null);
    api(
      `/runs/${run.run_id}/selection?component=${component}&weight=${weight}&z_cutoff=${cutoff}&trait=${encodeURIComponent(trait)}`,
    )
      .then((r) => {
        if (ticket === generation.current) setSelection(r);
      })
      .catch((e) => {
        if (ticket === generation.current) setError(e.message);
      });
  }, [run, component, weight, cutoff, trait]);

  const execute = async (source: "files" | "corpus" | "client") => {
    setBusy(true);
    setError("");
    setRun(null);
    setSelection(null);
    setEnriched(null);
    ++generation.current;
    try {
      const result = await api(
        source === "client" ? "/matrix/client-example" : source === "corpus" ? "/matrix/corpus" : "/matrix",
        source !== "files"
          ? {}
          : {
              matrix_csv: files.matrix,
              w_csv: files.w,
              h_csv: files.h,
              associations_csv: files.associations,
              components,
              algorithm,
              iterations,
              seed,
            },
      );
      setComponent(0);
      setWeight(0);
      setCutoff(0);
      setTrait("");
      setInputFiles(source === "client" ? ["Client V001 complete-case demo; independent NMF"] : source === "corpus" ? ["2hrG corpus baseline"] : inputFiles);
      setRun(result);
      moveStep(2);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const ask = async () => {
    if (!question.trim() || !run || !selection || loadingMoa) return;
    const ticket = generation.current;
    setLoadingMoa(true);
    setAnswer("");
    setAnswerDetails(null);
    setMoaStatus("");
    try {
      const data = await api(`/runs/${run.run_id}/question`, {
        question, component, weight, z_cutoff: cutoff, trait,
      });
      if (ticket !== generation.current) return;
      setAnswer(data.answer);
      setMoaStatus(data.status);
      setAnswerDetails(data);
    } catch (e: any) {
      if (ticket === generation.current) {
        setAnswer(e.message);
        setMoaStatus("error");
      }
    } finally {
      setLoadingMoa(false);
    }
  };

  const effects = selection?.genes.flatMap((r: Row) => r.effects) || [];
  const heatGenes: string[] = (selection?.genes || []).slice(0, genesToShow).map((g: Row) => g.gene);
  const heatTraits: string[] = (run?.traits || []).filter((t: string) => !trait || t.toLowerCase().includes(trait.toLowerCase()));
  const heatValues = effectMatrix(heatGenes, heatTraits, effects, effectMetric);

  return (
    <div className="page-stack">
      <section className="moa-intro">
        <span className="eyebrow">GUIDED ANALYSIS</span>
        <h1>Explore gene evidence</h1>
        <p>{step === 1 ? "Start with the client example, or bring your own data." : step === 2 ? "Choose a phenotype and inspect the genes that pass your filters." : "Ask why a gene was selected, then review its sources."}</p>
        {run && <span className="moa-context">{run.genes.length} measured genes · {run.traits.length} traits · {selection ? selection.total + " selected" : "Updating selection…"}</span>}
      </section>
      <ol className="moa-stepper" aria-label="Analysis steps">
        {steps.map((label, index) => <li key={label}>
          <button aria-current={step === index + 1 ? "step" : undefined}
            disabled={(index > 0 && !run) || (index === 2 && !selection)}
            onClick={() => moveStep(index + 1)}><span>{index + 1}</span>{label}</button>
        </li>)}
      </ol>
      <Notice error={error} loading={busy} />
      {step === 1 && <div className="moa-stage">
      <div className="data-source-bar moa-source">
        <div>
          <TableProperties size={20} />
          <div>
            <strong>Analysis inputs</strong>
            <span>
              {run
                ? `Analyzed (${run.components.length} components; ${run.diagnostics.method})`
                : "Try the client example to get started."}
            </span>
          </div>
        </div>
        <div className="input-status">
          {inputFiles.length > 0 ? (
            inputFiles.map((file) => (
              <span key={file}>
                <i /> {file}
              </span>
            ))
          ) : (
            <span>
              <i /> No data loaded
            </span>
          )}
        </div>
        <button className="primary-button" disabled={busy} onClick={() => execute("client")}>
          Load client example
        </button>
        <button
          className="primary-button"
          disabled={busy}
          onClick={() => execute("corpus")}
        >
          {busy ? "Decomposing..." : "Load Corpus Matrix"}
        </button>
      </div>

      <p className="moa-help">Recommended: load the client example to try the complete workflow.</p>
      <details className="moa-disclosure"><summary>About the example and its limits</summary>
        <p>200 complete-case genes across BMI, HDL, T2D and TG. NMF is independently refitted on absolute source Z values. The original matching W is unavailable; this is not a reproduction of the client's original factors.</p>
      </details>
      <details className="moa-disclosure"><summary>Use your own data · advanced</summary>
      <Panel
        id="phenotype-gene"
        title="Upload matrices"
        subtitle="Upload custom matrices or factorize live multi-omics association data"
        
      >
        <p style={{ color: "var(--muted)", fontSize: "12px", marginBottom: "14px" }}>
          Upload X (genes × traits), or both W (genes × components) and H (components × traits).
          Signed beta / z values belong in the separate associations file.
        </p>

        <div className="inline-controls" style={{ marginBottom: "16px" }}>
          {(["matrix", "w", "h", "associations", "gmt"] as const).map(
            (kind) => (
              <label key={kind}>
                <span>{kind.toUpperCase()} file</span>
                <input
                  type="file"
                  key={kind + fileVersion}
                  accept={kind === "gmt" ? ".gmt,.txt" : ".csv"}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    if (file.size > (kind === "gmt" ? 16000000 : 8000000)) {
                      setError(
                        "File is too large; reduce its size before uploading.",
                      );
                      e.target.value = "";
                      return;
                    }
                    try {
                      const text = await file.text();
                      setFiles((current) => ({ ...current, [kind]: text }));
                      setInputFiles((prev) =>
                        Array.from(new Set([...prev, file.name])),
                      );
                      setRun(null);
                      setSelection(null);
                      setEnriched(null);
                      ++generation.current;
                    } catch {
                      setError("Unable to read file.");
                    }
                  }}
                />
                <a
                  href={"/api/analysis/templates/" + kind}
                  style={{ fontSize: "10px", color: "var(--mint)", marginTop: "2px" }}
                >
                  Download template
                </a>
              </label>
            ),
          )}
        </div>

        <div className="inline-controls" style={{ marginBottom: "16px" }}>
          <label>
            <span>Algorithm</span>
            <select
              value={algorithm}
              onChange={(e) => setAlgorithm(e.target.value)}
            >
              <option value="nmf">
                NMF - multiplicative updates
              </option>
              <option value="bayesian">
                Bayesian NMF - Gibbs sampling
              </option>
            </select>
          </label>
          <label>
            <span>Components</span>
            <input
              type="number"
              min={1}
              max={20}
              value={components}
              onChange={(e) => setComponents(Number(e.target.value))}
            />
          </label>
          <label>
            <span>Iterations</span>
            <input
              type="number"
              min={100}
              max={2000}
              value={iterations}
              onChange={(e) => setIterations(Number(e.target.value))}
            />
          </label>
          <button
            className="primary-button"
            disabled={busy}
            onClick={() => void execute("files")}
          >
            Analyze Uploaded Files
          </button>
        </div>

        {run && (
          <div style={{ marginTop: "16px" }}>
            <h3 style={{ color: "var(--mint)", marginBottom: "8px" }}>
              Phenotype Loadings H ({run.components.length} components × {run.traits.length} traits)
            </h3>
            <Heatmap
              rows={run.components}
              cols={run.traits}
              values={run.h}
              annotate={annotateCells}
            />
            <div style={{ display: "flex", gap: "10px", marginTop: "12px" }}>
              <button
                className="text-button"
                onClick={() =>
                  exportRows(
                    "W.csv",
                    run.genes.map((g: string, i: number) =>
                      Object.fromEntries([
                        ["gene", g],
                        ...run.components.map((c: string, j: number) => [
                          c,
                          run.w[i][j],
                        ]),
                      ]),
                    ),
                  )
                }
              >
                <Download size={14} /> Export W Matrix
              </button>
              <button
                className="text-button"
                onClick={() =>
                  exportRows(
                    "H.csv",
                    run.components.map((c: string, i: number) =>
                      Object.fromEntries([
                        ["component", c],
                        ...run.traits.map((t: string, j: number) => [
                          t,
                          run.h[i][j],
                        ]),
                      ]),
                    ),
                  )
                }
              >
                <Download size={14} /> Export H Matrix
              </button>
            </div>
            <Limits data={run} />
          </div>
        )}
      </Panel>

      </details>
      {run && <button className="primary-button" onClick={() => moveStep(2)}>Continue with loaded data</button>}
      </div>}
      {step === 2 && <div className="moa-stage">
      <Panel
        id="top-weighted-genes"
        title="Filter your genes"
        subtitle="Filter genes by component weight and association Z-score"
        
      >
        <div className="inline-controls">
          <label><span>Phenotype</span><select value={trait} onChange={e => setTrait(e.target.value)}>
            <option value="">All measured traits</option>
            {(run?.traits || []).map((t: string) => <option key={t} value={t}>{t}</option>)}
          </select></label>
          <label><span>Minimum |Z-score|</span><input type="number" min={0} step="any" value={cutoff} onChange={e => setCutoff(Number(e.target.value))} /></label>
        </div>
        <p className="moa-help">Use 0 to include all measured effects. A higher threshold keeps stronger associations.</p>
        <details className="moa-disclosure"><summary>Advanced: component and weight filters</summary>
          <div className="inline-controls">
            <label><span>Component</span><select value={component} onChange={e => setComponent(Number(e.target.value))}>
              {run?.components.map((c: string, i: number) => <option key={c} value={i}>{c}</option>)}
            </select></label>
            <label><span>Min W Weight</span><input type="number" min={0} step="any" value={weight} onChange={e => setWeight(Number(e.target.value))} /></label>
          </div>
        </details>
        <details className="moa-disclosure"><summary>Gene weights and intervals</summary>
        <DataTable
          headers={[
            "Gene",
            "Component W",
            "Standardized W",
            "95% Interval Low",
            "95% Interval High",
          ]}
          rows={
            (selection?.genes || []).length > 0
              ? (selection?.genes || []).map((g: any) => [
                  g.gene,
                  display(g.weight),
                  display(g.weight_z),
                  display(g.credible_low),
                  display(g.credible_high),
                ])
              : [["No genes pass current selection criteria.", "-", "-", "-", "-"]]
          }
        />

        </details>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "12px" }}>
          <span style={{ fontSize: "12px", color: "var(--muted)" }}>
            {selection?.total ?? 0} genes selected
          </span>
          <button
            className="text-button"
            disabled={!selection}
            onClick={() =>
              exportRows("selected_genes.csv", selection?.genes || [])
            }
          >
            <Download size={14} /> Export selection
          </button>
        </div>
      </Panel>

      <Panel
        id="directional-effect"
        title="Gene–phenotype effects"
        subtitle="Measured association direction, not a treatment recommendation"
        
      >
        <p className="moa-help">Read across a trait to compare the selected genes. Click a cell for its source value.</p>
        <div className="inline-controls">
          <label><span>Metric</span><select value={effectMetric} onChange={e => {setEffectMetric(e.target.value as "z" | "beta");setActiveCell(null);}}>
            <option value="z">Z-score</option><option value="beta">Beta</option>
          </select></label>
          <label><span>Genes shown</span><select value={genesToShow} onChange={e => {setGenesToShow(Number(e.target.value));setActiveCell(null);}}>
            <option value={6}>6</option><option value={12}>12</option><option value={24}>24</option>
          </select></label>
          <label className="check-row"><span>Show values</span><input type="checkbox" checked={annotateCells} onChange={e => setAnnotateCells(e.target.checked)} /></label>
        </div>
        {heatGenes.length && heatTraits.length ? <Heatmap rows={heatTraits} cols={heatGenes} values={heatValues} signed annotate={annotateCells}
          onSelect={(row,col,value) => setActiveCell({gene:col,trait:row,value})} /> : <p>No effects to plot. Load data or loosen the filters.</p>}
        <p className="moa-help">Showing up to {genesToShow} genes ordered by component weight. Missing records remain N/A. {effectMetric === "beta" ? "Beta scales can differ between traits; compare within each trait." : "Z-score is signed association evidence."}</p>
        {activeCell && <div className="moa-cell-detail">
          <strong>{activeCell.gene} · {activeCell.trait}</strong>
          <p>{effectMetric === "z" ? "Z-score" : "Beta"}: {activeCell.value === null ? "Unavailable (missing or ambiguous record)" : activeCell.value}</p>
          <button className="text-button" onClick={() => {setQuestion("Why was " + activeCell.gene + " selected?");moveStep(3);}}>Explain this gene →</button>
        </div>}
        <details className="moa-disclosure"><summary>Source effect table</summary>
        <DataTable
          headers={[
            "Gene",
            "Phenotype",
            "Beta",
            "Association Z",
            "P-value",
            "Direction",
          ]}
          rows={
            effects.length > 0
              ? effects.map((e: Row) => [
                  e.gene,
                  e.phenotype,
                  display(e.beta),
                  display(e.z),
                  display(e.p_value),
                  e.direction,
                ])
              : [["No directional effect records in selection.", "-", "-", "-", "-", "-"]]
          }
        />
        </details>
        <p style={{ color: "var(--muted)", fontSize: "11px", marginTop: "10px" }}>
          Positive and negative effects describe the supplied phenotype scale.
          They do not establish agonist, antagonist or treatment recommendations.
        </p>
      </Panel>

      <details className="moa-disclosure"><summary>NMF component weights · H heatmap</summary>
        <p>Computed nonnegative weights. These are separate from signed source effects.</p>
        <Heatmap rows={run?.components || []} cols={run?.traits || []} values={run?.h || []} annotate={annotateCells} />
      </details>
      <details className="moa-disclosure"><summary>Optional: pathway enrichment</summary>
      <Panel
        id="gene-enrichment"
        title="Pathway enrichment"
        subtitle="Local hypergeometric test with Benjamini-Hochberg FDR correction"
        
      >
        <div className="inline-controls enrichment-controls" style={{ marginBottom: "16px" }}>
          <label>
            <span>Library</span>
            <select
              value={library}
              onChange={(e) => {
                setLibrary(e.target.value);
                setEnriched(null);
              }}
            >
              <option value="">Select a public library</option>
              {catalog.data?.libraries.map((l: Row) => (
                <option key={l.name}>{l.name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>BH q-value threshold</span>
            <input
              type="number"
              min={0.000001}
              max={1}
              step="any"
              value={q}
              onChange={(e) => {
                setQ(Number(e.target.value));
                setEnriched(null);
              }}
            />
          </label>
          <button
            className="primary-button"
            disabled={busy || !selection?.total || (!files.gmt && !library)}
            onClick={async () => {
              setBusy(true);
              setError("");
              setEnriched(null);
              const ticket = generation.current;
              try {
                const result = await api("/enrichment", {
                  genes: selection.genes.map((r: Row) => r.gene),
                  background: selection.background,
                  library,
                  gmt: files.gmt,
                  threshold: q,
                });
                if (ticket === generation.current) setEnriched(result);
              } catch (e: any) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Sparkles size={16} /> Run enrichment
          </button>
        </div>

        <p style={{ color: "var(--muted)", fontSize: "12px", marginBottom: "14px" }}>
          {files.gmt
            ? "Uses uploaded custom GMT library."
            : "Uses downloaded public reference library."}{" "}
          Background: all measured genes in current matrix ({selection?.background?.length ?? 0} genes).
        </p>

        {enriched && (
          <div style={{ marginTop: "16px" }}>
            <p style={{ fontSize: "12px", color: "var(--mint)", marginBottom: "10px" }}>
              {enriched.tested_terms} tested sets · {enriched.significant_count} pass BH q ≤ {enriched.threshold}
            </p>
            {enriched.results.length > 0 ? (
              <div className="chart-table-grid">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart
                    data={enriched.results.slice(0, 10).map((r: Row) => ({
                      name: r.term.length > 20 ? r.term.slice(0, 18) + "..." : r.term,
                      score: -Math.log10(Math.max(r.q_value, 1e-300)),
                    }))}
                    layout="vertical"
                  >
                    <CartesianGrid stroke="#303340" horizontal={false} />
                    <XAxis type="number" tick={{ fill: "#8f93a3" }} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={120}
                      tick={{ fill: "#9a9eac", fontSize: 10 }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#191c27",
                        border: "1px solid #343744",
                        color: "#f0f2f8",
                        borderRadius: "6px",
                      }}
                      itemStyle={{ color: "#f0f2f8" }}
                      labelStyle={{
                        color: "#9be0d5",
                        fontWeight: 600,
                        marginBottom: "4px",
                      }}
                    />
                    <Bar dataKey="score" fill="#f2b858" radius={[0, 5, 5, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <DataTable
                  headers={[
                    "Gene Set",
                    "P-value",
                    "BH q-value",
                    "Fold Enrichment",
                    "Overlapping Genes",
                  ]}
                  rows={enriched.results.map((r: Row) => [
                    r.term,
                    display(r.p_value),
                    display(r.q_value),
                    display(r.fold_enrichment),
                    r.overlap.join(", "),
                  ])}
                />
              </div>
            ) : (
              <p style={{ color: "var(--muted)", padding: "16px" }}>
                Zero gene sets meet the BH q ≤ {enriched.threshold} significance threshold.
              </p>
            )}
            <div style={{ marginTop: "12px" }}>
              <button
                className="text-button"
                onClick={() =>
                  exportRows("enrichment_results.csv", enriched.results)
                }
              >
                <Download size={14} /> Export enrichment
              </button>
            </div>
            <Limits data={enriched} />
          </div>
        )}
      </Panel>

      </details>
      </div>}
      {step === 3 && <div className="moa-stage">
      <Panel
        id="mechanism-action"
        title="Explain your results"
        subtitle="Explain the current selection using computed results, source effects and approved gene-function evidence"
        action={
          <button
            className="text-button"
            disabled={!run}
            onClick={() =>
              exportFile(
                "analysis_dossier.json",
                JSON.stringify({ run, selection, enrichment: enriched, explanation: answerDetails }, null, 2),
                "application/json",
              )
            }
          >
            <Download size={16} /> Export dossier JSON
          </button>
        }
      >
        <div className="embedded-chat">
          <div className="embedded-chat-head">
            <div>
              <Bot size={20} />
              <div>
                <strong>Ask questions about these genes & mechanisms</strong>
                <span>Uses this run and the current filters; changing filters clears the answer</span>
              </div>
            </div>
            <Badge tone="mint">Local cited explanation</Badge>
          </div>

          {answer && (
            <div className="embedded-answer">
              <Sparkles size={17} />
              <div>
                {moaStatus && (
                  <div style={{ marginBottom: "6px" }}>
                    <span
                      className={
                        moaStatus === "answer" || moaStatus === "verified"
                          ? "status-pill-verified"
                          : `status-pill-${moaStatus}`
                      }
                    >
                      {moaStatus === "verified" || moaStatus === "answer"
                        ? "Cited evidence"
                        : moaStatus.toUpperCase()}
                    </span>
                  </div>
                )}
                <p style={{whiteSpace: "pre-wrap"}}>{answer}</p>
                {answerDetails && <div>
                  <details className="moa-disclosure"><summary>Run details and limitations</summary>
                  <p>Analysis run: {answerDetails.analysis_run_id}</p>
                  <p>Question run: {answerDetails.query_run_id}</p>
                  <Limits data={answerDetails} />
                  </details>
                  <h4>Claims and sources</h4>
                  {answerDetails.claims.map((claim: any, i: number) => <details key={i}>
                    <summary>{claim.text.slice(0, 100)}…</summary>
                    <p>{claim.text}</p>
                    {claim.citations.map((id: string) => {
                      const cite = answerDetails.citations.find((c: any) => c.chunk_id === id);
                      return <div key={id}><strong>{cite?.title || cite?.source_name || id}</strong>
                        <p>{id}</p><pre style={{whiteSpace:"pre-wrap", overflowWrap:"anywhere"}}>
                          {JSON.stringify(cite, null, 2)}
                        </pre></div>;
                    })}
                  </details>)}
                </div>}
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
              placeholder="Why were the current genes selected? Explain the source effects."
            />
            <button aria-label="Ask question" disabled={loadingMoa || !run || !selection}>
              {loadingMoa ? (
                <Loader2 size={18} className="animate-spin" />
              ) : (
                <Send size={18} />
              )}
            </button>
          </form>
        </div>
      </Panel>

      <details className="moa-disclosure"><summary>Advanced: independent quality evaluation</summary><EvaluationPanel /></details>
      </div>}
      <div className="moa-footer">
        {step > 1 && <button className="text-button" onClick={() => moveStep(step - 1)}>Back</button>}
        {step === 2 && <button className="primary-button" disabled={!selection} onClick={() => moveStep(3)}>Explain this selection →</button>}
      </div>
    </div>
  );
}
