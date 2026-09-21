/**
 * app.js - views, routing, attempt/hint state machine.
 */
import { initDb, runUserQuery, runReference, grade,
         loadProgress, saveProgress, questionState, recordAttempt,
         recordHint, resetProgress, computeStats } from './core.js';
import { SAFETY_NOTE } from './guard.js';
import { TABLES, GROUPS, GAPS, ENUMS, AUTOCOMPLETE } from './schema-data.js';

const $  = (s, r = document) => r.querySelector(s);
const el = (t, c, h) => { const n = document.createElement(t); if (c) n.className = c; if (h !== undefined) n.innerHTML = h; return n; };
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));

const LEVEL_NAMES = {
  0:'Database Understanding', 1:'SQL Fundamentals', 2:'Aggregation', 3:'JOINs',
  4:'Subqueries & CTEs', 5:'CASE & Business Logic', 6:'Date & Time',
  7:'Window Functions', 8:'Advanced SQL', 9:'Senior QA Investigation',
};

const S = {
  view: 'dashboard',
  bank: [], byId: new Map(), challenges: [],
  progress: loadProgress(),
  current: null, editor: null,
  hintsShown: 0, revealed: false, lastResult: null,
  filterLevel: 'all',
  exam: null,
  challenge: null, challengeStep: 0,
};

/* ===================== bootstrap ===================== */

async function loadBank() {
  const files = [0,1,2,3,4,5,6,7,8].map((l) => `./data/questions/level${l}.json`);
  const all = await Promise.all(files.map((f) => fetch(f, {cache:'no-cache'}).then((r) => r.ok ? r.json() : [])));
  S.bank = all.flat();
  S.challenges = await fetch('./data/questions/challenges.json', {cache:'no-cache'}).then((r) => r.json());
  for (const c of S.challenges) for (const st of c.steps) S.bank.push(st);
  for (const q of S.bank) S.byId.set(q.id, q);
}

async function boot() {
  try {
    await loadBank();
    await initDb((m) => { $('#bootMsg').textContent = m; });
    $('#dbPill').classList.add('ready');
    $('#dbPillText').textContent = 'PostgreSQL · read-only';
    $('#boot').hidden = true;
    $('#app').hidden = false;
    render();
  } catch (e) {
    $('#bootMsg').innerHTML =
      `<span style="color:#e35d6a">Startup failed: ${esc(e.message)}</span><br>
       <span style="font-size:12px">Serve this folder over http:// — open it with <code>node server.js</code>, not by double-clicking index.html.</span>`;
    $('.spinner').style.display = 'none';
  }
}

$('#tabs').addEventListener('click', (e) => {
  const b = e.target.closest('.tab');
  if (!b) return;
  S.view = b.dataset.view;
  [...$('#tabs').children].forEach((t) => t.classList.toggle('active', t === b));
  S.challenge = null;
  render();
});

function render() {
  const app = $('#app');
  app.innerHTML = '';
  S.editor = null;
  ({ dashboard: viewDashboard, practice: viewPractice, exam: viewExam,
     senior: viewSenior, schema: viewSchema }[S.view] || viewDashboard)(app);
}

/* ===================== dashboard ===================== */

function viewDashboard(root) {
  const practiceBank = S.bank.filter((q) => q.level <= 8);
  const st = computeStats(S.progress, practiceBank);

  root.append(el('div','view-head',`
    <h1>Your progress</h1>
    <p>Nine levels built entirely on the Analytics Manager schema, then six production
       investigations. Solutions unlock only after five failed attempts — the point is to
       write the SQL, not to read it.</p>`));

  const pct = (a,b) => b ? Math.round(100*a/b) : 0;
  const stats = el('div','grid g4');
  stats.style.marginBottom = '14px';
  stats.innerHTML = `
    <div class="stat"><div class="v">${st.solved}<span style="font-size:15px;color:var(--fg3)">/${st.total}</span></div><div class="k">Questions solved</div></div>
    <div class="stat ${st.accuracy>=.75?'ok':st.accuracy>=.5?'warn':'bad'}"><div class="v">${pct(st.solved,st.attempted)}%</div><div class="k">Accuracy</div></div>
    <div class="stat ok"><div class="v">${pct(st.firstTry,st.solved)}%</div><div class="k">First-attempt rate</div></div>
    <div class="stat ${st.needsRevision?'warn':''}"><div class="v">${st.needsRevision}</div><div class="k">Needs revision</div></div>`;
  root.append(stats);

  const cols = el('div','grid g2');

  // levels
  const lv = el('div','card');
  lv.innerHTML = '<h3 style="margin:0 0 10px;font-size:14px">Level completion</h3>';
  for (let l = 0; l <= 8; l++) {
    const d = st.perLevel[l] || { total:0, solved:0 };
    const p = pct(d.solved, d.total);
    lv.append(el('div','lvl-row',`
      <div class="lvl-name"><b>Level ${l} · ${LEVEL_NAMES[l]}</b><span>${d.solved} of ${d.total} solved</span></div>
      <div class="lvl-bar"><div class="bar ${p===100?'ok':''}"><i style="width:${p}%"></i></div></div>
      <div class="lvl-num">${p}%</div>`));
  }
  const cst = challengeStats();
  lv.append(el('div','lvl-row',`
    <div class="lvl-name"><b>Senior QA investigations</b><span>${cst.done} of ${cst.total} steps</span></div>
    <div class="lvl-bar"><div class="bar ${cst.done===cst.total?'ok':''}"><i style="width:${pct(cst.done,cst.total)}%"></i></div></div>
    <div class="lvl-num">${pct(cst.done,cst.total)}%</div>`));
  cols.append(lv);

  // skills
  const sk = el('div','card');
  sk.innerHTML = '<h3 style="margin:0 0 10px;font-size:14px">Skill breakdown</h3>';
  if (!st.allSkills.length) {
    sk.append(el('p','muted','Solve a few questions and your strong and weak areas will appear here.'));
  } else {
    sk.append(el('h4',null,'<span style="font-size:11px;letter-spacing:.6px;color:var(--ok);text-transform:uppercase">Strong</span>'));
    const a = el('div','chips');
    a.append(...(st.strong.length ? st.strong.slice(0,14).map((s) => el('span','chip ok',`${esc(s.name)} · ${Math.round(s.rate*100)}%`))
                                  : [el('span','chip','nothing yet')]));
    sk.append(a);
    sk.append(el('h4',null,'<span style="font-size:11px;letter-spacing:.6px;color:var(--bad);text-transform:uppercase;display:block;margin-top:12px">Needs practice</span>'));
    const b = el('div','chips');
    b.append(...(st.weak.length ? st.weak.slice(0,14).map((s) => el('span','chip bad',`${esc(s.name)} · ${Math.round(s.rate*100)}%`))
                                : [el('span','chip','nothing flagged')]));
    sk.append(b);

    const rev = practiceBank.filter((q) => { const s = S.progress.questions[q.id]; return s && s.revealed && !s.firstTry; });
    if (rev.length) {
      sk.append(el('hr','sep'));
      sk.append(el('h4',null,'<span style="font-size:11px;letter-spacing:.6px;color:var(--warn);text-transform:uppercase">Revisit these</span>'));
      const c = el('div','chips');
      c.append(...rev.slice(0,12).map((q) => {
        const x = el('span','chip acc', `${q.id} · ${esc(q.title)}`);
        x.style.cursor = 'pointer';
        x.onclick = () => openQuestion(q.id);
        return x;
      }));
      sk.append(c);
    }
  }
  cols.append(sk);
  root.append(cols);

  const foot = el('div','card');
  foot.style.marginTop = '14px';
  foot.innerHTML = `<h3 style="margin:0 0 8px;font-size:14px">How your database stays safe</h3>
    <ol style="margin:0;padding-left:20px;color:var(--fg2);font-size:13px;line-height:1.75">
      ${SAFETY_NOTE.map((n) => `<li>${esc(n)}</li>`).join('')}
    </ol>`;
  const rb = el('div','btn-row'); rb.style.marginTop = '12px';
  const reset = el('button','btn ghost','Reset all progress');
  reset.onclick = () => {
    if (confirm('Erase all progress? This cannot be undone.')) {
      resetProgress(); S.progress = loadProgress(); render();
    }
  };
  rb.append(reset);
  foot.append(rb);
  root.append(foot);
}

function challengeStats() {
  let done = 0, total = 0;
  for (const c of S.challenges) for (const s of c.steps) {
    total++;
    if (S.progress.questions[s.id]?.solved) done++;
  }
  return { done, total };
}

/* ===================== practice ===================== */

function viewPractice(root) {
  root.append(el('div','view-head',`
    <h1>Practice</h1>
    <p>Pick a question, write the SQL, submit. Wrong answers earn a progressively stronger
       hint; the solution appears only after the fifth failed attempt.</p>`));

  const wrap = el('div','practice');
  const side = el('div','qlist');

  const head = el('div','qlist-head');
  const sel = el('select');
  sel.innerHTML = `<option value="all">All levels</option>` +
    [0,1,2,3,4,5,6,7,8].map((l) => `<option value="${l}">Level ${l} · ${LEVEL_NAMES[l]}</option>`).join('') +
    `<option value="weak">Weak topics only</option>`;
  sel.value = S.filterLevel;
  sel.onchange = () => { S.filterLevel = sel.value; render(); };
  head.append(sel);

  const rnd = el('button','btn sm','Random');
  rnd.onclick = () => {
    const pool = visibleQuestions().filter((q) => !S.progress.questions[q.id]?.solved);
    const from = pool.length ? pool : visibleQuestions();
    if (from.length) openQuestion(from[Math.floor(Math.random()*from.length)].id);
  };
  head.append(rnd);
  side.append(head);

  const scroll = el('div','qlist-scroll');
  const list = visibleQuestions();
  if (!list.length) scroll.append(el('div','empty','No questions match.'));
  for (const q of list) {
    const s = questionState(S.progress, q.id);
    const mark = s.solved ? ['st-solved','✓'] : s.revealed ? ['st-rev','!'] : s.attempts ? ['st-try','·'] : ['st-new','○'];
    const it = el('div', 'qitem' + (S.current?.id === q.id ? ' active' : ''), `
      <div class="st ${mark[0]}">${mark[1]}</div>
      <div class="tx"><div class="id">${q.id} · ${q.difficulty}</div><div class="ti">${esc(q.title)}</div></div>`);
    it.onclick = () => openQuestion(q.id);
    scroll.append(it);
  }
  side.append(scroll);
  wrap.append(side);

  const main = el('div');
  main.id = 'qpane';
  wrap.append(main);
  root.append(wrap);

  if (S.current && S.byId.has(S.current.id) && S.current.level <= 8) renderQuestion(main, S.current);
  else main.append(el('div','card empty','Select a question on the left, or press <b>Random</b>.'));
}

function visibleQuestions() {
  let list = S.bank.filter((q) => q.level <= 8);
  if (S.filterLevel === 'weak') {
    const st = computeStats(S.progress, list);
    const weak = new Set(st.weak.map((w) => w.name));
    list = list.filter((q) => (q.skills||[]).some((s) => weak.has(s)));
    if (!list.length) list = S.bank.filter((q) => q.level <= 8 && !S.progress.questions[q.id]?.solved);
  } else if (S.filterLevel !== 'all') {
    list = list.filter((q) => q.level === Number(S.filterLevel));
  }
  return list;
}

function openQuestion(id) {
  S.current = S.byId.get(id);
  S.hintsShown = 0; S.revealed = false; S.lastResult = null;
  if (S.current.level === 9) {
    S.view = 'senior';
    S.challenge = S.challenges.find((c) => c.steps.some((s) => s.id === id));
    S.challengeStep = S.challenge.steps.findIndex((s) => s.id === id);
    [...$('#tabs').children].forEach((t) => t.classList.toggle('active', t.dataset.view === 'senior'));
  } else {
    S.view = 'practice';
    [...$('#tabs').children].forEach((t) => t.classList.toggle('active', t.dataset.view === 'practice'));
  }
  render();
  document.querySelector('#qpane, #spane')?.scrollIntoView({ behavior:'smooth', block:'start' });
}

/* ===================== question renderer ===================== */

function renderQuestion(root, q, opts = {}) {
  const st = questionState(S.progress, q.id);
  const examMode = !!opts.exam;
  const card = el('div','card');

  card.append(el('div','qhead',`
    <div>
      <h2>${esc(q.title)}</h2>
      <div class="badges">
        <span class="badge lv">Level ${q.level}${q.level===9?' · Senior':''}</span>
        <span class="badge d-${q.difficulty}">${q.difficulty}</span>
        <span class="badge">${q.id}</span>
        ${(q.skills||[]).map((s)=>`<span class="badge">${esc(s)}</span>`).join('')}
      </div>
    </div>
    <div class="right">
      ${st.solved ? '<span class="chip ok">solved</span>' : st.revealed ? '<span class="chip bad">needs revision</span>' : ''}
      <div class="attempt-dots" style="justify-content:flex-end;margin-top:6px" title="${st.attempts} of 5 attempts used">
        ${[1,2,3,4,5].map((i)=>`<span class="adot ${i<=st.attempts?'used':''}"></span>`).join('')}
      </div>
    </div>`));

  card.append(el('div','qsec',`<h4>Scenario</h4><p>${esc(q.scenario)}</p>`));
  card.append(el('div','qsec task',`<h4>Task</h4><p>${esc(q.task)}</p>`));

  const meta = el('div','grid g2');
  meta.append(el('div','qsec',`<h4>Tables involved</h4><div class="chips">${(q.tables||[]).map((t)=>`<span class="chip acc">${esc(t)}</span>`).join('')}</div>`));
  if (!examMode) meta.append(el('div','qsec',`<h4>Expected result</h4><p class="muted" style="font-size:12.5px">${esc(q.expected||'')}</p>`));
  card.append(meta);

  if (q.orderMatters || q.checkColumnNames) {
    const notes = [];
    if (q.orderMatters) notes.push('row order is checked — include an ORDER BY');
    if (q.checkColumnNames) notes.push('column names are checked — alias them exactly as the task says');
    card.append(el('div','msg warn',`<p><b>Grading notes:</b> ${notes.join(' · ')}.</p>`));
  }

  // editor
  const ed = el('div','ed-wrap');
  ed.innerHTML = `<div class="ed-bar"><span>PostgreSQL · read-only</span>
    <span><span class="kbd">Ctrl</span>+<span class="kbd">Enter</span> run &nbsp;
          <span class="kbd">Ctrl</span>+<span class="kbd">↵</span>+<span class="kbd">Shift</span> submit &nbsp;
          <span class="kbd">Ctrl</span>+<span class="kbd">Space</span> complete</span></div>`;
  const ta = el('textarea');
  ta.value = opts.initial || q.starter || '';
  ed.append(ta);
  card.append(ed);

  const bar = el('div','btn-row'); bar.style.marginTop = '12px';
  const bRun    = el('button','btn','Run query');
  const bSubmit = el('button','btn primary','Submit answer');
  const bHint   = el('button','btn','Hint');
  const bReset  = el('button','btn ghost','Reset');
  const bClear  = el('button','btn ghost','Clear');
  bar.append(bRun, bSubmit);
  if (!examMode) bar.append(bHint);
  bar.append(bReset, bClear);
  if (!examMode) {
    const spacer = el('span'); spacer.style.flex = '1'; bar.append(spacer);
    const bSol = el('button','btn ghost sm','Show solution');
    bSol.disabled = !(st.attempts >= 5 || st.solved || st.revealed);
    bSol.title = bSol.disabled ? 'Unlocks after 5 failed attempts, or once solved' : '';
    bSol.onclick = () => { S.revealed = true; revealSolution(out, q); };
    bar.append(bSol);
  }
  card.append(bar);

  const out = el('div','res');
  card.append(out);
  root.append(card);

  const cm = CodeMirror.fromTextArea(ta, {
    mode:'text/x-pgsql', lineNumbers:true, matchBrackets:true, autoCloseBrackets:true,
    styleActiveLine:true, indentUnit:2, tabSize:2, lineWrapping:true,
    placeholder:'-- Write your PostgreSQL query here.\n-- Remember: identifiers are case-sensitive, so "VideoSources" needs the quotes.',
    extraKeys: {
      'Ctrl-Enter':      () => doRun(),
      'Cmd-Enter':       () => doRun(),
      'Shift-Ctrl-Enter':() => doSubmit(),
      'Shift-Cmd-Enter': () => doSubmit(),
      'Ctrl-Space':      'autocomplete',
      'Ctrl-/':          'toggleComment',
      'Cmd-/':           'toggleComment',
    },
    hintOptions: { tables: AUTOCOMPLETE },
  });
  S.editor = cm;
  setTimeout(() => cm.refresh(), 30);

  bRun.onclick = doRun;
  bSubmit.onclick = doSubmit;
  bReset.onclick = () => cm.setValue(q.starter || '');
  bClear.onclick = () => { cm.setValue(''); out.innerHTML = ''; };
  bHint.onclick = () => {
    if (S.hintsShown >= (q.hints||[]).length) return;
    S.hintsShown++;
    recordHint(S.progress, q);
    showHints(out, q, S.hintsShown, 'You asked for a hint');
    bHint.textContent = S.hintsShown >= q.hints.length ? 'No more hints' : `Hint (${S.hintsShown}/${q.hints.length})`;
    bHint.disabled = S.hintsShown >= q.hints.length;
  };

  async function doRun() {
    out.innerHTML = '';
    const sql = cm.getValue().trim();
    const r = await runUserQuery(sql);
    S.lastResult = r;
    if (!r.ok) return showError(out, r);
    out.append(resultTable(r, 'Result preview — this does not submit your answer'));
  }

  async function doSubmit() {
    out.innerHTML = '';
    const sql = cm.getValue().trim();
    const r = await runUserQuery(sql);
    S.lastResult = r;
    if (!r.ok) { showError(out, r); return; }

    let expected;
    try { expected = await runReference(q.solution); }
    catch (e) { out.append(el('div','msg err',`<h5>Reference query failed</h5><p>${esc(e.message)}</p>`)); return; }

    const verdict = grade(r, expected, { orderMatters:q.orderMatters, checkColumnNames:q.checkColumnNames });
    const s = recordAttempt(S.progress, q, verdict.correct, false);

    if (examMode) {
      opts.onExamAnswer?.(q, verdict.correct, sql);
      out.append(el('div','msg ok','<h5>Answer recorded</h5><p>Marking is shown at the end of the exam.</p>'));
      out.append(resultTable(r, 'Your result'));
      return;
    }

    if (verdict.correct) {
      out.append(el('div','msg ok',
        `<h5>✓ Correct${s.firstTry ? ' — first attempt' : ''}</h5>
         <p>${r.rows.length} row${r.rows.length===1?'':'s'} in ${r.ms} ms. ${
           s.firstTry ? 'No hints, no retries.' : `Solved after ${s.attempts} attempt${s.attempts===1?'':'s'}.`}</p>`));
      out.append(resultTable(r, 'Your result'));
      const rb = el('div','btn-row'); rb.style.marginTop = '12px';
      const bx = el('button','btn sm','Show the full explanation');
      bx.onclick = () => revealSolution(out, q, true);
      rb.append(bx);
      const bn = el('button','btn good sm','Next question →');
      bn.onclick = nextQuestion;
      rb.append(bn);
      out.append(rb);
      refreshSidebar();
      return;
    }

    // wrong
    const attempts = s.attempts;
    out.append(el('div','msg err',
      `<h5>✗ Not correct — attempt ${attempts} of 5</h5>
       <p>${esc(verdict.message)}</p>${verdict.detail?`<p>${esc(verdict.detail)}</p>`:''}`));
    out.append(resultTable(r, 'What your query returned'));

    if (attempts >= 5) {
      S.revealed = true;
      recordAttempt(S.progress, q, false, true);
      revealSolution(out, q);
    } else {
      const idx = Math.min(attempts, q.hints.length);
      showHints(out, q, idx, `Hint ${idx} of ${q.hints.length}`);
      out.append(el('p','muted',
        `<span style="font-size:12px">Solution unlocks after attempt 5. ${5-attempts} attempt${5-attempts===1?'':'s'} left.</span>`));
    }
    refreshSidebar();
  }

  function nextQuestion() {
    const list = visibleQuestions();
    const i = list.findIndex((x) => x.id === q.id);
    const next = list.slice(i+1).find((x) => !S.progress.questions[x.id]?.solved) ||
                 list.find((x) => !S.progress.questions[x.id]?.solved);
    if (next) openQuestion(next.id);
    else { S.view='dashboard'; [...$('#tabs').children].forEach((t)=>t.classList.toggle('active',t.dataset.view==='dashboard')); render(); }
  }

  if (st.attempts >= 5 || st.revealed) { S.revealed = true; revealSolution(out, q); }
  return cm;
}

function refreshSidebar() {
  if (S.view !== 'practice') return;
  document.querySelectorAll('.qitem').forEach((it) => {
    const id = it.querySelector('.id')?.textContent.split(' · ')[0];
    const s = S.progress.questions[id];
    if (!s) return;
    const m = it.querySelector('.st');
    if (s.solved) { m.className = 'st st-solved'; m.textContent = '✓'; }
    else if (s.revealed) { m.className = 'st st-rev'; m.textContent = '!'; }
    else if (s.attempts) { m.className = 'st st-try'; m.textContent = '·'; }
  });
}

function showHints(out, q, upto, label) {
  out.querySelectorAll('.hint').forEach((n) => n.remove());
  for (let i = 0; i < upto; i++) {
    out.append(el('div','hint',
      `<b>${i === upto-1 ? esc(label) : `Hint ${i+1}`}</b>${esc(q.hints[i])}`));
  }
}

function showError(out, r) {
  if (r.blocked) {
    out.append(el('div','msg blocked',
      `<h5>Blocked before execution — ${esc(r.code)}</h5>
       <p>${esc(r.error)}</p>${r.hint?`<p>${esc(r.hint)}</p>`:''}
       <p style="margin-top:8px;opacity:.75">This lab is read-only. Even if this check were removed, the
          PostgreSQL session itself runs with <code>default_transaction_read_only = on</code>.</p>`));
  } else {
    out.append(el('div','msg err',`<h5>PostgreSQL error</h5><p><code>${esc(r.error)}</code></p>`));
  }
}

function resultTable(r, caption) {
  const box = el('div');
  box.append(el('div','res-bar',
    `<span>${esc(caption)}</span><span>${r.rows.length} row${r.rows.length===1?'':'s'} · ${r.fields.length} column${r.fields.length===1?'':'s'} · ${r.ms} ms</span>`));
  if (!r.rows.length) { box.append(el('div','card empty','Query ran successfully and returned no rows.')); return box; }
  const sc = el('div','tbl-scroll');
  const t = el('table');
  t.innerHTML = `<thead><tr>${r.fields.map((f)=>`<th>${esc(f)}</th>`).join('')}</tr></thead>`;
  const tb = el('tbody');
  for (const row of r.rows.slice(0, 300)) {
    tb.append(el('tr', null, r.fields.map((f) => {
      const v = row[f];
      if (v === null || v === undefined) return '<td><span class="nullv">NULL</span></td>';
      if (typeof v === 'object') return `<td>${esc(JSON.stringify(v))}</td>`;
      return `<td>${esc(v)}</td>`;
    }).join('')));
  }
  t.append(tb);
  sc.append(t);
  box.append(sc);
  if (r.rows.length > 300) box.append(el('p','muted',`<span style="font-size:12px">Showing first 300 of ${r.rows.length} rows.</span>`));
  return box;
}

function revealSolution(out, q, solved = false) {
  if (out.querySelector('.sol')) return;
  const e = q.explanation || {};
  const blocks = [
    ['Query breakdown', e.breakdown],
    ['Why this approach', e.why],
    ['Common mistake', e.commonMistake],
    ['Alternative', e.alternative],
    ['Performance', e.performance],
    ['QA relevance', e.qaRelevance],
  ].filter(([,v]) => v);

  const sol = el('div','sol');
  sol.append(el('div','sol-head', solved ? 'Full explanation' : 'Solution revealed — marked "Needs revision"'));
  const body = el('div','sol-body');
  body.append(el('pre',null, esc(q.solution)));
  const cp = el('button','btn sm','Copy into the editor');
  cp.onclick = () => S.editor?.setValue(q.solution);
  body.append(cp);
  for (const [h,v] of blocks) body.append(el('div','exp-block',`<h5>${h}</h5><p>${esc(v)}</p>`));
  sol.append(body);
  out.append(sol);
}

/* ===================== exam ===================== */

function viewExam(root) {
  if (!S.exam) return examIntro(root);
  if (S.exam.finished) return examReport(root);
  return examRunner(root);
}

function examIntro(root) {
  root.append(el('div','view-head',`
    <h1>Exam mode</h1>
    <p>Ten questions drawn across the levels. No hints, no solutions, no feedback until you
       submit. You get a score with a per-skill breakdown at the end.</p>`));

  const c = el('div','card');
  c.style.maxWidth = '620px';
  c.innerHTML = `<h3 style="margin:0 0 12px;font-size:15px">Set up your assessment</h3>`;

  const row = el('div','btn-row'); row.style.marginBottom = '14px';
  const diff = el('select');
  diff.innerHTML = `<option value="mixed">Mixed (levels 1-8)</option>
    <option value="foundation">Foundation (levels 1-3)</option>
    <option value="advanced">Advanced (levels 5-8)</option>`;
  const timed = el('select');
  timed.innerHTML = `<option value="0">No time limit</option>
    <option value="30">30 minutes</option><option value="45">45 minutes</option><option value="60">60 minutes</option>`;
  row.append(el('span','muted','Scope'), diff, el('span','muted','Timer'), timed);
  c.append(row);

  const go = el('button','btn primary','Start the exam');
  go.onclick = () => {
    const ranges = { mixed:[1,8], foundation:[1,3], advanced:[5,8] };
    const [lo,hi] = ranges[diff.value];
    const pool = S.bank.filter((q) => q.level >= lo && q.level <= hi);
    const picked = [];
    const byLevel = {};
    for (const q of pool) (byLevel[q.level] ||= []).push(q);
    const levels = Object.keys(byLevel).map(Number).sort();
    // spread across levels, then top up randomly
    let li = 0;
    while (picked.length < 10 && levels.length) {
      const lvl = levels[li % levels.length];
      const arr = byLevel[lvl].filter((q) => !picked.includes(q));
      if (arr.length) picked.push(arr[Math.floor(Math.random()*arr.length)]);
      li++;
      if (li > 200) break;
    }
    S.exam = {
      questions: picked.slice(0,10), i:0, answers:{},
      minutes:Number(timed.value), started:Date.now(), finished:false,
    };
    render();
  };
  c.append(go);
  root.append(c);
}

function examRunner(root) {
  const ex = S.exam;
  const q = ex.questions[ex.i];

  const head = el('div','view-head');
  head.innerHTML = `<h1>Exam · question ${ex.i+1} of ${ex.questions.length}</h1>`;
  const bar = el('div','btn-row');
  bar.style.margin = '8px 0 4px';
  const answered = Object.keys(ex.answers).length;
  bar.append(el('span','muted',`${answered} answered`));
  if (ex.minutes) {
    const t = el('span','exam-timer'); t.id = 'examTimer'; bar.append(t);
    startTimer();
  }
  const sp = el('span'); sp.style.flex='1'; bar.append(sp);
  const prev = el('button','btn sm','← Previous'); prev.disabled = ex.i===0;
  prev.onclick = () => { ex.i--; render(); };
  const next = el('button','btn sm','Next →'); next.disabled = ex.i>=ex.questions.length-1;
  next.onclick = () => { ex.i++; render(); };
  const fin = el('button','btn primary sm','Finish & score');
  fin.onclick = () => {
    if (answered < ex.questions.length && !confirm(`${ex.questions.length-answered} question(s) unanswered. Finish anyway?`)) return;
    ex.finished = true; render();
  };
  bar.append(prev, next, fin);
  head.append(bar);
  root.append(head);

  const pane = el('div');
  root.append(pane);
  renderQuestion(pane, q, {
    exam: true,
    initial: ex.answers[q.id]?.sql || '',
    onExamAnswer: (qq, correct, sql) => { ex.answers[qq.id] = { correct, sql }; },
  });

  function startTimer() {
    clearInterval(S.examTick);
    S.examTick = setInterval(() => {
      const left = ex.minutes*60000 - (Date.now()-ex.started);
      const n = document.getElementById('examTimer');
      if (!n) return clearInterval(S.examTick);
      if (left <= 0) { clearInterval(S.examTick); ex.finished = true; render(); return; }
      const m = Math.floor(left/60000), s = Math.floor(left%60000/1000);
      n.textContent = `${m}:${String(s).padStart(2,'0')}`;
    }, 500);
  }
}

function examReport(root) {
  clearInterval(S.examTick);
  const ex = S.exam;
  const total = ex.questions.length;
  const right = ex.questions.filter((q) => ex.answers[q.id]?.correct).length;
  const pct = Math.round(100*right/total);
  const band = pct>=90?'Advanced':pct>=75?'Upper intermediate':pct>=55?'Intermediate':pct>=35?'Developing':'Foundation';

  root.append(el('div','view-head',`<h1>Assessment result</h1><p>Scored across ${total} questions.</p>`));

  const top = el('div','grid g4'); top.style.marginBottom='14px';
  top.innerHTML = `
    <div class="stat ${pct>=75?'ok':pct>=50?'warn':'bad'}"><div class="v">${pct}%</div><div class="k">Score</div></div>
    <div class="stat"><div class="v">${right}/${total}</div><div class="k">Correct</div></div>
    <div class="stat"><div class="v" style="font-size:17px">${band}</div><div class="k">Overall level</div></div>
    <div class="stat"><div class="v">${Math.round((Date.now()-ex.started)/60000)}m</div><div class="k">Time taken</div></div>`;
  root.append(top);

  // per-skill
  const bySkill = {};
  for (const q of ex.questions) {
    const ok = !!ex.answers[q.id]?.correct;
    for (const s of q.skills||[]) { bySkill[s] ||= {n:0,ok:0}; bySkill[s].n++; if (ok) bySkill[s].ok++; }
  }
  const cols = el('div','grid g2');

  const sk = el('div','card');
  sk.innerHTML = '<h3 style="margin:0 0 10px;font-size:14px">By skill</h3>';
  Object.entries(bySkill).sort((a,b)=>(a[1].ok/a[1].n)-(b[1].ok/b[1].n)).forEach(([name,v]) => {
    const p = Math.round(100*v.ok/v.n);
    sk.append(el('div','lvl-row',`
      <div class="lvl-name"><b>${esc(name)}</b><span>${v.ok} of ${v.n}</span></div>
      <div class="lvl-bar"><div class="bar ${p===100?'ok':''}"><i style="width:${p}%"></i></div></div>
      <div class="lvl-num">${p}%</div>`));
  });
  cols.append(sk);

  const rev = el('div','card');
  rev.innerHTML = '<h3 style="margin:0 0 10px;font-size:14px">Question review</h3>';
  for (const q of ex.questions) {
    const ok = !!ex.answers[q.id]?.correct;
    const r = el('div','lvl-row');
    r.innerHTML = `<div class="lvl-name"><b>${ok?'✓':'✗'} ${esc(q.title)}</b><span>${q.id} · Level ${q.level}</span></div>`;
    const b = el('button','btn sm', ok ? 'Review' : 'Practise this');
    b.style.marginLeft='auto';
    b.onclick = () => { S.exam=null; openQuestion(q.id); };
    r.append(b);
    rev.append(r);
  }
  cols.append(rev);
  root.append(cols);

  const weak = Object.entries(bySkill).filter(([,v])=>v.ok/v.n<0.6).map(([k])=>k);
  const foot = el('div','card'); foot.style.marginTop='14px';
  foot.innerHTML = `<h3 style="margin:0 0 6px;font-size:14px">Recommendation</h3>
    <p style="margin:0;color:var(--fg2)">${
      weak.length ? `Focus your next sessions on: <b>${weak.map(esc).join(', ')}</b>. In Practice, set the level filter to “Weak topics only”.`
                  : 'No weak areas showed up in this sample. Try the Advanced scope, or move on to the Senior QA investigations.'}</p>`;
  const rb = el('div','btn-row'); rb.style.marginTop='12px';
  const again = el('button','btn primary','New exam');
  again.onclick = () => { S.exam=null; render(); };
  rb.append(again);
  foot.append(rb);
  root.append(foot);
}

/* ===================== senior challenges ===================== */

function viewSenior(root) {
  if (S.challenge) return renderChallenge(root, S.challenge);

  root.append(el('div','view-head',`
    <h1>Senior QA investigations</h1>
    <p>Six production situations. Each is a chain of queries: confirm the symptom, attribute it,
       distinguish between candidate causes, then quantify the impact. Steps unlock in order.</p>`));

  const g = el('div','grid g2');
  for (const c of S.challenges) {
    const done = c.steps.filter((s) => S.progress.questions[s.id]?.solved).length;
    const card = el('div','chal',`
      <h3>${esc(c.title)}</h3>
      <p>${esc(c.brief)}</p>
      <div class="steps">${c.steps.map((s,i)=>`<div class="sdot ${S.progress.questions[s.id]?.solved?'done':''}"></div>`).join('')}</div>
      <div class="muted" style="font-size:11.5px;margin-top:7px">${done} of ${c.steps.length} steps complete</div>`);
    card.onclick = () => {
      S.challenge = c;
      S.challengeStep = Math.min(done, c.steps.length-1);
      S.current = c.steps[S.challengeStep];
      S.hintsShown = 0; S.revealed = false;
      render();
    };
    g.append(card);
  }
  root.append(g);
}

function renderChallenge(root, c) {
  const head = el('div','view-head');
  head.innerHTML = `<h1>${esc(c.title)}</h1><p>${esc(c.brief)}</p>`;
  const back = el('button','btn sm ghost','← All investigations');
  back.style.marginTop='10px';
  back.onclick = () => { S.challenge = null; render(); };
  head.append(back);
  root.append(head);

  const nav = el('div','step-nav');
  c.steps.forEach((s, i) => {
    const solved = !!S.progress.questions[s.id]?.solved;
    const prevSolved = i === 0 || !!S.progress.questions[c.steps[i-1].id]?.solved ||
                       !!S.progress.questions[c.steps[i-1].id]?.revealed;
    const b = el('button', 'step-btn' + (i===S.challengeStep?' active':'') + (solved?' done':''),
                 `${solved?'✓ ':''}Step ${i+1} · ${esc(s.title)}`);
    b.disabled = !prevSolved;
    if (!prevSolved) b.title = 'Solve the previous step first';
    b.onclick = () => { S.challengeStep = i; S.current = s; S.hintsShown=0; S.revealed=false; render(); };
    nav.append(b);
  });
  root.append(nav);

  const pane = el('div'); pane.id = 'spane';
  root.append(pane);
  renderQuestion(pane, c.steps[S.challengeStep]);

  const done = c.steps.every((s) => S.progress.questions[s.id]?.solved);
  if (done) {
    root.append(el('div','msg ok',
      `<h5>Investigation complete</h5>
       <p>You have worked this from symptom to root cause. In a real incident the write-up
          would now record: what changed, what you ruled out, the measured impact, and the
          standing query that detects a recurrence.</p>`));
  }
}

/* ===================== schema ===================== */

function viewSchema(root) {
  root.append(el('div','view-head',`
    <h1>Schema reference</h1>
    <p>The Analytics Manager schema as the practice database implements it: 19 tables,
       24 enforced foreign keys, and six relationships the database does <em>not</em> enforce.</p>`));

  root.append(el('div','card',`
    <h3 style="margin:0 0 10px;font-size:14px">Relationship map</h3>
    <div class="diagram">${esc(DIAGRAM)}</div>`));

  const gapsCard = el('div','card');
  gapsCard.style.marginTop = '14px';
  gapsCard.innerHTML = `<h3 style="margin:0 0 4px;font-size:14px">The six unenforced relationships</h3>
    <p class="muted" style="font-size:12.5px;margin:0 0 12px">These are in the production DDL, not invented for this exercise.
       They are why orphan and inconsistent rows exist, and they are the subject of most of the QA questions here.</p>`;
  const gg = el('div','grid g2');
  for (const g of GAPS) {
    gg.append(el('div','gapcard',
      `<h4>Gap ${g.id} · <code>${esc(g.where)}</code></h4>
       <p><b>${esc(g.what)}</b></p><p>${esc(g.why)}</p>`));
  }
  gapsCard.append(gg);
  root.append(gapsCard);

  const enums = el('div','card'); enums.style.marginTop='14px';
  enums.innerHTML = `<h3 style="margin:0 0 10px;font-size:14px">Integer enum decoding</h3>`;
  const et = el('div','grid g3');
  for (const [k,v] of Object.entries(ENUMS)) {
    et.append(el('div', null,
      `<div style="font-family:var(--mono);font-size:12px;color:var(--accent);margin-bottom:4px">${esc(k)}</div>
       <div class="chips">${Object.entries(v).map(([n,l])=>`<span class="chip">${n} = ${esc(l)}</span>`).join('')}</div>`));
  }
  enums.append(et);
  root.append(enums);

  const filt = el('div','btn-row'); filt.style.margin='18px 0 12px';
  filt.append(el('span','muted','Filter tables:'));
  const groups = ['all', ...Object.keys(GROUPS)];
  let active = 'all';
  const tablesWrap = el('div','grid g3');
  const paint = () => {
    tablesWrap.innerHTML = '';
    for (const t of TABLES) {
      if (active !== 'all' && t.group !== active) continue;
      const box = el('div','tbox');
      box.append(el('div','tbox-h',
        `<span>${esc(t.name)}</span><span class="chip" style="border-color:${GROUPS[t.group].color}44;color:${GROUPS[t.group].color}">${GROUPS[t.group].label}</span>`));
      if (t.note) box.append(el('div','tbox-n', esc(t.note)));
      const tb = el('table');
      tb.innerHTML = '<tbody>' + t.cols.map(([n,ty,fl]) =>
        `<tr><td>${esc(n)}</td><td>${esc(ty)}</td><td class="${/⚠/.test(fl)?'gap-warn':''}">${esc(fl)}</td></tr>`).join('') + '</tbody>';
      box.append(tb);
      tablesWrap.append(box);
    }
  };
  for (const g of groups) {
    const b = el('button','btn sm' + (g==='all'?' primary':''), g==='all'?'All':GROUPS[g].label);
    b.onclick = () => {
      active = g;
      [...filt.querySelectorAll('.btn')].forEach((x)=>x.classList.remove('primary'));
      b.classList.add('primary');
      paint();
    };
    filt.append(b);
  }
  root.append(filt);
  paint();
  root.append(tablesWrap);
}

const DIAGRAM = `
                        AnalyticManagers            deployment root
                        Id · Name · ManagerIp:Port · IsAnlayticManagerConnected
                               |
        +----------------------+----------------------+--------------------+
   FK   |  CASCADE        FK   |  CASCADE       NO FK  |  (gap 4)           |
        v                      v                       v                    |
   VideoSources             Events              AnalyticServers ---+ FK self|
   the camera fleet         the payload         Ip · RestPort      |  (failover)
        |                   Time / ReceivedTime  IsFailoverOnly <---+        |
        |                   are epoch MILLIS            |                    |
        |                   VideoSourceId  >>> NO FK (gap 1) <<<             |
        |                                               | FK CASCADE         |
        |                                               v                    |
        |                                          PipeLines ---FK---> PipeLineConfigs
        |                                          MaxVideoSourceAllowed
        |                                          (enforced nowhere)
        |                                               |
        +--------------------+--------------------------+
                             |  N:M
                             v
                    PipeLineVideoSources        intended assignment
                             vs
                  AnalyticServerDeviceMapping   actual placement
                    (these two drift apart)

   ExternalSources ---FK---> VideoSources ---FK---> VideoSourceConfigs
   LastSynced, ServerState        |                 AppliedRules text[]
                                  |                 ScheduleId >>> no such table (gap 3)
                                  |
                                  +--FK--> VideoSourceStreamMappings
                                  |        UNIQUE(VideoSourceId, StreamType)
                                  |        UseStreamType must match a row here
                                  |
                          activeConfigId  >>> NOT NULL, NO FK (gap 2) <<<

   AspNetRoles <--FK-- AspNetUsers."RoleId"        two sources of truth
        ^                    |                     for one user's role
        |                    +--FK--> UserVideoSources ---> VideoSources
        +--FK-- AspNetUserRoles (UserId, RoleId)   >>> gap 5 <<<

   Standalone:  SystemConfig (RecognitionConfidence = 0.5) · EmailServer · SmsGateway
`.trim();

boot();
