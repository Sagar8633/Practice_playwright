import { createServer } from 'node:http'
import { readFileSync } from 'node:fs'
const FILE = 'D:/Practice_Playwright/xau_iceberg/build/XAU_Iceberg_Indicator.pine'
createServer((req, res) => {
  const src = readFileSync(FILE, 'utf8')
  if (req.url.startsWith('/raw')) {
    res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' })
    return res.end(src)
  }
  const esc = src.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' })
  res.end('<!doctype html><meta charset="utf-8"><title>pine</title><body><pre id="p">' + esc + '</pre>')
}).listen(8899, '127.0.0.1', () => console.log('serving on http://127.0.0.1:8899'))
