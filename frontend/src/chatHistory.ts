export type Citation = {
  id?: string; chunk_id?: string; source_name?: string; title?: string;
  source_file?: string; corpus_version?: string; collection?: string;
};
export type Claim = { text: string; citations: string[] };
export type Reply = {
  status: string; answer: string; claims: Claim[]; citations: Citation[];
  limitations: string[]; retrieved_count: number; provider: string;
  model?: string | null;
  latency_s?: Record<string, number>; usage?: { api_calls?: number; estimated_cost_usd?: number | null };
};
export type Message = { role: "user"; text: string } | { role: "assistant"; reply: Reply };
export type Chat = { id: string; title: string; updatedAt: number; messages: Message[] };

const PREFIX = "cs46-chat-history-v1:";
const ACTIVE_PREFIX = "cs46-active-chat-v1:";
const MAX_CHATS = 20;
type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function summarizeTitle(question: string): string {
  const text = question.replace(/\s+/g, " ").trim().replace(/[?.!。？！]+$/, "");
  if (!text) return "Untitled chat";
  const linked = text.match(/^what evidence links (.+?) to (.+)$/i);
  if (linked) return `${linked[1]} ↔ ${linked[2]}`;
  const genes = text.match(/^what genes are associated with (.+)$/i);
  if (genes) return `${genes[1]} associated genes`;
  const correlation = text.match(/^what does (?:the supplied )?genetic correlation data say about (.+)$/i);
  if (correlation) return `${correlation[1]} genetic correlation`;
  const expression = text.match(/^what (?:tissue )?expression evidence is available for (.+)$/i);
  if (expression) return `${expression[1]} tissue expression`;
  const evidence = text.match(/^(?:what evidence is available|summarize (?:the )?evidence|show (?:me )?(?:the )?evidence) (?:for|on|about) (.+)$/i);
  if (evidence) return `${evidence[1]} evidence`;
  const cleaned = text
    .replace(/^(?:请问|请帮我|帮我|我想知道)\s*/, "")
    .replace(/^(?:please |could you |can you |help me |请|帮我)?(?:summarize|explain|describe|show|compare|tell me about|总结|解释|比较)\s*/i, "")
    .replace(/^(?:what|which|how|why)\s+(?:is|are|does|do|can|did)\s+(?:the |our |this |these )?/i, "")
    .replace(/^(?:the |our |this |these )?(?:available |supplied )?evidence (?:for|on|about) /i, "")
    .replace(/^(?:about|regarding|for)\s+/i, "")
    .trim();
  const phrase = cleaned.split(/[,;，；]|\s+(?:and|but)\s+(?=(?:what|how|why)\b)/i)[0].trim() || text;
  const words = phrase.split(" ");
  if (words.length > 11) return `${words.slice(0, 11).join(" ")}…`;
  const limit = /[\u3400-\u9fff]/.test(phrase) ? 32 : 90;
  return phrase.length > limit ? `${phrase.slice(0, limit)}…` : phrase;
}

function isMessage(value: unknown): value is Message {
  if (!value || typeof value !== "object") return false;
  const message = value as Record<string, unknown>;
  if (message.role === "user") return typeof message.text === "string";
  if (message.role !== "assistant" || !message.reply || typeof message.reply !== "object") return false;
  const reply = message.reply as Record<string, unknown>;
  return typeof reply.answer === "string" && typeof reply.status === "string"
    && Array.isArray(reply.claims) && reply.claims.every((claim: unknown) => claim && typeof claim === "object"
      && typeof (claim as Claim).text === "string" && Array.isArray((claim as Claim).citations))
    && Array.isArray(reply.citations) && reply.citations.every((citation: unknown) => citation && typeof citation === "object")
    && Array.isArray(reply.limitations) && reply.limitations.every((limit: unknown) => typeof limit === "string")
    && typeof reply.retrieved_count === "number";
}

export function readChats(store: Pick<Store, "getItem">, workspace: string): Chat[] {
  try {
    const parsed: unknown = JSON.parse(store.getItem(PREFIX + workspace) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((chat): chat is Chat => chat && typeof chat === "object"
      && typeof chat.id === "string" && typeof chat.title === "string"
      && typeof chat.updatedAt === "number" && Array.isArray(chat.messages)
      && chat.messages.every(isMessage))
      .map(chat => ({ ...chat, title: summarizeTitle(chat.messages.find(message => message.role === "user")?.text || chat.title) }))
      .sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX_CHATS);
  } catch { return []; }
}

export function saveChats(store: Pick<Store, "setItem">, workspace: string, chats: Chat[]) {
  store.setItem(PREFIX + workspace, JSON.stringify(chats.slice(0, MAX_CHATS)));
}

export function readActiveChat(store: Pick<Store, "getItem">, workspace: string, chats: Chat[]): string | null {
  try {
    const id = store.getItem(ACTIVE_PREFIX + workspace);
    return chats.some(chat => chat.id === id) ? id : null;
  } catch { return null; }
}

export function saveActiveChat(store: Store, workspace: string, id: string | null) {
  if (id) store.setItem(ACTIVE_PREFIX + workspace, id);
  else store.removeItem(ACTIVE_PREFIX + workspace);
}

export function appendMessage(chats: Chat[], id: string, message: Message, now: number): Chat[] {
  const existing = chats.find(chat => chat.id === id);
  const title = message.role === "user" ? summarizeTitle(message.text) : "Untitled chat";
  const updated: Chat = existing
    ? { ...existing, updatedAt: now, messages: [...existing.messages, message] }
    : { id, title, updatedAt: now, messages: [message] };
  return [updated, ...chats.filter(chat => chat.id !== id)].slice(0, MAX_CHATS);
}
