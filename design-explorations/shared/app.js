/* Shared behavior for all three concepts: routing, pages, interactions.
   Each concept provides window.CONCEPT = { dashboard(d, s, h) } and its own shell + CSS. */
(function () {
  const M = window.MOCK, S = window.Store;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (t) => String(t == null ? '' : t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = (t) => String(t).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

  const ROUTES = [
    ['dashboard', 'Dashboard'], ['study', 'Study'], ['assessments', 'Assessments'],
    ['vocabulary', 'Vocabulary'], ['challenges', 'Challenges'], ['progress', 'Progress'], ['settings', 'Settings'],
  ];
  const NAV_ICONS = {
    dashboard: '<path d="M3 11.5 12 4l9 7.5M5.5 10v10h13V10"/>',
    study: '<path d="M12 6c-2-1.5-5-2-8-1.5v13c3-.5 6 0 8 1.5 2-1.5 5-2 8-1.5v-13C17 4 14 4.5 12 6ZM12 6v13"/>',
    assessments: '<path d="M5 4h14v16H5zM8.5 9h7M8.5 13h7M8.5 17h4"/>',
    vocabulary: '<path d="m12 3 9 4.5-9 4.5-9-4.5ZM3 12l9 4.5 9-4.5M3 16.5 12 21l9-4.5"/>',
    challenges: '<path d="M8 4h8v5a4 4 0 0 1-8 0ZM8 6H4.5c0 3 1.2 4.5 3.5 5M16 6h3.5c0 3-1.2 4.5-3.5 5M12 13v4M8.5 20h7"/>',
    progress: '<path d="M5 20V11M10 20V6M15 20v-7M20 20V9"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8"/>',
  };
  const icon = (k) => `<svg class="ico" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${NAV_ICONS[k]}</svg>`;

  /* ---------- helpers handed to concepts ---------- */
  const bar = (ratio, from) => `<span class="bar"><span class="fill" data-to="${Math.max(0, Math.min(1, ratio))}" ${from != null ? `data-from="${from}"` : ''}></span></span>`;
  const pct = (r) => Math.round(r * 100);
  const helpers = { esc, bar, pct, icon };

  function dateLine() {
    return new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  }
  function dayDetail(d) {
    if (d.isFuture) return `${d.label}: not yet`;
    const parts = [];
    if (d.sessions) parts.push(`${d.sessions} ${d.sessions === 1 ? 'session' : 'sessions'}`);
    if (d.assessments) parts.push(`${d.assessments} ${d.assessments === 1 ? 'assessment' : 'assessments'}`);
    if (!parts.length) return `${d.label}: no study logged${d.isToday ? ' yet' : ''}`;
    return `${d.label}: ${parts.join(', ')}${d.minutes ? `, ${d.minutes} min` : ''}, ${d.xp} XP`;
  }
  helpers.dayDetail = dayDetail;
  helpers.dateLine = dateLine;
  helpers.skillText = (k) => (k.ratio == null ? 'Not yet assessed' : `${k.hits} of ${k.assessed} recalled`);
  helpers.streakNote = (st) => st.current === 0
    ? 'Log a study session to start a streak.'
    : st.activeToday ? 'Done for today.' : 'Log a session today to keep it going.';

  /* ---------- routing ---------- */
  function parseHash() {
    const raw = (location.hash || '#/dashboard').replace(/^#\/?/, '');
    const [name, arg] = raw.split('/');
    return { name: ROUTES.some((r) => r[0] === name) ? name : 'dashboard', arg };
  }

  /* ---------- page: study ---------- */
  let studyMode = 'self';
  let draft = null;
  function pageStudy() {
    const d = draft || { activity: M.activityTypes[0], minutes: '', context: '', terms: ['', '', ''], sentences: ['', ''] };
    const guided = studyMode === 'guided';
    const rows = (arr, name, label, max, ph) => arr.map((v, i) => `
      <div class="field"><label for="${name}-${i}">${label} ${i + 1}</label>
      <input id="${name}-${i}" data-${name}="${i}" value="${esc(v)}" placeholder="${ph}" autocomplete="off"></div>`).join('');
    return `
    <header class="page-head"><h1>Log a study session</h1>
      <p class="lede">Record what you studied. The backend, not the model, decides your XP.</p></header>
    <div class="seg" role="tablist" aria-label="Study mode">
      <button role="tab" aria-selected="${!guided}" data-mode="self">Self-Study</button>
      <button role="tab" aria-selected="${guided}" data-mode="guided">Guided Study</button>
    </div>
    <p class="note">${guided
      ? 'Guided Study suggests a focus. In Level 1 it uses the same log form; there is no automated curriculum yet.'
      : 'Self-Study: log anything you studied on your own, from a show to a textbook page.'}</p>
    <form id="study-form" class="form" novalidate>
      ${guided ? `<div class="field"><label for="focus">Suggested focus</label>
        <select id="focus">${M.guidedFocus.map((f) => `<option>${esc(f)}</option>`).join('')}</select></div>` : ''}
      <div class="row2">
        <div class="field"><label for="activity">Activity type</label>
          <select id="activity">${M.activityTypes.map((a) => `<option ${a === d.activity ? 'selected' : ''}>${esc(a)}</option>`).join('')}</select></div>
        <div class="field"><label for="minutes">Duration (minutes)</label>
          <input id="minutes" type="number" min="5" max="180" inputmode="numeric" value="${esc(d.minutes)}" placeholder="30"></div>
      </div>
      <div class="field"><label for="context">Context</label>
        <textarea id="context" rows="2" placeholder="What were you studying? e.g. La Casa de Papel, season 2, episode 4">${esc(d.context)}</textarea></div>
      <fieldset class="group"><legend>Words and phrases (3 to 5)</legend>
        <div id="terms">${rows(d.terms, 'term', 'Word or phrase', 5, 'e.g. quedarse')}</div>
        ${d.terms.length < 5 ? '<button type="button" class="btn ghost" data-add="term">Add another</button>' : ''}</fieldset>
      <fieldset class="group"><legend>Your own sentences (2 to 3)</legend>
        <div id="sentences">${rows(d.sentences, 'sentence', 'Sentence', 3, 'Write it in Spanish')}</div>
        ${d.sentences.length < 3 ? '<button type="button" class="btn ghost" data-add="sentence">Add another</button>' : ''}</fieldset>
      <p class="error" id="form-error" role="alert" hidden></p>
      <div class="actions"><button class="btn primary" type="submit">Save session</button>
        <span class="hint">Earns about ${M.rules.base}+ XP, scaled by duration and streak.</span></div>
    </form>`;
  }
  function readDraft() {
    const f = $('#study-form'); if (!f) return;
    draft = {
      activity: $('#activity').value, minutes: $('#minutes').value, context: $('#context').value,
      terms: $$('[data-term]').map((i) => i.value), sentences: $$('[data-sentence]').map((i) => i.value),
    };
  }
  function submitStudy(e) {
    e.preventDefault(); readDraft();
    const err = $('#form-error'); const problems = [];
    const mins = parseInt(draft.minutes, 10);
    if (!(mins >= 5 && mins <= 180)) problems.push('Duration must be between 5 and 180 minutes.');
    if (!draft.context.trim()) problems.push('Add a line of context.');
    const terms = draft.terms.map((t) => t.trim()).filter(Boolean);
    const sentences = draft.sentences.map((t) => t.trim()).filter(Boolean);
    if (terms.length < 3) problems.push('Enter at least 3 words or phrases.');
    if (sentences.length < 2) problems.push('Write at least 2 sentences.');
    if (problems.length) { err.hidden = false; err.textContent = problems.join(' '); err.focus && err.setAttribute('tabindex', '-1'); err.focus(); return; }
    const gain = S.logSession({ mode: studyMode, activity: draft.activity, minutes: mins, context: draft.context.trim(), terms, sentences });
    draft = null;
    announceGain(gain);
    location.hash = '#/dashboard';
  }

  /* ---------- page: assessments ---------- */
  let quiz = { phase: 'intro', qs: [], answers: {}, results: [] };
  function buildQuiz(s) {
    const pool = s.vocab.filter((v) => v.example && v.exampleEn && v.en !== 'Meaning not added yet');
    const ordered = pool.filter((v) => v.status !== 'recalled').concat(pool.filter((v) => v.status === 'recalled'));
    const w = ordered.slice(0, 4);
    if (w.length < 3) return [];
    const others = (key, skip) => pool.filter((v) => v.id !== skip).map((v) => v[key]);
    const opts = (right, key, skip) => { const o = others(key, skip).slice(0, 2).concat(right); return o.sort((a, b) => norm(a).localeCompare(norm(b))); };
    const qs = [
      { id: 'q1', type: 'choice', modality: 'reading', prompt: `What does “${w[0].es}” mean?`, options: opts(w[0].en, 'en', w[0].id), answer: w[0].en, explain: `${w[0].es}: ${w[0].en}. Example: ${w[0].example}` },
      { id: 'q2', type: 'choice', modality: 'reading', prompt: `Which English sentence matches: “${w[1].example}”`, options: opts(w[1].exampleEn, 'exampleEn', w[1].id), answer: w[1].exampleEn, explain: `“${w[1].example}” means “${w[1].exampleEn}”.` },
      { id: 'q3', type: 'text', modality: 'writing', prompt: `Write one Spanish sentence using “${w[2].es}”.`, target: w[2].es, model: w[2].example },
    ];
    if (w[3]) qs.push({ id: 'q4', type: 'text', modality: 'writing', prompt: `Translate into Spanish: “${w[3].exampleEn}”`, target: w[3].es, model: w[3].example });
    return qs;
  }
  function gradeText(q, ans) {
    const a = norm(ans.trim()); const words = a.split(/\s+/).filter(Boolean);
    const head = norm(q.target).split(/\s+/)[0];
    const stem = head.length > 5 ? head.slice(0, head.length - 2) : head;
    const used = a.includes(stem);
    if (used && words.length >= 4) return { outcome: 'HIT', note: `You used “${q.target}” in a full sentence. Compare with: ${q.model}` };
    if (used || words.length >= 4) return { outcome: 'PARTIAL', note: used ? `You used “${q.target}”, but the sentence is very short. Try a full clause. Example: ${q.model}` : `A full sentence, but “${q.target}” does not appear. Example: ${q.model}` };
    return { outcome: 'MISS', note: `Try to include “${q.target}” in a sentence of at least four words. Example: ${q.model}` };
  }
  function pageAssess() {
    const s = S.get();
    const head = '<header class="page-head"><h1>Quick assessment</h1><p class="lede">Short questions built from words you have already logged.</p></header>';
    const sim = '<p class="sim" role="note"><strong>Simulated feedback.</strong> This prototype checks answers with simple rules. It is not a production evaluation; the real app grades with a local model and LanguageTool.</p>';
    if (quiz.phase === 'intro') {
      const qs = buildQuiz(s);
      if (!qs.length) return `${head}<div class="empty"><h2>Nothing to ask about yet</h2><p>An assessment is built only from your own study log. Log a session with a few words first.</p><a class="btn primary" href="#/study">Start studying</a></div>`;
      return `${head}${sim}<div class="panel"><h2>Ready when you are</h2>
        <p>${qs.length} questions from ${[...new Set(qs.map((q) => q.target || ''))].filter(Boolean).length ? 'your recent words' : 'your study log'}. Each correct answer earns ${M.rules.quizPerCorrect} XP, up to ${M.rules.dailyCapAssess} XP a day.</p>
        <button class="btn primary" data-quiz="start">Begin assessment</button></div>`;
    }
    if (quiz.phase === 'run') {
      return `${head}${sim}<form id="quiz-form" class="form" novalidate>${quiz.qs.map((q, i) => `
        <fieldset class="group q"><legend>${i + 1}. ${esc(q.prompt)}</legend>
        ${q.type === 'choice'
          ? q.options.map((o, j) => `<label class="opt"><input type="radio" name="${q.id}" value="${esc(o)}" ${quiz.answers[q.id] === o ? 'checked' : ''}> <span>${esc(o)}</span></label>`).join('')
          : `<input class="wide" name="${q.id}" value="${esc(quiz.answers[q.id] || '')}" placeholder="Escribe aquí" autocomplete="off" lang="es">`}
        </fieldset>`).join('')}
        <p class="error" id="quiz-error" role="alert" hidden></p>
        <div class="actions"><button class="btn primary" type="submit">Submit answers</button></div></form>`;
    }
    const total = quiz.results.length; const hits = quiz.results.filter((r) => r.outcome === 'HIT').length;
    const lg = s.lastGain;
    return `${head}${sim}<div class="panel result"><h2>${hits} of ${total} correct</h2>
      <p>${lg && lg.amount ? `+${lg.amount} XP earned.` : 'No XP this time (daily assessment cap reached or no correct answers).'} Each attempt pays once.</p></div>
      <ol class="feedback">${quiz.results.map((r) => `<li class="fb ${r.outcome.toLowerCase()}"><p class="fb-q">${esc(r.prompt)}</p>
        <p class="fb-a"><span class="tag">${r.outcome === 'HIT' ? 'Correct' : r.outcome === 'PARTIAL' ? 'Partly there' : 'Not quite'}</span> Your answer: ${esc(r.given || '(blank)')}</p>
        <p class="fb-n">${esc(r.note)}</p></li>`).join('')}</ol>
      <div class="actions"><button class="btn" data-quiz="again">Take another</button><a class="btn primary" href="#/dashboard">Back to dashboard</a></div>`;
  }
  function submitQuiz(e) {
    e.preventDefault();
    const f = $('#quiz-form'); const fd = new FormData(f);
    const results = []; let blank = 0;
    quiz.qs.forEach((q) => {
      const v = (fd.get(q.id) || '').toString(); quiz.answers[q.id] = v; if (!v.trim()) blank++;
      if (q.type === 'choice') results.push({ prompt: q.prompt, given: v, modality: q.modality, outcome: v === q.answer ? 'HIT' : 'MISS', note: q.explain });
      else { const g = gradeText(q, v); results.push({ prompt: q.prompt, given: v, modality: q.modality, ...g }); }
    });
    if (blank) { const er = $('#quiz-error'); er.hidden = false; er.textContent = `${blank} ${blank === 1 ? 'question is' : 'questions are'} unanswered. Answer all to submit.`; return; }
    quiz.results = results; quiz.phase = 'done';
    announceGain(S.logAssessment(results));
    render();
  }

  /* ---------- page: vocabulary ---------- */
  let vocabQuery = '', vocabSel = null;
  function pageVocab() {
    const s = S.get(); const q = norm(vocabQuery);
    const list = s.vocab.filter((v) => !q || norm(v.es).includes(q) || norm(v.en).includes(q));
    const sel = s.vocab.find((v) => v.id === vocabSel);
    const statusLabel = { new: 'New', seen: 'Seen', recalled: 'Recalled' };
    return `<header class="page-head"><h1>Vocabulary</h1><p class="lede">${s.vocab.length} words and phrases you have encountered.</p></header>
    <div class="split"><div>
      <div class="field search"><label for="vq">Search</label><input id="vq" type="search" value="${esc(vocabQuery)}" placeholder="Spanish or English" autocomplete="off"></div>
      ${list.length ? `<ul class="vlist">${list.map((v) => `<li><button class="vrow" data-vid="${v.id}" aria-pressed="${v.id === vocabSel}">
        <span class="v-es">${esc(v.es)}</span><span class="v-en">${esc(v.en)}</span><span class="v-st st-${v.status}">${statusLabel[v.status]}</span></button></li>`).join('')}</ul>`
        : `<div class="empty"><h2>No match</h2><p>Nothing in your collection matches “${esc(vocabQuery)}”.</p></div>`}
    </div>
    <aside class="detail" aria-live="polite">${sel ? `
      <h2 lang="es">${esc(sel.es)}</h2><p class="pos">${esc(sel.pos)}</p><p class="meaning">${esc(sel.en)}</p>
      ${sel.example ? `<blockquote lang="es">${esc(sel.example)}<footer>${esc(sel.exampleEn)}</footer></blockquote>` : ''}
      ${sel.note ? `<p class="note">${esc(sel.note)}</p>` : ''}
      <dl><dt>Your sentence</dt><dd lang="es">${esc(sel.learnerSentence || '—')}</dd><dt>First met in</dt><dd>${esc(sel.source)}</dd><dt>Times logged</dt><dd>${sel.seen}</dd></dl>`
      : '<p class="empty-note">Choose a word to see its meaning, an example and where you met it.</p>'}</aside></div>`;
  }

  /* ---------- page: challenges ---------- */
  function pageChallenges() {
    const d = S.derive();
    return `<header class="page-head"><h1>Challenges</h1><p class="lede">Boss conversations and timed tests are planned for a later level. This is a preview only.</p></header>
    <div class="locked-list">
      <article class="locked"><h2>El mercado</h2><p>A spoken haggling scene with a stallholder. Needs speaking assessment, which is not part of Level 1.</p><p class="lock">Locked · requires Learner I (you are ${esc(d.rank.name)})</p></article>
      <article class="locked"><h2>La estación</h2><p>Follow a station announcement and answer questions. Needs listening assessment.</p><p class="lock">Locked · listening is not yet assessed</p></article>
      <article class="locked"><h2>Una carta</h2><p>Write a short letter and have it reviewed against what you have logged.</p><p class="lock">Locked · planned after Level 1</p></article>
    </div>`;
  }

  /* ---------- page: progress ---------- */
  function pageProgress(arg) {
    const d = S.derive(), s = S.get();
    const events = [...s.sessions.map((x) => ({ date: x.date, label: `${x.mode === 'guided' ? 'Guided' : 'Self'} study, ${x.minutes} min`, detail: x.activity, xp: x.xp })),
      ...s.assessments.map((x) => ({ date: x.date, label: `Assessment, ${x.correct} of ${x.total}`, detail: 'Quick assessment', xp: x.xp }))]
      .sort((a, b) => b.date.localeCompare(a.date)).slice(0, 12);
    const info = { reading: 'Recognising meaning in sentences you have logged.', writing: 'Producing your own Spanish sentences.', listening: 'Level 1 has no listening assessment.', speaking: 'Level 1 has no speaking assessment.' };
    return `<header class="page-head"><h1>Progress</h1><p class="lede">${s.xp} XP in total. Skills are tracked separately; one never raises another.</p></header>
    <section aria-labelledby="p-skills"><h2 id="p-skills">Skills</h2><ul class="skill-detail">${d.skills.map((k) => `
      <li class="${arg === k.key ? 'focus' : ''}" id="skill-${k.key}"><div class="sd-top"><span class="sd-name">${k.label}</span><span class="sd-val">${helpers.skillText(k)}</span></div>
      ${k.ratio == null ? '' : bar(k.ratio)}<p class="sd-note">${info[k.key]}</p></li>`).join('')}</ul></section>
    <section aria-labelledby="p-ranks"><h2 id="p-ranks">Rank ladder</h2><ol class="ladder">${M.ranks.map((r, i) => `<li class="${i < d.rank.index ? 'done' : i === d.rank.index ? 'now' : ''}" ${i === d.rank.index ? 'aria-current="step"' : ''}><span>${r[1]}</span><span class="num">${r[0]} XP</span></li>`).join('')}</ol>
      <p class="note">An activity rank, not a proficiency claim. Thresholds are provisional.</p></section>
    <section aria-labelledby="p-hist"><h2 id="p-hist">Recent XP</h2>
      ${events.length ? `<table class="table"><thead><tr><th>Date</th><th>Activity</th><th class="r">XP</th></tr></thead><tbody>${events.map((e) => `<tr><td>${e.date}</td><td>${esc(e.label)}<br><span class="sub">${esc(e.detail)}</span></td><td class="r num">+${e.xp}</td></tr>`).join('')}</tbody></table>`
        : '<p class="empty-note">No XP yet. Log a session to begin.</p>'}</section>`;
  }

  /* ---------- page: settings ---------- */
  function pageSettings() {
    const st = S.get().settings;
    return `<header class="page-head"><h1>Settings</h1><p class="lede">Local to this browser. Nothing leaves your machine.</p></header>
    <form class="form" id="settings-form">
      <div class="field"><label for="set-lang">Language</label><select id="set-lang"><option selected>Spanish</option><option disabled>French (not configured)</option><option disabled>Portuguese (not configured)</option></select>
        <span class="hint">Other languages are added through configuration in the open-source project.</span></div>
      <div class="field"><label for="set-scene">Environment image</label><select id="set-scene"><option value="daily" ${st.scene === 'daily' ? 'selected' : ''}>Rotate daily</option>
        ${M.scenes.map((x) => `<option value="${x.id}" ${st.scene === x.id ? 'selected' : ''}>${esc(x.place)}: ${esc(x.title)}</option>`).join('')}</select></div>
      <div class="field"><label for="set-motion">Motion</label><select id="set-motion"><option value="system" ${st.motion === 'system' ? 'selected' : ''}>Follow system setting</option><option value="reduce" ${st.motion === 'reduce' ? 'selected' : ''}>Reduce motion</option></select></div>
    </form>
    <section class="danger"><h2>Prototype data</h2><p>Reset to the sample learner, or clear everything this prototype stored.</p>
      <div class="actions"><button class="btn" data-act="reset">Reset sample data</button></div></section>`;
  }

  /* ---------- toast + XP gain ---------- */
  let toastTimer;
  function toast(msg) {
    const t = $('#toast'); if (!t) return;
    t.textContent = msg; t.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 4200);
  }
  function announceGain(g) {
    if (!g) return;
    const d = S.derive();
    const rankUp = d.rank.index > g.fromRank;
    const extra = g.multiplier > 1 ? ` (includes ×${g.multiplier.toFixed(2)} streak bonus)` : '';
    toast(g.amount ? `+${g.amount} XP${extra}${rankUp ? `. Rank up: ${d.rank.name}` : ''}` : 'Saved. No XP: the daily cap was reached.');
  }

  /* ---------- scene + chrome ---------- */
  function paintScene(d) {
    const el = $('#scene'); if (!el) return;
    const sc = d.scene;
    el.style.setProperty('--s1', sc.s1); el.style.setProperty('--s2', sc.s2); el.style.setProperty('--s3', sc.s3);
    if (sc.photo) el.style.backgroundImage = `url(${sc.photo})`;
    const cap = $('#scene-caption'); if (cap) cap.innerHTML = `<span class="cap-place">${esc(sc.place)}</span> <span class="cap-title">${esc(sc.title)}</span><span class="cap-ph"> · placeholder, photo goes here</span>`;
  }
  function paintNav(route) {
    const nav = $('#nav'); if (!nav) return;
    nav.innerHTML = ROUTES.map(([k, l]) => `<a href="#/${k}" data-route="${k}" ${k === route ? 'aria-current="page"' : ''}>${icon(k)}<span>${l}</span></a>`).join('');
  }
  function animateBars(root, gain) {
    $$('.fill', root).forEach((f) => {
      const to = parseFloat(f.dataset.to);
      const from = f.dataset.from != null ? parseFloat(f.dataset.from) : null;
      f.style.setProperty('--w', from != null ? from : to);
      if (from != null) requestAnimationFrame(() => requestAnimationFrame(() => f.style.setProperty('--w', to)));
    });
  }

  /* ---------- render ---------- */
  function render() {
    const { name, arg } = parseHash();
    const d = S.derive(), s = S.get();
    document.body.dataset.route = name;
    document.documentElement.dataset.motion = s.settings.motion;
    paintNav(name); paintScene(d);
    const view = $('#view');
    const titles = { dashboard: 'Dashboard', study: 'Study', assessments: 'Assessments', vocabulary: 'Vocabulary', challenges: 'Challenges', progress: 'Progress', settings: 'Settings' };
    document.title = `${titles[name]} · Language AI`;
    let html = '';
    if (name === 'dashboard') {
      const fresh = s.lastGain && Date.now() - s.lastGain.at < 15000;
      const ctx = { ...d, gain: fresh ? s.lastGain : null, user: M.user, date: dateLine(), empty: !s.sessions.length };
      html = window.CONCEPT.dashboard(ctx, s, helpers);
    } else if (name === 'study') html = pageStudy();
    else if (name === 'assessments') html = pageAssess();
    else if (name === 'vocabulary') html = pageVocab();
    else if (name === 'challenges') html = pageChallenges();
    else if (name === 'progress') html = pageProgress(arg);
    else html = pageSettings();
    view.innerHTML = html;
    animateBars(view);
    if (name === 'dashboard' && s.lastGain) { S.clearGain(); }
    if (name === 'progress' && arg) { const t = $('#skill-' + arg); t && t.scrollIntoView({ block: 'center' }); }
  }

  /* ---------- events (delegated) ---------- */
  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-mode],[data-add],[data-quiz],[data-vid],[data-act],[data-day]');
    if (!t) return;
    if (t.dataset.mode) { readDraft(); studyMode = t.dataset.mode; render(); }
    else if (t.dataset.add) { readDraft(); const k = t.dataset.add === 'term' ? 'terms' : 'sentences'; draft[k].push(''); render(); const ins = $$(`[data-${t.dataset.add}]`); ins[ins.length - 1].focus(); }
    else if (t.dataset.quiz === 'start') { quiz = { phase: 'run', qs: buildQuiz(S.get()), answers: {}, results: [] }; render(); }
    else if (t.dataset.quiz === 'again') { quiz = { phase: 'intro', qs: [], answers: {}, results: [] }; render(); }
    else if (t.dataset.vid) { vocabSel = vocabSel === t.dataset.vid ? null : t.dataset.vid; render(); const b = $(`[data-vid="${t.dataset.vid}"]`); b && b.focus(); }
    else if (t.dataset.act === 'reset') { if (confirm('Reset all prototype data to the sample learner?')) { S.reset(); draft = null; quiz = { phase: 'intro', qs: [], answers: {}, results: [] }; toast('Sample data restored.'); } }
  });
  document.addEventListener('submit', (e) => {
    if (e.target.id === 'study-form') submitStudy(e);
    else if (e.target.id === 'quiz-form') submitQuiz(e);
    else if (e.target.id === 'settings-form') e.preventDefault();
  });
  document.addEventListener('input', (e) => {
    if (e.target.id === 'vq') { vocabQuery = e.target.value; const p = e.target.selectionStart; render(); const n = $('#vq'); n.focus(); n.setSelectionRange(p, p); }
  });
  document.addEventListener('change', (e) => {
    if (e.target.id === 'set-scene') S.set((s) => { s.settings.scene = e.target.value; });
    else if (e.target.id === 'set-motion') S.set((s) => { s.settings.motion = e.target.value; });
  });
  function dayHover(e) {
    const b = e.target.closest('[data-day]'); if (!b) return;
    const d = S.derive().week[+b.dataset.day];
    $$('[data-week-readout]').forEach((n) => { n.textContent = dayDetail(d); });
  }
  document.addEventListener('mouseover', dayHover);
  document.addEventListener('focusin', dayHover);
  window.addEventListener('hashchange', () => { render(); window.scrollTo(0, 0); });
  S.subscribe(() => { if (parseHash().name === 'settings') { const d = S.derive(); document.documentElement.dataset.motion = S.get().settings.motion; paintScene(d); } });

  window.App = { render, helpers };
  document.addEventListener('DOMContentLoaded', render);
})();
