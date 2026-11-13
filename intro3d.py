"""Intro 3D réaliste de l'app : un alley-oop joué par deux vrais modèles humains (Mixamo).

- Les joueurs (static/intro/passer.glb et dunker.glb) sont des personnages Mixamo, avec des
  mouvements enregistrés sur de vrais acteurs (motion capture).
- La page enchaîne ces mouvements avec Three.js et place le ballon et le panier au bon endroit :
  le ballon part des mains du passeur, arrive dans celles du dunkeur, puis tombe dans le cercle.
- Streamlit affiche la page dans une iframe étirée en plein écran.
"""

# Durée avant que le tableau de bord commence à apparaître (environ la durée de l'intro)
INTRO3D_OFFSET = "6.2s"
THREE_VERSION = "0.187.0"      # version de Three.js, figée volontairement

PARENT_CSS = f"""
<style>
:root {{ --o: {INTRO3D_OFFSET}; }}
.st-key-intro3d {{ position: fixed !important; inset: 0 !important; z-index: 1000000 !important;
                   width: 100vw !important; height: 100vh !important; margin: 0 !important; padding: 0 !important;
                   gap: 0 !important; background: #05070D;
                   animation: ao3-out .45s ease-in 20s forwards; }}   /* filet de sécurité */
.st-key-intro3d > div, .st-key-intro3d [data-testid="stElementContainer"], .st-key-intro3d iframe {{
  width: 100vw !important; height: 100vh !important; max-width: none !important; }}
.st-key-intro3d iframe {{ border: 0; display: block; }}
@keyframes ao3-out {{ to {{ opacity: 0; visibility: hidden; pointer-events: none; }} }}
@media (prefers-reduced-motion: reduce) {{
  .st-key-intro3d {{ display: none !important; }}
  :root {{ --o: 0s; }}
}}
</style>
"""

_PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Bungee&family=Sedgwick+Ave+Display&display=block" rel="stylesheet">
<style>
html, body { margin: 0; height: 100%; overflow: hidden; background: #05070D; cursor: pointer; user-select: none; }
canvas { display: block; }
#ui { position: fixed; inset: 0; pointer-events: none; }
.loading { position: absolute; inset: 0; display: grid; place-items: center; background: #05070D; transition: opacity .4s; }
.loading.gone { opacity: 0; }
.loading div { font-family: 'Bungee', sans-serif; font-size: 14px; letter-spacing: 2px; color: #0B1220; background: #FACC15;
               border: 3px solid #0B1220; border-radius: 10px; padding: 8px 16px 6px; box-shadow: 5px 5px 0 #60A5FA;
               transform: rotate(-3deg); animation: pulse 1s ease-in-out infinite alternate; }
@keyframes pulse { to { transform: rotate(-3deg) scale(1.06); } }
.flash { position: absolute; inset: 0; background: #fff; opacity: 0; }
.flash.on { animation: flash .4s ease-out forwards; }
@keyframes flash { 0% { opacity: .75; } 100% { opacity: 0; } }
.bars::before, .bars::after { content: ""; position: absolute; left: 0; right: 0; height: 0; background: #000; transition: height .5s ease; z-index: 1; }
.bars::before { top: 0; } .bars::after { bottom: 0; }
.bars.on::before, .bars.on::after { height: 8vh; }
.pop { position: absolute; font-family: 'Bungee', sans-serif; opacity: 0; transform: scale(.3) rotate(-10deg); z-index: 2;
       transition: opacity .2s, transform .45s cubic-bezier(.34,1.56,.64,1); }
.pop.on { opacity: 1; transform: rotate(var(--r, -6deg)); }
.pop.off { opacity: 0; transform: translateY(-20px) rotate(var(--r, -6deg)); transition: opacity .3s, transform .3s; }
.lob { left: 7%; top: 22%; font-size: clamp(18px, 2.6vw, 34px); color: #4ADE80; --r: -4deg;
       -webkit-text-stroke: 6px #0B1220; paint-order: stroke fill; }
.oop { right: 7%; top: 16%; font-size: clamp(22px, 3.6vw, 48px); color: #0B1220; background: #FACC15;
       border: 4px solid #0B1220; border-radius: 12px; padding: 8px 20px 4px; box-shadow: 7px 7px 0 #0B1220; --r: -8deg; }
.title { position: absolute; left: 0; right: 0; top: 9%; text-align: center; z-index: 2; }
.tag { display: inline-block; font-family: 'Sedgwick Ave Display', cursive; font-size: clamp(54px, 9vw, 120px); line-height: 1;
       color: #fff; text-transform: uppercase; letter-spacing: 2px; transform: rotate(-4deg);
       -webkit-text-stroke: 3px #0B1220; paint-order: stroke fill; text-shadow: 5px 5px 0 #F97316, 9px 9px 0 #0B1220;
       clip-path: inset(-20% 100% -20% -5%); }
.tag span { color: #60A5FA; }
.tag.on { animation: spray .55s steps(9) forwards; }
@keyframes spray { to { clip-path: inset(-20% -5% -20% -5%); } }
.sticker { display: block; width: max-content; margin: 14px auto 0; font-family: 'Bungee', sans-serif;
           font-size: clamp(13px, 1.6vw, 20px); letter-spacing: 1.5px; color: #0B1220; background: #FACC15;
           border: 3px solid #0B1220; border-radius: 10px; padding: 7px 16px 5px; box-shadow: 5px 5px 0 #60A5FA;
           opacity: 0; transform: rotate(-12deg) scale(.4); transition: opacity .2s, transform .45s cubic-bezier(.34,1.56,.64,1); }
.sticker.on { opacity: 1; transform: rotate(2deg); }
.skip { position: absolute; right: 22px; bottom: 20px; z-index: 3; font-family: 'Bungee', sans-serif; font-size: 12px; letter-spacing: 1px;
        color: #0B1220; background: #fff; border: 2.5px solid #0B1220; border-radius: 8px; padding: 6px 11px 4px;
        box-shadow: 3px 3px 0 #60A5FA; transform: rotate(-2deg); }
.skip .touch { display: none; }
@media (max-aspect-ratio: 1/1) {
  .skip .desk { display: none; } .skip .touch { display: inline; }
  .title { top: 13%; } .lob { top: 30%; } .oop { top: 22%; right: 5%; }
}
body.out { animation: out .45s ease-in forwards; }
@keyframes out { to { opacity: 0; } }
</style>
<script type="importmap">{"imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@__THREE__/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@__THREE__/examples/jsm/"}}</script>
</head>
<body>
<div id="ui">
  <div class="bars" id="bars"></div>
  <div class="flash" id="flash"></div>
  <div class="pop lob" id="lob">Perfect lob</div>
  <div class="pop oop" id="oop">Alley-oop!</div>
  <div class="title"><div class="tag" id="tag">Court<span>Side</span></div><div class="sticker" id="sticker">Tonight's picks are in</div></div>
  <div class="loading" id="loading"><div>Warming up…</div></div>
  <div class="skip"><span class="desk">Click to skip</span><span class="touch">Tap to skip</span></div>
</div>
<script>
// Fin de l'intro : on masque l'iframe dans la page Streamlit
window.aoFinish = function () {
  if (window.aoDone) return; window.aoDone = true;
  try {
    const box = window.parent.document.querySelector('.st-key-intro3d');
    if (box) { box.style.transition = 'opacity .45s'; box.style.opacity = '0'; setTimeout(() => box.style.display = 'none', 460); }
    window.parent.document.documentElement.style.setProperty('--o', '0s');
  } catch (e) {}
  document.body.classList.add('out');
};
document.addEventListener('click', () => window.aoFinish());
if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) window.aoFinish();
// Si la 3D n'a pas démarré au bout de 12 s (connexion lente, pas de 3D), on passe directement à l'app
setTimeout(() => { if (!window.aoStarted) window.aoFinish(); }, 12000);
</script>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// Adresse des fichiers 3D servis par Streamlit (dossier static/)
let BASE;
try { BASE = new URL('app/static/intro/', window.parent.location.href).href; }
catch (e) { BASE = new URL('app/static/intro/', document.baseURI).href; }
if (window.AO_BASE) BASE = window.AO_BASE;

// ============================================================ Rendu
let renderer;
try { renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' }); }
catch (e) { window.aoFinish(); throw e; }
const mobile = Math.min(innerWidth, innerHeight) < 600;
renderer.setPixelRatio(Math.min(devicePixelRatio, mobile ? 1.5 : 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x070A14);
scene.fog = new THREE.FogExp2(0x0B0F1E, 0.028);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.18;
const camera = new THREE.PerspectiveCamera(38, innerWidth / innerHeight, 0.05, 300);

function canvasTex(w, h, draw, repeat = null, srgb = true) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  if (repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(...repeat); }
  return t;
}
function noise(g, w, h, n, alpha, light = false) {
  for (let i = 0; i < n; i++) {
    const v = light ? 200 + Math.random() * 55 : Math.random() * 60;
    g.fillStyle = `rgba(${v},${v},${v},${Math.random() * alpha})`;
    g.fillRect(Math.random() * w, Math.random() * h, 1 + Math.random() * 2, 1 + Math.random() * 2);
  }
}
const std = (o) => new THREE.MeshStandardMaterial(o);
function add(geo, mat, pos, { rot = null, shadow = true, receive = true } = {}) {
  const m = new THREE.Mesh(geo, mat); m.position.set(...pos); if (rot) m.rotation.set(...rot);
  m.castShadow = shadow; m.receiveShadow = receive; scene.add(m); return m;
}

// ============================================================ Le terrain (dimensions réelles, en mètres)
const ZR = 6.0, RIM_Y = 3.05, RIM_R = 0.23;            // centre du cercle
const BOARD_Z = ZR + 0.38;

function buildCourt() {
  const asphalt = canvasTex(1024, 1024, (g, w, h) => {
    g.fillStyle = '#2A2F3A'; g.fillRect(0, 0, w, h); noise(g, w, h, 60000, 0.35); noise(g, w, h, 6000, 0.12, true);
    g.strokeStyle = 'rgba(10,12,16,.6)'; g.lineWidth = 2;
    for (let i = 0; i < 6; i++) { g.beginPath(); let x = Math.random() * w, y = Math.random() * h; g.moveTo(x, y);
      for (let k = 0; k < 8; k++) { x += (Math.random() - .5) * 120; y += Math.random() * 60; g.lineTo(x, y); } g.stroke(); }
  }, [14, 14]);
  add(new THREE.PlaneGeometry(140, 140), std({ map: asphalt, roughness: 0.96, metalness: 0 }), [0, 0, 0],
      { rot: [-Math.PI / 2, 0, 0], shadow: false });

  // Marquages : raquette bleue, lignes blanches, arc à 3 points, cercle des lancers francs
  const court = canvasTex(2048, 2048, (g, w, h) => {
    const S = 2048 / 20, X = (x) => (x + 10) * S, Z = (z) => (z - (ZR - 14)) * S;   // 20 m x 20 m
    const base = ZR + 1.2, ft = base - 5.8;
    g.fillStyle = 'rgba(30,64,175,.85)'; g.fillRect(X(-2.45), Z(ft), 4.9 * S, (base - ft) * S);
    g.strokeStyle = 'rgba(245,247,250,.92)'; g.lineWidth = 0.05 * S;
    g.strokeRect(X(-2.45), Z(ft), 4.9 * S, (base - ft) * S);
    g.beginPath(); g.arc(X(0), Z(ft), 1.8 * S, Math.PI, 2 * Math.PI); g.stroke();
    g.beginPath(); g.moveTo(X(-10), Z(base)); g.lineTo(X(10), Z(base)); g.stroke();
    g.beginPath(); g.arc(X(0), Z(ZR), 6.75 * S, Math.PI * 1.03, Math.PI * 1.97); g.stroke();
    g.save(); g.translate(X(-5.6), Z(ZR - 9.5)); g.rotate(-0.12); g.globalAlpha = 0.28;
    g.font = `${1.2 * S}px Bungee`; g.fillStyle = '#FACC15'; g.fillText('COURTSIDE', 0, 0); g.restore();
  });
  add(new THREE.PlaneGeometry(20, 20), std({ map: court, transparent: true, roughness: 0.85, depthWrite: false }), [0, 0.004, ZR - 4],
      { rot: [-Math.PI / 2, 0, 0], shadow: false });
}

function buildSurroundings() {
  // Mur de briques graffé derrière le terrain (côté gauche de la caméra)
  const bricks = canvasTex(4096, 512, (g, w, h) => {
    g.fillStyle = '#4A2E2A'; g.fillRect(0, 0, w, h);
    for (let y = 0; y < h; y += 32) for (let x = ((y / 32) % 2) * 32; x < w; x += 64) {
      const v = 60 + Math.random() * 40; g.fillStyle = `rgb(${v + 30},${v * 0.55},${v * 0.45})`; g.fillRect(x + 2, y + 2, 60, 28);
    }
    noise(g, w, h, 40000, 0.25);
    const tag = (txt, x, y, size, fill, rot) => {
      g.save(); g.translate(x, y); g.rotate(rot); g.font = `${size}px "Sedgwick Ave Display"`; g.lineJoin = 'round';
      g.lineWidth = size * 0.08; g.strokeStyle = '#0B1220'; g.strokeText(txt, 0, 0); g.fillStyle = fill; g.fillText(txt, 0, 0); g.restore();
    };
    const gr = g.createLinearGradient(700, 0, 1800, 0); gr.addColorStop(0, '#F97316'); gr.addColorStop(1, '#FACC15');
    tag('HOOPS', 650, 400, 330, gr, -0.05); tag('CS', 2250, 380, 260, '#60A5FA', 0.06); tag('NIGHT BALL', 2850, 330, 150, '#F472B6', -0.04);
    noise(g, w, h, 20000, 0.18);
  });
  const wallMat = std({ map: bricks, roughness: 0.95 });
  add(new THREE.BoxGeometry(0.4, 4, 32), wallMat, [-9.5, 2, ZR - 8]);
  // Grillage (côté droit et fond), poteaux
  const mesh = canvasTex(256, 256, (g, w, h) => {
    g.strokeStyle = 'rgba(190,198,210,1)'; g.lineWidth = 6;
    g.beginPath(); g.moveTo(0, 0); g.lineTo(w, h); g.moveTo(w, 0); g.lineTo(0, h); g.stroke();
  }, [40, 6]);
  const fenceMat = std({ map: mesh, transparent: true, alphaTest: 0.3, side: THREE.DoubleSide, metalness: 0.6, roughness: 0.5 });
  const fence = (w, pos, rotY) => add(new THREE.PlaneGeometry(w, 4.5), fenceMat, pos, { rot: [0, rotY, 0], shadow: false });
  fence(30, [0, 2.25, ZR + 4.5], 0); fence(30, [9, 2.25, ZR - 8], Math.PI / 2);
  const steel = std({ color: 0x4B5563, metalness: 0.7, roughness: 0.45 });
  for (let z = ZR - 22; z <= ZR + 4.5; z += 3) add(new THREE.CylinderGeometry(0.04, 0.04, 4.6, 10), steel, [9, 2.3, z]);
  for (let x = -9; x <= 9; x += 3) add(new THREE.CylinderGeometry(0.04, 0.04, 4.6, 10), steel, [x, 2.3, ZR + 4.5]);

  // Ville au loin : immeubles aux fenêtres allumées
  const win = canvasTex(256, 512, (g, w, h) => {
    g.fillStyle = '#0D1326'; g.fillRect(0, 0, w, h);
    for (let y = 14; y < h - 14; y += 30) for (let x = 12; x < w - 12; x += 26)
      if (Math.random() < 0.1) { g.fillStyle = `rgba(255,${190 + Math.random() * 50 | 0},${110 + Math.random() * 60 | 0},${0.5 + Math.random() * 0.5})`; g.fillRect(x, y, 12, 16); }
  });
  let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 60; i++) {
    const a = rnd() * Math.PI * 1.4 - 0.2, r = 95 + rnd() * 50, w = 10 + rnd() * 14, h = 18 + rnd() * 55;
    const t = win.clone(); t.needsUpdate = true; t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(w / 6, h / 12);
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, w), new THREE.MeshBasicMaterial({ map: t, fog: false, color: 0x5E6380 }));
    m.position.set(Math.cos(a) * r, h / 2 - 1, ZR + Math.sin(a) * r * 0.8 + 10); m.lookAt(0, h / 2, ZR); scene.add(m);
  }
  const moon = new THREE.Mesh(new THREE.SphereGeometry(3, 24, 16), new THREE.MeshBasicMaterial({ color: 0xFFF1C4, fog: false }));
  moon.position.set(-30, 60, ZR + 90); moon.visible = false;

  // Projecteurs sur poteaux
  for (const [x, z] of [[-8.6, ZR - 1], [8.4, ZR - 10]]) {
    add(new THREE.CylinderGeometry(0.08, 0.11, 8, 12), steel, [x, 4, z]);
    const head = add(new THREE.BoxGeometry(0.9, 0.35, 0.5), std({ color: 0x1F2937, metalness: 0.5, roughness: 0.4 }), [x, 8.05, z]);
    const lens = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 0.28), new THREE.MeshBasicMaterial({ color: 0xFFF6DE }));
    lens.position.set(x, 7.9, z); lens.lookAt(0, 0, ZR - 3); scene.add(lens);
  }
}

function buildHoop() {
  const steel = std({ color: 0x374151, metalness: 0.75, roughness: 0.35 });
  const orange = std({ color: 0xE5560F, metalness: 0.55, roughness: 0.35 });
  // poteau + bras
  add(new THREE.CylinderGeometry(0.1, 0.12, 3.95, 18), steel, [0, 1.975, BOARD_Z + 1.25]);
  add(new THREE.BoxGeometry(0.22, 1.5, 0.22), std({ color: 0x1E40AF, roughness: 0.8 }), [0, 0.75, BOARD_Z + 1.25]);   // protection
  add(new THREE.BoxGeometry(0.12, 0.12, 1.3), steel, [0, 3.85, BOARD_Z + 0.62]);
  add(new THREE.BoxGeometry(0.12, 0.12, 1.3), steel, [0, 3.35, BOARD_Z + 0.62], { rot: [0.35, 0, 0] });
  // planche : acier peint blanc, carré orange, cadre
  const boardTex = canvasTex(1024, 600, (g, w, h) => {
    g.fillStyle = '#E8EAEE'; g.fillRect(0, 0, w, h); noise(g, w, h, 20000, 0.1);
    for (let i = 0; i < 30; i++) { g.fillStyle = `rgba(120,80,40,${Math.random() * 0.15})`; g.fillRect(Math.random() * w, Math.random() * h, 3 + Math.random() * 30, 2 + Math.random() * 6); }
    g.strokeStyle = '#E5560F'; g.lineWidth = 16; g.strokeRect(w / 2 - 170, h - 330, 340, 250); g.strokeStyle = '#111827'; g.lineWidth = 22; g.strokeRect(11, 11, w - 22, h - 22);
  });
  add(new THREE.BoxGeometry(1.83, 1.07, 0.05), [steel, steel, steel, steel, std({ map: boardTex, roughness: 0.6, metalness: 0.1 }), steel],
      [0, 2.9 + 0.535, BOARD_Z], { rot: [0, Math.PI, 0] });
  add(new THREE.BoxGeometry(0.16, 0.06, 0.2), orange, [0, RIM_Y - 0.02, BOARD_Z - 0.1]);
}

// Cercle + filet à chaînes, dans un groupe qui peut plier vers le bas au moment du dunk
const flexG = new THREE.Group(); flexG.position.set(0, RIM_Y, BOARD_Z - 0.02); scene.add(flexG);
const rimG = new THREE.Group(); rimG.position.set(0, 0, ZR - (BOARD_Z - 0.02)); flexG.add(rimG);
const netG = new THREE.Group(); rimG.add(netG);
{
  const orange = std({ color: 0xE5560F, metalness: 0.55, roughness: 0.35 });
  const rim = new THREE.Mesh(new THREE.TorusGeometry(RIM_R, 0.011, 12, 64), orange); rim.rotation.x = Math.PI / 2; rim.castShadow = true; rimG.add(rim);
  const chain = std({ color: 0xC9CED6, metalness: 0.9, roughness: 0.3 });
  const link = new THREE.TorusGeometry(0.012, 0.0035, 5, 10);
  for (let k = 0; k < 12; k++) {
    const a = (k / 12) * Math.PI * 2, b = a + 0.32;
    const p1 = new THREE.Vector3(RIM_R * Math.cos(a), 0, RIM_R * Math.sin(a));
    const p3 = new THREE.Vector3(0.14 * Math.cos(b), -0.45, 0.14 * Math.sin(b));
    const curve = new THREE.QuadraticBezierCurve3(p1, p1.clone().lerp(p3, 0.5).add(new THREE.Vector3(0, -0.03, 0)), p3);
    const n = 18;
    const inst = new THREE.InstancedMesh(link, chain, n); inst.castShadow = true;
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0);
    for (let i = 0; i < n; i++) {
      const p = curve.getPoint(i / (n - 1)), tg = curve.getTangent(i / (n - 1));
      q.setFromUnitVectors(up, tg); if (i % 2) q.multiply(new THREE.Quaternion().setFromAxisAngle(up, Math.PI / 2));
      q.multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI / 2));
      m.compose(p, q, new THREE.Vector3(1, 1.6, 1)); inst.setMatrixAt(i, m);
    }
    netG.add(inst);
  }
}

// ============================================================ Ballon
const ballTex = canvasTex(1024, 512, (g, w, h) => {
  g.fillStyle = '#C8571B'; g.fillRect(0, 0, w, h);
  for (let i = 0; i < 90000; i++) { const v = Math.random(); g.fillStyle = v > 0.5 ? 'rgba(255,170,110,.18)' : 'rgba(60,20,5,.2)'; g.fillRect(Math.random() * w, Math.random() * h, 2, 2); }
  g.strokeStyle = '#1A0C05'; g.lineWidth = 9;
  for (const x of [0, w / 4, w / 2, 3 * w / 4]) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke(); }
  g.beginPath(); g.moveTo(0, h / 2); g.lineTo(w, h / 2); g.stroke();
});
const ballBump = canvasTex(512, 256, (g, w, h) => { g.fillStyle = '#808080'; g.fillRect(0, 0, w, h); noise(g, w, h, 60000, 0.9, true); noise(g, w, h, 30000, 0.9); }, null, false);
const BALL_R = 0.12;
const ball = new THREE.Mesh(new THREE.SphereGeometry(BALL_R, 40, 28), std({ map: ballTex, bumpMap: ballBump, bumpScale: 1.2, roughness: 0.72 }));
ball.castShadow = true; scene.add(ball);
const ghosts = [0.25, 0.12].map(o => { const m = new THREE.Mesh(ball.geometry, std({ map: ballTex, transparent: true, opacity: o, depthWrite: false })); scene.add(m); return m; });

// ============================================================ Lumières de nuit
scene.add(new THREE.HemisphereLight(0x5466A8, 0x1A1410, 0.55));
function flood(pos, target, color, intensity, shadow) {
  const l = new THREE.SpotLight(color, intensity, 0, 0.62, 0.55, 1.4);
  l.position.set(...pos); l.target.position.set(...target);
  if (shadow) { l.castShadow = true; l.shadow.mapSize.set(mobile ? 1024 : 2048, mobile ? 1024 : 2048); l.shadow.bias = -0.0004; l.shadow.normalBias = 0.02; }
  scene.add(l, l.target); return l;
}
flood([-8.6, 7.9, ZR - 1], [0, 0, ZR - 3], 0xFFF1D6, 380, true);
flood([8.4, 7.9, ZR - 10], [-1, 0, ZR - 3], 0xDCE6FF, 260, !mobile);
const rimLight = new THREE.DirectionalLight(0xF97316, 0.7); rimLight.position.set(0, 6, ZR + 12); scene.add(rimLight);

// ============================================================ Joueurs
const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
const loadGLB = (n) => new Promise((res, rej) => loader.load(BASE + n, res, undefined, rej));

class Player {
  constructor(gltf, stripXZ) {
    this.model = gltf.scene; this.model.scale.setScalar(0.01);
    this.model.traverse(o => {
      if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.frustumCulled = false;
        const ms = Array.isArray(o.material) ? o.material : [o.material];
        ms.forEach(m => { m.envMapIntensity = 0.6; if (m.roughness !== undefined) m.roughness = Math.max(0.55, m.roughness); m.metalness = 0; }); }
    });
    scene.add(this.model);
    this.bone = (n) => this.model.getObjectByName('mx_' + n);
    this.hips = this.bone('Hips'); this.lh = this.bone('LeftHand'); this.rh = this.bone('RightHand');
    this.mixer = new THREE.AnimationMixer(this.model);
    this.clips = {}; this.act = {}; this.rootTrack = {};
    for (const c of gltf.animations) {
      this.clips[c.name] = c;
      if (stripXZ.includes(c.name)) this.rootTrack[c.name] = this.strip(c);
      const a = this.mixer.clipAction(c); a.play(); a.setEffectiveWeight(0); a.paused = true; this.act[c.name] = a;
    }
  }
  // Retire l'avancée des hanches (x, z) d'un mouvement et la garde à part : c'est nous qui déplaçons le joueur
  strip(clip) {
    const tr = clip.tracks.find(t => t.name === 'mx_Hips.position');
    const out = { times: tr.times.slice(), x: [], z: [] };
    const x0 = tr.values[0], z0 = tr.values[2];
    for (let i = 0; i < tr.times.length; i++) { out.x.push(tr.values[i * 3] - x0); out.z.push(tr.values[i * 3 + 2] - z0); tr.values[i * 3] = x0; tr.values[i * 3 + 2] = z0; }
    return out;
  }
  rootAt(name, t) {
    const r = this.rootTrack[name]; if (!r) return [0, 0];
    const T = r.times; t = Math.max(0, Math.min(T[T.length - 1], t));
    let i = 0; while (i < T.length - 2 && T[i + 1] < t) i++;
    const s = (t - T[i]) / Math.max(1e-6, T[i + 1] - T[i]);
    return [(r.x[i] + (r.x[i + 1] - r.x[i]) * s) * 0.01, (r.z[i] + (r.z[i + 1] - r.z[i]) * s) * 0.01];
  }
  // weights : { nomDuMouvement: [poids, tempsDansLeMouvement] }
  pose(weights) {
    for (const [n, a] of Object.entries(this.act)) {
      const w = weights[n]; a.setEffectiveWeight(w ? w[0] : 0);
      if (w) a.time = Math.min(w[1], this.clips[n].duration - 1e-3);
    }
    this.mixer.update(0);
  }
  handsLocal() {   // milieu des mains, par rapport à la position du joueur
    this.model.updateMatrixWorld(true);
    const a = this.lh.getWorldPosition(new THREE.Vector3()), b = this.rh.getWorldPosition(new THREE.Vector3());
    return a.add(b).multiplyScalar(0.5).sub(this.model.position);
  }
  // Ballon tenu dans la main droite : un peu au-delà du poignet, dans le prolongement de l'avant-bras
  ballInRightHand() {
    this.model.updateMatrixWorld(true);
    const h = this.rh.getWorldPosition(new THREE.Vector3());
    const e = this.bone('RightForeArm').getWorldPosition(new THREE.Vector3());
    return h.clone().add(h.clone().sub(e).normalize().multiplyScalar(0.13));
  }
  handsWorld() { this.model.updateMatrixWorld(true); const a = this.lh.getWorldPosition(new THREE.Vector3()), b = this.rh.getWorldPosition(new THREE.Vector3()); return a.add(b).multiplyScalar(0.5); }
}

// ============================================================ Chorégraphie (en secondes d'action)
const sm = (a, b, x) => { const s = Math.min(1, Math.max(0, (x - a) / (b - a))); return s * s * (3 - 2 * s); };
const T = {
  P0: 0.15,          // le passeur commence son lancer
  REL: 1.5,          // instant du lâcher, dans le mouvement « throw »
  J: 2.75,           // début du saut du dunkeur (mouvement « jumphang »)
  CATCH: 0.07,       // le ballon arrive dans les mains (dans « jumphang »)
  GRAB: 0.2,         // les mains attrapent le cercle (dans « jumphang »)
  DROP: 1.25,        // il commence à lâcher le cercle (dans « jumphang »)
  LET: 0.3, LAND: 0.56,   // dans « drop » : lâche le cercle / touche le sol
  END: 5.2,
};
const GRIP = new THREE.Vector3(0, RIM_Y + 0.025, ZR - RIM_R - 0.02);   // mains sur l'avant du cercle
const PASSER_START = new THREE.Vector3(-2.7, 0, ZR - 9.6);
const RUN_SPEED = 4.83;
let P, D, O_AIR, CATCH_POINT, PASS_YAW, REL_POINT, REL_VEL, RELEASE_OFFSET;

function passerState(t) {
  const p = t - T.P0;
  const tw = P.clips.throw.duration;
  const wCheer = sm(tw - 0.35, tw + 0.15, p);
  P.pose({ throw: [1 - wCheer, Math.max(0, p)], cheer: [wCheer, Math.max(0, p - tw + 0.35)] });
  const [rx, rz] = P.rootAt('throw', Math.max(0, p));
  const c = Math.cos(PASS_YAW), s = Math.sin(PASS_YAW);
  P.model.position.set(PASSER_START.x + rx * c + rz * s, 0, PASSER_START.z - rx * s + rz * c);
  P.model.rotation.y = PASS_YAW;
}

function dunkerState(t) {
  const c = t - T.J;                       // temps dans « jumphang »
  const dur = D.clips.run.duration;
  if (c < T.DROP) {
    const wJ = sm(-0.32, 0, c);
    D.pose({ run: [1 - wJ, ((t % dur) + dur) % dur], jumphang: [wJ, Math.max(0, c)] });
    const free = new THREE.Vector3(0, 0, GRIP.z - 0.75 + RUN_SPEED * Math.min(c, 0) + 1.2 * Math.max(0, c));
    let off;
    if (c < T.GRAB) {
      const k = 1 - Math.pow(1 - sm(-0.36, 0.02, c), 2);       // impulsion du saut
      off = free.clone().lerp(O_AIR, k);
    } else {
      off = GRIP.clone().sub(D.handsLocal());                  // suspendu : les mains restent sur le cercle
    }
    D.model.position.copy(off);
    if (c >= T.GRAB) { D.model.position.set(0, 0, 0); D.model.position.copy(GRIP.clone().sub(D.handsLocal())); }
    return;
  }
  const d = c - T.DROP;                    // temps dans « drop »
  const wDrop = sm(0, 0.18, d), wCheer = sm(1.0, 1.35, d);
  D.pose({ jumphang: [1 - wDrop, c], drop: [wDrop * (1 - wCheer), d], cheer: [wCheer, Math.max(0, d - 1.0)] });
  if (d < T.LET) { D.model.position.set(0, 0, 0); D.model.position.copy(GRIP.clone().sub(D.handsLocal())); RELEASE_OFFSET = D.model.position.clone(); return; }
  const f = sm(T.LET, T.LAND, d);
  D.model.position.set(RELEASE_OFFSET.x, RELEASE_OFFSET.y * (1 - f * f), RELEASE_OFFSET.z);
}

const G = -9.81;
function ballState(t) {
  const tRel = T.P0 + T.REL, tCatch = T.J + T.CATCH, tGrab = T.J + T.GRAB;
  const fwd = (yaw) => new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw));
  if (t <= tRel) return P.handsWorld().add(fwd(PASS_YAW).multiplyScalar(0.13)).add(new THREE.Vector3(0, 0.03, 0));
  if (t <= tCatch) {
    const u = t - tRel;
    return REL_POINT.clone().add(REL_VEL.clone().multiplyScalar(u)).add(new THREE.Vector3(0, 0.5 * G * u * u, 0));
  }
  if (t <= tGrab) return D.ballInRightHand();
  // dans le cercle, puis rebonds
  let u = t - tGrab, p = D_BALL0.clone(), v = new THREE.Vector3((0 - p.x) * 3, -2.2, (ZR - p.z) * 3);
  const dt = 1 / 240; let bounces = 0;
  for (let s = 0; s < u; s += dt) {
    v.y += G * dt; p.addScaledVector(v, dt);
    if (p.y < RIM_Y - 0.3) { v.x *= 0.96; v.z *= 0.96; }
    if (p.y < BALL_R) { p.y = BALL_R; v.y = -v.y * 0.62; v.z = -0.6 - bounces * 0.1; v.x = 0.25; bounces++; }
  }
  return p;
}
let D_BALL0;

// ============================================================ Caméra (plans de cinéma)
const SHOTS = [
  [0.0, [-4.6, 1.7, ZR - 14.5], [-1.4, 1.5, ZR - 6.0]],
  [0.9, [-5.6, 1.15, ZR - 9.0], [-2.5, 1.7, ZR - 8.4]],
  [1.6, [-6.4, 1.4, ZR - 7.2], [-1.6, 2.4, ZR - 6.0]],
  [2.3, [-7.0, 2.0, ZR - 4.6], [-0.4, 3.0, ZR - 2.4]],
  [2.75, [1.3, 1.0, ZR - 4.4], [0.0, 2.7, ZR - 0.4]],
  [3.15, [0.9, 1.05, ZR - 3.5], [0.0, 2.85, ZR - 0.1]],
  [3.9, [3.2, 1.6, ZR - 4.4], [0.0, 2.0, ZR - 0.6]],
  [5.2, [5.4, 2.4, ZR - 11.5], [-1.2, 1.4, ZR - 4.0]],
];
function hermite(keys, t, idx) {
  if (t <= keys[0][0]) return keys[0][idx];
  if (t >= keys[keys.length - 1][0]) return keys[keys.length - 1][idx];
  let i = 0; while (keys[i + 1][0] < t) i++;
  const k0 = keys[Math.max(0, i - 1)], k1 = keys[i], k2 = keys[i + 1], k3 = keys[Math.min(keys.length - 1, i + 2)];
  const h = k2[0] - k1[0], s = (t - k1[0]) / h;
  const h00 = 2 * s ** 3 - 3 * s ** 2 + 1, h10 = s ** 3 - 2 * s ** 2 + s, h01 = -2 * s ** 3 + 3 * s ** 2, h11 = s ** 3 - s ** 2;
  return k1[idx].map((_, j) => {
    const m1 = i > 0 ? (k2[idx][j] - k0[idx][j]) / (k2[0] - k0[0]) : 0;
    const m2 = i + 2 < keys.length ? (k3[idx][j] - k1[idx][j]) / (k3[0] - k1[0]) : 0;
    return h00 * k1[idx][j] + h10 * h * m1 + h01 * k2[idx][j] + h11 * h * m2;
  });
}
const tgt = new THREE.Vector3();
function placeCamera(t, ballPos) {
  const portrait = innerWidth / innerHeight < 0.9;
  const p = hermite(SHOTS, t, 1), q = hermite(SHOTS, t, 2);
  tgt.set(...q);
  const w = 0.55 * (sm(1.6, 1.85, t) - sm(2.45, 2.7, t));          // suit le ballon pendant le lob
  if (w > 0) tgt.lerp(ballPos, w);
  const k = portrait ? 1.45 : 1;
  camera.position.set(q[0] + (p[0] - q[0]) * k, q[1] + (p[1] - q[1]) * k, q[2] + (p[2] - q[2]) * k);
  const tg = T.J + T.GRAB;
  if (t > tg) { const a = 0.05 * Math.exp(-(t - tg) * 6) * Math.sin((t - tg) * 60); camera.position.y += a; camera.position.x += a * 0.5; }
  camera.fov = portrait ? 56 : 38; camera.aspect = innerWidth / innerHeight;
  camera.lookAt(tgt); camera.updateProjectionMatrix();
}

// Ralenti façon 2K autour de l'attrapé et du dunk
const rate = (t) => 1 - 0.7 * (sm(T.J - 0.25, T.J - 0.1, t) - sm(T.J + 0.3, T.J + 0.45, t));
const REAL = []; for (let ms = 0, t = 0; ms <= 9000; ms++) { REAL.push(t); t += rate(t) / 1000; }
const animTime = (ms) => REAL[Math.max(0, Math.min(REAL.length - 1, Math.round(ms)))];

// ============================================================ Effets d'interface
const $ = (id) => document.getElementById(id);
let EVENTS = [], nextEvent = 0;
function fx(t) { while (nextEvent < EVENTS.length && t >= EVENTS[nextEvent][0]) EVENTS[nextEvent++][1](); }

function render(ms) {
  const t = Math.min(animTime(ms), T.END + 2);
  passerState(t); dunkerState(t);
  const b = ballState(t); ball.position.copy(b); ball.rotation.x = Math.max(0, t - T.P0 - T.REL) * -9;
  ghosts.forEach((g, i) => { const tt = t - 0.035 * (i + 1); g.visible = t > T.P0 + T.REL + 0.05 && t < T.J + T.CATCH - 0.02;
    if (g.visible) { const u = tt - T.P0 - T.REL; g.position.copy(REL_POINT).addScaledVector(REL_VEL, u).add(new THREE.Vector3(0, 0.5 * G * u * u, 0)); } });
  const tg = T.J + T.GRAB;
  const bend = t < tg ? 0 : t < T.J + T.DROP + T.LET ? 0.11 : 0.11 * Math.exp(-(t - (T.J + T.DROP + T.LET)) * 9) * Math.cos((t - (T.J + T.DROP + T.LET)) * 37);
  flexG.rotation.x = bend;
  const nt = t - tg; netG.scale.y = nt > 0 ? 1 + 0.35 * Math.exp(-nt * 6) * Math.cos(nt * 22) : 1; netG.rotation.z = nt > 0 ? 0.12 * Math.exp(-nt * 5) * Math.sin(nt * 25) : 0;
  placeCamera(t, b);
  fx(t);
  renderer.render(scene, camera);
}
window.aoRender = render;
window.aoDebug = () => ({ P: P.model.position.toArray(), D: D.model.position.toArray(), yaw: PASS_YAW, catch: CATCH_POINT.toArray(), rel: REL_POINT.toArray() });
addEventListener('resize', () => renderer.setSize(innerWidth, innerHeight));

// ============================================================ Chargement puis lecture
const fontsReady = Promise.race([Promise.all([document.fonts.load('100px "Sedgwick Ave Display"'), document.fonts.load('100px Bungee')]),
                                 new Promise((r) => setTimeout(r, 1500))]);
Promise.all([loadGLB('passer.glb'), loadGLB('dunker.glb'), fontsReady]).then(([pg, dg]) => {
  buildCourt(); buildSurroundings(); buildHoop();
  P = new Player(pg, ['throw', 'cheer']);
  D = new Player(dg, ['run', 'cheer']);

  // Où le dunkeur doit-il être en l'air pour que ses mains arrivent pile sur le cercle ?
  D.model.position.set(0, 0, 0); D.pose({ jumphang: [1, T.GRAB] });
  O_AIR = GRIP.clone().sub(D.handsLocal());
  // Où sont ses mains au moment où il attrape le ballon ?
  D.model.position.copy(O_AIR); D.pose({ jumphang: [1, T.CATCH] });
  CATCH_POINT = D.ballInRightHand();
  D.model.position.copy(O_AIR); D.pose({ jumphang: [1, T.GRAB] });
  D_BALL0 = D.ballInRightHand();
  // Le passeur se tourne vers le point d'attrapé ; on calcule son lâcher et la trajectoire du lob
  PASS_YAW = Math.atan2(CATCH_POINT.x - PASSER_START.x, CATCH_POINT.z - PASSER_START.z) - 0.1;
  passerState(T.P0 + T.REL);
  REL_POINT = P.handsWorld().add(new THREE.Vector3(Math.sin(PASS_YAW), 0, Math.cos(PASS_YAW)).multiplyScalar(0.13)).add(new THREE.Vector3(0, 0.03, 0));
  const F = (T.J + T.CATCH) - (T.P0 + T.REL);
  REL_VEL = CATCH_POINT.clone().sub(REL_POINT).sub(new THREE.Vector3(0, 0.5 * G * F * F, 0)).divideScalar(F);

  EVENTS = [
    [0.0, () => $('bars').classList.add('on')],
    [T.P0 + T.REL + 0.05, () => $('lob').classList.add('on')],
    [T.P0 + T.REL + 0.75, () => { $('lob').classList.remove('on'); $('lob').classList.add('off'); }],
    [T.J + T.GRAB, () => $('flash').classList.add('on')],
    [T.J + T.GRAB + 0.04, () => $('oop').classList.add('on')],
    [T.J + 1.3, () => { $('oop').classList.remove('on'); $('oop').classList.add('off'); }],
    [T.J + 1.7, () => { $('bars').classList.remove('on'); $('tag').classList.add('on'); }],
    [T.J + 2.05, () => $('sticker').classList.add('on')],
  ];
  $('loading').classList.add('gone');
  window.aoStarted = true;
  if (window.aoManual) { render(0); return; }
  const END_MS = REAL.findIndex(v => v >= T.END) + 250;
  let start = null;
  const loop = (now) => {
    if (window.aoDone) return;
    if (start === null) start = now;
    const el = now - start; render(el);
    if (el < END_MS) requestAnimationFrame(loop); else window.aoFinish();
  };
  requestAnimationFrame(loop);
}).catch((e) => { console.error('intro3d', e); window.aoFinish(); });
</script>
</body></html>
"""


def intro3d_page() -> str:
    """La page HTML complète de l'intro 3D."""
    return _PAGE.replace("__THREE__", THREE_VERSION)