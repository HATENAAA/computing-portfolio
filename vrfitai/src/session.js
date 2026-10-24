export class TrainingSession {
  constructor(now = () => performance.now()) {
    this.now = now;
    this.state = "idle";
    this.elapsed = 0;
    this.hits = 0;
    this.startedAt = null;
  }
  start(duration) {
    if (this.state === "running" || this.state === "paused") return;
    this.duration = duration * 1000;
    this.elapsed = 0;
    this.hits = 0;
    this.startedAt = new Date().toISOString();
    this.mark = this.now();
    this.state = "running";
  }
  milliseconds() {
    return Math.min(
      this.duration || 0,
      this.elapsed + (this.state === "running" ? this.now() - this.mark : 0)
    );
  }
  pause() {
    if (this.state !== "running") return;
    this.elapsed = this.milliseconds();
    this.state = "paused";
  }
  resume() {
    if (this.state !== "paused") return;
    this.mark = this.now();
    this.state = "running";
  }
  hit() {
    if (this.state === "running" && this.milliseconds() < this.duration)
      this.hits++;
  }
  finish() {
    if (!["running", "paused"].includes(this.state)) return;
    this.elapsed = this.milliseconds();
    this.state = "finished";
    return {
      activeSeconds: Math.round(this.elapsed / 1000),
      hits: this.hits,
      startedAt: this.startedAt,
    };
  }
}
