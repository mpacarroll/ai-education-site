
(function(){
  var tabs = document.querySelectorAll('.tab[data-track]');
  var panels = document.querySelectorAll('.panel[data-track]');
  function show(track){
    tabs.forEach(function(t){ t.setAttribute('aria-selected', t.dataset.track === track ? 'true' : 'false'); });
    panels.forEach(function(p){ p.hidden = p.dataset.track !== track; });
    try { localStorage.setItem('hat-track', track); } catch (e) {}
  }
  if (tabs.length) {
    tabs.forEach(function(t){ t.addEventListener('click', function(e){ e.preventDefault(); clearSearch(); show(t.dataset.track); }); });
    var start = {'#family':'family','#teach-yourself':'adult','#test-prep':'test-prep'}[location.hash];
    try { start = start || localStorage.getItem('hat-track'); } catch (e) {}
    show(start && document.querySelector('.panel[data-track="' + start + '"]') ? start : 'family');
  }
  /* guide search */
  var q = document.getElementById('q'), results = document.getElementById('results');
  var catalog = null;
  function norm(s){ return (s || '').toLowerCase(); }
  function clearSearch(){ if (q) { q.value = ''; results.hidden = true; results.innerHTML = ''; panels.forEach(function(p){ p.classList.remove('dim'); }); document.getElementById('shelves').hidden = false; } }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function card(i){
    return '<article class="card"><a class="img" href="' + i.page + '"><img src="' + i.cover + '" alt="Cover of ' + esc(i.title) + '" width="640" height="480" loading="lazy"></a>' +
      '<h4><a href="' + i.page + '">' + esc(i.title) + '</a></h4><p class="meta">' + esc(i.meta) + '</p>' +
      '<div class="buy">' + (i.etsy ? '<a href="' + i.etsy + '">$' + i.price + ' on Etsy &rarr;</a>' : '') +
      (i.check ? '<a class="free" href="' + i.check + '">Free placement check</a>' : '') + '</div></article>';
  }
  function run(){
    var v = norm(q.value).trim();
    if (!v) { clearSearch(); return; }
    var words = v.split(/\s+/);
    var hits = catalog.filter(function(i){ var h = norm(i.search); return words.every(function(w){ return h.indexOf(w) >= 0; }); });
    document.getElementById('shelves').hidden = true;
    results.hidden = false;
    results.innerHTML = '<div class="group"><h3>Results <span>' + hits.length + ' guide' + (hits.length === 1 ? '' : 's') + ' for "' + esc(q.value.trim()) + '"</span></h3>' +
      (hits.length ? '<div class="grid">' + hits.map(card).join('') + '</div>' : '<p class="empty">No guide matches that yet. Try a broader word, or browse by subject.</p>') + '</div>';
  }
  if (q) {
    q.addEventListener('input', function(){
      if (catalog) { run(); return; }
      fetch(q.dataset.catalog).then(function(r){ return r.json(); }).then(function(d){ catalog = d; run(); }).catch(function(){});
    });
  }
  /* placement-check filter */
  var cq = document.getElementById('cq');
  if (cq) {
    var aud = 'all';
    function filter(){
      var words = norm(cq.value).trim().split(/\s+/).filter(Boolean);
      document.querySelectorAll('.cgroup').forEach(function(g){
        var any = false;
        g.querySelectorAll('a').forEach(function(a){
          var ok = (aud === 'all' || a.dataset.track === aud) && words.every(function(w){ return norm(a.textContent + ' ' + g.dataset.subject).indexOf(w) >= 0; });
          a.hidden = !ok; any = any || ok;
        });
        g.hidden = !any;
      });
      document.getElementById('cempty').hidden = !!document.querySelector('.cgroup:not([hidden])');
    }
    cq.addEventListener('input', filter);
    document.querySelectorAll('[data-aud]').forEach(function(b){ b.addEventListener('click', function(){
      aud = b.dataset.aud;
      document.querySelectorAll('[data-aud]').forEach(function(x){ x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
      filter();
    }); });
  }
  /* copy button on placement-check pages */
  var cb = document.getElementById('cbtn');
  if (cb) cb.addEventListener('click', function(){
    var t = document.getElementById('proto').innerText;
    var done = function(){ cb.innerText = 'Copied. Now paste it into your AI chat'; setTimeout(function(){ cb.innerText = 'Copy the prompt'; }, 2500); };
    if (navigator.clipboard) navigator.clipboard.writeText(t).then(done).catch(function(){});
  });
})();
