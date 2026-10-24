<template>
  <div class="map-wrapper">
    <!-- 主题标题与筛选控制栏 -->
    <div class="control-bar">
      <h1>城市文化探索地图</h1>
      <label class="search-label">搜索景点 <input v-model="searchText" placeholder="名称或地址" /></label>
      <label><input type="checkbox" v-model="favoritesOnly" />只看收藏</label>
      <p class="search-count" role="status">找到 {{ visibleCount }} 个景点</p>
      <p v-if="!visibleCount" class="empty-search">没有匹配的地点，试试其他关键词或取消筛选。</p>
      <div class="collection-actions"><button @click="clearFilters">清除筛选</button><button @click="exportFavorites" :disabled="!favorites.length">导出收藏 JSON</button></div>
      <div class="style-selector">
    <select v-model="selectedStyle" @change="switchBaseMap">
      <option value="7">默认风格</option>
      <option value="8">道路图</option>
      <option value="6">卫星影像</option>
    </select>
  </div>
      <div class="filters">
        <select v-model="selectedRoute" @change="updateRouteDisplay">
          <option value="all">全部景点</option>
          <option value="route1">初心启航路线</option>
          <option value="route2">光辉历程路线</option>
          <option value="route3">信仰如磐路线</option>
        </select>
        <button 
  @click="showHeatmap = !showHeatmap" 
  :class="['toggle-btn', { active: showHeatmap }]"
>
  {{ showHeatmap ? '隐藏热度分布' : '显示热度分布' }}
</button>

        <button @click="toggleRoute" class="route-toggle-btn">
  {{ showRoute ? '隐藏路线轨迹' : '显示路线轨迹' }}
</button>


      </div>
      
    </div>

    <!-- 主地图容器 -->
    <div id="map"></div>

    <!-- 信息展示面板 -->
    <div class="info-panel" v-if="selectedSite">
  <h2>{{ selectedSite.name }}</h2>
  <p><strong>地址：</strong>{{ selectedSite.address }}</p>
  <p><strong>开放时间：</strong>{{ selectedSite.openTime }}</p>
  <p><strong>热度：</strong>
    <span :style="{ color: getHeatColor(selectedSite.popularity) }">
      {{ selectedSite.popularity }} / 10
    </span>
  </p>
  <p><strong>简介：</strong>{{ selectedSite.description }}</p>

  <button @click="showRouteAnimation(selectedSite.route)">查看路线轨迹</button>
  <button @click="showNearbySites(selectedSite)">附近景点</button>
  <button @click="markStartOrEnd(selectedSite)">计算直线距离</button>
  <button @click="toggleFavorite(selectedSite)">{{ favorites.includes(selectedSite.name) ? "取消收藏" : "收藏景点" }}</button>
</div>

    <!-- 坐标显示 -->
    <div id="coord" class="coordinate-display">
      移动鼠标查看坐标
    </div>

    <!-- 地图角标 Logo -->
    <div class="map-logo">
      <img src="/icons/red-logo.png" alt="Red Theme Logo" />
      <div class="project-tagline">城市文化 · 个人探索</div>
      <div class="project-tagline">示例地点资料 · 出行前请核实开放信息</div>
    </div>
    <div id="distance-display" style="position:absolute; bottom:60px; right:20px; background:white; padding:8px 12px; border-radius:6px; box-shadow:0 0 8px rgba(0,0,0,0.2); font-weight:bold; z-index:2000;">
  点击两个景点查看直线距离
</div>
  </div>
</template>


<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";
import { redSites } from '@/assets/redsite.js';
import { routes } from '@/assets/routes.js';
let startMarker = null;
let endMarker = null;


const shanghaiCenter = [31.2304, 121.4737];
const selectedSite = ref(null);
const searchText = ref('');
const favoritesOnly = ref(false);
const loadFavorites = () => {
  try { const x = JSON.parse(localStorage.getItem('city-favorites') || '[]'); return Array.isArray(x) ? x.filter(v => typeof v === 'string') : []; }
  catch { return []; }
};
const favorites = ref(loadFavorites());
const clearFilters = () => { searchText.value=''; favoritesOnly.value=false; selectedRoute.value='all'; };
const exportFavorites = () => {
  const sites=redSites.filter(site=>favorites.value.includes(site.name));
  const payload={exportedAt:new Date().toISOString(),coordinateNote:'Source coordinates are unverified; this is not a navigation dataset.',sites};
  const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='city-explorer-favorites.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
const toggleFavorite = (site) => {
  favorites.value = favorites.value.includes(site.name) ? favorites.value.filter(n => n !== site.name) : [...favorites.value, site.name];
  try { localStorage.setItem('city-favorites', JSON.stringify(favorites.value)); } catch { /* In-memory favorites remain available. */ }
};
const filteredSites = () => redSites.filter(site =>
  (selectedRoute.value === 'all' || site.route === selectedRoute.value) &&
  (!favoritesOnly.value || favorites.value.includes(site.name)) &&
  (site.name + site.address).toLowerCase().includes(searchText.value.trim().toLowerCase()));
const visibleCount = computed(() => filteredSites().length);
let animationToken = 0;
let activeRoute = null;

const selectedRoute = ref("all");
const showHeatmap = ref(true);
const showRoute = ref(true);
const routeNameMap = {
  route1: "初心启航路线",
  route2: "光辉历程路线",
  route3: "信仰如磐路线"
};

let map = null;
let heatLayer = null;
let routeLayer = null;
let markersLayer = null;

const selectedStyle = ref("7");  
let baseLayer = null;

const switchBaseMap = () => {
  if (baseLayer) {
    map.removeLayer(baseLayer);
  }

  baseLayer = L.tileLayer(`https://wprd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=${selectedStyle.value}&x={x}&y={y}&z={z}`, {
    maxZoom: 18,
    attribution: "© 高德地图",
    subdomains: ['1', '2', '3', '4'],
    crossOrigin: 'anonymous'
  }).addTo(map);
};



onMounted(() => {
  map = L.map("map").setView(shanghaiCenter, 12);
  switchBaseMap(); // 初始化加载底图

  map.on("mousemove", (e) => {
    document.getElementById("coord").innerText =
      `纬度: ${e.latlng.lat.toFixed(5)}, 经度: ${e.latlng.lng.toFixed(5)}`;
  });

  createSiteMarkers();
  createHeatmap();
});


const createSiteMarkers = () => {
  if (markersLayer) {
    map.removeLayer(markersLayer);
  }
  markersLayer = L.layerGroup().addTo(map);

  const redIcon = L.divIcon({
    className: 'red-marker',
    html: '<div class="marker-pin"></div>',
    iconSize: [30, 42],
    iconAnchor: [15, 42]
  });

  filteredSites().forEach(site => {
    const marker = L.marker(site.position, { icon: redIcon, title: site.name, alt: site.name }).addTo(markersLayer);
    marker.bindPopup(`
      <div class="popup-content">
        <h3>${site.name}</h3>
        <p><b>地址:</b> ${site.address}</p>
        <p><b>开放时间:</b> ${site.openTime}</p>
        <p><b>热度:</b> <span style="color:${getHeatColor(site.popularity)}">${site.popularity}/10</span></p>
      </div>
    `);
    marker.on('click', () => {
      selectedSite.value = site;
      marker.openPopup();
    });

    L.circleMarker(site.position, {
      interactive: false,
      radius: 10,
      color: "#d9534f",
      fillColor: "#f08080",
      fillOpacity: 0.8,
      weight: 2
    }).addTo(markersLayer);
   
  });
};

const getHeatColor = (popularity) => {
  if (popularity >= 9) return "red";
  if (popularity >= 8) return "orange";
  if (popularity >= 6) return "yellowgreen";
  return "green";
};

const createHeatmap = () => {
  if (heatLayer) {
    map.removeLayer(heatLayer);
  }
  if (!showHeatmap.value) return;

  const heatPoints = filteredSites().map(site => [...site.position, site.popularity / 10]);

  heatLayer = L.heatLayer(heatPoints, {
    radius: 25, 
    blur: 15,
    maxZoom: 17,
  }).addTo(map);


};



const showRouteAnimation = async (routeName) => {
  const token = ++animationToken;
  activeRoute = routeName;
  
  if (!routeName || !routes[routeName]) {
    alert("该景点未配置路线数据。");
    return;
  }

  if (routeLayer) {
    map.removeLayer(routeLayer);
    routeLayer = null;
  }

  if (!showRoute.value) return;

  const routePoints = routes[routeName];
  let totalLength = 0;

  for (let i = 0; i < routePoints.length - 1; i++) {
    const p1 = L.latLng(routePoints[i]);
    const p2 = L.latLng(routePoints[i + 1]);
    totalLength += p1.distanceTo(p2);
  }

  const km = (totalLength / 1000).toFixed(2);
  document.getElementById('distance-display').innerText = `路线折线长度：${km} 公里`;

  if (startMarker) map.removeLayer(startMarker);
  if (endMarker) map.removeLayer(endMarker);
  startMarker = null; endMarker = null;

  routeLayer = L.polyline([], {
    color: "blue",
    weight: 5,
    opacity: 0.8,
    dashArray: "10, 10",
  }).addTo(map);

  routeLayer.on('click', (e) => {
    const displayName = routeNameMap[routeName] || routeName;
    L.popup()
      .setLatLng(e.latlng)
      .setContent(`<b>路线名称：</b>${displayName}<br><b>总距离：</b>${km} 公里`)
      .openOn(map);
  });


  map.fitBounds(L.polyline(routePoints).getBounds());

  // 动画逐点添加轨迹
  for (let i = 0; i < routePoints.length; i++) {
    await new Promise(resolve => setTimeout(resolve, 300));
    if (token !== animationToken || !routeLayer || !map) return;
    routeLayer.addLatLng(routePoints[i]);
  }

  // 起点和终点标记
  const startIcon = L.icon({
    iconUrl: '/icons/start-flag.png',  // 起点旗帜图标路径
    iconSize: [32, 37],
    iconAnchor: [16, 37],
    popupAnchor: [0, -28]
  });

  const endIcon = L.icon({
    iconUrl: '/icons/finish-flag.png', // 终点图标路径
    iconSize: [32, 37],
    iconAnchor: [16, 37],
    popupAnchor: [0, -28]
  });

  startMarker = L.marker(routePoints[0], { icon: startIcon }).addTo(map).bindPopup("起点");
endMarker = L.marker(routePoints[routePoints.length - 1], { icon: endIcon }).addTo(map).bindPopup("终点");
};


watch([selectedRoute, showHeatmap, searchText, favoritesOnly, favorites], () => {
  if (!map) return;
  createSiteMarkers();
  createHeatmap();
  if (selectedSite.value && !filteredSites().some(site => site.name === selectedSite.value.name)) selectedSite.value = null;
});

watch(showRoute, () => {
  if (!showRoute.value) {
    ++animationToken;
    if (routeLayer) {
      map.removeLayer(routeLayer);
      routeLayer = null;
    }
    if (startMarker) {
      map.removeLayer(startMarker);
      startMarker = null;
    }
    if (endMarker) {
      map.removeLayer(endMarker);
      endMarker = null;
    }
  }
});


const updateRouteDisplay = () => {
  ++animationToken;
  activeRoute = null;
  if (routeLayer) { map.removeLayer(routeLayer); routeLayer = null; }
  if (startMarker) { map.removeLayer(startMarker); startMarker = null; }
  if (endMarker) { map.removeLayer(endMarker); endMarker = null; }
  if (bufferCircle) { map.removeLayer(bufferCircle); bufferCircle = null; }
  clickedPoints.value = []; clickedSiteNames.value = [];
  document.getElementById('distance-display').innerText = '点击两个景点查看直线距离';
  if (showRoute.value && selectedRoute.value !== 'all') showRouteAnimation(selectedRoute.value);
};
const toggleRoute = () => {
  showRoute.value = !showRoute.value;
  if (showRoute.value && activeRoute) showRouteAnimation(activeRoute);
};
onBeforeUnmount(() => {
  ++animationToken;
  if (map) { map.remove(); map = null; }
});

const clickedPoints = ref([]);
const clickedSiteNames = ref([]);

const calculateDistance = () => {
  if (clickedPoints.value.length === 2 && clickedSiteNames.value.length === 2) {
    const [latlng1, latlng2] = clickedPoints.value;
    const [name1, name2] = clickedSiteNames.value;

    const distance = latlng1.distanceTo(latlng2); 
    const km = (distance / 1000).toFixed(2);

    const distanceDiv = document.getElementById('distance-display');
    distanceDiv.innerText = `从 "${name1}" 到 "${name2}" 的直线距离：${km} 公里`;
  }
};


let bufferCircle = null;

const showNearbySites = (centerSite) => {
  if (bufferCircle) map.removeLayer(bufferCircle);

  const center = L.latLng(centerSite.position[0], centerSite.position[1]);
  bufferCircle = L.circle(center, {
    radius: 1000, 
    color: "#3388ff",
    fillColor: "#99ccff",
    fillOpacity: 0.3,
  }).addTo(map);

  const nearby = redSites.filter(site => {
    const siteLatLng = L.latLng(site.position);
    return center.distanceTo(siteLatLng) <= 1000 && site.name !== centerSite.name;
  });

  const names = nearby.map(s => s.name).join("、");
  alert(`1 公里范围内邻近景点：\n${names || "无"}`);
};

const markStartOrEnd = (site) => {
  const latlng = L.latLng(site.position);

  if (clickedPoints.value.length >= 2) {
    clickedPoints.value = [];
    clickedSiteNames.value = [];
  }

  clickedPoints.value.push(latlng);
  clickedSiteNames.value.push(site.name); 

  if (clickedPoints.value.length === 2) {
    calculateDistance();
  } else {
    const info = clickedPoints.value.length === 1 ? '已选择起点，请选择终点' : '请选择起点';
    document.getElementById('distance-display').innerText = info;
  }
};



</script>

<style scoped>
.control-bar {
  position: absolute;
  top: 10px;
  left: 260px;
  transform: translateX(-50%);
  z-index: 2000;
  background: linear-gradient(135deg, #d9534f, #ff4d4d);
  padding: 16px 24px;
  border-radius: 12px;
  box-shadow: 0 6px 12px rgba(217, 83, 79, 0.6);
  font-family: "微软雅黑", sans-serif;
  width: 360px;
  color: white;
  user-select: none;
  transition: box-shadow 0.3s ease;
}

.control-bar:hover {
  box-shadow: 0 8px 20px rgba(217, 83, 79, 0.9);
}

.control-bar h1 {
  margin: 0 0 12px 0;
  font-weight: 900;
  font-size: 1.8rem;
  text-shadow: 1px 1px 2px rgba(150, 0, 0, 0.7);
  letter-spacing: 1.2px;
}

.filters {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.filters select,
.filters input[type="checkbox"] + label,
.filters button {
  cursor: pointer;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  transition: background-color 0.3s ease, color 0.3s ease;
}

.filters select {
  padding: 6px 10px;
  border: 2px solid white;
  background: white;
  color: #d9534f;
  font-weight: 700;
  outline: none;
}


/* 复选框标签文字 */
.filters label {
  color: white;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 路线切换按钮 */
.route-toggle-btn {
  background-color: white;
  color: #d9534f;
  border: 2px solid white;
  padding: 6px 14px;
  font-weight: 700;
  border-radius: 6px;
  transition: background-color 0.3s ease, color 0.3s ease;
}

.toggle-btn {
  background-color: white;
  color: #d9534f;
  border: 2px solid white;
  padding: 6px 14px;
  font-weight: 700;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
}

.toggle-btn:hover {
  background-color: #d9534f;
  color: white;
  border-color: #d9534f;
  box-shadow: 0 0 8px #ff6666;
}


.toggle-btn.active {
  background-color: #d9534f;
  color: white;
  border-color: #d9534f;
  box-shadow: 0 0 8px #ff6666;
}

.route-toggle-btn:hover {
  background-color: #d9534f;
  color: white;
  border-color: #d9534f;
  box-shadow: 0 0 8px #ff6666;
}

#map {
  width: 100%;
  height: 100%;
  z-index: 1;
}

.coordinate-display {
  position: absolute;
  bottom: 10px;
  left: 15px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.85);
  font-size: 12px;
  font-family: monospace;
  border-radius: 4px;
  z-index: 3000;
}

.info-panel {
  position: absolute;
  top: 110px;
  right: 60px;
  width: 320px;
  background-color: white;
  padding: 12px;
  border-radius: 6px;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.3);
  font-family: "微软雅黑", sans-serif;
  z-index: 2000;
}
.info-panel h2 {
  margin-top: 0;
  font-weight: bold;
  color: #d9534f;
}

.info-panel p {
  margin: 6px 0;
  font-size: 14px;
}

.info-panel button {
  margin-top: 10px;
  background-color: #d9534f;
  color: white;
  border: none;
  padding: 8px 14px;
  border-radius: 4px;
  cursor: pointer;
}

.info-panel button:hover {
  background-color: #c9302c;
}

/* 自定义红色标记点样式 */
:deep(.red-marker .marker-pin) {
  width: 30px;
  height: 42px;
  background-color: #d9534f;
  border-radius: 15px 15px 15px 0;
  transform: rotate(-45deg);
  position: relative;
  border: 2px solid white;
  box-shadow: 0 0 4px rgba(0,0,0,0.3);
}

:deep(.red-marker .marker-pin::after) {
  content: "";
  width: 14px;
  height: 14px;
  margin: 7px 0 0 7px;
  background: white;
  position: absolute;
  border-radius: 50%;
}

/* 弹窗样式 */
.popup-content h3 {
  margin: 0 0 6px 0;
  font-weight: bold;
  color: #d9534f;
  font-family: "微软雅黑", sans-serif;
}

.popup-content p {
  margin: 2px 0;
  font-size: 13px;
  font-family: "微软雅黑", sans-serif;
}

.map-logo {
  position: absolute;
  top: 10px;     
  right: 10px;    
  z-index: 1000;
}
.map-logo img {
  width: 48px;
  height: 48px;
}

.map-wrapper {
  height: 100vh;
  width: 100vw;
  position: relative;
  overflow: hidden;
}

#map {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  width: 100%;
  z-index: 1;
}

</style>
<style>

html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  width: 100%;
  overflow: hidden;

  
}

.project-tagline {
  font-size: 10px;
  color: #666;
  font-weight: 500;
  margin-bottom: 4px;
}

.style-selector {
  margin-bottom: 10px;
  cursor: pointer;
}

.style-selector select {
  cursor: pointer;
  padding: 6px 10px;
  border: 2px solid white;
  background: white;
  color: #d9534f;
  font-weight: 700;
  outline: none;
}

</style>
<style scoped>
.search-label { display:block; margin:10px 0; }
.search-label input { max-width:210px; padding:6px; }
.filters { flex-wrap:wrap; }
@media(max-width:650px) { .control-bar { left:10px; transform:none; width:calc(100% - 68px); } .info-panel { top:auto; bottom:65px; right:10px; width:calc(100% - 44px); max-height:30vh; overflow:auto; } .map-logo { display:none; } }
</style>

<style scoped>
.collection-actions{display:flex;justify-content:center;gap:8px;margin:8px 0}.collection-actions button{padding:6px 12px;border:1px solid #bdcec3;border-radius:5px;background:#fff;color:#355e4e;cursor:pointer}.collection-actions button:disabled{opacity:.4;cursor:default}.empty-search{font-size:12px;color:#7a4b36}
</style>
