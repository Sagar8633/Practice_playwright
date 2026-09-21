#!/usr/bin/env node
// ---------------------------------------------------------------------------
// Static checker for the assembled XAU Iceberg Pine v6 file.
//
// Every rule here exists because it is a WHOLE-FILE property. A reviewer
// reading one part file cannot see a duplicate declaration in another, and
// TradingView only reports the first compile error, so a file with 20 of them
// takes 20 paste-and-wait round trips to clean. This finds them in one pass.
//
// Rules are heuristic and deliberately noisy on the side of reporting. Every
// finding carries the line so it can be judged, not trusted blindly.
// ---------------------------------------------------------------------------
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const PARTS_DIR = process.argv[2] || 'D:/Practice_Playwright/xau_iceberg/parts'
const ORDER = [
  '00_globals', '01_types', '02_helpers', '02b_state', '03_structure', '04_liquidity',
  '05_sweep', '06_absorption', '07_reject', '08_displacement', '09_bos', '10_retest',
  '11_risk', '12_score', '13_filters', '14_machine', '15_failure', '16_visuals',
  '17_alerts', '18_exec', '19_presets',
]

// ---- assemble, remembering which part each line came from ------------------
const lines = []
const missing = []
for (const p of ORDER) {
  const f = join(PARTS_DIR, p + '.pine')
  if (!existsSync(f)) { missing.push(p); continue }
  const src = readFileSync(f, 'utf8').split(/\r?\n/)
  src.forEach((text, i) => lines.push({ text, part: p, srcLine: i + 1 }))
}

const findings = []
const add = (sev, rule, ln, msg) =>
  findings.push({ sev, rule, where: ln ? `${ln.part}:${ln.srcLine}` : '-', msg, text: ln ? ln.text.trim().slice(0, 110) : '' })

// A line is "code" if it is not blank and not a pure comment.
const isCode = (t) => t.trim().length > 0 && !t.trim().startsWith('//')
// Strip trailing comments and string literals so patterns do not match inside them.
const strip = (t) => t.replace(/"(\\.|[^"\\])*"/g, '""').replace(/\/\/.*$/, '')
const topLevel = (t) => isCode(t) && !/^\s/.test(t)

// ---- 1. DUPLICATE TOP-LEVEL DECLARATIONS ----------------------------------
// The single most destructive whole-file error: two chunks declaring one name.
const declared = new Map()
const DECL = [
  /^(?:var(?:ip)?\s+)?(?:array<[^>]+>|matrix<[^>]+>|map<[^,]+,[^>]+>|float|int|bool|string|color|line|label|box|table|[A-Z]\w*)\s+([A-Za-z_]\w*)\s*(?:=|:=)/,
  /^([A-Za-z_]\w*)\s*=\s*(?!=)/,            // plain inferred assignment
  /^\[([^\]]+)\]\s*=/,                       // tuple destructuring
  /^(?:export\s+)?method\s+([A-Za-z_]\w*)\s*\(/,
  /^(?:export\s+)?type\s+([A-Za-z_]\w*)/,
  /^(?:export\s+)?enum\s+([A-Za-z_]\w*)/,
  /^([A-Za-z_]\w*)\s*\([^)]*\)\s*=>/,        // function definition
]
for (const ln of lines) {
  if (!topLevel(ln.text)) continue
  const t = strip(ln.text)
  for (const re of DECL) {
    const m = t.match(re)
    if (!m) continue
    const names = m[1].includes(',') ? m[1].split(',').map(s => s.trim()) : [m[1]]
    for (const nm of names) {
      if (!nm || !/^[A-Za-z_]\w*$/.test(nm)) continue
      if (declared.has(nm)) {
        add('ERROR', 'duplicate-decl', ln,
          `"${nm}" is already declared at ${declared.get(nm)}. Pine rejects the whole script.`)
      } else declared.set(nm, `${ln.part}:${ln.srcLine}`)
    }
    break
  }
}

// ---- 2. nz()/na()/fixnan() ON A BOOL  (v6 compile error) ------------------
for (const ln of lines) {
  const t = strip(ln.text)
  if (/\b(?:nz|fixnan)\s*\([^)]*,\s*(?:true|false)\s*\)/.test(t))
    add('ERROR', 'bool-nz', ln, 'nz()/fixnan() with a bool default. In v6 a bool is never na and these reject bool args.')
  if (/\bnz\s*\(\s*(?:not\s+)?[A-Za-z_]\w*\s*(?:and|or)\s/.test(t))
    add('ERROR', 'bool-nz', ln, 'nz() wrapping a boolean expression - compile error in v6.')
}

// ---- 3. ta.* CALLED LAZILY (inside if / and / or / ternary) ---------------
// v6 short-circuits and/or, so a ta.* call there is skipped on some bars and
// its internal history silently desynchronises. It must sit at global scope.
for (const ln of lines) {
  const t = strip(ln.text)
  if (!/\bta\.\w+\s*\(/.test(t)) continue
  const indented = /^\s+\S/.test(ln.text)
  const inCond = /\b(?:and|or)\b/.test(t) || /\?/.test(t) || /^\s*if\b/.test(t)
  if (indented && !/^\s*(?:float|int|bool|var|[A-Za-z_]\w*)\s*(?::=|=)/.test(t))
    add('WARN', 'ta-in-block', ln, 'ta.* inside an indented block - verify it executes on EVERY bar.')
  else if (inCond)
    add('ERROR', 'ta-lazy', ln, 'ta.* inside a conditional/and/or/ternary. v6 evaluates lazily - hoist it to global scope.')
}

// ---- 4. USE BEFORE DECLARATION --------------------------------------------
// Pine is strictly single-pass. A name used above its declaration line fails.
const declLine = new Map()
{
  let n = 0
  for (const ln of lines) {
    n++
    if (!topLevel(ln.text)) continue
    const t = strip(ln.text)
    for (const re of DECL) {
      const m = t.match(re)
      if (!m) continue
      const names = m[1].includes(',') ? m[1].split(',').map(s => s.trim()) : [m[1]]
      for (const nm of names) if (/^[A-Za-z_]\w*$/.test(nm) && !declLine.has(nm)) declLine.set(nm, n)
      break
    }
  }
  n = 0
  const BUILTIN = /^(?:open|high|low|close|volume|time|bar_index|na|nz|math|ta|str|array|matrix|map|color|line|label|box|table|input|plot|plotshape|plotchar|alert|alertcondition|strategy|indicator|request|timeframe|syminfo|barstate|session|dayofweek|year|month|dayofmonth|hour|minute|second|weekofyear|timenow|format|size|location|shape|position|xloc|yloc|extend|barmerge|display|scale|true|false|if|for|while|switch|var|varip|not|and|or|float|int|bool|string|series|simple|const|method|type|enum|export|import|f_slot)$/
  for (const ln of lines) {
    n++
    if (!isCode(ln.text)) continue
    const t = strip(ln.text)
    const body = t.replace(/^[^=]*(?::=|=>|=)/, '')   // right-hand side only
    // The leading [^.\w] guard is essential: without it `LevelKind.pdh` matches
    // the global `pdh`, and every enum member / UDT field / method call gets
    // reported as a use-before-declaration.
    for (const m of body.matchAll(/(^|[^.\w])([A-Za-z_]\w*)\b/g)) {
      const nm = m[2]
      if (BUILTIN.test(nm) || !declLine.has(nm)) continue
      if (declLine.get(nm) > n)
        add('ERROR', 'use-before-decl', ln, `"${nm}" is used here but first declared later (line ${declLine.get(nm)} of the assembled file).`)
    }
  }
}

// ---- 5. PLOT-SLOT BUDGET (hard cap 64) ------------------------------------
{
  let slots = 0
  const PLOTTERS = /\b(plot|plotshape|plotchar|plotarrow|plotcandle|plotbar|bgcolor|barcolor|fill|alertcondition|hline)\s*\(/g
  for (const ln of lines) {
    if (!isCode(ln.text)) continue
    slots += [...strip(ln.text).matchAll(PLOTTERS)].length
  }
  if (slots > 64) add('ERROR', 'plot-budget', null, `${slots} plot-consuming calls against TradingView's hard cap of 64.`)
  else add('INFO', 'plot-budget', null, `${slots}/64 plot slots used.`)
}

// ---- 6. UNBALANCED PARENTHESES ON A LOGICAL LINE --------------------------
// Pine continuation lines are indented; a top-level line must balance by the
// time the next top-level line starts.
{
  let depth = 0, start = null
  for (const ln of lines) {
    if (!isCode(ln.text)) continue
    if (topLevel(ln.text) && depth !== 0) {
      add('ERROR', 'paren-balance', start, `Unbalanced parentheses (depth ${depth}) before the next top-level statement.`)
      depth = 0
    }
    if (depth === 0) start = ln
    const t = strip(ln.text)
    for (const ch of t) { if (ch === '(' || ch === '[') depth++; else if (ch === ')' || ch === ']') depth-- }
  }
}

// ---- 7. TICK / POINT DENOMINATION (the 10x broker bug) --------------------
for (const ln of lines) {
  const t = strip(ln.text)
  if (/\bsyminfo\.mintick\b/.test(t) && !/round_to_mintick|format\.mintick|^\s*tick\s*=/.test(t))
    add('WARN', 'tick-denom', ln, 'Raw syminfo.mintick outside rounding/formatting. Tolerances must use f_tol().')
  if (/\bi_\w*Ticks\b/.test(t))
    add('WARN', 'tick-denom', ln, 'A ticks-denominated input mis-scales 10x between 0.01 and 0.001 gold feeds.')
}

// ---- 8. REPAINT SURFACE ----------------------------------------------------
for (const ln of lines) {
  const t = strip(ln.text)
  if (/lookahead\s*=\s*barmerge\.lookahead_on/.test(t) && !/\[1\]|bOut|rdyOut/.test(t))
    add('WARN', 'lookahead', ln, 'lookahead_on must be paired with a one-bar offset. Verify the shift is present.')
  if (/\bvarip\b/.test(t))
    add('ERROR', 'varip', ln, 'varip updates intrabar and cannot be non-repainting.')
  if (/request\.security_lower_tf/.test(t))
    add('ERROR', 'ltf', ln, 'request.security_lower_tf was excluded from this design - it repaints.')
}

// ---- 9. CLAIM HYGIENE ------------------------------------------------------
// Narrow on purpose. The first version flagged every line that DISCLAIMED an
// overclaim ("it is not real order flow"), which is exactly the text we want to
// see. Only fire when the claim is asserted and nothing negates it on that line.
const CLAIM = /(guaranteed\s+(?:profit|win|return|success)|\d+\s*%\s*(?:probability|win\s*rate|accuracy)|\btrue\s+delta\b|\breal\s+order\s+flow\b|\binstitutional\s+(?:hidden\s+)?orders?\b)/i
const NEGATED = /\b(?:not|never|no|cannot|can't|isn't|without|rather than|instead of|proxy|PROXY)\b/i
for (const ln of lines) {
  const t = ln.text
  if (!/"/.test(t)) continue
  if (CLAIM.test(t) && !NEGATED.test(t))
    add('ERROR', 'overclaim', ln, 'User-facing string overclaims. This system infers from tick volume - it is a proxy.')
}

// ---- report ---------------------------------------------------------------
const order = { ERROR: 0, WARN: 1, INFO: 2 }
findings.sort((a, b) => order[a.sev] - order[b.sev])
const nErr = findings.filter(f => f.sev === 'ERROR').length
const nWarn = findings.filter(f => f.sev === 'WARN').length

if (missing.length) console.log(`MISSING PARTS: ${missing.join(', ')}\n`)
console.log(`Assembled ${lines.length} lines from ${ORDER.length - missing.length} parts`)
console.log(`${nErr} errors, ${nWarn} warnings\n`)
for (const f of findings) {
  if (f.sev === 'INFO') { console.log(`  INFO  ${f.rule.padEnd(16)} ${f.msg}`); continue }
  console.log(`${f.sev.padEnd(5)} ${f.rule.padEnd(16)} ${f.where.padEnd(22)} ${f.msg}`)
  if (f.text) console.log(`      | ${f.text}`)
}
process.exit(nErr > 0 ? 1 : 0)
