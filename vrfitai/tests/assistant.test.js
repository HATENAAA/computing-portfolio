import { test } from "node:test";
import assert from "node:assert/strict";
import { answer, aiConfig } from "../server/assistant.js";
const config = {
  key: "test-secret-never-return",
  base: "https://example.test/v1",
  model: "test-model",
};
const input = { messages: [{ role: "user", content: "怎样开始？" }] };
test("DeepSeek and compatible providers share configurable endpoint", () => {
  const c = aiConfig({
    DEEPSEEK_API_KEY: "x",
    AI_BASE_URL: "https://example.test/v1/",
  });
  assert.equal(c.base, "https://example.test/v1");
  assert.equal(c.key, "x");
  assert.equal(c.model, "deepseek-flash");
});
test("missing key fails explicitly without invoking upstream", async () => {
  await assert.rejects(
    () =>
      answer(input, { ...config, key: "" }, () => assert.fail("must not call")),
    (e) => e.status === 503
  );
});
test("real request shape, secret on server, no implicit record sharing", async () => {
  const result = await answer(input, config, async (url, options) => {
    assert.equal(url, "https://example.test/v1/chat/completions");
    assert.equal(options.headers.Authorization, "Bearer " + config.key);
    const body = JSON.parse(options.body);
    assert.equal(body.model, "test-model");
    assert.equal(body.messages.length, 2);
    assert.match(body.messages[0].content, /null/);
    assert.equal(body.messages[1].content, "怎样开始？");
    return Response.json({
      choices: [{ message: { content: "可以从节奏触点开始。" } }],
    });
  });
  assert.equal(result.message, "可以从节奏触点开始。");
  assert.ok(!JSON.stringify(result).includes(config.key));
});
test("only explicitly supplied summary is added", async () => {
  await answer(
    { ...input, summary: { program: "rhythm", activeSeconds: 30, hits: 5 } },
    config,
    async (url, options) => {
      assert.match(JSON.parse(options.body).messages[0].content, /"hits":5/);
      return Response.json({
        choices: [{ message: { content: "记录了 5 次交互。" } }],
      });
    }
  );
});
test("upstream error text and credentials never reach user", async () => {
  for (const status of [401, 429, 500])
    await assert.rejects(
      () =>
        answer(
          input,
          config,
          async () => new Response("sensitive upstream text", { status })
        ),
      (e) => e.status === 502 && !e.message.includes("sensitive")
    );
});
test("timeout, malformed response and remote HTTP are rejected", async () => {
  await assert.rejects(
    () =>
      answer(input, config, async () => {
        throw new Error("secret");
      }),
    (e) => e.status === 502 && !e.message.includes("secret")
  );
  await assert.rejects(
    () => answer(input, config, async () => Response.json({ choices: [] })),
    (e) => e.status === 502
  );
  await assert.rejects(
    () =>
      answer(input, { ...config, base: "http://remote.test" }, () =>
        assert.fail()
      ),
    /HTTPS/
  );
});
