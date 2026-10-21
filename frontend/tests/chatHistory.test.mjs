import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/chatHistory.ts", import.meta.url), "utf8");
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { appendMessage, readActiveChat, readChats, saveActiveChat, saveChats, summarizeTitle } = await import(`data:text/javascript,${encodeURIComponent(js)}`);

test("history titles keep the scientific topic rather than the whole question", () => {
  assert.equal(summarizeTitle("What evidence links ADCY5 to 2-hour glucose?"), "ADCY5 ↔ 2-hour glucose");
  assert.equal(summarizeTitle("What does the supplied genetic correlation data say about 2-hour insulin?"), "2-hour insulin genetic correlation");
  assert.equal(summarizeTitle("What tissue expression evidence is available for PPARG?"), "PPARG tissue expression");
  assert.equal(summarizeTitle("What genes are associated with 2-hour glucose (2hrG)?"), "2-hour glucose (2hrG) associated genes");
  assert.equal(summarizeTitle("Summarize evidence for PPARG in adipose tissue?"), "PPARG in adipose tissue evidence");
});

function storage() {
  const values = new Map();
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
}

test("conversations persist per evidence scope with answer citations", () => {
  const store = storage();
  const question = { role: "user", text: "What evidence links ADCY5 to 2-hour glucose?" };
  const answer = { role: "assistant", reply: {
    status: "qualified", answer: "Supported by source one.", claims: [{ text: "A claim", citations: ["source-1"] }],
    citations: [{ id: "source-1", source_name: "Client data" }], limitations: [], retrieved_count: 1, provider: "offline",
  } };
  let chats = appendMessage([], "chat-1", question, 1);
  chats = appendMessage(chats, "chat-1", answer, 2);
  saveChats(store, "all", chats);
  saveActiveChat(store, "all", "chat-1");
  assert.deepEqual(readChats(store, "all"), chats);
  assert.equal(readChats(store, "all")[0].messages[1].reply.citations[0].id, "source-1");
  assert.equal(readActiveChat(store, "all", chats), "chat-1");
  store.setItem("cs46-chat-history-v1:all", JSON.stringify([{ ...chats[0], title: question.text }]));
  assert.equal(readChats(store, "all")[0].title, "ADCY5 ↔ 2-hour glucose");
  assert.deepEqual(readChats(store, "genetics"), []);
  assert.equal(readActiveChat(store, "genetics", []), null);
  saveActiveChat(store, "all", null);
  assert.equal(readActiveChat(store, "all", chats), null);
});

test("new chats are newest first and malformed browser data is ignored", () => {
  const store = storage();
  let chats = appendMessage([], "first", { role: "user", text: "First" }, 1);
  chats = appendMessage(chats, "second", { role: "user", text: "Second" }, 2);
  chats = appendMessage(chats, "first", { role: "user", text: "Follow-up" }, 3);
  assert.deepEqual(chats.map(chat => chat.id), ["first", "second"]);
  assert.equal(chats[0].title, "First");
  store.setItem("cs46-chat-history-v1:all", "not JSON");
  assert.deepEqual(readChats(store, "all"), []);
});
