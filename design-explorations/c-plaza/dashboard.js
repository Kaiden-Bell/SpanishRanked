/* Concept C: Plaza. Sticky scene panel with rank ladder, hairline sections, bottom dock. */
window.CONCEPT = {
  dashboard(d, s, h) {
    const { esc, bar } = h;
    const st = d.streak;
    const ranks = window.MOCK.ranks;

    // Last 14 days, oldest first, for the streak strip.
    const active = new Set(s.sessions.map((x) => x.date).concat(s.assessments.map((x) => x.date)));
    const pad = (n) => String(n).padStart(2, '0');
    const days = Array.from({ length: 14 }, (_, i) => {
      const dt = new Date(); dt.setDate(dt.getDate() - (13 - i));
      const key = `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;
      return { key, on: active.has(key), today: i === 13 };
    });
    const bonus = st.nextMultiplier > 1 ? `×${st.nextMultiplier.toFixed(2)} XP on your next session` : 'Bonus begins at three days';
    const maxMin = Math.max(45, ...d.week.map((x) => x.minutes));
    const from = d.gain ? (d.gain.fromRank < d.rank.index ? 0 : d.gain.fromPct) : null;

    return `
    <aside class="c-ladder" aria-label="Rank ladder">
      <ol>${ranks.slice().reverse().map((r) => {
        const i = ranks.indexOf(r);
        return `<li class="${i < d.rank.index ? 'done' : i === d.rank.index ? 'now' : ''}" ${i === d.rank.index ? 'aria-current="step"' : ''}><span>${r[1]}</span></li>`;
      }).join('')}</ol>
    </aside>

    <header class="c-hello">
      <h1>¡Hola, ${esc(d.user.name)}!</h1>
      <p>${d.empty ? 'Log a first session to begin.' : 'Ready to keep learning Spanish?'} <span class="c-date">${esc(d.date)}</span></p>
      <div class="c-cta"><a class="btn primary" href="#/study">Start Studying</a><a class="btn" href="#/assessments">Quick Assessment</a></div>
    </header>

    <section class="c-sec" aria-labelledby="rk">
      <h2 id="rk">${esc(d.rank.name)}</h2>
      <p class="c-line">Current rank${d.next ? `, ${d.xpToNext} XP from ${esc(d.next.name)}` : ''}</p>
      ${bar(d.pct, from)}
      <p class="c-fine num">${s.xp} XP in total${d.gain && d.gain.amount ? ` <b class="c-gain">+${d.gain.amount} XP</b>` : ''}</p>
    </section>

    <section class="c-sec" aria-labelledby="sk">
      <h2 id="sk">${st.current === 0 ? 'No streak yet' : `${st.current} ${st.current === 1 ? 'day' : 'days'} running`}</h2>
      <p class="c-line">${esc(h.streakNote(st))} ${bonus}.</p>
      <div class="c-dots" role="img" aria-label="Study days in the last 14 days">${days.map((x) => `<i class="${x.on ? 'on' : ''} ${x.today ? 'today' : ''}" title="${x.key}"></i>`).join('')}</div>
    </section>

    <section class="c-sec" aria-labelledby="sp">
      <h2 id="sp">Skill profile</h2>
      <p class="c-line">Four separate skills. None speaks for another.</p>
      <ul class="c-skills">${d.skills.map((k) => `
        <li><a href="#/progress/${k.key}" aria-label="${k.label}: ${h.skillText(k)}">
          <span class="c-col ${k.ratio == null ? 'na' : ''}"><i style="--r:${k.ratio == null ? 0 : k.ratio}"></i></span>
          <span class="c-sn">${k.label}</span>
          <span class="c-sv ${k.ratio == null ? 'na' : 'num'}">${k.ratio == null ? 'Not yet assessed' : h.pct(k.ratio) + '%'}</span></a></li>`).join('')}</ul>
    </section>

    <section class="c-sec" aria-labelledby="wk">
      <h2 id="wk">Weekly activity</h2>
      <p class="c-line num">${d.daysDone} of 7 days. Minutes studied each day.</p>
      <div class="c-week" role="list">${d.week.map((x, i) => `
        <button class="c-cell ${x.isToday ? 'today' : ''} ${x.isFuture ? 'future' : ''}" data-day="${i}" role="listitem" style="--a:${x.minutes ? .2 + .8 * (x.minutes / maxMin) : 0}" aria-label="${esc(h.dayDetail(x))}">
          <span class="c-min num">${x.minutes || '·'}</span><span class="c-dn">${x.label}</span></button>`).join('')}</div>
      <p class="c-fine" data-week-readout aria-live="polite">Hover or focus a day for details.</p>
    </section>`;
  },
};
