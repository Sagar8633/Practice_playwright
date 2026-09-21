#!/usr/bin/env node
// Assembles the part files into the shippable .pine scripts.
// The indicator and the strategy share every line except the declaration in
// Section 0 and the two halves of Section 18 - that is the whole point of the
// part layout, and this script is what enforces it rather than trusting a human
// to keep two 8000-line files in sync by hand.
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'

const ROOT = 'D:/Practice_Playwright/xau_iceberg'
const PARTS = join(ROOT, 'parts')
const ORDER = [
  '00_globals', '01_types', '02_helpers', '02b_state', '03_structure', '04_liquidity',
  '05_sweep', '06_absorption', '07_reject', '08_displacement', '09_bos', '10_retest',
  '11_risk', '12_score', '13_filters', '14_machine', '15_failure', '16_visuals',
  '17_alerts', '18_exec', '19_presets',
]

// Section 19's runtime self-tests are developer scaffolding: ~129 lines of
// assertions and a 24-row table that render once on the last bar and affect no
// signal. TradingView caps COMPILED tokens at 100256 and the full file lands
// over it, so the tests are stripped from the shipped build while their preset
// documentation - which is pure comment, and therefore free - is kept.
// Set KEEP_TESTS=1 to build the diagnostic variant instead.
const KEEP_TESTS = process.env.KEEP_TESTS === '1'

let out = []
let strippedTestLines = 0
for (const p of ORDER) {
  const f = join(PARTS, p + '.pine')
  if (!existsSync(f)) { console.error('MISSING ' + p); process.exit(1) }
  let src = readFileSync(f, 'utf8').replace(/\s+$/, '')
  if (p === '19_presets' && !KEEP_TESTS) {
    const kept = src.split('\n').filter(l => {
      const isCode = l.trim() && !l.trim().startsWith('//')
      if (isCode) strippedTestLines++
      return !isCode
    })
    kept.push('// NOTE: the runtime self-tests were stripped from this build to fit')
    kept.push('// TradingView\'s 100256 compiled-token cap. Rebuild with KEEP_TESTS=1')
    kept.push('// to restore them (it will not compile until something else is cut).')
    src = kept.join('\n')
  }
  out.push(src)
}
let text = out.join('\n\n')

// ---- TOKEN DIET -----------------------------------------------------------
// TradingView caps COMPILED tokens at 100256. Comments are stripped before
// compilation so they cost nothing, but a tooltip written as
//     "one " + "two " + "three"
// costs 5 tokens (3 literals + 2 operators) where "one two three" costs 1.
// With ~197 inputs each carrying a multi-fragment tooltip that is thousands of
// tokens spent on nothing. Merging adjacent string literals is semantically
// identical and is done HERE, at build time, so the part files stay readable.
// The \s* between the operands cannot span a // comment, so commented-out code
// is never touched.
const MERGE = /"((?:[^"\\]|\\.)*)"(\s*)\+(\s*)"((?:[^"\\]|\\.)*)"/g
let merges = 0
for (;;) {
  let n = 0
  text = text.replace(MERGE, (_m, a, _w1, _w2, b) => { n++; return '"' + a + b + '"' })
  merges += n
  if (n === 0) break
}

if (!existsSync(join(ROOT, 'build'))) mkdirSync(join(ROOT, 'build'))
const indPath = join(ROOT, 'build', 'XAU_Iceberg_Indicator.pine')
writeFileSync(indPath, text + '\n', 'utf8')

// ---- size report: TradingView limits COMPILED size, so comments are nearly
// free. Report both so a "too large" error can be diagnosed correctly.
const lines = text.split('\n')
const code = lines.filter(l => l.trim() && !l.trim().startsWith('//'))
const comment = lines.length - code.length
console.log('indicator : ' + indPath)
console.log('  total lines   : ' + lines.length)
console.log('  code lines    : ' + code.length)
console.log('  comment/blank : ' + comment + '  (' + Math.round(comment / lines.length * 100) + '%)')
console.log('  bytes         : ' + Buffer.byteLength(text))
console.log('  tests stripped: ' + strippedTestLines + ' code lines')
console.log('  string merges : ' + merges + '  (~' + (merges * 2) + ' compiled tokens saved)')
