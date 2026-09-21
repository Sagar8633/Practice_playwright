#!/usr/bin/env node
// Checks every `.field` / `.method()` access against the types actually declared
// in 01_types.pine and the methods declared anywhere in the file.
//
// This is the error class the per-chunk reviewers structurally cannot catch:
// nine agents wrote against a TYPE CONTRACT they each read separately, so a
// field renamed in one author's head (z.bottom vs z.bot, s.plan vs s.riskPlan)
// compiles fine in isolation and dies on assembly. TradingView reports one error
// per compile, so finding these in bulk here is worth a lot of round trips.
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const PARTS = process.argv[2] || 'D:/Practice_Playwright/xau_iceberg/parts'
const ORDER = [
  '00_globals', '01_types', '02_helpers', '02b_state', '03_structure', '04_liquidity',
  '05_sweep', '06_absorption', '07_reject', '08_displacement', '09_bos', '10_retest',
  '11_risk', '12_score', '13_filters', '14_machine', '15_failure', '16_visuals',
  '17_alerts', '18_exec', '19_presets',
]

const lines = []
for (const p of ORDER) {
  const f = join(PARTS, p + '.pine')
  if (!existsSync(f)) continue
  readFileSync(f, 'utf8').split(/\r?\n/).forEach((text, i) => lines.push({ text, part: p, srcLine: i + 1 }))
}
const strip = (t) => t.replace(/"(\\.|[^"\\])*"/g, '""').replace(/\/\/.*$/, '')

// ---- 1. collect declared types, their fields, and their enum members -------
const fields = new Set()      // every legal field name across all UDTs
const enumMembers = new Set() // every legal enum member name
const typeNames = new Set()
const enumNames = new Set()
{
  let mode = null
  for (const ln of lines) {
    const raw = ln.text
    if (!raw.trim() || raw.trim().startsWith('//')) continue
    const t = strip(raw)
    const mt = t.match(/^(?:export\s+)?type\s+([A-Za-z_]\w*)/)
    const me = t.match(/^(?:export\s+)?enum\s+([A-Za-z_]\w*)/)
    if (mt) { mode = 'type'; typeNames.add(mt[1]); continue }
    if (me) { mode = 'enum'; enumNames.add(me[1]); continue }
    if (!/^\s/.test(raw)) { mode = null; continue }        // dedent ends the block
    if (mode === 'type') {
      // "    float  price  = na"  ->  price
      const m = t.match(/^\s+(?:array<[^>]+>|matrix<[^>]+>|map<[^>]+>|[A-Za-z_]\w*)\s+([A-Za-z_]\w*)/)
      if (m) fields.add(m[1])
    } else if (mode === 'enum') {
      const m = t.match(/^\s+([A-Za-z_]\w*)/)
      if (m) enumMembers.add(m[1])
    }
  }
}

// ---- 2. collect method names ----------------------------------------------
const methods = new Set()
for (const ln of lines) {
  const m = strip(ln.text).match(/^(?:export\s+)?method\s+([A-Za-z_]\w*)\s*\(/)
  if (m) methods.add(m[1])
}

// ---- 3. Pine built-in namespaces: anything after these is the language's ---
const NS = new Set(['math', 'ta', 'str', 'array', 'matrix', 'map', 'color', 'line', 'label', 'box',
  'table', 'input', 'request', 'timeframe', 'syminfo', 'barstate', 'strategy', 'session', 'alert',
  'format', 'size', 'location', 'shape', 'position', 'xloc', 'yloc', 'extend', 'barmerge', 'display',
  'scale', 'plot', 'hline', 'currency', 'dayofweek', 'order', 'text', 'font', 'chart', 'linefill',
  'polyline', 'runtime', 'ticker', 'earnings', 'dividends', 'splits', 'adjustment', 'backadjustment',
  'settlement', 'seriestype', 'volume', 'time'])

// Pine v6 allows method-call syntax on built-in collections and drawing objects
// (arr.size(), lbl.set_text(...)), so those member names are legal on any object.
const BUILTIN_METHODS = new Set([
  // array / matrix / map
  'size', 'get', 'set', 'push', 'pop', 'shift', 'unshift', 'insert', 'remove', 'clear',
  'slice', 'concat', 'copy', 'sort', 'sort_indices', 'reverse', 'includes', 'indexof',
  'lastindexof', 'first', 'last', 'sum', 'avg', 'min', 'max', 'median', 'mode', 'stdev',
  'variance', 'range', 'covariance', 'percentrank', 'fill', 'join', 'binary_search',
  'new', 'keys', 'values', 'contains', 'put', 'row', 'col', 'rows', 'columns', 'abs',
  // drawing objects
  'delete', 'set_xy1', 'set_xy2', 'set_x1', 'set_y1', 'set_x2', 'set_y2', 'set_text',
  'set_color', 'set_textcolor', 'set_bgcolor', 'set_style', 'set_width', 'set_extend',
  'set_size', 'set_align', 'set_tooltip', 'set_point', 'set_top', 'set_bottom',
  'set_left', 'set_right', 'set_border_color', 'set_border_width', 'set_text_color',
  'set_text_size', 'set_text_halign', 'set_text_valign', 'set_text_font_family',
  'get_price', 'get_x1', 'get_y1', 'get_x2', 'get_y2', 'get_text', 'set_yloc',
  'cell', 'cell_set_text', 'cell_set_bgcolor', 'cell_set_text_color', 'set_position',
  'merge_cells', 'set_frame_color', 'set_frame_width', 'set_border_style',
])

const bad = []
for (const ln of lines) {
  if (!ln.text.trim() || ln.text.trim().startsWith('//')) continue
  const t = strip(ln.text)
  for (const m of t.matchAll(/(?:^|[^\w.])([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)/g)) {
    const obj = m[1], mem = m[2]
    if (NS.has(obj)) continue                       // builtin namespace
    if (enumNames.has(obj)) {                       // EnumName.member
      if (!enumMembers.has(mem)) bad.push({ ln, msg: `enum ${obj} has no member "${mem}"` })
      continue
    }
    if (typeNames.has(obj)) continue                // TypeName.new(...)
    if (fields.has(mem) || methods.has(mem) || BUILTIN_METHODS.has(mem)) continue
    bad.push({ ln, msg: `"${obj}.${mem}" - "${mem}" is not a declared UDT field, a method, or a builtin namespace member` })
  }
}

console.log(`types: ${typeNames.size}  fields: ${fields.size}  enums: ${enumNames.size}  enum members: ${enumMembers.size}  methods: ${methods.size}`)
console.log(`${bad.length} suspicious member access(es)\n`)
const seen = new Set()
for (const b of bad) {
  const key = b.msg
  if (seen.has(key)) continue
  seen.add(key)
  console.log(`${(b.ln.part + ':' + b.ln.srcLine).padEnd(24)} ${b.msg}`)
  console.log(`  | ${b.ln.text.trim().slice(0, 110)}`)
}
