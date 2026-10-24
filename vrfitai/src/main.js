import { createApp } from "vue";
import { createRouter, createWebHashHistory } from "vue-router";
import App from "./App.vue";
import "./style.css";
const routes = ["/", "/studio", "/records", "/assistant"].map((path) => ({
  path,
  component: { template: "<span></span>" },
}));
createApp(App)
  .use(createRouter({ history: createWebHashHistory(), routes }))
  .mount("#app");
