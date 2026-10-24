import express from "express";
import { DatabaseSync } from "node:sqlite";
import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { z } from "zod";
import { programs, getProgram } from "../src/catalog.js";
import { answer, aiConfig } from "./assistant.js";
export function createApp({
  database = ":memory:",
  config = aiConfig(),
  fetcher = fetch,
  logger = null,
} = {}) {
  const app = express(),
    db = new DatabaseSync(database);
  app.disable("x-powered-by");
  db.exec(
    "CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, program TEXT, started TEXT, seconds INTEGER, hits INTEGER, mode TEXT)"
  );
  db.exec("PRAGMA busy_timeout=5000; CREATE INDEX IF NOT EXISTS sessions_started ON sessions(started DESC,id DESC)");
  if (database !== ":memory:") db.exec("PRAGMA journal_mode=WAL");
  app.use((req, res, next) => {
    const requestId = randomUUID(), start = performance.now();
    res.set("X-Request-ID", requestId);
    res.on("finish", () => {
      // Do not log questions, training summaries, query strings or credentials.
      if (logger) {
        try {
          logger({ requestId, method: req.method, route: req.route?.path || "unmatched",
            status: res.statusCode, durationMs: Math.round((performance.now() - start) * 100) / 100 });
        } catch { /* Logging must not interrupt a completed request. */ }
      }
    });
    next();
  });
  app.use((req, res, next) => {
    const origin = req.get("origin");
    if (origin) {
      try {
        const u = new URL(origin);
        if (
          !["localhost", "127.0.0.1", "[::1]"].includes(u.hostname) &&
          u.host !== req.get("host")
        )
          return res.status(403).json({ error: "来源不允许" });
      } catch {
        return res.status(403).json({ error: "来源不允许" });
      }
    }
    res.set("X-Content-Type-Options", "nosniff");
    next();
  });
  app.use(express.json({ limit: "32kb" }));
  app.get("/api/health", (req, res) =>
    res.json({
      status: "ok",
      aiConfigured: Boolean(config.key),
      model: config.model,
    })
  );
  app.get("/api/programs", (req, res) => res.json(programs));
  const session = z
    .object({
      id: z.string().uuid().optional(),
      program: z.enum(["rhythm", "focus", "flow"]),
      startedAt: z.string().datetime(),
      activeSeconds: z.number().int().min(1).max(3600),
      hits: z.number().int().min(0).max(10000),
      mode: z.enum(["desktop", "vr"]),
    })
    .strict();
  app.post("/api/sessions", (req, res) => {
    const r = session.safeParse(req.body);
    if (!r.success) return res.status(400).json({ error: "训练记录格式无效" });
    const x = r.data,
      id = x.id || randomUUID();
    x.startedAt = new Date(x.startedAt).toISOString();
    const existing = db.prepare("SELECT * FROM sessions WHERE id=?").get(id);
    if (existing) {
      const same = existing.program === x.program && Date.parse(existing.started) === Date.parse(x.startedAt) &&
        existing.seconds === x.activeSeconds && existing.hits === x.hits && existing.mode === x.mode;
      if (!same) return res.status(409).json({ error: "同一记录编号的内容不一致，请保留原记录并检查重试内容。" });
      return res.json(existing);
    }
    db.prepare("INSERT INTO sessions VALUES(?,?,?,?,?,?)").run(
      id,
      x.program,
      x.startedAt,
      x.activeSeconds,
      x.hits,
      x.mode
    );
    res.status(201).json({ id });
  });
  app.get("/api/sessions", (req, res) =>
    res.json(db.prepare("SELECT * FROM sessions ORDER BY started DESC").all())
  );
  const pageQuery = z.object({
    limit: z.coerce.number().int().min(1).max(100).default(20),
    offset: z.coerce.number().int().min(0).max(1000000).default(0),
    program: z.enum(["rhythm", "focus", "flow"]).optional(),
    mode: z.enum(["desktop", "vr"]).optional(),
  }).strict();
  app.get("/api/session-page", (req, res) => {
    const parsed = pageQuery.safeParse(req.query);
    if (!parsed.success) return res.status(400).json({ error: "分页或筛选参数无效" });
    const {limit, offset, program, mode} = parsed.data;
    const clauses = [], values = [];
    if (program) { clauses.push("program=?"); values.push(program); }
    if (mode) { clauses.push("mode=?"); values.push(mode); }
    const where = clauses.length ? " WHERE " + clauses.join(" AND ") : "";
    const {total} = db.prepare("SELECT COUNT(*) AS total FROM sessions" + where).get(...values);
    const items = db.prepare("SELECT * FROM sessions" + where + " ORDER BY started DESC,id DESC LIMIT ? OFFSET ?")
      .all(...values, limit, offset);
    res.json({items, total, limit, offset});
  });
  const statsQuery = z.object({
    days: z.coerce.number().int().min(1).max(90).default(7),
    end: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  }).strict();
  app.get("/api/stats", (req, res) => {
    const parsed = statsQuery.safeParse(req.query);
    if (!parsed.success) return res.status(400).json({ error: "统计参数无效" });
    const {days} = parsed.data, end = parsed.data.end || new Date().toISOString().slice(0,10);
    const endMs = Date.parse(end + "T00:00:00Z");
    if (!Number.isFinite(endMs) || new Date(endMs).toISOString().slice(0,10) !== end)
      return res.status(400).json({ error: "统计日期无效" });
    const startMs = endMs - (days - 1) * 86400000;
    const start = new Date(startMs).toISOString(), stop = new Date(endMs + 86400000).toISOString();
    const allTime = db.prepare("SELECT COUNT(*) AS sessions, COALESCE(SUM(seconds),0) AS seconds, COALESCE(SUM(hits),0) AS hits FROM sessions").get();
    const rows = db.prepare("SELECT substr(started,1,10) AS day, COUNT(*) AS sessions, SUM(seconds) AS seconds, SUM(hits) AS hits FROM sessions WHERE started>=? AND started<? GROUP BY day ORDER BY day")
      .all(start, stop);
    const byDay = new Map(rows.map(row => [row.day, row]));
    const daily = Array.from({length: days}, (_, i) => {
      const day = new Date(startMs + i * 86400000).toISOString().slice(0,10);
      return byDay.get(day) || {day, sessions: 0, seconds: 0, hits: 0};
    });
    res.json({timezone: "UTC", allTime, daily});
  });
  app.get("/api/sessions/export", (req, res) => {
    const rows = db
      .prepare("SELECT * FROM sessions ORDER BY started DESC")
      .all();
    res
      .attachment("vrfitai-sessions.csv")
      .type("text/csv")
      .send(
        "\uFEFF课程,开始时间,有效秒数,交互命中,模式\n" +
          rows
            .map((x) =>
              [
                getProgram(x.program).title,
                x.started,
                x.seconds,
                x.hits,
                x.mode,
              ].join(",")
            )
            .join("\n")
      );
  });
  const msg = z
    .object({
      role: z.enum(["user", "assistant"]),
      content: z.string().trim().min(1).max(2000),
    })
    .strict();
  const chat = z
    .object({
      messages: z.array(msg).min(1).max(12),
      summary: z
        .object({
          program: z.enum(["rhythm", "focus", "flow"]),
          activeSeconds: z.number().int().min(0).max(3600),
          hits: z.number().int().min(0).max(10000),
        })
        .strict()
        .optional(),
    })
    .strict();
  const requests = new Map();
  app.post("/api/chat", async (req, res) => {
    const r = chat.safeParse(req.body);
    if (!r.success || r.data.messages.at(-1)?.role !== "user")
      return res.status(400).json({ error: "对话格式无效" });
    const now = Date.now(),
      key = req.ip;
    for (const [k, v] of requests) if (v.reset < now) requests.delete(k);
    const bucket = requests.get(key) || { count: 0, reset: now + 60000 };
    bucket.count++;
    requests.set(key, bucket);
    if (bucket.count > 10)
      return res
        .status(429)
        .json({ error: "请稍后再发送，每分钟最多 10 次。" });
    try {
      res.json(await answer(r.data, config, fetcher));
    } catch (e) {
      res
        .status(e.status || 502)
        .json({
          error: e.status ? e.message : "AI 配置或响应异常，请检查服务端。",
        });
    }
  });
  app.use("/api", (req, res) => res.status(404).json({ error: "接口不存在" }));
  app.use(express.static(resolve("dist")));
  app.use((err, req, res, next) =>
    res
      .status(err.status === 413 ? 413 : 400)
      .json({ error: err.status === 413 ? "请求内容过大" : "请求格式无效" })
  );
  return { app, close: () => db.close() };
}
