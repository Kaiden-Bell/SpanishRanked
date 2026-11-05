/* Concept B: Biblioteca. Top bar, fixed backdrop, one ruled reading column. */
window.CONCEPT = {
  dashboard(d, s, h) {
    const { esc, bar } = h;
    const st = d.streak;
    const ranks = window.MOCK.ranks;
    const ledger = ranks.map((r, i) => {
      const cls = i < d.rank.index ? 'done' : i === d.rank.index ? 'now' : 'next';
      const row = `<span class="b-rname">${r[1]}</span><span class="b-rxp num">${r[0]} XP</span>`;
      if (i !== d.rank.index) return `<li class="${cls}">${row}</li>`;
      return `<li class="now" aria-current="step">${row}
        <div class="b-inline">${bar(d.pct, d.gain ? d.gain.fromRank < d.rank.index ? 0 : d.gain.fromPct : null)}
        <span class="num">${d.next ? `${s.xp} of ${d.next.min} XP` : 'Highest rank'}${d.gain && d.gain.amount ? ` <b class="b-gain">+${d.gain.amount}</b>` : ''}</span></div></li>`;
    }).join('');
    const maxDots = 4;
    const bonus = st.nextMultiplier > 1 ? `Your next session earns +${Math.round((st.nextMultiplier - 1) * 100)}% XP.` : 'A bonus begins at three days.';
    return `
    <header class="b-hello">
      <h1>¡Hola, ${esc(d.user.name)}!</h1>
      <p class="b-sub">${d.empty ? 'Your journal is empty. Log a first session.' : 'Ready to keep learning Spanish?'} <span class="b-date">${esc(d.date)}</span></p>
      <div class="b-cta"><a class="btn primary" href="#/study">Start Studying</a><a class="btn" href="#/assessments">Quick Assessment</a></div>
    </header>

    <section class="b-sec" aria-labelledby="rk">
      <h2 id="rk">Current rank: ${esc(d.rank.name)}</h2>
      <ol class="b-ledger">${ledger}</ol>
    </section>

    <section class="b-sec b-streak" aria-labelledby="sk">
      <span class="b-ribbon num" aria-hidden="true">${st.current}</span>
      <div><h2 id="sk">${st.current === 0 ? 'No streak yet' : `${st.current} ${st.current === 1 ? 'day' : 'days'} in a row`}</h2>
      <p class="b-note">${esc(h.streakNote(st))} ${bonus}</p></div>
    </section>

    <section class="b-sec" aria-labelledby="sp">
      <h2 id="sp">Skill profile</h2>
      <ul class="b-skills">${d.skills.map((k) => {
        const on = k.ratio == null ? 0 : Math.round(k.ratio * 10);
        return `<li><a href="#/progress/${k.key}"><span class="b-sn">${k.label}</span>
          <span class="b-ticks ${k.ratio == null ? 'na' : ''}" aria-hidden="true">${Array.from({ length: 10 }, (_, i) => `<i class="${i < on ? 'on' : ''}" style="--i:${i}"></i>`).join('')}</span>
          <span class="b-sv ${k.ratio == null ? 'na' : ''}">${k.ratio == null ? 'Not yet assessed' : h.skillText(k)}</span></a></li>`;
      }).join('')}</ul>
    </section>

    <section class="b-sec" aria-labelledby="wk">
      <div class="b-wkhead"><h2 id="wk">This week</h2><span class="b-sv num">${d.daysDone} of 7 days</span></div>
      <div class="b-week" role="list">${d.week.map((x, i) => {
        const n = Math.min(maxDots, x.sessions + x.assessments);
        return `<button class="b-d ${x.isToday ? 'today' : ''} ${x.isFuture ? 'future' : ''}" data-day="${i}" role="listitem" aria-label="${esc(h.dayDetail(x))}">
          <span class="b-stack">${Array.from({ length: n }, (_, j) => `<i style="--j:${j}"></i>`).join('')}</span><span class="b-dl">${x.label}</span></button>`;
      }).join('')}</div>
      <p class="b-readout" data-week-readout aria-live="polite">One mark for each completed session or assessment.</p>
    </section>`;
  },
};
