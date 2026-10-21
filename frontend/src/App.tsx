import { useEffect, useRef, useState, type CSSProperties } from "react";
import { BookOpen, ChevronDown, CircleHelp, KeyRound, Menu, MessageSquare, Plus, Send, Sparkles, Trash2, X } from "lucide-react";
import { changeWorkspace, currentWorkspace, scopedFetch } from "./api";
import { appendMessage, readActiveChat, readChats, saveActiveChat, saveChats, type Chat, type Citation, type Reply } from "./chatHistory";
import { evidenceHighlights } from "./highlights";
import { ModelSettingsPanel } from "./ModelSettingsPanel";
import { generationSettings, selectProvider, PROVIDERS } from "./modelSettings";

const EXAMPLES = [
  "What evidence links ADCY5 to 2-hour glucose?",
  "What does the supplied genetic correlation data say about 2-hour insulin?",
  "What tissue expression evidence is available for PPARG?",
];
const WORKSPACES = [
  { id: "all", label: "All current evidence" },
  { id: "annotations", label: "Annotations and expression" },
  { id: "genetics", label: "Genetic associations" },
];

function Evidence({ citation }: { citation: Citation }) {
  const id = citation.chunk_id || citation.id;
  const [passage, setPassage] = useState<{ content: string; metadata: Record<string, unknown> } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  async function load() {
    if (!id || loading || passage) return;
    setLoading(true);
    setError("");
    try {
      const version = citation.corpus_version ? `?corpus_version=${encodeURIComponent(citation.corpus_version)}` : "";
      const response = await scopedFetch(`/api/evidence/${encodeURIComponent(id)}${version}`);
      if (!response.ok) throw new Error(response.status === 409 ? "Evidence version changed. Ask again to inspect the current source." : "Source passage unavailable.");
      setPassage(await response.json());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Source passage unavailable.");
    } finally {
      setLoading(false);
    }
  }
  return <details className="source" onToggle={event => { if (event.currentTarget.open) void load(); }}>
    <summary><BookOpen size={15} aria-hidden="true" /><span>{citation.source_name || citation.title || "Source"}<small>{citation.collection?.replaceAll("_", " ") || id}</small></span><ChevronDown size={15} aria-hidden="true" /></summary>
    {loading && <p>Loading passage…</p>}
    {error && <p role="alert">{error} <button type="button" onClick={() => void load()}>Retry</button></p>}
    {passage && <div className="source-body"><p>{passage.content}</p><small>{citation.collection}{citation.source_file ? ` · ${citation.source_file}` : ""}</small><details><summary>Source metadata</summary><pre>{JSON.stringify(passage.metadata, null, 2)}</pre></details></div>}
  </details>;
}

const METRIC = /((?:(?:bf_common|pValue|p|beta|rg)\s*=\s*|median\s+)-?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)/gi;
const METRIC_ONLY = /^(?:(?:bf_common|pValue|p|beta|rg)\s*=\s*|median\s+)-?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i;

function HighlightedText({ text }: { text: string }) {
  return <>{text.split(METRIC).map((part, index) =>
    METRIC_ONLY.test(part) ? <strong className="metric" key={index}>{part}</strong> : part
  )}</>;
}

function AnswerView({ reply }: { reply: Reply }) {
  const points = evidenceHighlights(reply.claims);
  const refused = reply.status === "refuse" || reply.status === "refused";
  const status = refused ? "Insufficient evidence" : reply.status === "qualified" ? "Qualified answer" : reply.status === "error" ? "Answer unavailable" : "Evidence answer";
  return <div className="answer">
    <div className={`answer-status ${reply.status}`}>{status}</div>
    {points.length > 0 ? <>
      <div className="highlights-head"><h2>Evidence highlights</h2><span>{points.length} of {reply.claims.length} cited claims</span></div>
      <p className="highlight-note">Excerpts from cited claims. Open the full answer for context.</p>
      <ol className="highlight-list">{points.map((point, index) => <li key={index}>
        <p><HighlightedText text={point.text} /></p>
        <small>{point.citations.map((id) => {
          const sourceIndex = reply.citations.findIndex((citation) => (citation.chunk_id || citation.id) === id);
          return sourceIndex < 0 ? id : `Source ${sourceIndex + 1}`;
        }).join(", ")}</small>
      </li>)}</ol>
      <details className="full-answer"><summary>Read full answer <ChevronDown size={15} aria-hidden="true" /></summary><p className="answer-text">{reply.answer}</p></details>
    </> : <p className="answer-text">{reply.answer}</p>}
    {reply.citations.length > 0 && <div className="sources"><h2>Sources <span>{reply.citations.length}</span></h2>{reply.citations.map((citation, index) => <Evidence key={`${citation.chunk_id || citation.id}-${index}`} citation={{ ...citation, source_name: `${index + 1}. ${citation.source_name || citation.title || "Source"}` }} />)}</div>}
    {reply.limitations.length > 0 && <div className="limitations"><strong><CircleHelp size={15} /> Evidence limits</strong><ul>{reply.limitations.map((limit, index) => <li key={index}>{limit}</li>)}</ul></div>}
    <div className="answer-meta"><span>{reply.retrieved_count} passages retrieved</span><span>{reply.provider || "Offline"}{reply.model ? ` · ${reply.model}` : ""}</span>{reply.latency_s?.total_api != null && <span>{reply.latency_s.total_api.toFixed(1)}s</span>}</div>
  </div>;
}

function HistoryTitle({ title }: { title: string }) {
  const viewport = useRef<HTMLSpanElement>(null);
  const content = useRef<HTMLSpanElement>(null);
  const [overflow, setOverflow] = useState(0);
  useEffect(() => {
    const measure = () => setOverflow(Math.max(0, (content.current?.scrollWidth || 0) - (viewport.current?.clientWidth || 0)));
    measure();
    const observer = new ResizeObserver(measure);
    if (viewport.current) observer.observe(viewport.current);
    if (content.current) observer.observe(content.current);
    return () => observer.disconnect();
  }, [title]);
  const style = { "--marquee-distance": `${overflow}px`, "--marquee-duration": `${Math.max(7, overflow / 22 + 6)}s` } as CSSProperties;
  return <span className={`history-title ${overflow > 1 ? "scrolling" : ""}`} ref={viewport}><span className="history-title-text" ref={content} style={style}>{title}</span></span>;
}

export default function App() {
  const [workspace, setWorkspace] = useState(currentWorkspace());
  const [chats, setChats] = useState<Chat[]>(() => {
    try { return readChats(window.localStorage, workspace); } catch { return []; }
  });
  const [activeId, setActiveId] = useState<string | null>(() => {
    try { return readActiveChat(window.localStorage, workspace, chats); } catch { return null; }
  });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const messages = chats.find(chat => chat.id === activeId)?.messages || [];
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [modelSettings, setModelSettings] = useState(() => selectProvider("aihubmix"));
  const [showKey, setShowKey] = useState(false);
  const [health, setHealth] = useState<"checking" | "ready" | "unavailable">("checking");
  const [sourceCount, setSourceCount] = useState<number | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);
  useEffect(() => {
    try { saveChats(window.localStorage, workspace, chats); setHistoryError(false); }
    catch { setHistoryError(true); }
  }, [chats, workspace]);
  useEffect(() => {
    try { saveActiveChat(window.localStorage, workspace, activeId); } catch { setHistoryError(true); }
  }, [activeId, workspace]);
  useEffect(() => {
    let active = true;
    scopedFetch("/api/health").then(async response => {
      if (!response.ok) throw new Error("API unavailable");
      const data = await response.json();
      if (active) { setHealth("ready"); setSourceCount(data.total_chunks); }
    }).catch(() => { if (active) setHealth("unavailable"); });
    return () => { active = false; };
  }, []);

  async function ask(raw: string) {
    const text = raw.trim();
    if (!text || busy) return;
    let generation;
    try { generation = generationSettings(modelSettings); }
    catch (cause) { setError((cause as Error).message); setShowKey(true); return; }
    const chatId = activeId || crypto.randomUUID();
    setActiveId(chatId);
    setChats(previous => appendMessage(previous, chatId, { role: "user", text }, Date.now()));
    setQuestion(""); setError(""); setBusy(true);
    try {
      const response = await scopedFetch("/api/rag/query", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, top_k: 8, ...generation }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(typeof detail.detail === "string" ? detail.detail : `Request failed (${response.status}).`);
      }
      const reply: Reply = await response.json();
      setChats(previous => appendMessage(previous, chatId, { role: "assistant", reply }, Date.now()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not get a response.");
    } finally { setBusy(false); }
  }

  function newChat() {
    if (busy) return;
    setActiveId(null); setQuestion(""); setError(""); setSidebarOpen(false);
  }

  function selectChat(id: string) {
    if (busy) return;
    setActiveId(id); setQuestion(""); setError(""); setSidebarOpen(false);
  }

  function deleteChat(id: string) {
    if (busy || !window.confirm("Delete this chat from this browser?")) return;
    setChats(previous => previous.filter(chat => chat.id !== id));
    if (activeId === id) setActiveId(null);
  }

  return <div className="app">
    {sidebarOpen && <button className="sidebar-backdrop" type="button" aria-label="Close chat history" onClick={() => setSidebarOpen(false)} />}
    <aside className={`history-sidebar ${sidebarOpen ? "history-open" : ""}`} aria-label="Chat history">
      <div className="history-heading"><strong><MessageSquare size={17} /> Chats</strong><button type="button" className="sidebar-close" aria-label="Close chat history" onClick={() => setSidebarOpen(false)}><X size={18} /></button></div>
      <button type="button" className="history-new" onClick={newChat} disabled={busy}><Plus size={17} /> New chat</button>
      <div className="history-scope">Recent conversations <span>{chats.length}</span></div>
      <nav className="history-list" aria-label="Saved conversations">
        {chats.length === 0 && <p className="history-empty">Your conversations will appear here after you ask a question.</p>}
        {chats.map(chat => <div className={`history-item ${chat.id === activeId ? "selected" : ""}`} key={chat.id}>
          <button type="button" className="history-select" onClick={() => selectChat(chat.id)} disabled={busy} aria-current={chat.id === activeId ? "page" : undefined} title={chat.messages.find(message => message.role === "user")?.text || chat.title}><MessageSquare size={15} /><HistoryTitle title={chat.title} /></button>
          <button type="button" className="history-delete" onClick={() => deleteChat(chat.id)} disabled={busy} aria-label={`Delete chat: ${chat.title}`} title="Delete chat"><Trash2 size={14} /></button>
        </div>)}
      </nav>
      <p className="history-note">Saved only in this browser.{historyError && <span role="alert"> History could not be saved; check browser storage.</span>}</p>
    </aside>
    <header className="topbar"><div className="brand"><button type="button" className="sidebar-toggle" aria-label="Open chat history" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button><span className="brand-mark"><Sparkles size={19} /></span><div><strong>CS46 Evidence Assistant</strong><small>Scientific RAG · client data</small></div></div><div className="header-actions"><span className={`connection ${health}`}>{health === "ready" ? "Data ready" : health === "checking" ? "Checking data" : "Backend unavailable"}</span></div></header>
    <main className="chat-layout"><section className="chat-content" aria-label="Scientific evidence chat">
      {messages.length === 0 ? <div className="welcome"><span className="welcome-icon"><Sparkles size={26} /></span><p className="eyebrow">EVIDENCE-GROUNDED SCIENTIFIC RAG</p><h1>Ask the evidence.</h1><p className="intro">Explore the supplied gene, phenotype, variant and tissue data. Answers include inspectable citations and state when the evidence is insufficient.</p><div className="example-list"><span>Try a question</span>{EXAMPLES.map(example => <button key={example} type="button" onClick={() => void ask(example)} disabled={busy}>{example}<span aria-hidden="true">↗</span></button>)}</div></div> : <div className="conversation">{messages.map((message, index) => message.role === "user" ? <div className="turn user-turn" key={index}><div className="turn-label">You</div><div className="user-bubble">{message.text}</div></div> : <article className="turn assistant-turn" key={index}><div className="turn-label"><span className="assistant-mark"><Sparkles size={13} /></span> Evidence Assistant</div><AnswerView reply={message.reply} /></article>)}{busy && <div className="turn assistant-turn"><div className="turn-label"><span className="assistant-mark"><Sparkles size={13} /></span> Evidence Assistant</div><div className="thinking" role="status">Searching current evidence…</div></div>}<div ref={bottom} /></div>}
      <div className="composer-area"><div className="controls"><label>Evidence scope <select value={workspace} onChange={event => { setWorkspace(event.target.value); changeWorkspace(event.target.value); }} aria-label="Evidence scope">{WORKSPACES.map(option => <option value={option.id} key={option.id}>{option.label}</option>)}</select></label><button type="button" className="key-toggle" onClick={() => setShowKey(value => !value)}><KeyRound size={15} /> {modelSettings.apiKey.trim() ? `${PROVIDERS[modelSettings.provider].label} · key set` : "Model settings · offline"}</button></div><div hidden={!showKey}><ModelSettingsPanel settings={modelSettings} onChange={setModelSettings} busy={busy} /></div><form className="composer" onSubmit={event => { event.preventDefault(); void ask(question); }}><textarea aria-label="Ask a scientific question" placeholder="Ask about a gene, phenotype, tissue or evidence gap…" rows={2} value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void ask(question); } }} /><button type="submit" disabled={!question.trim() || busy} aria-label="Send question"><Send size={19} /></button></form>{error && <p className="request-error" role="alert">{error} <button type="button" onClick={() => void ask(messages.length && messages[messages.length - 1].role === "user" ? (messages[messages.length - 1] as {role: "user"; text: string}).text : question)}>Retry</button></p>}<p className="disclaimer">{sourceCount == null ? "Current client corpus" : `${sourceCount.toLocaleString()} indexed passages`} · Workspace filter is a demonstration, not access control. Verify important claims against the cited source.</p></div>
    </section></main>
  </div>;
}
