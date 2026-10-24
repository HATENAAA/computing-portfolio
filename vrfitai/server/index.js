import { mkdirSync } from "node:fs";
import { createApp } from "./app.js";
mkdirSync("data", { recursive: true });
const { app, close } = createApp({ database: "data/vrfitai.sqlite",
  logger: record => console.log(JSON.stringify(record)) });
const port = Number(process.env.PORT || 8780),
  host = process.env.HOST || "127.0.0.1";
const server = app.listen(port, host, () =>
  console.log(`VRFitAI: http://${host}:${port}`)
);
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () =>
    server.close(() => {
      close();
      process.exit(0);
    })
  );
