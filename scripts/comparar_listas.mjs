#!/usr/bin/env node
// ============================================================================
// Comparador de listas de los jugadores.
//
// Lee cada listas/<nick>.txt (export de MTGO/Arena/mtggoldfish en texto plano),
// lo compara carta a carta:
//   - entre los jugadores (matriz cartas x jugadores),
//   - frente a La 75 Definitiva  (meta/mi-75.json, lista de referencia de Fer),
//   - frente al consenso del meta (meta/prowess.json, si existe).
// Produce listas/comparativa.json, que consume la pestana "Listas" del dashboard.
//
// No necesita nada instalado (Node 18+).
//
// Uso:  node scripts/comparar_listas.mjs [--dir listas] [--ref meta/mi-75.json]
//                                        [--meta meta/prowess.json] [--date YYYY-MM-DD]
// ============================================================================
import { readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const arg = (flag, def) => { const i = process.argv.indexOf(flag); return i > -1 ? process.argv[i + 1] : def; };
const DIR = arg('--dir', 'listas');
const REF = arg('--ref', 'meta/mi-75.json');
const META = arg('--meta', 'meta/prowess.json');
const ROSTER = arg('--roster', 'automation/jugadores.json');
const stamp = arg('--date', '');

const norm = (n) => n.toLowerCase().replace(/[^a-z0-9]/g, '');
// Quita sufijos de edicion que meten algunos exports: "(MID) 143", " #F", etc.
const clean = (n) => n.replace(/\s+\([A-Za-z0-9]{2,6}\)\s+\d+.*$/, '').replace(/\s+#.*$/, '').trim();
const readJSON = (p) => { try { return existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) : null; } catch { return null; } };

// --- Parser tolerante de una lista en texto plano ---------------------------
function parseList(txt) {
  // "Cabecera" = una linea de encabezado propia (Sideboard / SB / Deck / Maindeck, sola).
  // El prefijo "SB: 2 Carta" NO cuenta: se autoclasifica y no debe anular el corte por
  // linea en blanco (asi una lista con linea en blanco + alguna linea SB: se parsea bien).
  const hasHeader = /^\s*(sideboard|sb|deck|maindeck|main deck)\s*:?\s*$/im.test(txt);
  let titulo = null;
  const main = new Map(), side = new Map(); // norm -> {n, q}  (agrega duplicados)
  const add = (bucket, name, q) => {
    const k = norm(name); if (!k) return;
    const e = bucket.get(k); if (e) e.q += q; else bucket.set(k, { n: clean(name), q });
  };
  let bucket = main, seenMainCard = false;
  for (const raw of txt.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) { // linea en blanco: separa main/side SOLO si no hay cabecera explicita
      if (!hasHeader && seenMainCard && bucket === main) bucket = side;
      continue;
    }
    if (line.startsWith('#') || line.startsWith('//')) {
      if (titulo === null) { const t = line.replace(/^[#/]+\s*/, '').trim(); if (t) titulo = t; }
      continue;
    }
    if (/^(sideboard|sb)\b\s*:?\s*$/i.test(line)) { bucket = side; continue; }
    if (/^(deck|maindeck|main deck)\b\s*:?\s*$/i.test(line)) { bucket = main; continue; }
    let m = line.match(/^sb:\s*(\d+)\s*x?\s+(.+?)\s*$/i);     // "SB: 2 Card"
    if (m) { add(side, m[2], parseInt(m[1], 10)); continue; }
    m = line.match(/^(\d+)\s*x?\s+(.+?)\s*$/);                // "4 Card" / "4x Card"
    if (m) { add(bucket, m[2], parseInt(m[1], 10)); if (bucket === main) seenMainCard = true; continue; }
    // cualquier otra linea (encabezados raros) se ignora
  }
  const toArr = (mp) => [...mp.values()];
  return { titulo, main: toArr(main), side: toArr(side) };
}

const zoneCount = (arr) => arr.reduce((s, c) => s + c.q, 0);
const asMap = (arr) => new Map(arr.map((c) => [norm(c.n), c]));

// --- Cargar referencia (La 75 Definitiva) y meta ----------------------------
const refRaw = readJSON(REF);
if (!refRaw || !refRaw.main) { console.error(`No pude leer la referencia ${REF}`); process.exit(1); }
const ref = { nombre: refRaw.nombre || 'La 75 Definitiva', main: refRaw.main.map((c) => ({ n: c.n, q: c.q })), side: (refRaw.side || []).map((c) => ({ n: c.n, q: c.q })) };
const refMainMap = asMap(ref.main), refSideMap = asMap(ref.side);

const metaRaw = readJSON(META);
const metaMap = (zone) => {
  const m = new Map();
  if (metaRaw && metaRaw[zone]) for (const r of metaRaw[zone]) m.set(norm(r.n), { q: r.typical, pct: r.pct });
  return m;
};
const metaMainMap = metaMap('main'), metaSideMap = metaMap('side');

// --- Leer las listas de la carpeta ------------------------------------------
const files = existsSync(DIR) ? readdirSync(DIR).filter((f) => f.toLowerCase().endsWith('.txt')) : [];
const jugadores = [];
for (const f of files.sort()) {
  const nick = f.replace(/\.txt$/i, '');
  const parsed = parseList(readFileSync(join(DIR, f), 'utf8'));
  const mainN = zoneCount(parsed.main), sideN = zoneCount(parsed.side);
  if (mainN === 0 && sideN === 0) { console.error(`  ${f}: vacia, descartada`); continue; }
  const jMain = asMap(parsed.main), jSide = asMap(parsed.side);

  // Diferencias vs la referencia (por zona)
  const diff = (jMap, rMap) => {
    const soloEl = [], soloRef = [], distintos = [];
    let comun = 0; // copias compartidas = suma de min(suyo, ref) sobre la union
    const keys = new Set([...jMap.keys(), ...rMap.keys()]);
    for (const k of keys) {
      const a = jMap.get(k), b = rMap.get(k);
      const qa = a ? a.q : 0, qb = b ? b.q : 0;
      comun += Math.min(qa, qb);
      if (qa && !qb) soloEl.push({ n: a.n, q: qa });
      else if (qb && !qa) soloRef.push({ n: b.n, q: qb });
      else if (qa !== qb) distintos.push({ n: (b || a).n, suyo: qa, ref: qb });
    }
    const byN = (x, y) => y.q - x.q || x.n.localeCompare(y.n);
    return { soloEl: soloEl.sort(byN), soloRef: soloRef.sort(byN), distintos: distintos.sort((x, y) => x.n.localeCompare(y.n)), comun };
  };
  const dM = diff(jMain, refMainMap), dS = diff(jSide, refSideMap);
  const refTotal = zoneCount(ref.main) + zoneCount(ref.side);
  const pctSim = refTotal ? Math.round(((dM.comun + dS.comun) / refTotal) * 100) : 0;
  const esRef = norm(nick) === norm('feralo77');

  jugadores.push({
    nick, titulo: parsed.titulo || nick, esRef,
    mainN, sideN, overlapMain: dM.comun, overlapSide: dS.comun, pctSim,
    soloEl: { main: dM.soloEl, side: dS.soloEl },
    soloRef: { main: dM.soloRef, side: dS.soloRef },
    distintos: { main: dM.distintos, side: dS.distintos },
    _main: jMain, _side: jSide,
  });
}

// --- Matriz carta x jugador (union de listas de los jugadores + referencia) --
function matriz(getJMap, refMap, metaM) {
  const names = new Map(); // norm -> nombre para mostrar (prioriza referencia)
  for (const [k, v] of refMap) names.set(k, v.n);
  for (const j of jugadores) for (const [k, v] of getJMap(j)) if (!names.has(k)) names.set(k, v.n);
  const rows = [...names.entries()].map(([k, n]) => {
    const j = {}; for (const jug of jugadores) { const e = getJMap(jug).get(k); j[jug.nick] = e ? e.q : 0; }
    const rq = refMap.get(k), mq = metaM.get(k);
    return { n, ref: rq ? rq.q : 0, meta: mq ? mq.q : null, metaPct: mq ? mq.pct : null, j };
  });
  const total = (r) => Object.values(r.j).reduce((a, b) => a + b, 0);
  rows.sort((a, b) => b.ref - a.ref || total(b) - total(a) || a.n.localeCompare(b.n));
  return rows;
}
const matrizMain = matriz((j) => j._main, refMainMap, metaMainMap);
const matrizSide = matriz((j) => j._side, refSideMap, metaSideMap);

// --- Quien falta por entregar su lista --------------------------------------
const roster = readJSON(ROSTER);
const tienen = new Set(jugadores.map((j) => norm(j.nick)));
const esperando = (roster && roster.players ? roster.players : []).filter((p) => !tienen.has(norm(p)));

// --- Notas por reglas (nucleo comun, mayor divergencia) ---------------------
const notas = [];
if (jugadores.length >= 2) {
  // Nucleo comun del main: cartas que TODOS llevan (al menos 1 copia)
  const comun = matrizMain.filter((r) => jugadores.every((j) => r.j[j.nick] > 0));
  const comunCopias = comun.reduce((s, r) => s + Math.min(...jugadores.map((j) => r.j[j.nick])), 0);
  notas.push(`Núcleo común a las ${jugadores.length} listas: ${comun.length} cartas distintas (${comunCopias} copias) que todas llevan en el mazo principal.`);
  // Cartas que solo una lista lleva (exclusivas)
  const exclusivas = matrizMain.filter((r) => jugadores.filter((j) => r.j[j.nick] > 0).length === 1);
  if (exclusivas.length) notas.push(`Cartas de main que solo lleva una lista: ${exclusivas.map((r) => r.n).slice(0, 12).join(', ')}${exclusivas.length > 12 ? '…' : ''}.`);
} else {
  notas.push('Solo hay una lista cargada: el comparador se llena en cuanto haya más .txt en la carpeta listas/.');
}

// --- Escribir ---------------------------------------------------------------
const strip = (j) => { const { _main, _side, ...rest } = j; return rest; };
const out = {
  generado: stamp || null,
  referencia: ref.nombre,
  jugadores: jugadores.map(strip),
  esperando,
  matrizMain,
  matrizSide,
  notas,
};
writeFileSync(join(DIR, 'comparativa.json'), JSON.stringify(out, null, 2));
console.error(`OK -> ${DIR}/comparativa.json  (${jugadores.length} lista(s) · ${matrizMain.length} cartas main · esperando ${esperando.length})`);
