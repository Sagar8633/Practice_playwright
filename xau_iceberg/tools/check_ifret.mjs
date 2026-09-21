#!/usr/bin/env node
// Finds if/else pairs whose branches end with DIFFERENT value-ness.
//
// Pine types the last statement of a block as that block's value. An assignment
// (`x := y`) is typed as its value; a call like array.set()/box.delete() is void.
// When such an if/else sits in return position, Pine rejects it with:
//   "Return type of one of the if or switch blocks is not compatible with
//    return type of other block(s) (void; series bool)"
// The fix is always the same: add an explicit trailing expression after the
// if/else so the if is a statement rather than the return value.
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const PARTS = 'D:/Practice_Playwright/xau_iceberg/parts'
const ORDER = [
  '00_globals', '01_types', '02_helpers', '02b_state', '03_structure', '04_liquidity',
  '05_sweep', '06_absorption', '07_reject', '08_displacement', '09_bos', '10_retest',
  '11_risk', '12_score', '13_filters', '14_machine', '15_failure', '16_visuals',
  '17_alerts', '18_exec', '19_presets',
]

const VOID_CALL = /^\s*(?:[A-Za-z_][\w.]*\.)?(?:set|push|pop|clear|insert|remove|delete|unshift|shift|fill|sort|reverse|cell|merge_cells|alert)\s*\(/
const VOID_NS   = /^\s*(?:array|box|line|label|table|matrix|map)\.\w+\s*\(/
const ASSIGN    = /^\s*[A-Za-z_][\w.\[\]]*\s*:=/
const isVoid = (s) => VOID_CALL.test(s) || VOID_NS.test(s) || /^\s*[A-Za-z_][\w.]*\.\w+\s*\(/.test(s) && !ASSIGN.test(s)

let hits = 0
for (const p of ORDER) {
  const f = join(PARTS, p + '.pine')
  if (!existsSync(f)) continue
  const lines = readFileSync(f, 'utf8').split(/\r?\n/)
  const code = lines.map(l => l.replace(/\/\/.*$/, '').replace(/\s+$/, ''))

  for (let i = 0; i < code.length; i++) {
    const m = code[i].match(/^(\s*)else\s*$/)
    if (!m) continue
    const ind = m[1].length

    // last statement of the ELSE branch
    let j = i + 1, elseLast = null
    while (j < code.length) {
      const l = code[j]
      if (l.trim()) {
        const li = l.match(/^ */)[0].length
        if (li <= ind) break
        if (li === ind + 4) elseLast = l
      }
      j++
    }
    // last statement of the matching IF branch (scan back to the `if` at `ind`)
    let k = i - 1, ifLast = null
    while (k >= 0) {
      const l = code[k]
      if (l.trim()) {
        const li = l.match(/^ */)[0].length
        if (li === ind && /^\s*if\b/.test(l)) break
        if (li === ind + 4 && ifLast === null) ifLast = l
        if (li < ind) break
      }
      k--
    }
    if (!elseLast || !ifLast) continue

    const a = isVoid(ifLast), b = isVoid(elseLast)
    const av = ASSIGN.test(ifLast), bv = ASSIGN.test(elseLast)
    if ((a && bv) || (b && av)) {
      hits++
      console.log(`${p}:${i + 1}  if/else branches disagree on value-ness`)
      console.log(`    if-last   | ${ifLast.trim().slice(0, 90)}   -> ${a ? 'void' : 'value'}`)
      console.log(`    else-last | ${elseLast.trim().slice(0, 90)}   -> ${b ? 'void' : 'value'}`)
    }
  }
}
console.log(`\n${hits} suspicious if/else return-type mismatch(es)`)
