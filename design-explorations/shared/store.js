/* localStorage-backed prototype state. Mirrors the backend rules in src/backend/app/rules.py.
   Every storage call is guarded: the app renders correctly with storage blocked. */
(function () {
  const KEY = 'languageai.concepts.v1';
  const M = window.MOCK;
  const listeners = [];

  const pad = (n) => String(n).padStart(2, '0');
  const dayKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const today = () => dayKey(new Date());

  function seed() {
    const now = new Date();
    const sessions = [];
    // Twelve consecutive days ending yesterday, so "log today" visibly extends the streak.
    const minutes = [25, 40, 20, 35, 30, 45, 15, 30, 40, 25, 35, 30];
    const types = M.activityTypes;
    for (let i = 12; i >= 1; i--) {
      const m = minutes[12 - i];
      sessions.push({
        id: 's' + i, date: dayKey(addDays(now, -i)), mode: i % 4 === 0 ? 'guided' : 'self',
        activity: types[i % 5], minutes: m,
        context: 'Sample entry', terms: [], sentences: [], xp: Math.min(M.rules.sessionCap, M.rules.base + Math.floor(m / M.rules.minutesPerBonus)),
      });
    }
    return {
      xp: M.seedXp, sessions, vocab: M.vocab.map((v) => ({ ...v })), assessments: [],
      skills: JSON.parse(JSON.stringify(M.skills)),
      settings: { language: 'Spanish', scene: 'daily', motion: 'system' },
      lastGain: null,
    };
  }

  let state;
  function load() {
    try { const raw = localStorage.getItem(KEY); if (raw) return JSON.parse(raw); } catch (e) { /* storage blocked */ }
    return seed();
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* storage blocked */ } }
  function emit() { listeners.forEach((fn) => fn(state)); }

  function rankFor(xp) {
    let i = 0;
    M.ranks.forEach((r, idx) => { if (xp >= r[0]) i = idx; });
    return i;
  }

  function activeDays(s) {
    const set = new Set(s.sessions.map((x) => x.date));
    s.assessments.forEach((a) => set.add(a.date));
    return set;
  }

  function streakInfo(s) {
    const set = activeDays(s);
    const now = new Date();
    const activeToday = set.has(dayKey(now));
    let cursor = activeToday ? now : addDays(now, -1);
    let n = 0;
    while (set.has(dayKey(cursor))) { n++; cursor = addDays(cursor, -1); }
    const mult = (days) => { const hit = M.streakMultipliers.find((m) => days >= m[0]); return hit ? hit[1] : 1; };
    // Multiplier applied to the next action: counts the day it would complete.
    const nextDays = activeToday ? n : n + 1;
    return { current: n, activeToday, multiplier: mult(Math.max(n, 1)), nextMultiplier: mult(nextDays) };
  }

  function xpToday(s, source) {
    const t = today();
    if (source === 'study') return s.sessions.filter((x) => x.date === t).reduce((a, b) => a + b.xp, 0);
    return s.assessments.filter((x) => x.date === t).reduce((a, b) => a + b.xp, 0);
  }

  function weekView(s) {
    const now = new Date();
    const mondayOffset = (now.getDay() + 6) % 7;
    const monday = addDays(now, -mondayOffset);
    const labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return labels.map((label, i) => {
      const d = addDays(monday, i);
      const key = dayKey(d);
      const ss = s.sessions.filter((x) => x.date === key);
      const aa = s.assessments.filter((x) => x.date === key);
      return {
        label, key, isToday: key === dayKey(now), isFuture: d > now && key !== dayKey(now),
        sessions: ss.length, assessments: aa.length,
        minutes: ss.reduce((a, b) => a + b.minutes, 0),
        xp: ss.reduce((a, b) => a + b.xp, 0) + aa.reduce((a, b) => a + b.xp, 0),
      };
    });
  }

  function derive(s) {
    const ri = rankFor(s.xp);
    const rank = { name: M.ranks[ri][1], min: M.ranks[ri][0], index: ri };
    const next = M.ranks[ri + 1] ? { name: M.ranks[ri + 1][1], min: M.ranks[ri + 1][0] } : null;
    const span = next ? next.min - rank.min : 1;
    const into = next ? s.xp - rank.min : 1;
    const skills = ['reading', 'writing', 'listening', 'speaking'].map((k) => {
      const v = s.skills[k];
      return { key: k, label: k[0].toUpperCase() + k.slice(1), assessed: v ? v.assessed : 0, hits: v ? v.hits : 0, ratio: v && v.assessed ? v.hits / v.assessed : null };
    });
    const week = weekView(s);
    const daysDone = week.filter((d) => d.sessions || d.assessments).length;
    const dayOfYear = Math.floor((new Date() - new Date(new Date().getFullYear(), 0, 0)) / 864e5);
    let scene = M.scenes[dayOfYear % M.scenes.length];
    if (s.settings.scene !== 'daily') scene = M.scenes.find((x) => x.id === s.settings.scene) || scene;
    return {
      rank, next, pct: into / span, xpToNext: next ? next.min - s.xp : 0, into, span,
      streak: streakInfo(s), week, daysDone, skills, scene,
      todayStudyXp: xpToday(s, 'study'), todayAssessXp: xpToday(s, 'assess'),
    };
  }

  function logSession(entry) {
    const before = derive(state);
    const streak = streakInfo(state);
    const base = Math.min(M.rules.sessionCap, M.rules.base + Math.floor(entry.minutes / M.rules.minutesPerBonus));
    const room = Math.max(0, M.rules.dailyCapStudy - xpToday(state, 'study'));
    const mult = streak.nextMultiplier;
    const awarded = Math.min(room, Math.round(base * mult));
    state.sessions.push({ id: 's' + Date.now(), date: today(), xp: awarded, ...entry });
    state.xp += awarded;
    // New terms enter the vocabulary collection.
    entry.terms.forEach((t) => {
      const exists = state.vocab.find((v) => v.es.toLowerCase() === t.toLowerCase());
      if (exists) { exists.seen += 1; return; }
      state.vocab.unshift({ id: 'v' + Date.now() + Math.random().toString(16).slice(2, 5), es: t, en: 'Meaning not added yet', pos: '—', example: entry.sentences.find((x) => x.toLowerCase().includes(t.toLowerCase())) || '', exampleEn: '', source: entry.activity, learnerSentence: entry.sentences[0] || '', seen: 1, status: 'new' });
    });
    state.lastGain = { amount: awarded, base, multiplier: mult, capped: awarded < Math.round(base * mult), fromPct: before.pct, fromRank: before.rank.index, at: Date.now() };
    save(); emit();
    return state.lastGain;
  }

  function logAssessment(results) {
    const before = derive(state);
    const correct = results.filter((r) => r.outcome === 'HIT').length;
    const room = Math.max(0, M.rules.dailyCapAssess - xpToday(state, 'assess'));
    const awarded = Math.min(room, Math.round(correct * M.rules.quizPerCorrect * streakInfo(state).nextMultiplier));
    results.forEach((r) => {
      const k = r.modality === 'writing' ? 'writing' : 'reading';
      if (!state.skills[k]) state.skills[k] = { assessed: 0, hits: 0 };
      state.skills[k].assessed += 1;
      if (r.outcome === 'HIT') state.skills[k].hits += 1;
    });
    state.assessments.push({ id: 'a' + Date.now(), date: today(), correct, total: results.length, xp: awarded });
    state.xp += awarded;
    state.lastGain = { amount: awarded, base: correct * M.rules.quizPerCorrect, multiplier: streakInfo(state).multiplier, capped: false, fromPct: before.pct, fromRank: before.rank.index, at: Date.now() };
    save(); emit();
    return state.lastGain;
  }

  window.Store = {
    get: () => state, derive: () => derive(state), today,
    subscribe: (fn) => listeners.push(fn),
    set(fn) { fn(state); save(); emit(); },
    clearGain() { state.lastGain = null; save(); },
    logSession, logAssessment,
    reset() { state = seed(); save(); emit(); },
    clearAll() { state = seed(); try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ } emit(); },
  };
  state = load();
})();
