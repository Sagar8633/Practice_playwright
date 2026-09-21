#!/usr/bin/env node
// Adds `display = display.none` to every input.*() call.
//
// TradingView prints every input's VALUE into the chart status line by default.
// With ~209 inputs that renders as an unreadable wall of numbers across the top
// of the chart, burying the legend. display.none suppresses the status-line and
// Data Window copies while leaving the input fully present and editable in the
// script's Settings/Inputs tab.
//
// Usage: node add_display.mjs [--write]
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

let total = 0, skipped = 0
for (const p of ORDER) {
  const f = join(PARTS, p + '.pine')
  if (!existsSync(f)) continue
  let src = readFileSync(f, 'utf8')
  let out = ''
  let i = 0
  let count = 0

  while (i < src.length) {
    const m = /input\.\w+\s*\(/g
    m.lastIndex = i
    let hit = m.exec(src)
    // Skip matches that sit inside a // comment. 18_exec carries the entire
    // strategy variant commented out, and a commented input.*( has no matching
    // close paren in live code - the scanner then ran to EOF and appended the
    // new argument past the end of the file.
    while (hit) {
      const lineStart = src.lastIndexOf('\n', hit.index) + 1
      const before = src.slice(lineStart, hit.index)
      if (!before.includes('//')) break
      m.lastIndex = hit.index + hit[0].length
      hit = m.exec(src)
    }
    if (!hit) { out += src.slice(i); break }

    // copy everything up to and including the opening paren
    const open = hit.index + hit[0].length
    out += src.slice(i, open)

    // walk to the matching close paren, skipping string literals and comments
    let depth = 1, j = open, inStr = false, strCh = ''
    while (j < src.length && depth > 0) {
      const c = src[j], prev = src[j - 1]
      if (inStr) {
        if (c === strCh && prev !== '\\') inStr = false
      } else if (c === '"' || c === "'") {
        inStr = true; strCh = c
      } else if (c === '/' && src[j + 1] === '/') {
        while (j < src.length && src[j] !== '\n') j++
        continue
      } else if (c === '(' || c === '[') depth++
      else if (c === ')' || c === ']') depth--
      if (depth === 0) break
      j++
    }
    const body = src.slice(open, j)
    if (/\bdisplay\s*=/.test(body)) {
      out += body            // already has one - leave it alone
      skipped++
    } else {
      // match the call's own wrapping: if it spans lines, put the new arg on its
      // own continuation line indented by 5 (NOT a multiple of 4 - see fix_cont)
      out += body.replace(/\s*$/, '') + (body.includes('\n') ? ',\n     display = display.none' : ', display = display.none')
      count++; total++
    }
    out += ')'
    i = j + 1
  }

  if (WRITE && count) writeFileSync(f, out, 'utf8')
  if (count) console.log(`${p}: +${count}`)
}
console.log(`\n${total} input(s) given display.none` + (skipped ? `, ${skipped} already had one` : '') + (WRITE ? ' - WRITTEN' : ' - dry run'))
