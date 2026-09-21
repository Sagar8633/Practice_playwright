#!/usr/bin/env node
/**
 * Analytics Manager SQL Lab - static file server.
 *
 * Zero dependencies. Its only job is to serve this folder over http://
 * so the browser will load the PGlite WebAssembly module (browsers refuse
 * to instantiate WASM from a file:// origin).
 *
 * This server NEVER connects to a database. It has no driver, no
 * connection string and no credentials. It reads files from this
 * directory and nothing else.
 */

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const url = require('node:url');

const ROOT = __dirname;
const PORT = Number(process.env.PORT) || 4173;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.sql': 'text/plain; charset=utf-8',
  '.wasm': 'application/wasm',
  '.data': 'application/octet-stream',
  '.tar.gz': 'application/gzip',
  '.gz': 'application/gzip',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.map': 'application/json; charset=utf-8',
};

function mimeFor(p) {
  if (p.endsWith('.tar.gz')) return MIME['.tar.gz'];
  return MIME[path.extname(p).toLowerCase()] || 'application/octet-stream';
}

const server = http.createServer((req, res) => {
  let pathname;
  try {
    pathname = decodeURIComponent(url.parse(req.url).pathname);
  } catch {
    res.writeHead(400).end('Bad request');
    return;
  }

  if (pathname === '/') pathname = '/index.html';

  // Contain every request inside ROOT.
  const target = path.join(ROOT, path.normalize(pathname).replace(/^([/\\])+/, ''));
  if (!target.startsWith(ROOT)) {
    res.writeHead(403).end('Forbidden');
    return;
  }

  fs.stat(target, (err, stat) => {
    if (err || !stat.isFile()) {
      res.writeHead(404, { 'Content-Type': 'text/plain' }).end('404 Not Found');
      return;
    }
    res.writeHead(200, {
      'Content-Type': mimeFor(target),
      'Content-Length': stat.size,
      'Cache-Control': 'no-cache',
    });
    fs.createReadStream(target).pipe(res);
  });
});

server.listen(PORT, () => {
  const line = '='.repeat(60);
  console.log(`\n${line}`);
  console.log('  Analytics Manager SQL Lab');
  console.log(line);
  console.log(`  Open:  http://localhost:${PORT}`);
  console.log('');
  console.log('  The practice database is PostgreSQL compiled to WASM and');
  console.log('  lives entirely in your browser tab. This server holds no');
  console.log('  database connection of any kind.');
  console.log(`${line}\n  Ctrl+C to stop.\n`);
});

server.on('error', (e) => {
  if (e.code === 'EADDRINUSE') {
    console.error(`\nPort ${PORT} is already in use.`);
    console.error(`Try:  PORT=4174 node server.js\n`);
    process.exit(1);
  }
  throw e;
});
