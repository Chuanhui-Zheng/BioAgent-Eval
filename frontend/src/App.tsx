import { scopedFetch as fetch, currentWorkspace, changeWorkspace } from "./api";
import {
  GeneAnalysis as GenePage,
  PhenotypeAnalysis as PhenotypePage,
  RegionAnalysis as RegionPage,
  MoAAnalysis as MoAPage,
} from "./ScientificPages";
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
  source_version?: string;
  corpus_version?: string;
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
  status?: "qualified" | "refused" | "refuse" | "error" | "answer";
  limitations?: string[];
  claims?: ClaimItem[];
  citations?: CitationItem[];
  latency_ms?: number;
  retrieved_count?: number;
  provider?: string;
  loading?: boolean;
  run_id?: string;
  usage?: { api_calls?: number; input_tokens?: number; output_tokens?: number; estimated_cost_usd?: number | null };
}

interface GeneAssociation {
  phenotype: string;
  label: string;
  common_bf: number | null;
  rare_bf: number | null;
  huge_score: number | null;
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
  huge_score?: number | null;
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
    { id: "genetic-correlation", label: "Genetic correlation" },
    { id: "global-annotation", label: "Global enriched annotation" },
  ],
  region: [
    { id: "significant-variants", label: "Most significant variants" },
    { id: "genomics-region", label: "Genomics region" },
    { id: "inferred-region", label: "Variant reference annotation" },
  ],
  moa: [
    { id: "phenotype-gene", label: "Phenotype–Gene association" },
    { id: "top-weighted-genes", label: "Top weighted genes" },
    { id: "gene-enrichment", label: "Gene enrichment" },
    { id: "directional-effect", label: "Directional effect" },
    { id: "mechanism-action", label: "Evidence dossier" },
    { id: "quality-evaluation", label: "Annotated evaluation" },
  ],
};

function downloadCsv(
  filename: string,
  headers: string[],
  rows: (string | number)[][],
) {
  const escape = (value: string | number) =>
    `"${String(value).replaceAll('"', '""')}"`;
  const csv = [headers, ...rows]
    .map((row) => row.map(escape).join(","))
    .join("\n");
  const url = URL.createObjectURL(
    new Blob([csv], { type: "text/csv;charset=utf-8" }),
  );
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
  const res = await fetch(
    `/api/genes/${encodeURIComponent(symbol.toUpperCase())}`,
  );
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
  {
    id: "phenotype" as Page,
    label: "Phenotype Search",
    short: "Trait",
    icon: Activity,
  },
  {
    id: "region" as Page,
    label: "Gene Region",
    short: "Region",
    icon: GitBranch,
  },
  { id: "moa" as Page, label: "Gene MoA", short: "MoA", icon: FlaskConical },
];

function CitationEvidence({ citation }: { citation: CitationItem }) {
  const [evidence, setEvidence] = useState<{
    content: string;
    metadata: Record<string, unknown>;
    citation: Record<string, unknown>;
  } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const id = citation.chunk_id || citation.id;
  const name = citation.source_name || citation.title || id || "Source";
  const load = async () => {
    if (!id || evidence || loading) return;
    setLoading(true);
    setError("");
    try {
      const version = citation.corpus_version ? `?corpus_version=${encodeURIComponent(citation.corpus_version)}` : "";
      const response = await fetch(`/api/evidence/${encodeURIComponent(id)}${version}`);
      if (!response.ok) throw new Error(response.status === 409 ? "Evidence version changed. Ask the question again to inspect current sources." : "Evidence passage unavailable in this workspace");
      setEvidence(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load source");
    } finally {
      setLoading(false);
    }
  };
  return (
    <details
      className="citation-evidence"
      onToggle={(event) => {
        if (event.currentTarget.open) void load();
      }}
    >
      <summary className="citation-tag">
        [{id}] {name}
      </summary>
      {loading && <p>Loading source passage…</p>}
      {error && (
        <p role="alert">
          {error} <button onClick={() => void load()}>Retry</button>
        </p>
      )}
      {evidence && (
        <>
          <p style={{ whiteSpace: "pre-wrap" }}>{evidence.content}</p>
          <details>
            <summary>Source metadata and provenance</summary>
            <pre>
              {JSON.stringify(
                { metadata: evidence.metadata, citation: evidence.citation },
                null,
                2,
              )}
            </pre>
          </details>
        </>
      )}
    </details>
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
}: {
  headers: string[];
  rows: (string | number)[][];
}) {
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
                  {cellIndex === 0 ? (
                    <span className="table-link">{cell}</span>
                  ) : (
                    cell
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SearchBar({
  page,
  onSearch,
}: {
  page: Page;
  onSearch: (value: string) => void;
}) {
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

function App() {
  const [page, setPage] = useState<Page>("gene");
  const [selectedGene, setSelectedGene] = useState("PPARG");
  const [selectedPhenotype, setSelectedPhenotype] = useState("2hrG");
  const [selectedRegion, setSelectedRegion] = useState({
    chromosome: "10",
    start: "114752503",
    end: "114808903",
  });
  const [draftQuestion, setDraftQuestion] = useState("");
  const [moaSection, setMoaSection] = useState<{id: string; tick: number}>();
  const [navOpen, setNavOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [systemHealth, setSystemHealth] = useState<{
    status: string;
    total_chunks: number;
  } | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => {
        if (!r.ok) throw new Error("Health check failed");
        return r.json();
      })
      .then((data) => setSystemHealth(data))
      .catch((err) => console.log("Backend offline or connecting:", err));
  }, []);

  const title =
    NAV_ITEMS.find((item) => item.id === page)?.label ?? "Workspace";
  const showToast = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2500);
  };

  const handleGlobalSearch = async (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      showToast("Enter a gene, phenotype, genomic interval or question");
      return;
    }
    const region = trimmed.match(/^(?:chr)?([A-Za-z0-9]+):([\d,]+)-([\d,]+)$/i);
    if (region) {
      setSelectedRegion({
        chromosome: region[1],
        start: region[2].replaceAll(",", ""),
        end: region[3].replaceAll(",", ""),
      });
      setPage("region");
      return;
    }
    if (
      trimmed.includes("?") ||
      /^(what|how|why|does|explain|is|which|compare|summari[sz]e)\b/i.test(
        trimmed,
      )
    ) {
      setDraftQuestion(trimmed);
      setChatOpen(true);
      return;
    }
    try {
      const response = await fetch(
        "/api/phenotypes/" + encodeURIComponent(trimmed),
      );
      if (response.ok) {
        const result = await response.json();
        setSelectedPhenotype(result.code);
        setPage("phenotype");
        return;
      }
      if (response.status !== 404) throw new Error("Backend unavailable");
      const geneResponse = await fetch(
        "/api/genes/" + encodeURIComponent(trimmed),
      );
      if (geneResponse.ok) {
        const gene = await geneResponse.json();
        setSelectedGene(gene.symbol);
        setPage("gene");
        return;
      }
      if (geneResponse.status !== 404) throw new Error("Backend unavailable");
      showToast(
        "No matching gene or phenotype; use Ask RAG Assistant for a scientific question",
      );
    } catch {
      showToast("Cannot search while the backend is unavailable");
    }
  };

  const goToSection = (targetPage: Page, id?: string) => {
    setPage(targetPage);
    if (targetPage === "moa") setMoaSection({id: id || "phenotype-gene", tick: Date.now()});
    window.setTimeout(() => {
      if (id)
        document
          .getElementById(id)
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
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
            <button
              key={id}
              className={page === id ? "active" : ""}
              title={label}
              onClick={() => setPage(id)}
            >
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
          <IconButton
            label="Collapse navigation"
            onClick={() => setNavOpen(false)}
          >
            <PanelLeftClose size={19} />
          </IconButton>
        </div>

        <label className="workspace-selector">Simulated workspace
          <select value={currentWorkspace()} onChange={e => changeWorkspace(e.target.value)}>
            <option value="all">All approved evidence</option>
            <option value="annotations">Annotations and expression</option>
            <option value="genetics">Genetic associations</option>
          </select>
          <small>Demonstrates data isolation; not a login.</small>
        </label>
        <nav className="site-contents">
          {NAV_ITEMS.map(({ id, label }) => (
            <section className={page === id ? "active" : ""} key={id}>
              <button
                className="sidebar-page-title"
                onClick={() => goToSection(id)}
              >
                <span>{label}</span>
                <ChevronRight size={15} />
              </button>
              <div className="section-nav">
                {PAGE_SECTIONS[id].map((section) => (
                  <button
                    key={section.id}
                    onClick={() => goToSection(id, section.id)}
                  >
                    {section.label}
                  </button>
                ))}
              </div>
            </section>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div
            className="status-dot"
            style={{ background: systemHealth ? "#69d39b" : "#f4b759" }}
          />
          <div>
            <strong>Evidence Corpus</strong>
            <span>
              {systemHealth
                ? `${systemHealth.total_chunks.toLocaleString()} chunks indexed`
                : "Connecting backend..."}
            </span>
          </div>
        </div>
      </aside>

      <main className="main-area" onClick={() => navOpen && setNavOpen(false)}>
        <header className="topbar">
          <div
            className="mobile-nav-toggle"
            onClick={(event) => event.stopPropagation()}
          >
            <IconButton
              label="Open navigation"
              onClick={() => setNavOpen(true)}
            >
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
              onClick={() =>
                showToast(
                  systemHealth
                    ? `Corpus contains ${systemHealth.total_chunks.toLocaleString()} passages. Illustrative analysis panels are labelled separately.`
                    : "Backend unavailable; start the API to retrieve corpus evidence.",
                )
              }
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
          <div
            className="context-pill"
            title="Connected to live FastAPI backend on port 8000"
          >
            <span>ENGINE</span>
            <strong style={{ color: systemHealth ? "#69d39b" : "#f2b858" }}>
              {systemHealth
                ? `RAG · ${systemHealth.total_chunks.toLocaleString()} passages`
                : "Backend unavailable"}
            </strong>
          </div>
        </div>

        <div className="content-scroll" ref={contentRef}>
          {page === "gene" ? (
            <GenePage initialGene={selectedGene} />
          ) : page === "phenotype" ? (
            <PhenotypePage initialPhenotype={selectedPhenotype} />
          ) : page === "region" ? (
            <RegionPage
              initialRegion={selectedRegion}
              goToMoa={() => setPage("moa")}
            />
          ) : (
            <MoAPage />
          )}
        </div>
      </main>

      {chatOpen && (
        <ChatPanel
          initialQuestion={draftQuestion}
          page={page}
          onClose={() => setChatOpen(false)}
        />
      )}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function ChatPanel({
  page,
  onClose,
  initialQuestion = "",
}: {
  page: Page;
  onClose: () => void;
  initialQuestion?: string;
}) {
  const context: Record<Page, string> = {
    gene: "Gene Information & Association Corpus",
    phenotype: "Curated Phenotype Glossary & GWAS",
    region: "Genomic Interval & Locus Variants",
    moa: "Directional Effects & MoA Rules",
  };

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      text: "Ask a scientific question to retrieve corpus evidence and source references. Citation checks confirm reference IDs; they do not verify scientific conclusions.",
    },
  ]);
  const [input, setInput] = useState(initialQuestion);
  useEffect(() => {
    setInput(initialQuestion);
  }, [initialQuestion]);
  const [loading, setLoading] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [showConfig, setShowConfig] = useState(false);

  const suggestions = useMemo(
    () =>
      page === "gene"
        ? [
            "What is the function of PPARG in the approved corpus?",
            "What common and rare variant associations support ADCY5?",
            "Compare TCF7L2 and PPARG evidence tiers",
          ]
        : page === "phenotype"
          ? [
              "What genes are associated with 2-hour glucose (2hrG)?",
              "Explain the difference between 2hrG and 2hrI phenotypes",
            ]
          : [
              "What rare-variant association evidence is available for LPCAT2?",
              "What evidence limitations apply when interpreting genetic associations?",
            ],
    [page],
  );

  const send = async (text = input) => {
    const q = text.trim();
    if (!q || loading) return;

    // Append user message
    const userMsg: ChatMessage = { role: "user", text: q };
    const loadingMsg: ChatMessage = {
      role: "assistant",
      text: "",
      loading: true,
    };
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
        limitations: data.limitations || [],
        latency_ms: Math.round((data.latency_s?.total_api || 0.005) * 1000),
        retrieved_count: data.retrieved_count,
        provider: data.provider,
        run_id: data.run_id,
        usage: data.usage,
      };
      setMessages((curr) => [...curr.slice(0, -1), assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        role: "assistant",
        text: `Unable to retrieve evidence: ${err.message}. Please verify the RAG backend is running on http://127.0.0.1:8000.`,
        status: "error",
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
          <IconButton
            label="Provider settings"
            onClick={() => setShowConfig(!showConfig)}
          >
            <Key size={17} />
          </IconButton>
          <IconButton label="Close assistant" onClick={onClose}>
            <X size={20} />
          </IconButton>
        </div>
      </header>

      {showConfig && (
        <div className="api-toggle-box">
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <strong>LLM Generator Option</strong>
            <Badge tone="blue">{apiKey ? "AIHubMix" : "Offline Engine"}</Badge>
          </div>
          <p
            style={{ margin: "4px 0", color: "var(--muted)", fontSize: "10px" }}
          >
            Leave blank for local evidence excerpts, or enter an AIHubMix API
            key for live GPT-4o-mini synthesis.
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
        <Badge tone="blue">Corpus retrieval</Badge>
      </div>

      <div className="messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            {message.role === "assistant" && (message.status || message.loading) && (
              <div className="message-meta">
                {message.loading ? (
                  <span className="status-pill-qualified">
                    <Loader2 size={12} className="animate-spin" /> Retrieving
                    evidence...
                  </span>
                ) : message.status === "answer" ? (
                  <span className="status-pill-verified">
                    <CheckCircle2 size={12} /> Cited evidence
                  </span>
                ) : message.status === "qualified" ? (
                  <span className="status-pill-qualified">
                    <AlertTriangle size={12} /> Qualified
                  </span>
                ) : (
                  <span className="status-pill-refused">
                    <AlertOctagon size={12} /> {message.status === "error" ? "Request failed" : "Insufficient evidence"}
                  </span>
                )}
                {message.latency_ms !== undefined && (
                  <span className="message-latency">
                    ⚡ {message.latency_ms}ms · {message.retrieved_count}{" "}
                    sources
                  </span>
                )}
              </div>
            )}

            {message.loading ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  color: "var(--muted)",
                }}
              >
                <span>Searching BM25 index & ranking passages...</span>
              </div>
            ) : (
              <div style={{ whiteSpace: "pre-line" }}>{message.text}</div>
            )}

            {message.run_id && <details className="citation-evidence"><summary>Run and usage</summary>
              <div>Run: {message.run_id}</div>
              <div>Input tokens: {message.usage?.input_tokens ?? "unavailable"}; output tokens: {message.usage?.output_tokens ?? "unavailable"}</div>
              <div>Estimated cost: {message.usage?.estimated_cost_usd == null ? "unavailable (rates or usage missing)" : `$${message.usage.estimated_cost_usd.toFixed(6)}`}</div>
            </details>}
            {message.limitations && message.limitations.length > 0 && (
              <div className="answer-limitations">
                <strong>Evidence limitations</strong>
                <ul>
                  {message.limitations.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {message.claims && message.claims.length > 0 && (
              <details className="citation-evidence">
                <summary>Claim-to-source references</summary>
                <ul>
                  {message.claims.map((claim, i) => (
                    <li key={i}>
                      {claim.text}
                      <br />
                      <small>Sources: {claim.citations.join(", ")}</small>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {message.provider && (
              <small>
                Source: {message.provider} · Citation structure checked;
                scientific support requires review.
              </small>
            )}
            {/* Citations Box */}
            {message.citations && message.citations.length > 0 && (
              <div className="citations-box">
                <div className="citations-title">
                  <FileText size={12} /> Cited Sources (
                  {message.citations.length})
                </div>
                <div>
                  {message.citations.map((citation, i) => (
                    <CitationEvidence
                      key={citation.chunk_id || citation.id || i}
                      citation={citation}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="suggestions">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => send(suggestion)}
            disabled={loading}
          >
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
          {loading ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <Send size={18} />
          )}
        </button>
      </form>
      <p className="chat-note">
        Evidence-Grounded RAG Engine · Citation and Numeric Checks
      </p>
    </aside>
  );
}

export default App;
