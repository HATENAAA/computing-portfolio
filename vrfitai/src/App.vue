<script setup>
import {
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  watch,
  defineAsyncComponent,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { programs, getProgram } from "./catalog.js";
import { TrainingSession } from "./session.js";
const FitnessScene = defineAsyncComponent(() =>
  import("./components/FitnessScene.vue")
);
const route = useRoute(),
  router = useRouter();
const page = computed(() => route.path);
const chosen = ref("rhythm"),
  duration = ref(60),
  records = ref([]),
  analytics = ref({allTime: {sessions: 0, seconds: 0, hits: 0}, daily: []}),
  loadingRecords = ref(false),
  status = ref(""),
  health = ref({ aiConfigured: false }),
  state = ref("idle"),
  seconds = ref(0),
  hits = ref(0),
  xr = ref(false),
  pendingSave = ref(null),
  saving = ref(false),
  message = ref(""),
  busy = ref(false),
  chat = ref([]),
  includeSummary = ref(false),
  chatError = ref("");
const engine = new TrainingSession();
let timer,
  usedXR = false;
const selected = computed(() => getProgram(chosen.value));
const remaining = computed(() => Math.max(0, duration.value - seconds.value));
const totalMinutes = computed(() =>
  (analytics.value.allTime.seconds / 60).toFixed(1)
);
const sevenDays = computed(() =>
  analytics.value.daily.map(d => ({label: d.day.slice(5), value: d.seconds / 60}))
);
const active = computed(() => state.value === "running");
async function request(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}
async function loadRecords() {
  const [page, stats] = await Promise.all([request("/api/session-page"), request("/api/stats")]);
  records.value = page.items;
  analytics.value = stats;
}
async function loadMoreRecords() {
  if (loadingRecords.value) return;
  loadingRecords.value = true;
  try {
    const page = await request(`/api/session-page?offset=${records.value.length}`);
    const known = new Set(records.value.map(r => r.id));
    records.value.push(...page.items.filter(r => !known.has(r.id)));
  } catch (e) { status.value = e.message; }
  finally { loadingRecords.value = false; }
}
onMounted(async () => {
  try {
    health.value = await request("/api/health");
    await loadRecords();
  } catch (e) {
    status.value = "服务连接失败：" + e.message;
  }
  timer = setInterval(() => {
    seconds.value = Math.floor(engine.milliseconds() / 1000);
    hits.value = engine.hits;
    if (engine.state === "running" && engine.milliseconds() >= engine.duration)
      finish();
  }, 150);
  document.addEventListener("visibilitychange", visibility);
});
onBeforeUnmount(() => {
  clearInterval(timer);
  document.removeEventListener("visibilitychange", visibility);
});
function visibility() {
  if (document.hidden && active.value) {
    engine.pause();
    state.value = engine.state;
  }
}
function select(p) {
  if (["running", "paused"].includes(state.value)) return;
  chosen.value = p.id;
  duration.value = p.seconds;
}
function start() {
  if (pendingSave.value) {
    status.value = "请先保存上一条训练记录。";
    return;
  }
  if (engine.state === "paused") {
    engine.resume();
  } else if (engine.state !== "running") {
    engine.start(duration.value);
    seconds.value = 0;
    hits.value = 0;
    usedXR = xr.value;
  }
  state.value = engine.state;
  status.value = "";
  router.push("/studio");
}
function toggle() {
  if (engine.state === "running") engine.pause();
  else if (engine.state === "paused") engine.resume();
  else {
    start();
    return;
  }
  state.value = engine.state;
}
function onHit() {
  engine.hit();
  hits.value = engine.hits;
}
function onXR(value) {
  xr.value = value;
  if (value) usedXR = true;
  if (!value && active.value) toggle();
}
async function finish() {
  const result = engine.finish();
  if (!result) return;
  state.value = engine.state;
  seconds.value = result.activeSeconds;
  if (result.activeSeconds < 1) {
    status.value = "练习不足 1 秒，未保存记录。";
    return;
  }
  pendingSave.value = {
    ...result,
    id: crypto.randomUUID(),
    program: chosen.value,
    mode: usedXR ? "vr" : "desktop",
  };
  await save();
}
async function save() {
  if (!pendingSave.value || saving.value) return;
  saving.value = true;
  try {
    await request("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pendingSave.value),
    });
    pendingSave.value = null;
    await loadRecords();
    status.value = "训练记录已保存。";
  } catch (e) {
    status.value = "保存失败，可重试：" + e.message;
  } finally {
    saving.value = false;
  }
}
watch(page, (value) => {
  if (value !== "/studio" && active.value) toggle();
});
async function send() {
  const text = message.value.trim();
  if (!text || busy.value) return;
  busy.value = true;
  chatError.value = "";
  const messages = [...chat.value, { role: "user", content: text }].slice(-12);
  while (
    messages.reduce((n, m) => n + m.content.length, 0) > 7000 &&
    messages.length > 1
  )
    messages.shift();
  const last = records.value[0];
  const payload = { messages };
  if (includeSummary.value && last)
    payload.summary = {
      program: last.program,
      activeSeconds: last.seconds,
      hits: last.hits,
    };
  try {
    const r = await request("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    chat.value = [...messages, { role: "assistant", content: r.message }];
    message.value = "";
  } catch (e) {
    chatError.value = e.message;
  } finally {
    busy.value = false;
  }
}
function ask(text) {
  message.value = text;
  router.push("/assistant");
}
</script>
<template>
  <div class="shell">
    <aside class="sidebar">
      <RouterLink to="/" class="logo"
        ><span>✳</span> VRFit<span class="logo-ai">AI</span></RouterLink
      >
      <p class="sidebar-caption">MOVE INTO YOUR SPACE</p>
      <nav>
        <RouterLink to="/" :class="{ current: page === '/' }"
          >◫ <span>训练概览</span></RouterLink
        ><RouterLink to="/studio" :class="{ current: page === '/studio' }"
          >◎ <span>沉浸训练</span></RouterLink
        ><RouterLink to="/records" :class="{ current: page === '/records' }"
          >▤ <span>训练记录</span></RouterLink
        ><RouterLink to="/assistant" :class="{ current: page === '/assistant' }"
          >✧ <span>AI 助手</span></RouterLink
        >
      </nav>
      <div class="sidebar-bottom">
        <b>每次一点，找到节奏。</b>
        <p>桌面与 VR，都有你的空间。</p>
        <span class="local-dot">本机个人空间</span>
      </div>
    </aside>
    <main>
      <header>
        <span>{{
          page === "/studio"
            ? "沉浸训练 / STUDIO"
            : page === "/records"
            ? "训练记录 / HISTORY"
            : page === "/assistant"
            ? "AI 助手 / COACH"
            : "训练概览 / OVERVIEW"
        }}</span
        ><span class="profile">JW <small>Jiawei 的训练空间</small></span>
      </header>
      <template v-if="page === '/'"
        ><section class="greeting">
          <p class="eyebrow">LET’S FIND YOUR RHYTHM</p>
          <h1>今天，也为自己动一下。</h1>
          <p>进入沉浸空间，让专注与节奏一起发生。</p>
        </section>
        <div class="overview-grid">
          <section class="hero">
            <div class="hero-copy">
              <span class="pill">本次精选 · {{ selected.tag }}</span>
              <h2>{{ selected.title }}<br />从一次触点开始。</h2>
              <p>{{ selected.subtitle }}。选择适合你的时长，随时可以暂停。</p>
              <button class="primary" @click="start">
                开始训练 <span>↗</span>
              </button>
            </div>
            <div class="orbital-art" aria-hidden="true">
              <div class="orbit o1"></div>
              <div class="orbit o2"></div>
              <div class="orbit o3"></div>
              <div class="core">✳</div>
              <span class="art-caption">YOUR PACE. YOUR SPACE.</span>
            </div>
            <div class="hero-footer">
              <span>◎ 桌面 / WebXR</span><span>{{ duration }} 秒体验</span
              ><span>轻量交互训练</span>
            </div>
          </section>
          <section class="card weekly">
            <div class="section-head">
              <h3>最近 7 天（UTC）</h3>
              <span>有效分钟</span>
            </div>
            <div class="weekly-value">
              {{ totalMinutes }}<small>累计训练分钟</small>
            </div>
            <div class="chart">
              <div v-for="(d, i) in sevenDays" :key="i" class="bar-column">
                <span>{{ d.value.toFixed(1) }}</span>
                <div
                  class="bar"
                  :style="{
                    height: Math.max(3, Math.min(110, d.value * 12)) + 'px',
                  }"
                ></div>
                <small>{{ d.label }}</small>
              </div>
            </div>
            <p>
              {{
                records.length
                  ? `已完成 ${analytics.allTime.sessions} 次训练，保持自己的节奏。`
                  : "完成第一次训练后，这里会记录你的进展。"
              }}
            </p>
          </section>
        </div>
        <div class="section-head program-heading">
          <h2>选择你的训练</h2>
          <span>从轻量体验开始</span>
        </div>
        <div class="program-grid">
          <button
            v-for="(p, i) in programs"
            :key="p.id"
            class="program-card"
            :class="{ selected: chosen === p.id }"
            @click="select(p)"
          >
            <div class="program-visual" :style="{ '--tone': p.color }">
              <span>{{ ["◎", "✧", "◒"][i] }}</span
              ><small>0{{ i + 1 }}</small>
            </div>
            <div class="program-details">
              <span>{{ p.tag }}</span>
              <h3>{{ p.title }} <b>↗</b></h3>
              <p>{{ p.subtitle }}</p>
            </div>
          </button>
        </div>
        <section class="coach-banner">
          <span class="coach-symbol">✧</span>
          <div>
            <h3>让 AI 助手陪你开始</h3>
            <p>了解课程、解读训练记录，或找到下一步。</p>
          </div>
          <button @click="ask('我第一次使用 VRFitAI，应该怎样开始？')">
            问问助手 ↗
          </button>
        </section></template
      >
      <template v-else-if="page === '/studio'"
        ><section class="greeting compact">
          <p class="eyebrow">IMMERSIVE STUDIO</p>
          <h1>{{ selected.title }}</h1>
          <p>{{ selected.description }}</p>
        </section>
        <div class="studio-grid">
          <div class="stage">
            <FitnessScene
              :active="active"
              :remaining="remaining"
              :program="chosen"
              @hit="onHit"
              @xr="onXR"
              @toggle="toggle"
            />
          </div>
          <section class="card session-controls">
            <span class="pill">{{
              state === "running"
                ? "正在训练"
                : state === "paused"
                ? "已暂停"
                : state === "finished"
                ? "本次已结束"
                : "准备开始"
            }}</span>
            <div class="timer">
              {{ String(Math.floor(remaining / 60)).padStart(2, "0") }}:{{
                String(remaining % 60).padStart(2, "0")
              }}
            </div>
            <p>剩余时间</p>
            <div class="hit-stat">
              <strong>{{ hits }}</strong
              ><span>交互命中次数</span>
            </div>
            <label
              >训练课程<select
                v-model="chosen"
                :disabled="['running', 'paused'].includes(state)"
              >
                <option v-for="p in programs" :value="p.id">
                  {{ p.title }}
                </option>
              </select></label
            ><label
              >体验时长<select
                v-model.number="duration"
                :disabled="['running', 'paused'].includes(state)"
              >
                <option :value="30">30 秒</option>
                <option :value="60">1 分钟</option>
                <option :value="120">2 分钟</option>
                <option :value="300">5 分钟</option>
              </select></label
            ><button
              v-if="!['running', 'paused'].includes(state)"
              class="primary"
              :disabled="!!pendingSave"
              @click="start"
            >
              开始训练 ↗</button
            ><template v-else
              ><button class="primary" @click="toggle">
                {{ active ? "暂停训练" : "继续训练" }}</button
              ><button class="secondary" @click="finish">
                结束并保存
              </button></template
            ><button
              v-if="pendingSave"
              class="secondary"
              :disabled="saving"
              @click="save"
            >
              重试保存
            </button>
            <p class="micro">
              记录计时与交互命中，不测量姿势或运动强度。体验不适时请停止。
            </p>
          </section>
        </div></template
      >
      <template v-else-if="page === '/records'"
        ><section class="greeting">
          <p class="eyebrow">YOUR TRAINING JOURNAL</p>
          <h1>每一次开始，都有记录。</h1>
          <p>回顾自己的练习节奏。</p>
        </section>
        <div class="stat-grid">
          <div class="card">
            <span>累计次数</span><strong>{{ analytics.allTime.sessions }}</strong>
          </div>
          <div class="card">
            <span>有效分钟</span><strong>{{ totalMinutes }}</strong>
          </div>
          <div class="card">
            <span>交互命中</span
            ><strong>{{ analytics.allTime.hits }}</strong>
          </div>
        </div>
        <section class="card">
          <div class="section-head">
            <h3>训练历史</h3>
            <a class="text-link" href="/api/sessions/export">导出 CSV ↗</a>
          </div>
          <div v-if="!records.length" class="empty">
            还没有训练记录。<button @click="router.push('/studio')">
              开启第一次练习 ↗
            </button>
          </div>
          <div v-else class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>课程</th>
                  <th>开始时间</th>
                  <th>有效时长</th>
                  <th>交互命中</th>
                  <th>模式</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in records" :key="r.id">
                  <td>{{ getProgram(r.program)?.title }}</td>
                  <td>{{ new Date(r.started).toLocaleString() }}</td>
                  <td>{{ r.seconds }} 秒</td>
                  <td>{{ r.hits }}</td>
                  <td>{{ r.mode === "vr" ? "VR" : "桌面" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <button v-if="records.length < analytics.allTime.sessions" class="secondary"
            :disabled="loadingRecords" @click="loadMoreRecords">
            {{ loadingRecords ? '正在读取…' : '加载更多记录' }}
          </button>
        </section></template
      >
      <template v-else-if="page === '/assistant'"
        ><section class="greeting compact">
          <p class="eyebrow">A LITTLE GUIDANCE, A BETTER START</p>
          <h1>你的 AI 训练助手</h1>
          <p>了解体验方式，回顾训练，找到下一次开始的方向。</p>
        </section>
        <div class="assistant-grid">
          <section class="card chat-card">
            <div class="section-head">
              <h3>✧ VRFitAI 助手</h3>
              <span>{{
                health.aiConfigured ? "服务已配置" : "等待连接 AI 服务"
              }}</span>
            </div>
            <div class="messages" aria-live="polite">
              <div v-if="!chat.length" class="chat-welcome">
                <div>✧</div>
                <h3>今天想从哪里开始？</h3>
                <p>我可以解释课程与训练记录。对话通过你配置的 AI 服务处理。</p>
                <button @click="message = '三个训练课程有什么区别？'">
                  三个训练课程有什么区别？</button
                ><button @click="message = '怎样在 VR 设备上使用训练空间？'">
                  怎样进入 VR 训练？
                </button>
              </div>
              <article
                v-for="(m, i) in chat"
                :key="i"
                :class="['bubble', m.role]"
              >
                <small>{{ m.role === "user" ? "你" : "AI 助手" }}</small>
                <p>{{ m.content }}</p>
              </article>
              <p v-if="busy" class="muted">正在思考…</p>
            </div>
            <p v-if="chatError" class="error" role="alert">{{ chatError }}</p>
            <form @submit.prevent="send">
              <label class="summary-opt"
                ><input
                  type="checkbox"
                  v-model="includeSummary"
                  :disabled="!records.length"
                />附带最近一次训练摘要</label
              >
              <div class="chat-input">
                <textarea
                  v-model="message"
                  aria-label="发送给 AI 助手的消息"
                  placeholder="问问课程、操作方法或训练记录…"
                  maxlength="2000"
                  rows="2"
                  required
                ></textarea
                ><button class="primary" :disabled="busy || !message.trim()">
                  {{ busy ? "发送中" : "发送 ↑" }}
                </button>
              </div>
            </form>
          </section>
          <section class="card coach-notes">
            <span class="coach-symbol">✧</span>
            <h3>由你决定分享什么</h3>
            <p>
              默认只发送本次对话。选中摘要后，才会附带最近一次的课程、有效秒数与命中次数。
            </p>
            <p>助手可以帮助理解训练数据，不提供伤病诊断或治疗建议。</p>
            <div class="connection">
              <b>{{
                health.aiConfigured ? "AI 接口已配置" : "尚未配置 AI 密钥"
              }}</b>
              <p>
                {{
                  health.aiConfigured
                    ? "消息会发送到你配置的服务。"
                    : "请在本机项目 .env 中设置 AI_API_KEY，然后重新启动。密钥不会进入网页。"
                }}
              </p>
            </div>
            <button
              class="secondary"
              @click="
                chat = [];
                chatError = '';
              "
            >
              清空当前对话
            </button>
          </section>
        </div></template
      >
      <p v-if="status" class="status" role="status">{{ status }}</p>
      <footer>
        <span>VRFitAI · 沉浸式交互训练作品</span
        ><span>YOUR PACE. YOUR SPACE.</span>
      </footer>
    </main>
  </div>
</template>
