/* Concept A: Alhambra Dusk. Left rail, scene banner, 2 x 2 modules. */
window.CONCEPT = {
  dashboard(d, s, h) {
    const { esc, bar } = h;
    const st = d.streak;
    const xpLine = d.next ? `${d.into} / ${d.span} XP to ${esc(d.next.name)}` : 'Highest rank reached';
    const maxMin = Math.max(45, ...d.week.map((x) => x.minutes));
    const streakHead = st.current === 0 ? 'No streak yet' : `${st.current} ${st.current === 1 ? 'day' : 'days'} running`;
    const bonus = st.nextMultiplier > 1 ? `+${Math.round((st.nextMultiplier - 1) * 100)}% XP on your next session` : 'Streak bonus starts at 3 days';
    return `
    <header class="a-hello">
      <p class="a-date">${esc(d.date)}</p>
      <h1>¡Hola, ${esc(d.user.name)}!</h1>
      <p class="a-sub">${d.empty ? 'Log your first session to begin.' : 'Ready to keep learning Spanish?'}</p>
      <div class="a-cta"><a class="btn primary" href="#/study">Start Studying</a><a class="btn" href="#/assessments">Quick Assessment</a></div>
    </header>

    <div class="a-grid">
      <section class="a-card a-rank" aria-labelledby="rk">
        <h2 id="rk">${esc(d.rank.name)}</h2>
        <p class="a-cap">Current rank</p>
        ${bar(d.pct, d.gain ? d.gain.fromRank < d.rank.index ? 0 : d.gain.fromPct : null)}
        <p class="a-meta num">${xpLine}${d.gain && d.gain.amount ? ` <span class="a-gain">+${d.gain.amount} XP</span>` : ''}</p>
      </section>

      <section class="a-card a-streak" aria-labelledby="sk">
        <h2 id="sk">${streakHead}</h2>
        <p class="a-cap">${esc(h.streakNote(st))}</p>
        <p class="a-meta">${bonus}</p>
      </section>

      <section class="a-card a-skills" aria-labelledby="sp">
        <div class="a-head"><h2 id="sp">Skill profile</h2><p class="a-cap">Each skill stands alone</p></div>
        <ul class="a-skill-list">${d.skills.map((k) => `
          <li><a href="#/progress/${k.key}" class="a-skill">
            <span class="a-sname">${k.label}</span>
            ${k.ratio == null ? '<span class="bar empty-track"></span>' : bar(k.ratio)}
            <span class="a-sval ${k.ratio == null ? 'na' : 'num'}">${k.ratio == null ? 'Not yet assessed' : h.pct(k.ratio) + '%'}</span>
          </a>${k.ratio == null ? '' : `<span class="sr">${h.skillText(k)}</span>`}</li>`).join('')}</ul>
        <p class="a-foot">Recall in your own assessments, not a CEFR level.</p>
      </section>

      <section class="a-card a-week" aria-labelledby="wk">
        <div class="a-head"><h2 id="wk">Weekly activity</h2><p class="a-cap num">${d.daysDone} of 7 days</p></div>
        <div class="a-bars" role="list">${d.week.map((x, i) => `
          <button class="a-day ${x.isToday ? 'today' : ''} ${x.isFuture ? 'future' : ''}" data-day="${i}" role="listitem" aria-label="${esc(h.dayDetail(x))}">
            <span class="a-col"><span class="a-barfill" style="--h:${x.minutes ? Math.max(.12, x.minutes / maxMin) : 0}"></span></span>
            <span class="a-dl">${x.label}</span></button>`).join('')}</div>
        <p class="a-readout" data-week-readout aria-live="polite">Hover or focus a day for details.</p>
      </section>
    </div>`;
  },
};
