export const programs = [
  {
    id: "rhythm",
    title: "节奏触点",
    subtitle: "在专注中找到自己的节奏",
    tag: "协调 · 轻量",
    color: "#a9e670",
    seconds: 60,
    description:
      "跟随亮起的球体，点击或使用 VR 控制器射线触发。记录交互命中，练习注意力与节奏。",
  },
  {
    id: "focus",
    title: "专注空间",
    subtitle: "放慢节奏，保持稳定",
    tag: "专注 · 轻量",
    color: "#b3c4ff",
    seconds: 120,
    description:
      "在更缓慢的目标变化中完成触点。支持坐姿桌面体验；不测量身体动作或运动强度。",
  },
  {
    id: "flow",
    title: "活力节拍",
    subtitle: "用一段短练习唤醒状态",
    tag: "反应 · 自选节奏",
    color: "#ffb080",
    seconds: 60,
    description:
      "目标位置变化更频繁。可以随时暂停或提前结束，按自己的舒适程度体验。",
  },
];
export function getProgram(id) {
  return programs.find((p) => p.id === id);
}
