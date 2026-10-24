<template>
  <div ref="container" class="fitness-scene">
    <div v-if="error" class="scene-error">{{ error }}</div>
    <div class="scene-label">
      交互训练空间 <span>{{ active ? "训练进行中" : "可拖动查看场景" }}</span>
    </div>
    <div ref="vrMount" class="vr-entry"></div>
    <p class="scene-tip">点击发光球体 · 拖动旋转视角 · VR 模式使用控制器扳机</p>
  </div>
</template>
<script setup>
// Scene lifecycle and WebXR setup adapted from Moeary/Vue_Ocean_Museum OceanScene.vue.
// Fitness geometry, target interaction, in-world HUD and training events are new.
import { ref, onMounted, onBeforeUnmount } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { VRButton } from "three/examples/jsm/webxr/VRButton.js";
const props = defineProps({
  active: Boolean,
  remaining: { type: Number, default: 60 },
  program: { type: String, default: "rhythm" },
});
const emit = defineEmits(["hit", "xr", "toggle"]);
const container = ref(),
  vrMount = ref(),
  error = ref("");
let scene,
  camera,
  renderer,
  controls,
  observer,
  vrButton,
  targets = [],
  targetIndex = 0,
  clock,
  hud,
  hudCanvas,
  hudContext,
  disposed = false,
  lastHud = "",
  nextTargetAt = 0,
  controllers = [];
const raycaster = new THREE.Raycaster(),
  pointer = new THREE.Vector2(),
  rotation = new THREE.Matrix4();
const mesh = (geo, color, x, y, z) => {
  const m = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color, roughness: 0.65 })
  );
  m.position.set(x, y, z);
  scene.add(m);
  return m;
};
function buildScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color("#172827");
  scene.fog = new THREE.Fog("#172827", 12, 40);
  camera = new THREE.PerspectiveCamera(58, 1, 0.1, 100);
  camera.position.set(0, 2.8, 5.8);
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.7));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.xr.enabled = true;
  renderer.xr.setReferenceSpaceType("local-floor");
  container.value.appendChild(renderer.domElement);
  scene.add(new THREE.HemisphereLight(0xe4ffed, 0x304043, 2.2));
  const light = new THREE.DirectionalLight(0xffe7cd, 3);
  light.position.set(3, 8, 4);
  scene.add(light);
  mesh(new THREE.BoxGeometry(18, 0.2, 18), "#344e44", 0, -0.12, -3);
  mesh(new THREE.BoxGeometry(18, 6, 0.2), "#203f35", 0, 2.9, -9);
  for (let i = -7; i <= 7; i += 2)
    mesh(new THREE.BoxGeometry(0.035, 0.01, 16), "#4b6757", i, 0.001, -3);
  for (let i = -9; i <= 4; i += 2)
    mesh(new THREE.BoxGeometry(16, 0.01, 0.035), "#4b6757", 0, 0.001, i);
  mesh(
    new THREE.CylinderGeometry(2.6, 2.8, 0.09, 64),
    "#b4d3b1",
    0,
    0.02,
    -1.2
  );
  mesh(new THREE.CylinderGeometry(2.4, 2.4, 0.1, 64), "#54725b", 0, 0.04, -1.2);
  for (const x of [-6, 6]) {
    mesh(new THREE.BoxGeometry(0.2, 5, 10), "#3b574c", x, 2.5, -3);
    for (let z = -6; z <= 0; z += 3) {
      mesh(new THREE.BoxGeometry(0.22, 3, 2), "#a6c4ac", x, 2.6, z);
    }
  }
  for (const x of [-4, 4]) {
    mesh(new THREE.BoxGeometry(1.5, 0.2, 3), "#d0b993", x, 0.6, -3);
    for (const z of [-4, -2])
      mesh(new THREE.BoxGeometry(0.15, 0.6, 0.15), "#26352e", x, 0.25, z);
  }
  // Stylised guide, intentionally not a tracked human or pose-estimation output.
  const guide = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.CapsuleGeometry(0.27, 0.65, 5, 12),
    new THREE.MeshStandardMaterial({ color: "#d3d7ff" })
  );
  body.position.y = 1.05;
  guide.add(body);
  const head = new THREE.Mesh(
    new THREE.SphereGeometry(0.22, 20, 20),
    new THREE.MeshStandardMaterial({ color: "#f1d1aa" })
  );
  head.position.y = 1.8;
  guide.add(head);
  for (const x of [-0.18, 0.18]) {
    const leg = new THREE.Mesh(
      new THREE.CylinderGeometry(0.1, 0.1, 0.7, 12),
      new THREE.MeshStandardMaterial({ color: "#bcc4df" })
    );
    leg.position.set(x, 0.4, 0);
    guide.add(leg);
  }
  guide.position.set(0, 0.1, -3.6);
  scene.add(guide);
  const positions = [
    [-1.3, 1.25, -2.2],
    [1.3, 1.25, -2.2],
    [-0.7, 1.85, -2.5],
    [0.7, 1.85, -2.5],
    [0, 1.1, -1.8],
  ];
  targets = positions.map((p, i) => {
    const m = mesh(new THREE.SphereGeometry(0.19, 28, 28), "#aeec6c", ...p);
    m.userData.index = i;
    return m;
  });
  const pause = mesh(
    new THREE.BoxGeometry(0.6, 0.25, 0.12),
    "#cebafa",
    1.9,
    0.75,
    -2.4
  );
  pause.userData.pause = true;
  targets.push(pause);
  hudCanvas = document.createElement("canvas");
  hudCanvas.width = 1024;
  hudCanvas.height = 256;
  hudContext = hudCanvas.getContext("2d");
  hud = new THREE.CanvasTexture(hudCanvas);
  const board = new THREE.Mesh(
    new THREE.PlaneGeometry(4, 0.95),
    new THREE.MeshBasicMaterial({ map: hud, transparent: true })
  );
  board.position.set(0, 3, -5);
  scene.add(board);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 1, -2);
  controls.enableDamping = true;
  controls.minDistance = 3;
  controls.maxDistance = 9;
  controls.maxPolarAngle = Math.PI * 0.49;
  controls.enablePan = false;
  observer = new ResizeObserver(resize);
  observer.observe(container.value);
  resize();
}
function resize() {
  if (!renderer || disposed) return;
  const { width, height } = container.value.getBoundingClientRect();
  camera.aspect = width / Math.max(1, height);
  camera.updateProjectionMatrix();
  renderer.setSize(width, Math.max(1, height));
}
function chooseTarget() {
  targetIndex = (targetIndex + 1) % 5;
  nextTargetAt =
    clock.elapsedTime +
    (props.program === "focus" ? 6 : props.program === "flow" ? 2 : 4);
}
function hit(ray) {
  const hits = ray.intersectObjects(targets);
  if (!hits.length) return;
  const object = hits[0].object;
  if (object.userData.pause) {
    emit("toggle");
    return;
  }
  if (props.active && object.userData.index === targetIndex) {
    emit("hit");
    chooseTarget();
  }
}
let down = null;
function pointerDown(e) {
  down = [e.clientX, e.clientY];
}
function pointerUp(e) {
  if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 8) return;
  down = null;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.set(
    ((e.clientX - rect.left) / rect.width) * 2 - 1,
    (-(e.clientY - rect.top) / rect.height) * 2 + 1
  );
  raycaster.setFromCamera(pointer, camera);
  hit(raycaster);
}
function controllerSelect(event) {
  rotation.identity().extractRotation(event.target.matrixWorld);
  raycaster.ray.origin.setFromMatrixPosition(event.target.matrixWorld);
  raycaster.ray.direction.set(0, 0, -1).applyMatrix4(rotation);
  hit(raycaster);
}
function startXR() {
  controls.enabled = false;
  camera.position.set(0, 1.6, 0);
  emit("xr", true);
}
function endXR() {
  controls.enabled = true;
  camera.position.set(0, 2.8, 5.8);
  controls.target.set(0, 1, -2);
  emit("xr", false);
}
function animate() {
  if (disposed) return;
  const t = clock.getElapsedTime();
  if (props.active && t > nextTargetAt) chooseTarget();
  targets.slice(0, 5).forEach((m, i) => {
    const on = props.active && i === targetIndex;
    m.material.color.set(on ? "#c8ff79" : "#708d80");
    m.material.emissive.set(on ? "#75a42e" : "#000000");
    m.material.emissiveIntensity = on ? 0.5 : 0;
    m.scale.setScalar(on ? 1 + Math.sin(t * 4) * 0.08 : 1);
  });
  const text = `${props.active ? "TRAINING" : "READY / PAUSED"}  ${Math.ceil(
    props.remaining
  )}s`;
  if (text !== lastHud) {
    hudContext.clearRect(0, 0, 1024, 256);
    hudContext.fillStyle = "#d9f5c5";
    hudContext.font = "bold 56px sans-serif";
    hudContext.textAlign = "center";
    hudContext.fillText("VRFitAI", 512, 80);
    hudContext.font = "38px sans-serif";
    hudContext.fillText(text, 512, 146);
    hudContext.font = "24px sans-serif";
    hudContext.fillText(
      "Trigger: touch light / Purple tile: start / pause",
      512,
      200
    );
    hud.needsUpdate = true;
    lastHud = text;
  }
  controls.update();
  renderer.render(scene, camera);
}
onMounted(async () => {
  try {
    buildScene();
    clock = new THREE.Clock();
    renderer.domElement.addEventListener("pointerdown", pointerDown);
    renderer.domElement.addEventListener("pointerup", pointerUp);
    for (let i = 0; i < 2; i++) {
      const c = renderer.xr.getController(i);
      c.addEventListener("select", controllerSelect);
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(),
          new THREE.Vector3(0, 0, -4),
        ]),
        new THREE.LineBasicMaterial({ color: "#c8ff79" })
      );
      c.add(line);
      scene.add(c);
      controllers.push(c);
    }
    renderer.xr.addEventListener("sessionstart", startXR);
    renderer.xr.addEventListener("sessionend", endXR);
    renderer.setAnimationLoop(animate);
    const supported =
      Boolean(navigator.xr) &&
      (await navigator.xr
        .isSessionSupported("immersive-vr")
        .catch(() => false));
    if (disposed) return;
    if (supported) {
      vrButton = VRButton.createButton(renderer);
      vrMount.value.appendChild(vrButton);
    } else {
      vrMount.value.textContent = "桌面模式 · 当前设备未提供 WebXR";
    }
  } catch {
    error.value = "当前设备无法创建 3D 场景。请使用支持 WebGL 的浏览器。";
  }
});
onBeforeUnmount(() => {
  disposed = true;
  observer?.disconnect();
  if (renderer) {
    renderer.setAnimationLoop(null);
    const session = renderer.xr.getSession();
    if (session) {
      emit("xr", false);
      session.end().catch(() => {});
    }
    renderer.xr.removeEventListener("sessionstart", startXR);
    renderer.xr.removeEventListener("sessionend", endXR);
    renderer.domElement.removeEventListener("pointerdown", pointerDown);
    renderer.domElement.removeEventListener("pointerup", pointerUp);
  }
  controllers.forEach((c) => c.removeEventListener("select", controllerSelect));
  controls?.dispose();
  scene?.traverse((o) => {
    o.geometry?.dispose();
    if (o.material) {
      for (const m of Array.isArray(o.material) ? o.material : [o.material])
        m.dispose();
    }
  });
  hud?.dispose();
  renderer?.dispose();
  renderer?.domElement.remove();
  vrButton?.remove();
});
</script>
