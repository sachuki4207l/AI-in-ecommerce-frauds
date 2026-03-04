// Small shared client JS for listing sellers and loading advisory
(function(){
  function debounce(fn, wait=200){
    let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), wait)}
  }

  async function fetchJson(url){
    const res = await fetch(url);
    if(!res.ok) throw new Error('Network error');
    return res.json();
  }

  function renderSellers(sellers, container){
    container.innerHTML = '';
    if(!sellers || sellers.length===0){
      container.innerHTML = '<div class="empty">No sellers found.</div>';
      return;
    }

    sellers.forEach(s=>{
      const div = document.createElement('div');
      div.className = 'card seller-card';
      div.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div class="seller-name">${escapeHtml(s.name || '—')}</div>
            <div class="muted">ID: ${s.id} • Account Age: ${s.account_age_days ?? 'N/A'} days</div>
          </div>
          <div style="display:flex;flex-direction:column;gap:8px">
            <a class="btn" href="/seller/${s.id}">View Advisory</a>
            <a class="btn secondary" href="/products/seller/${s.id}">Products</a>
          </div>
        </div>
      `;
      container.appendChild(div);
    })
  }

  function escapeHtml(s){
    return String(s).replace(/[&<>\"']/g, c=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'
    }[c]));
  }

  window.loadSellers = async function(containerId='seller-list', searchId='search'){
    const container = document.getElementById(containerId);
    if(!container) return;
    container.innerHTML = '<div class="empty">Loading sellers…</div>';
    try{
      const sellers = await fetchJson('/sellers/all');
      window._sellersCache = sellers;
      renderSellers(sellers, container);

      const search = document.getElementById(searchId);
      if(search){
        const doSearch = debounce(()=>{
          const q = search.value.trim().toLowerCase();
          if(!q) return renderSellers(window._sellersCache, container);
          const filtered = (window._sellersCache || []).filter(s=>{
            return String(s.name||'').toLowerCase().includes(q) || String(s.id||'').toLowerCase().includes(q);
          });
          renderSellers(filtered, container);
        }, 150);
        search.addEventListener('input', doSearch);
      }

    }catch(e){
      container.innerHTML = `<div class="empty">Error loading sellers</div>`;
      console.error(e);
    }
  }

  window.loadAdvisory = async function(id, containerId='advisory'){
    const container = document.getElementById(containerId);
    if(!container) return;
    container.innerHTML = '<div class="empty">Loading advisory…</div>';
    try{
      const data = await fetchJson(`/advisory/seller/${id}`);
      if(data.error){ container.innerHTML = `<div class="empty">${escapeHtml(data.error)}</div>`; return; }

      const reasons = (data.reasons||[]).map(r=>`<li>${escapeHtml(r)}</li>`).join('');

      container.innerHTML = `
        <div class="advisory-hero">
          <div class="score">
            <h2>${escapeHtml(data.trust_score)}</h2>
            <p class="muted">Trust Score</p>
          </div>
          <div>
            <h3 style="margin:0">${escapeHtml(data.risk_level)}</h3>
            <p class="muted" style="margin-top:6px">${escapeHtml(data.recommendation || '')}</p>
            <div style="margin-top:12px">
              <a class="btn" onclick="simulateBuy('${escapeHtml(data.risk_level)}')">Buy Product</a>
              <a class="btn secondary" href="/products/seller/${id}" style="margin-left:8px">View Products</a>
            </div>
          </div>
        </div>
        <div style="margin-top:14px">
          <h4>Reasons</h4>
          <ul>${reasons}</ul>
        </div>
      `;
    }catch(e){
      container.innerHTML = `<div class="empty">Failed to load advisory</div>`;
      console.error(e);
    }
  }

  window.simulateBuy = function(risk){
    if(risk === 'High Risk'){
      alert('⚠️ Purchase blocked: Seller marked High Risk');
    }else if(risk === 'Caution'){
      alert('⚠️ Warning: Proceed with caution');
    }else{
      alert('✅ Safe purchase recommended');
    }
  }

})();
