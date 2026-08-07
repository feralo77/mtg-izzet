#!/usr/bin/env node
// ============================================================================
// RADAR DE METAJUEGO — "¿ha cambiado algo que me obligue a adaptarme?"
//
// Lo que hace: cada corrida cruza TRES cosas y saca alarmas.
//   1. El campo global de Modern (mtgtop8, página de metajuego): qué arquetipos
//      hay y con qué peso, y cuánto han subido o bajado desde la corrida anterior.
//   2. La liga de Fer (registro.csv, todos los jugadores): con qué se cruza de
//      verdad, en la ventana reciente frente a la anterior.
//   3. Su récord real contra cada uno (registro.csv filtrado por él).
//
// La regla que pidió Fer: si un mazo SUBE y nuestro winrate contra él es BAJO,
// hay que adaptarse. Eso es lo que produce este script.
//
// Lo que NO hace, a propósito: decidir qué carta responde a qué mazo. Eso es
// criterio de Magic y sale del brainstorm con /mtg-expert. El radar dice CUÁNDO
// hace falta un brainstorm y POR QUÉ, con los datos ya preparados.
//
// Salida: meta/radar.json (lo pinta la pestaña "Brainstorm" del dashboard).
// No necesita nada instalado (Node 18+).
//
// Uso:  node scripts/radar_meta.mjs [--out meta] [--dias 30] [--cadencia 4]
// ============================================================================
import { writeFileSync, readFileSync, existsSync, readdirSync, mkdirSync } from 'node:fs';

const META_URL = 'https://mtgtop8.com/format?f=MO&meta=54';
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';

const arg = (f, d) => { const i = process.argv.indexOf(f); return i > -1 ? process.argv[i + 1] : d; };
const outDir = arg('--out', 'meta');
const VENTANA = Number(arg('--dias', 30));      // ventana reciente de la liga, en días
const CADENCIA = Number(arg('--cadencia', 4));  // cada cuántos días toca brainstorm
const hoyISO = arg('--hoy', new Date().toISOString().slice(0, 10));

// --- Umbrales. Todos explícitos aquí para que se puedan discutir. ------------
const WR_MALO = 45;        // por debajo de esto, el matchup es un problema
const N_MINIMO = 3;        // menos de 3 partidas no sostienen una conclusión
const FREC_ALTA = 5;       // % de la liga a partir del cual un mazo "es frecuente"
const SUBE_LIGA = 3;       // puntos de subida en la liga para considerarlo tendencia
const SUBE_CAMPO = 2;      // puntos de subida en el campo global
const CAMPO_RELEVANTE = 3; // % del campo global para avisar de un mazo que nunca has visto
const MIN_BASE = 30;       // partidas mínimas en CADA mitad para afirmar una tendencia

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------
const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
const pct1 = (a, b) => (b ? Math.round((1000 * a) / b) / 10 : 0);

// registro.csv: fechas en DD/MM/YYYY
function fechaISO(s) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec((s || '').trim());
  return m ? `${m[3]}-${m[2]}-${m[1]}` : null;
}
const diasEntre = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 86400000);
const menos = (iso, d) => new Date(Date.parse(iso) - d * 86400000).toISOString().slice(0, 10);

// Parser de CSV con comillas (los apuntes traen comas dentro de las notas).
function leerCSV(ruta) {
  const txt = readFileSync(ruta, 'utf8');
  const filas = []; let campo = '', fila = [], enComillas = false;
  for (let i = 0; i < txt.length; i++) {
    const c = txt[i];
    if (enComillas) {
      if (c === '"') { if (txt[i + 1] === '"') { campo += '"'; i++; } else enComillas = false; }
      else campo += c;
    } else if (c === '"') enComillas = true;
    else if (c === ',') { fila.push(campo); campo = ''; }
    else if (c === '\n') { fila.push(campo); filas.push(fila); fila = []; campo = ''; }
    else if (c !== '\r') campo += c;
  }
  if (campo || fila.length) { fila.push(campo); filas.push(fila); }
  const cab = filas.shift();
  return filas.filter(f => f.length === cab.length).map(f => Object.fromEntries(cab.map((h, i) => [h, f[i]])));
}

// ---------------------------------------------------------------------------
// 1. El campo global (mtgtop8)
// ---------------------------------------------------------------------------
async function campoGlobal() {
  const r = await fetch(META_URL, { headers: { 'User-Agent': UA } });
  if (!r.ok) throw new Error(`mtgtop8 respondió ${r.status}`);
  const h = await r.text();
  const totalM = /<div class=S14 align=center>\s*(\d+)\s+decks/.exec(h);
  const total = totalM ? Number(totalM[1]) : null;
  const re = /archetype\?a=(\d+)&meta=54&f=MO>(.*?)<\/a>[\s\S]{0,400}?class=S14>\s*([\d.]+)\s*%/g;
  const vistos = new Map();
  let m;
  while ((m = re.exec(h))) {
    const nombre = m[2].replace(/&#0?39;/g, "'").replace(/&amp;/g, '&').trim();
    const p = Number(m[3]);
    if (!vistos.has(nombre)) vistos.set(nombre, p); // la primera aparición es la buena
  }
  return { mazos: total, fuente: META_URL, arquetipos: [...vistos].map(([n, pct]) => ({ n, pct })) };
}

// ---------------------------------------------------------------------------
// 2 y 3. La liga y tus números
// ---------------------------------------------------------------------------
// Cómo se mide "sube" en la liga. La tentación es comparar los últimos 30 días
// contra los 30 anteriores, pero con el histórico corto que hay eso da basura:
// la ventana anterior se queda con las partidas de un par de días sueltos y
// cualquier mazo que ese día no saliera aparece como "+6 puntos". Así que se
// parte el histórico en DOS MITADES POR NÚMERO DE PARTIDAS y se compara antes
// contra ahora, diciendo siempre qué fechas cubre cada mitad. Es una comparación
// real desde el primer día, y se vuelve más fina según se acumulan partidas.
function liga(registro, jugador, mapa) {
  const con = registro.map(r => ({ ...r, iso: fechaISO(r.Fecha) })).filter(r => r.iso && r.Arquetipo)
    .sort((a, b) => (a.iso < b.iso ? -1 : a.iso > b.iso ? 1 : 0));
  const limpio = a => a && !a.startsWith('¿?');
  let util = con.filter(r => limpio(r.Arquetipo));

  // AGRUPAR VARIANTES DEL MISMO MAZO. El registro trae "Eldrazi", "Eldrazi Ramp",
  // "Eldrazi PT" y "Mono-Green Eldrazi" como etiquetas distintas, y sin agrupar cada
  // una sale con 0-1 partidas: el winrate queda diluido justo donde importa. El mapa
  // de meta/arquetipos.json ya dice cuales son el mismo mazo, asi que se usa tambien
  // aqui. La etiqueta que se muestra es la variante MAS jugada, no la de mtgtop8,
  // porque es la que Fer reconoce.
  const grupoDe = new Map();          // etiqueta del registro -> id de grupo
  for (const [g, variantes] of Object.entries(mapa)) for (const v of variantes) grupoDe.set(v, g);
  const cuentaVar = {};
  util.forEach(r => { cuentaVar[r.Arquetipo] = (cuentaVar[r.Arquetipo] || 0) + 1; });
  const etiqueta = new Map();         // id de grupo -> etiqueta a mostrar
  const variantesDe = new Map();      // id de grupo -> variantes realmente vistas
  for (const [v, g] of grupoDe) {
    if (!cuentaVar[v]) continue;
    variantesDe.set(g, [...(variantesDe.get(g) || []), v]);
    const actual = etiqueta.get(g);
    if (!actual || cuentaVar[v] > cuentaVar[actual]) etiqueta.set(g, v);
  }
  const canon = (a) => { const g = grupoDe.get(a); return g && etiqueta.has(g) ? etiqueta.get(g) : a; };
  const variantesDeEtiqueta = new Map();
  for (const [g, vs] of variantesDe) if (vs.length > 1) variantesDeEtiqueta.set(etiqueta.get(g), vs);
  util = util.map(r => ({ ...r, Arquetipo: canon(r.Arquetipo) }));

  const cuenta = (filas) => {
    const c = {}; filas.forEach(r => { c[r.Arquetipo] = (c[r.Arquetipo] || 0) + 1; });
    return { c, total: filas.length, desde: filas.length ? filas[0].iso : null, hasta: filas.length ? filas[filas.length - 1].iso : null };
  };
  const corteIdx = Math.floor(util.length / 2);
  const previo = cuenta(util.slice(0, corteIdx));
  const reciente = cuenta(util.slice(corteIdx));
  // Sin mitades suficientemente gordas, no se afirma ninguna tendencia.
  const hayBase = previo.total >= MIN_BASE && reciente.total >= MIN_BASE;

  // Tu récord por arquetipo (todas tus partidas, no solo la ventana: n ya es escaso)
  const mio = {};
  util.filter(r => r['Reportado por'] === jugador).forEach(r => {
    const k = r.Arquetipo; mio[k] = mio[k] || { w: 0, l: 0 };
    if (r['Resultado (W/L)'] === 'W') mio[k].w++; else if (r['Resultado (W/L)'] === 'L') mio[k].l++;
  });

  const nombres = new Set([...Object.keys(reciente.c), ...Object.keys(previo.c), ...Object.keys(mio)]);
  const arquetipos = [...nombres].map(n => {
    const fr = pct1(reciente.c[n] || 0, reciente.total);
    const fp = hayBase ? pct1(previo.c[n] || 0, previo.total) : null;
    const r = mio[n] || { w: 0, l: 0 }; const nn = r.w + r.l;
    return {
      n, variantes: variantesDeEtiqueta.get(n) || null, partidas: reciente.c[n] || 0, frec: fr, frecPrev: fp,
      delta: fp === null ? null : Math.round((fr - fp) * 10) / 10,
      w: r.w, l: r.l, n_: nn, wr: nn ? pct(r.w, nn) : null,
    };
  }).sort((a, b) => b.frec - a.frec || b.n_ - a.n_);

  return {
    modo: 'dos mitades del histórico, por número de partidas',
    ahora: { partidas: reciente.total, desde: reciente.desde, hasta: reciente.hasta },
    antes: { partidas: previo.total, desde: previo.desde, hasta: previo.hasta },
    hayBase,
    avisoBase: hayBase ? null : `Aún no se puede hablar de tendencias en tu liga: hacen falta ${MIN_BASE} partidas en cada mitad y ahora hay ${previo.total} y ${reciente.total}. Mientras tanto las alarmas se basan en la frecuencia absoluta y en tu récord, que sí son fiables.`,
    arquetipos,
  };
}

// ---------------------------------------------------------------------------
// Las alarmas: donde se cruza todo
// ---------------------------------------------------------------------------
function alarmas(lg, campo, mapa, previoCampo) {
  // De nombre de mtgtop8 -> nombres del registro, y al revés
  const aMios = new Map(Object.entries(mapa));
  const deMio = new Map();
  for (const [g, mios] of aMios) for (const m of mios) deMio.set(m, g);

  const campoPorNombre = new Map(campo.arquetipos.map(a => [a.n, a.pct]));
  const prevPorNombre = new Map((previoCampo || []).map(a => [a.n, a.pct]));
  const campoDe = (mio) => {
    const g = deMio.get(mio); if (!g) return null;
    const p = campoPorNombre.get(g); if (p === undefined) return null;
    const pp = prevPorNombre.get(g);
    return { global: g, pct: p, pctPrev: pp ?? null, delta: pp === undefined ? null : Math.round((p - pp) * 10) / 10 };
  };

  const out = [];

  // (a) ADAPTARSE: es frecuente o sube, y pierdes contra él con muestra suficiente
  for (const a of lg.arquetipos) {
    const c = campoDe(a.n);
    const sube = (a.delta !== null && a.delta >= SUBE_LIGA) || (c && c.delta !== null && c.delta >= SUBE_CAMPO);
    const frecuente = a.frec >= FREC_ALTA;
    if (a.n_ >= N_MINIMO && a.wr !== null && a.wr < WR_MALO && (sube || frecuente)) {
      const motivo = sube
        ? `está subiendo (${a.delta !== null && a.delta >= SUBE_LIGA ? `+${a.delta} pts en tu liga` : `+${c.delta} pts en el campo global`})`
        : `es el ${a.frec}% de tu liga`;
      out.push({
        nivel: 'adaptarse', mazo: a.n,
        titular: `${a.n}: ${motivo} y vas ${a.w}-${a.l} (${a.wr}%)`,
        porQue: sube ? `Sube y lo pierdes: las dos condiciones a la vez. Es donde un cambio de banquillo se paga solo.` : `No es que esté subiendo — es que ya pesa en tu liga y lo pierdes. Merece un plan aunque el metajuego no se mueva.`,
        datos: { frecLiga: a.frec, deltaLiga: a.delta, campo: c, w: a.w, l: a.l, wr: a.wr, n: a.n_ },
      });
    }
  }

  // (b) PINTA MAL: poca muestra, pero todo lo que sabes es malo, y encima pesa o sube.
  //     Es el caso mas frecuente en una liga local: nunca vas a tener n=10 por matchup.
  //     Se separa de "adaptarse" para no vender como conclusion lo que son 2 partidas.
  for (const a of lg.arquetipos) {
    const c = campoDe(a.n);
    const sube = (a.delta !== null && a.delta >= SUBE_LIGA) || (c && c.delta !== null && c.delta >= SUBE_CAMPO);
    const relevante = a.frec >= FREC_ALTA || sube;
    if (relevante && a.n_ > 0 && a.n_ < N_MINIMO && a.wr !== null && a.wr < WR_MALO) {
      out.push({
        nivel: 'pinta-mal', mazo: a.n,
        titular: `${a.n}: ${sube && a.delta !== null && a.delta >= SUBE_LIGA ? `sube +${a.delta} pts` : `${a.frec}% de tu liga`} y de ${a.n_} partida${a.n_ === 1 ? '' : 's'} has ganado ${a.w}`,
        porQue: `Son ${a.n_} partidas, asi que no es una conclusion: es un aviso. Pero pesa en tu liga y todo lo que sabes de el es malo.`,
        datos: { frecLiga: a.frec, deltaLiga: a.delta, campo: c, w: a.w, l: a.l, wr: a.wr, n: a.n_ },
      });
    }
  }

  // (c) VIGILAR: te lo vas a cruzar y no tienes datos para saber como va.
  //     Si vas ganando comodo (>=60%) no es una preocupacion, no se lista.
  for (const a of lg.arquetipos) {
    const c = campoDe(a.n);
    const sube = (a.delta !== null && a.delta >= SUBE_LIGA) || (c && c.delta !== null && c.delta >= SUBE_CAMPO);
    const relevante = a.frec >= FREC_ALTA || sube;
    const yaAvisado = a.n_ > 0 && a.wr !== null && a.wr < WR_MALO;
    if (relevante && a.n_ < N_MINIMO && !yaAvisado && (a.wr === null || a.wr < 60)) {
      out.push({
        nivel: 'vigilar', mazo: a.n,
        titular: `${a.n}: ${a.frec}% de tu liga y ${a.n_ === 0 ? 'ni una partida tuya' : `solo ${a.n_} partida${a.n_ === 1 ? '' : 's'} tuya${a.n_ === 1 ? '' : 's'}`}`,
        porQue: `No es que vayas mal: es que no hay datos. Te lo vas a cruzar y no sabes como va el matchup.`,
        datos: { frecLiga: a.frec, deltaLiga: a.delta, campo: c, w: a.w, l: a.l, wr: a.wr, n: a.n_ },
      });
    }
  }

  // (d) NUEVO EN EL CAMPO: pesa fuera y nunca lo has visto
  const conocidos = new Set(lg.arquetipos.map(a => a.n));
  for (const g of campo.arquetipos) {
    if (g.pct < CAMPO_RELEVANTE) continue;
    const mios = aMios.get(g.n) || [];
    if (mios.some(m => conocidos.has(m))) continue;
    const pp = prevPorNombre.get(g.n);
    out.push({
      nivel: 'nuevo', mazo: g.n,
      titular: `${g.n}: ${g.pct}% del campo global y nunca te lo has cruzado`,
      porQue: `Existe fuera con peso real. Si aparece en la liga, hoy irías a ciegas.`,
      datos: { frecLiga: 0, deltaLiga: null, campo: { global: g.n, pct: g.pct, pctPrev: pp ?? null, delta: pp === undefined ? null : Math.round((g.pct - pp) * 10) / 10 }, w: 0, l: 0, wr: null, n: 0 },
    });
  }

  const orden = { adaptarse: 0, 'pinta-mal': 1, vigilar: 2, nuevo: 3 };
  return out.sort((a, b) => orden[a.nivel] - orden[b.nivel] || (b.datos.frecLiga || 0) - (a.datos.frecLiga || 0) || (b.datos.campo?.pct || 0) - (a.datos.campo?.pct || 0));
}

// ---------------------------------------------------------------------------
// Cadencia del brainstorm
// ---------------------------------------------------------------------------
function cadencia(dir) {
  // También publica la LISTA de brainstorms: el dashboard no puede listar una carpeta
  // por HTTP, así que necesita este índice para poder pintar el más reciente.
  let ficheros = [];
  try {
    ficheros = readdirSync(dir).filter(x => /^\d{4}-\d{2}-\d{2}\.md$/.test(x)).sort().reverse();
  } catch { /* sin carpeta todavía */ }
  const ultimo = ficheros.length ? ficheros[0].replace('.md', '') : null;
  const base = { ficheros: ficheros.map(f => `${dir}/${f}`), cadenciaDias: CADENCIA };
  if (!ultimo) return { ...base, ultimo: null, proximo: hoyISO, diasDesde: null, toca: true };
  const d = diasEntre(ultimo, hoyISO);
  return {
    ...base, ultimo,
    proximo: new Date(Date.parse(ultimo) + CADENCIA * 86400000).toISOString().slice(0, 10),
    diasDesde: d, toca: d >= CADENCIA,
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
const registro = leerCSV('registro.csv');
const mapa = JSON.parse(readFileSync(`${outDir}/arquetipos.json`, 'utf8')).mapa;
const rutaSalida = `${outDir}/radar.json`;
const previo = existsSync(rutaSalida) ? JSON.parse(readFileSync(rutaSalida, 'utf8')) : null;

// Si mtgtop8 no responde, NO se tira la corrida entera: se reutiliza el campo de la
// vez anterior y se marca como no fresco. La parte de la liga y las alarmas de récord
// siguen sirviendo, que es lo que Fer mira cada dia.
let campo, campoFresco = true, campoError = null;
try {
  campo = await campoGlobal();
} catch (e) {
  if (!previo?.campo) throw e;          // primera corrida y sin red: no hay nada que salvar
  campo = previo.campo; campoFresco = false; campoError = String(e.message || e);
  console.error(`aviso: mtgtop8 no respondio (${campoError}). Se reutiliza el campo del ${previo.generado}.`);
}
const lg = liga(registro, 'feralo77', mapa);
const al = alarmas(lg, campo, mapa, previo?.campo?.arquetipos);
const cad = cadencia('docs/brainstorm');

// El campo se compara con la corrida anterior; si es la primera, no hay deltas y se dice.
const salida = {
  generado: hoyISO,
  comoFunciona: 'Cruza el campo global de Modern (mtgtop8), la frecuencia real en la liga de Fer (registro.csv) y su récord contra cada mazo. Si algo sube y el récord es malo, salta la alarma. Lo que NO hace: decidir qué carta responde a qué mazo — eso sale del brainstorm con /mtg-expert. El radar dice cuándo hace falta uno y por qué.',
  umbrales: { winrateMalo: WR_MALO, partidasMinimas: N_MINIMO, frecuenciaAlta: FREC_ALTA, subeLiga: SUBE_LIGA, subeCampo: SUBE_CAMPO, campoRelevante: CAMPO_RELEVANTE },
  brainstorm: cad,
  hayComparacionCampo: campoFresco && !!previo?.campo?.arquetipos,
  campoFresco,
  campoDesde: campoFresco ? hoyISO : (previo?.generado || null),
  campoError,
  campo,
  liga: lg,
  alarmas: al,
};

mkdirSync(outDir, { recursive: true });
writeFileSync(rutaSalida, JSON.stringify(salida, null, 1));

const cuenta = n => al.filter(a => a.nivel === n).length;
console.log(`radar.json escrito · campo: ${campo.mazos} mazos, ${campo.arquetipos.length} arquetipos · liga: ${lg.antes.partidas} partidas antes (${lg.antes.desde}→${lg.antes.hasta}) vs ${lg.ahora.partidas} ahora (${lg.ahora.desde}→${lg.ahora.hasta})`);
if (!lg.hayBase) console.log(`  aviso: ${lg.avisoBase}`);
console.log(`alarmas: ${cuenta('adaptarse')} adaptarse · ${cuenta('pinta-mal')} pinta mal · ${cuenta('vigilar')} vigilar · ${cuenta('nuevo')} nuevo en el campo`);
console.log(`brainstorm: último ${cad.ultimo || '(ninguno)'} · ${cad.toca ? 'TOCA YA' : `siguiente ${cad.proximo}`}`);
al.filter(a => a.nivel === 'adaptarse' || a.nivel === 'pinta-mal').forEach(a => console.log(`  [${a.nivel.toUpperCase()}] ${a.titular}`));
