(() => {
  // Elements
  const els = {
    q: document.getElementById('q'),
    country: document.getElementById('country'),
    region: document.getElementById('region'),
    focus: document.getElementById('focus'),
    ratingMin: document.getElementById('ratingMin'),
    verifier: document.getElementById('verifier'),
    applyBtn: document.getElementById('applyBtn'),
    clearBtn: document.getElementById('clearBtn'),
    sortBy: document.getElementById('sortBy'),
    results: document.getElementById('results'),
    empty: document.getElementById('empty'),
    activePills: document.getElementById('activePills'),
    banner: document.getElementById('banner')
  };

  // State
  let DATA = [];

  // Fetch charities.json
  async function loadData(){
    setBanner('Loading charities…');
    try{
      const res = await fetch('/static/charities.json', { cache: 'no-store' });
      if(!res.ok) throw new Error('Network response was not ok');
      const json = await res.json();
      if(!Array.isArray(json)) throw new Error('Invalid charities JSON');
      DATA = json;
      populateCountryOptions(DATA);
      clearBanner();
      // Initial render: show everything with default sort, but no live updates afterward
      applyFilters();
    }catch(err){
      console.error(err);
      setBanner('Failed to load charities. Showing nothing. Check /static/charities.json.', true);
      DATA = [];
      populateCountryOptions(DATA);
      applyFilters();
    }
  }

  function setBanner(msg, isError=false){
    els.banner.textContent = msg;
    els.banner.hidden = false;
    els.banner.classList.toggle('error', !!isError);
  }
  function clearBanner(){ els.banner.hidden = true; els.banner.classList.remove('error'); }

  function populateCountryOptions(list){
    els.country.innerHTML = '<option value="">Any</option>';
    const countries = Array.from(new Set(list.map(c => c.country).filter(Boolean))).sort();
    for (const c of countries){
      const opt = document.createElement('option');
      opt.value = c; opt.textContent = c; els.country.appendChild(opt);
    }
  }

  // Read current form state
  function currentFilters(){
    return {
      q: els.q.value.trim().toLowerCase(),
      country: els.country.value,
      region: els.region.value.trim().toLowerCase(),
      focus: els.focus.value,
      ratingMin: Number(els.ratingMin.value || 0),
      verifier: els.verifier.value,
      sortBy: els.sortBy.value
    };
  }

  // Apply filters (only when clicking the button or on initial load)
  function applyFilters(){
    const f = currentFilters();
    let data = DATA.filter(ch => {
      if (f.q){
        const hay = (ch.name + ' ' + ch.mission + ' ' + (ch.focus||[]).join(' ') + ' ' + (ch.region||'') + ' ' + (ch.country||'')).toLowerCase();
        if (!hay.includes(f.q)) return false;
      }
      if (f.country && ch.country !== f.country) return false;
      if (f.region && !(ch.region || '').toLowerCase().includes(f.region)) return false;
      if (f.focus && !(ch.focus||[]).includes(f.focus)) return false;
      if (typeof ch.rating === 'number' && ch.rating < f.ratingMin) return false;
      if (f.verifier && !((ch.verified_by||[]).includes(f.verifier))) return false;
      return true;
    });

    // Sorting (applied on click as well)
    const [key, dir] = f.sortBy.split('-');
    data.sort((a,b)=>{
      if (key === 'rating') return dir === 'desc' ? b.rating - a.rating : a.rating - b.rating;
      if (key === 'name') return dir === 'asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
      return 0;
    });

    renderPills(f);
    renderResults(data);
  }

  function renderPills(f){
    els.activePills.innerHTML = '';
    const items = [];
    if (f.q) items.push(['q', `Search: "${f.q}"`]);
    if (f.country) items.push(['country', f.country]);
    if (f.region) items.push(['region', f.region.toUpperCase()]);
    if (f.focus) items.push(['focus', f.focus]);
    if (f.ratingMin>0) items.push(['ratingMin', `Rating ≥ ${f.ratingMin}`]);
    if (f.verifier) items.push(['verifier', f.verifier]);

    for (const [key,label] of items){
      const pill = document.createElement('button');
      pill.className='pill';
      pill.textContent = label + ' ✕';
      pill.setAttribute('aria-label', 'Remove filter ' + label);
      pill.addEventListener('click', ()=>{
        if (key === 'ratingMin') els[key].value = '0';
        else if (key in els && (els[key].tagName==='SELECT' || els[key].tagName==='INPUT')) els[key].value='';
        // No auto-apply; user must click Apply Filters.
      });
      els.activePills.appendChild(pill);
    }
  }

  function resultCard(ch){
    const div = document.createElement('div');
    div.className = 'card';
    div.setAttribute('role','listitem');
    div.innerHTML = `
      <h3>${ch.name}</h3>
      <div class="meta">
        <span class="rating">${typeof ch.rating==='number' ? ch.rating + '/100' : '—'}</span>
        <span>• ${ch.country || '—'}${ch.region ? ', ' + ch.region : ''}</span>
        ${(ch.verified_by && ch.verified_by.length) ? `<span class="verified" title="Verified by ${ch.verified_by.join(', ')}">${checkIcon()} Verified</span>` : ''}
      </div>
      <div>${(ch.focus||[]).map(f=>`<span class="pill">${f}</span>`).join(' ')}</div>
      <p style="margin:.25rem 0 .5rem; color:#cbd5e1;">${ch.mission || ''}</p>
      <div class="actions">
        ${ch.url ? `<a class="btn-ghost" href="${ch.url}" target="_blank" rel="noopener noreferrer">Website</a>` : ''}
        ${ch.donate_url ? `<a class="btn-primary" href="${ch.donate_url}" target="_blank" rel="noopener noreferrer">Donate</a>` : ''}
      </div>
    `;
    return div;
  }

  function renderResults(data){
    els.results.innerHTML = '';
    if (!data.length){ els.empty.hidden = false; return; }
    els.empty.hidden = true;
    for (const ch of data){ els.results.appendChild(resultCard(ch)); }
  }

  function checkIcon(){
    return `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M12 2a10 10 0 100 20 10 10 0 000-20Z" stroke="#10b981" stroke-width="1.5"/><path d="M7 12l3 3 7-7" stroke="#10b981" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  }

  // Events — update ONLY when clicking Apply
  els.applyBtn.addEventListener('click', applyFilters);

  // Clear just resets inputs; does NOT re-render until Apply is clicked
  els.clearBtn.addEventListener('click', ()=>{
    els.q.value=''; els.country.value=''; els.region.value='';
    els.focus.value=''; els.ratingMin.value='0'; els.verifier.value='';
    els.sortBy.value='rating-desc';
    // No apply here
  });

  // Initial load
  loadData();
})();
