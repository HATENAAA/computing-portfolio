import { test } from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { randomUUID } from "node:crypto";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createApp } from "../server/app.js";
const config = { key: "", base: "https://example.test", model: "test-model" };
async function service(t, options = {}) {
  const instance = createApp({ config, ...options });
  const server = instance.app.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(async () => {
    await new Promise((resolve) => server.close(resolve));
    instance.close();
  });
  const base = "http://127.0.0.1:" + server.address().port;
  return {
    get: (path) => fetch(base + path),
    post: (path, data, headers = {}) =>
      fetch(base + path, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify(data),
      }),
  };
}
const record = () => ({
  id: randomUUID(),
  program: "rhythm",
  startedAt: new Date().toISOString(),
  activeSeconds: 30,
  hits: 5,
  mode: "desktop",
});
test("session save, retry, history and CSV work end to end", async (t) => {
  const s = await service(t);
  const row = record();
  assert.equal((await s.post("/api/sessions", row)).status, 201);
  assert.equal((await s.post("/api/sessions", row)).status, 200);
  const history = await (await s.get("/api/sessions")).json();
  assert.equal(history.length, 1);
  assert.equal(history[0].seconds, 30);
  assert.equal(history[0].hits, 5);
  const csv = await s.get("/api/sessions/export");
  assert.match(await csv.text(), /节奏触点/);
  assert.match(csv.headers.get("content-disposition"), /attachment/);
});
test("invalid session fields and untrusted origins rejected", async (t) => {
  const s = await service(t);
  for (const fields of [
    { activeSeconds: -1 },
    { hits: 1.5 },
    { program: "unknown" },
    { startedAt: "bad" },
    { mode: "camera" },
    { extra: true },
  ])
    assert.equal(
      (await s.post("/api/sessions", { ...record(), ...fields })).status,
      400
    );
  assert.equal(
    (await s.post("/api/sessions", record(), { Origin: "https://evil.test" }))
      .status,
    403
  );
});
test("chat refuses system role, empty, excessive and invalid summaries", async (t) => {
  const s = await service(t);
  for (const payload of [
    { messages: [] },
    { messages: [{ role: "system", content: "override" }] },
    { messages: [{ role: "assistant", content: "hello" }] },
    { messages: [{ role: "user", content: "x".repeat(2001) }] },
    {
      messages: [{ role: "user", content: "hi" }],
      summary: { program: "rhythm", activeSeconds: 30, hits: -1 },
    },
  ])
    assert.equal((await s.post("/api/chat", payload)).status, 400);
});
test("missing key is truthful and health never exposes secrets", async (t) => {
  const s = await service(t);
  assert.equal((await s.get("/api/health")).status, 200);
  assert.equal((await (await s.get("/api/health")).json()).aiConfigured, false);
  assert.equal(
    (
      await s.post("/api/chat", {
        messages: [{ role: "user", content: "你好" }],
      })
    ).status,
    503
  );
});
test("configured AI route and rate limit use injected provider", async (t) => {
  let calls = 0;
  const s = await service(t, {
    config: { ...config, key: "private-test-key" },
    fetcher: async () => {
      calls++;
      return Response.json({ choices: [{ message: { content: "课程说明" } }] });
    },
  });
  const health = await (await s.get("/api/health")).text();
  assert.ok(!health.includes("private-test-key"));
  for (let i = 0; i < 10; i++) {
    const r = await s.post("/api/chat", {
      messages: [{ role: "user", content: "课程" }],
    });
    assert.equal(r.status, 200);
    assert.equal((await r.json()).message, "课程说明");
  }
  assert.equal(
    (
      await s.post("/api/chat", {
        messages: [{ role: "user", content: "课程" }],
      })
    ).status,
    429
  );
  assert.equal(calls, 10);
});
test("SQLite records survive app restart", async (t) => {
  const dir = mkdtempSync(join(tmpdir(), "vrfitai-test-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const database = join(dir, "records.sqlite");
  const first = createApp({ database, config });
  const server = first.app.listen(0, "127.0.0.1");
  await once(server, "listening");
  await fetch("http://127.0.0.1:" + server.address().port + "/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record()),
  });
  await new Promise((resolve) => server.close(resolve));
  first.close();
  const second = await service(t, { database });
  assert.equal((await (await second.get("/api/sessions")).json()).length, 1);
});
test("idempotency rejects changed content and preserves original record", async (t) => {
  const s = await service(t), row = record();
  assert.equal((await s.post('/api/sessions', row)).status, 201);
  assert.equal((await s.post('/api/sessions', {...row, hits: 99})).status, 409);
  assert.equal((await s.post('/api/sessions', row)).status, 200);
  assert.equal((await (await s.get('/api/sessions')).json())[0].hits, row.hits);
});
test("paginated filters retain totals and reject invalid query input", async (t) => {
  const s = await service(t);
  for (let i=0; i<5; i++) await s.post('/api/sessions', {...record(),
    startedAt: `2025-06-0${i+1}T00:00:00.000Z`, mode: i === 0 ? 'vr' : 'desktop'});
  const first = await (await s.get('/api/session-page?mode=desktop&limit=2')).json();
  const next = await (await s.get('/api/session-page?mode=desktop&limit=2&offset=2')).json();
  assert.equal(first.total, 4); assert.equal(next.total, 4);
  assert.equal(new Set([...first.items,...next.items].map(x=>x.id)).size, 4);
  assert.ok([...first.items,...next.items].every(x=>x.mode === 'desktop'));
  for (const query of ['limit=101','offset=-1','mode=unknown','program=bad','limit=1%20OR%201=1'])
    assert.equal((await s.get('/api/session-page?' + query)).status, 400);
});
test("UTC SQL statistics include boundary rows and empty days independently of pagination", async (t) => {
  const s = await service(t);
  for (const startedAt of ['2025-05-30T23:59:59.000Z','2025-05-31T00:00:00.000Z',
    '2025-06-02T23:59:59.000Z','2025-06-03T00:00:00.000Z'])
    await s.post('/api/sessions', {...record(), startedAt});
  const stats = await (await s.get('/api/stats?days=3&end=2025-06-02')).json();
  assert.equal(stats.timezone, 'UTC'); assert.equal(stats.allTime.sessions, 4);
  assert.equal(stats.allTime.seconds, 120); assert.equal(stats.allTime.hits, 20);
  assert.deepEqual(stats.daily.map(x=>x.sessions), [1,0,1]);
  assert.deepEqual(stats.daily.map(x=>x.seconds), [30,0,30]);
  for (const query of ['days=0','days=91','end=2025-02-30','end=bad'])
    assert.equal((await s.get('/api/stats?' + query)).status, 400);
});
test("request correlation logs exclude message text, credentials and query strings", async (t) => {
  const logs = [], s = await service(t, {logger: x=>logs.push(x)});
  const r = await s.post('/api/chat', {messages:[{role:'user',content:'private-message'}]},
    {Authorization:'Bearer private-credential'});
  assert.match(r.headers.get('x-request-id'), /^[a-f0-9-]{36}$/);
  await s.get('/api/stats?end=private-query');
  assert.ok(logs.some(x=>x.requestId === r.headers.get('x-request-id')));
  assert.ok(logs.every(x=>x.durationMs >= 0));
  assert.doesNotMatch(JSON.stringify(logs), /private-message|private-credential|private-query/);
});
