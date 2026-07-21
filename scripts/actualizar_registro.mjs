#!/usr/bin/env node
// Carga diaria: baja el CSV de la hoja del Drive (publicada), le añade la columna
// "Arquetipo" (mapeando el mazo del oponente a un arquetipo limpio) y "Reportado por",
// y escribe registro.csv en la raíz del repo. El dashboard lo lee sin CORS.
//
// Uso:  SHEET_CSV_URL="<url csv publicada>" node scripts/actualizar_registro.mjs
// Si SHEET_CSV_URL no está definida o la descarga falla (p. ej. la hoja aún no es
// pública), NO escribe nada y sale con código 0 (para no romper el workflow).

import { writeFileSync, readFileSync, existsSync } from 'node:fs';

const URL_DEFECTO = 'https://docs.google.com/spreadsheets/d/1Ha71dPwJkPevqCK_ulfJwgMn8Khm3cjHxx4EbN36uBs/gviz/tq?tqx=out:csv&gid=1091441461';
const SHEET_CSV_URL = (process.env.SHEET_CSV_URL || URL_DEFECTO).trim();
const SALIDA = 'registro.csv';
const REPORTADO_POR_DEFECTO = 'feralo77';

// Mapa: "Mazo del Oponente" (como lo apunta Fer) -> Arquetipo limpio.
// Si un oponente no está aquí, se conserva su texto original (no se pierde nada);
// añade nuevas entradas cuando aparezcan mazos nuevos.
const ARQUETIPOS = {
  'loki': 'Azorius Loki',
  'devoted': 'Devoted Combo',
  'affinity': 'Izzet Affinity',
  'broodscale': 'Broodscale',
  'dimir': 'Dimir Frog',
  'na': 'N/A (bye/concede)',
  'boros': 'Boros Energy',
  'vivoras': 'Sultai Midrange',
  'izzet': 'Izzet Prowess',
  'monob reanimator': 'Reanimator (MonoB)',
  'neoform': 'Neoform',
  'ponza': 'Boros Ponza',
  'gorys': "Esper Goryo's",
  'sam': 'Sam Combo',
  'grixis reanimator': 'Grixis Reanimator',
  'uw': 'Azorius Control',
  'through the breach': 'Through the Breach',
};

function splitCSVLine(l) {
  const out = []; let cur = '', q = false;
  for (let i = 0; i < l.length; i++) {
    const c = l[i];
    if (c === '"') { if (q && l[i + 1] === '"') { cur += '"'; i++; } else q = !q; }
    else if (c === ',' && !q) { out.push(cur); cur = ''; }
    else cur += c;
  }
  out.push(cur); return out;
}
const csvField = s => /[",\n]/.test(s) ? `"${String(s).replace(/"/g, '""')}"` : String(s);
const norm = s => (s || '').trim();
const key = s => norm(s).toLowerCase().replace(/\s+/g, ' ');

async function main() {
  if (!SHEET_CSV_URL) { console.log('SHEET_CSV_URL no configurada; nada que hacer.'); return; }
  let txt;
  try {
    const res = await fetch(SHEET_CSV_URL, { redirect: 'follow' });
    if (!res.ok) { console.log(`La hoja respondió HTTP ${res.status} (¿aún no es pública?). Se deja registro.csv como está.`); return; }
    txt = await res.text();
  } catch (e) { console.log('No se pudo descargar la hoja:', e.message, '- se deja registro.csv como está.'); return; }

  const lines = txt.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) { console.log('La hoja vino vacía; no se toca registro.csv.'); return; }

  const header = splitCSVLine(lines[0]).map(norm);
  const hkey = header.map(key);
  const idxOp = hkey.findIndex(h => ['mazo del oponente', 'rival', 'oponente'].includes(h));
  const hasArq = hkey.includes('arquetipo');
  const hasBy = hkey.includes('reportado por');

  const outHeader = header.slice();
  if (!hasArq) outHeader.splice(idxOp >= 0 ? idxOp + 1 : outHeader.length, 0, 'Arquetipo');
  if (!hasBy) outHeader.push('Reportado por');

  const rows = lines.slice(1).map(splitCSVLine).map(cells => {
    const row = cells.slice();
    if (!hasArq) {
      const op = idxOp >= 0 ? norm(cells[idxOp]) : '';
      const arq = ARQUETIPOS[key(op)] || op || 'Otros (¿?)';
      row.splice(idxOp >= 0 ? idxOp + 1 : row.length, 0, arq);
    }
    if (!hasBy) row.push(REPORTADO_POR_DEFECTO);
    return row;
  });

  const csv = [outHeader, ...rows].map(r => r.map(csvField).join(',')).join('\n') + '\n';
  const anterior = existsSync(SALIDA) ? readFileSync(SALIDA, 'utf8') : '';
  if (csv === anterior) { console.log('Sin cambios respecto al registro.csv actual.'); return; }
  writeFileSync(SALIDA, csv, 'utf8');
  console.log(`registro.csv actualizado: ${rows.length} partidas.`);
}

main();
