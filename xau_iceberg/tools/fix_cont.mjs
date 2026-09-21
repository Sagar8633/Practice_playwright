#!/usr/bin/env node
// Pine line-continuation rule: a wrapped expression's continuation line must be
// indented by a number of spaces that is NOT a multiple of 4. Four spaces means
// "new block", so the parser hits the end of the previous line still expecting
// more and reports:
//     Syntax error at input "end of line without line continuation"
//
// This is invisible per-chunk (each file looks fine) and only one error is
// reported per compile, so finding them all mechanically beats 20 paste cycles.
//
// Usage:  node fix_cont.mjs [--write]
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const PARTS = 'D:/Practice_Playwright/xau_iceberg/parts'
const ORDER = [
  '00_globals', '01_types', '02_helpers', '02b_state', '03_structure', '04_liquidity',
  '05_sweep', '06_absorption', '07_reject', '08_displacement', '09_bos', '10_retest',
  '11_risk', '12_score', '13_filters', '14_machine', '15_failure', '16_visuals',
  '17_alerts', '18_exec', '19_presets',
]
const WRITE = process.argv.includes('--write')

// A line that ends with one of these is an INCOMPLETE expression: whatever
// follows must be a continuation, never a block.
const OPEN_END = /(\?|:|\+|-|\*|\/|%|,|\(|\[|\bor\b|\band\b|\bnot\b|==|!=|>=|<=|>|<|=|:=)\s*$/
// ...except these, which legitimately open an indented block.
const BLOCK_END = /(=>|\bif\b.*|\belse\b|\bfor\b.*|\bwhile\b.*|\bswitch\b.*)\s*$/

const strip = (t) => t.replace(/"(\\.|[^"\\])*"/g, '""').replace(/\/\/.*$/, '')
let total = 0
const report = []

for (const p of ORDER) {
  const f = join(PARTS, p + '.pine')
  if (!existsSync(f)) continue
  const lines = readFileSync(f, 'utf8').split(/\r?\n/)
  let changed = false

  for (let i = 0; i < lines.length - 1; i++) {
    const cur = lines[i]
    if (!cur.trim() || cur.trim().startsWith('//')) continue
    const curCode = strip(cur).replace(/\s+$/, '')
    if (!curCode) continue
    if (BLOCK_END.test(curCode)) continue
    if (!OPEN_END.test(curCode)) continue

    // find the next non-blank, non-comment line
    let j = i + 1
    while (j < lines.length && (!lines[j].trim() || lines[j].trim().startsWith('//'))) j++
    if (j >= lines.length) continue
    const nxt = lines[j]
    const indent = nxt.match(/^ */)[0].length
    if (indent === 0) continue                    // not a continuation at all
    if (indent % 4 !== 0) continue                // already legal

    total++
    report.push(`${p}:${j + 1}  indent ${indent} (multiple of 4) continues line ${i + 1}`)
    report.push(`    prev | ${cur.trim().slice(0, 96)}`)
    report.push(`    cont | ${nxt.trim().slice(0, 96)}`)
    if (WRITE) { lines[j] = ' ' + nxt; changed = true }
  }
  if (WRITE && changed) writeFileSync(f, lines.join('\n'), 'utf8')
}

console.log(report.join('\n'))
console.log(`\n${total} continuation line(s) indented by a multiple of 4` + (WRITE ? ' - FIXED (one space added to each)' : ''))
