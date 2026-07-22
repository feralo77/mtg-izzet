#!/usr/bin/env node
// ============================================================================
// Recolector de meta de UR / Izzet Prowess desde mtgtop8.
//
// Baja las ~20 listas recientes del arquetipo, parsea main + sideboard desde la
// exportacion en texto plano (mtgtop8.com/mtgo?d=<id>) y produce meta/prowess.json:
//   - lista media (consenso) main + sideboard
//   - agregado por carta con VARIANZA (min / max / tipico / % / media)
//   - TENDENCIA vs la tirada anterior (que sube / baja / entra / sale)
//   - DELTAS vs tu 75 (meta/mi-75.json): que juega el campo y tu no, y desvios
//   - SUGERENCIAS por reglas (datos, no coaching)
//
// Lo consume la pestana "Meta" del dashboard. NO necesita nada instalado (Node 18+).
//
// Uso:  node scripts/meta_mtgtop8.mjs [--out meta] [--milista meta/mi-75.json] [--date YYYY-MM-DD]
// ============================================================================
import { writeFileSync, mkdirSync, readFileSync, existsSync } from 'node:fs';

const ARCH_URL = 'https://mtgtop8.com/archetype?a=351&meta=54&f=MO';
const EXPORT = (id) => `https://mtgtop8.com/mtgo?d=${id}`;
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';

// Umbrales (ajustables): que consideramos nucleo / habitual / notable.
const CORE = 90, HABIT = 50;          // main: nucleo >=90%, habitual 50-89%, flex <50%
const SIDE_KEEP = 40;                 // sideboard: "fijas" del consenso >=40%
const FIELD_MAIN_NOTABLE = 50;        // para deltas: carta de main "del campo" si >=50%
const FIELD_SIDE_NOTABLE = 25;        // para deltas: carta de sideboard "del campo" si >=25%
const RARE_MAIN = 50, RARE_SIDE = 25; // "tu la juegas pero el campo apenas": por debajo de esto
const TREND_DELTA = 15;               // pts de % para marcar subida/bajada
const TREND_MIN = 15;                 // % minimo para reportar una carta nueva/fuera

const arg = (flag, def) => { const i = process.argv.indexOf(flag); return i > -1 ? process.argv[i + 1] : def; };
const outDir = arg('--out', 'meta');
const miPath = arg('--milista', `${outDir}/mi-75.json`);
const stamp = arg('--date', '');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const norm = (n) => n.toLowerCase().replace(/[^a-z0-9]/g, '');
// Manabase conocida: una desviacion de +-1 en estas cartas es ruido, no una sugerencia.
const LANDS = new Set(['aridmesa', 'scaldingtarn', 'woodedfoothills', 'bloodstainedmire', 'floodedstrand',
  'polluteddelta', 'steamvents', 'bloodcrypt', 'sacredfoundry', 'spirebluffcanal', 'fieryislet',
  'thunderingfalls', 'mountain', 'island', 'snowcoveredmountain', 'snowcoveredisland', 'barbarianring',
  'sunbakedcanyon', 'wastes']);

async function get(url) {
  const r = await fetch(url, { headers: { 'User-Agent': UA, 'Accept-Language': 'es-ES,es;q=0.9' } });
  if (!r.ok) throw new Error(`HTTP ${r.status} en ${url}`);
  return r.text();
}

function parseList(txt) {
  const main = [], side = [];
  let bucket = main;
  for (const raw of txt.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;
    if (/^sideboard$/i.test(line)) { bucket = side; continue; }
    const m = line.match(/^(\d+)\s+(.+?)\s*$/);
    if (m) bucket.push({ q: parseInt(m[1], 10), n: m[2] });
  }
  return { main, side };
}

// Agrega una zona a lo largo de todos los mazos, con varianza.
function aggregate(decks, zone, total) {
  const map = new Map();
  for (const d of decks) for (const { q, n } of d[zone]) {
    if (!map.has(n)) map.set(n, { copies: [], counts: {} });
    const e = map.get(n); e.copies.push(q); e.counts[q] = (e.counts[q] || 0) + 1;
  }
  const rows = [...map.entries()].map(([n, e]) => {
    const decksN = e.copies.length, sum = e.copies.reduce((a, b) => a + b, 0);
    const typical = +Object.entries(e.counts).sort((a, b) => b[1] - a[1] || b[0] - a[0])[0][0];
    return {
      n, decks: decksN, pct: Math.round((decksN / total) * 100),
      avg: +(sum / decksN).toFixed(2), typical,
      min: Math.min(...e.copies), max: Math.max(...e.copies),
    };
  });
  rows.sort((a, b) => b.pct - a.pct || b.avg - a.avg || a.n.localeCompare(b.n));
  return rows;
}

function readJSON(p) { try { return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) : null; } catch { return null; } }

// --- 1) ids del arquetipo ---------------------------------------------------
console.error('Bajando pagina del arquetipo...');
const arch = await get(ARCH_URL);
const ids = [...new Set([...arch.matchAll(/[?&]d=(\d+)/g)].map((m) => m[1]))];
if (!ids.length) throw new Error('No se encontraron mazos (¿cambio el HTML de mtgtop8?)');
console.error(`  ${ids.length} mazos`);

// --- 2) bajar y parsear -----------------------------------------------------
const decks = [];
for (const id of ids) {
  try {
    const { main, side } = parseList(await get(EXPORT(id)));
    const mc = main.reduce((s, c) => s + c.q, 0);
    if (mc < 40) { console.error(`  d=${id}: main=${mc} incompleto, descartado`); continue; }
    decks.push({ id, main, side });
    await sleep(120);
  } catch (e) { console.error(`  d=${id}: ${e.message}`); }
}
const N = decks.length;
if (!N) throw new Error('No se pudo parsear ninguna lista');

const mainAgg = aggregate(decks, 'main', N);
const sideAgg = aggregate(decks, 'side', N);

// --- 3) lista media (consenso) ----------------------------------------------
const listaMain = mainAgg.filter((r) => r.pct >= HABIT).map((r) => ({ n: r.n, q: r.typical }));
const listaSide = sideAgg.filter((r) => r.pct >= SIDE_KEEP).map((r) => ({ n: r.n, q: r.typical }));
const sideDisputa = sideAgg.filter((r) => r.pct >= TREND_MIN && r.pct < SIDE_KEEP)
  .map((r) => ({ n: r.n, pct: r.pct, q: r.typical }));
const totalMain = listaMain.reduce((s, c) => s + c.q, 0);
const totalSide = listaSide.reduce((s, c) => s + c.q, 0);

// Indice de consenso: copias en cartas nucleo (>=CORE%) / total de la lista media (main)
const nucleoCopies = mainAgg.filter((r) => r.pct >= CORE)
  .reduce((s, r) => s + (listaMain.find((c) => c.n === r.n)?.q || r.typical), 0);
const consenso = Math.round((nucleoCopies / (totalMain || 1)) * 100);

// --- 4) tendencia vs tirada anterior ----------------------------------------
const prev = readJSON(`${outDir}/prowess.json`);
let tendencia = { hayPrevio: false, suben: [], bajan: [], nuevas: [], fuera: [] };
if (prev && prev.main && prev.side) {
  // Clave por ZONA: una carta puede estar en main y en sideboard con % distintos.
  const zkey = (zona, n) => zona + '|' + norm(n);
  const pmap = new Map(), pname = new Map();
  const learn = (rows, zona) => { for (const r of rows) { const k = zkey(zona, r.n); pmap.set(k, r.pct); pname.set(k, r.n); } };
  learn(prev.main, 'main'); learn(prev.side, 'side');
  const nowKeys = new Set();
  const scan = (rows, zona) => { for (const r of rows) {
    const k = zkey(zona, r.n); nowKeys.add(k); const p = pmap.get(k);
    if (p == null) { if (r.pct >= TREND_MIN) tendencia.nuevas.push({ n: r.n, pct: r.pct, zona }); }
    else if (r.pct - p >= TREND_DELTA) tendencia.suben.push({ n: r.n, de: p, a: r.pct, zona });
    else if (p - r.pct >= TREND_DELTA) tendencia.bajan.push({ n: r.n, de: p, a: r.pct, zona });
  } };
  tendencia.hayPrevio = true;
  scan(mainAgg, 'main'); scan(sideAgg, 'side');
  for (const [k, p] of pmap) if (!nowKeys.has(k) && p >= TREND_MIN)
    tendencia.fuera.push({ n: pname.get(k), pctPrev: p, zona: k.split('|')[0] });
}

// --- 5) deltas vs tu 75 -----------------------------------------------------
const mi = readJSON(miPath);
let deltas = null;
if (mi && mi.main && mi.side) {
  const miMain = new Map(mi.main.map((c) => [norm(c.n), c.q]));
  const miSide = new Map(mi.side.map((c) => [norm(c.n), c.q]));
  const campoJuegaYoNo = [], yoJuegoCampoNo = [], desviaciones = [];
  const isMinor = (k, mio, campo) => LANDS.has(k) && Math.abs(mio - campo) <= 1;
  for (const r of mainAgg) {
    const k = norm(r.n);
    if (r.pct >= FIELD_MAIN_NOTABLE && !miMain.has(k)) campoJuegaYoNo.push({ n: r.n, pct: r.pct, zona: 'main' });
    else if (miMain.has(k) && miMain.get(k) !== r.typical) desviaciones.push({ n: r.n, mio: miMain.get(k), campo: r.typical, pct: r.pct, zona: 'main', menor: isMinor(k, miMain.get(k), r.typical) });
  }
  for (const r of sideAgg) {
    const k = norm(r.n);
    if (r.pct >= FIELD_SIDE_NOTABLE && !miSide.has(k)) campoJuegaYoNo.push({ n: r.n, pct: r.pct, zona: 'side' });
    else if (miSide.has(k) && miSide.get(k) !== r.typical) desviaciones.push({ n: r.n, mio: miSide.get(k), campo: r.typical, pct: r.pct, zona: 'side', menor: isMinor(k, miSide.get(k), r.typical) });
  }
  // Para "yo la juego pero el campo apenas": mirar el % en la MISMA zona (no mezclar main y side).
  const fieldMainPct = new Map(mainAgg.map((r) => [norm(r.n), r.pct]));
  const fieldSidePct = new Map(sideAgg.map((r) => [norm(r.n), r.pct]));
  for (const [k, q] of miMain) { const p = fieldMainPct.get(k) || 0; if (p < RARE_MAIN) yoJuegoCampoNo.push({ n: mi.main.find((c) => norm(c.n) === k).n, mio: q, pct: p, zona: 'main' }); }
  for (const [k, q] of miSide) { const p = fieldSidePct.get(k) || 0; if (p < RARE_SIDE) yoJuegoCampoNo.push({ n: mi.side.find((c) => norm(c.n) === k).n, mio: q, pct: p, zona: 'side' }); }
  campoJuegaYoNo.sort((a, b) => b.pct - a.pct);
  deltas = { lista: mi.nombre || 'tu 75', campoJuegaYoNo, yoJuegoCampoNo, desviaciones };
}

// --- 6) sugerencias por reglas (datos, no coaching) -------------------------
const sug = [];
if (deltas) {
  for (const c of deltas.campoJuegaYoNo)
    sug.push(`El campo juega ${c.n} (${c.pct}% · ${c.zona}) y tu lista no lo lleva.`);
  for (const d of deltas.desviaciones) if (!d.menor)
    sug.push(`${d.n} (${d.zona}): tu ${d.mio}, el consenso ${d.campo}.`);
  for (const y of deltas.yoJuegoCampoNo)
    sug.push(`Llevas ${y.n} (${y.zona}) pero solo el ${y.pct}% del campo lo juega.`);
}
for (const t of tendencia.nuevas) sug.push(`Nuevo en el meta: ${t.n} (${t.pct}%).`);
for (const t of tendencia.suben) sug.push(`Sube ${t.n}: ${t.de}% → ${t.a}%.`);
for (const t of tendencia.bajan) sug.push(`Baja ${t.n}: ${t.de}% → ${t.a}%.`);

// --- 7) escribir ------------------------------------------------------------
mkdirSync(outDir, { recursive: true });
const out = {
  generado: stamp || null,
  fuente: ARCH_URL,
  mazos: N,
  consenso,
  listaMedia: { main: listaMain, side: listaSide, totalMain, totalSide, sideDisputa },
  main: mainAgg,
  side: sideAgg,
  tendencia,
  deltas,
  sugerencias: sug,
};
writeFileSync(`${outDir}/prowess.json`, JSON.stringify(out, null, 2));
console.error(`OK -> ${outDir}/prowess.json  (${N} mazos · consenso ${consenso}% · ${sug.length} sugerencias)`);
