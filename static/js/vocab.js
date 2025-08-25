import { postJSON, $, $all } from './common.js';

/** ======== State ======== */
let allCards = [];
let filtered = [];
let currentDetailId = null;

/** ======== Boot ======== */
window.addEventListener('DOMContentLoaded', async () => {
  bindUI();
  await loadSummary();
  applyFiltersAndRender();
});

/** ======== UI Bindings ======== */
function bindUI(){
  $('#btnEnrichAll').addEventListener('click', onEnrichAll);
  $('#btnRefresh').addEventListener('click', async ()=>{ await loadSummary(); applyFiltersAndRender(); });

  $('#q').addEventListener('input', onFilterChange);
  $('#filterStatus').addEventListener('change', onFilterChange);
  $('#filterMemory').addEventListener('change', onFilterChange);
}

function onFilterChange(){
  applyFiltersAndRender();
}

/** ======== Data ======== */
async function loadSummary(){
  const r = await fetch('/vocab/summary');
  if(!r.ok){ alert('Không tải được dữ liệu'); return; }
  const data = await r.json();
  allCards = data.cards || [];

  // counts
  $('#countRaw').textContent = data.counts.raw || 0;
  $('#countEnrich').textContent = data.counts.enrich || 0;
  $('#countAdditional').textContent = data.counts.additional || 0;
  $('#countLTM').textContent = data.counts.LTM || 0;
  $('#countSTM').textContent = data.counts.STM || 0;
  $('#countREVIEW').textContent = data.counts.REVIEW || 0;
}

/** ======== Filtering + Rendering ======== */
function applyFiltersAndRender(){
  const q = ($('#q').value || '').trim().toLowerCase();
  const fs = $('#filterStatus').value;
  const fm = $('#filterMemory').value;

  filtered = allCards.filter(c => {
    const okQ = !q || [c.word, c.meaning_vi, c.usage, c.phonetic].join(' ').toLowerCase().includes(q);
    const okS = !fs || (c.status || '').toLowerCase() === fs;
    const mem = (c.memory_label || (c.memory_label==="" ? "REVIEW" : "")).toUpperCase();
    const okM = !fm || (mem === fm || (fm==="REVIEW" && (mem==="" || mem==="REVIEW")));
    return okQ && okS && okM;
  });

  renderList();
  renderStatsInfo();

  // giữ panel chi tiết nếu đang mở
  if(currentDetailId){
    const found = allCards.find(x => x.id === currentDetailId);
    if(found) showDetail(found.id, false);
    else clearDetail();
  }
}

function renderStatsInfo(){
  $('#statsInfo').textContent = `Hiển thị ${filtered.length}/${allCards.length} thẻ`;
}

function renderList(){
  const box = $('#wordList');
  box.innerHTML = '';
  if(filtered.length === 0){
    box.innerHTML = '<i>Không có thẻ nào khớp bộ lọc.</i>';
    return;
  }

  // Sắp xếp nhẹ: ưu tiên raw → enrich → additional, rồi theo chữ cái
  const order = {raw:0, enrich:1, additional:2};
  const items = [...filtered].sort((a,b)=>{
    const sa = order[(a.status||'').toLowerCase()] ?? 9;
    const sb = order[(b.status||'').toLowerCase()] ?? 9;
    if(sa !== sb) return sa - sb;
    return (a.word||'').localeCompare(b.word||'', undefined, {sensitivity:'base'});
  });

  items.forEach(c => {
    const div = document.createElement('div');
    div.className = 'card';
    div.style.cursor = 'pointer';
    div.dataset.cardId = c.id;

    const memory = c.memory_label || '—';
    div.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <div>
          <div style="font-weight:600">${c.word || ''}</div>
          <div class="small mono">${c.phonetic || ''}</div>
          <div style="opacity:.9">${c.meaning_vi || ''}</div>
        </div>
        <div style="text-align:right;min-width:120px;">
          <div><span class="badge">${c.status || ''}</span></div>
          <div><span class="badge">${memory}</span></div>
        </div>
      </div>
    `;

    div.addEventListener('click', ()=> showDetail(c.id, true));
    box.appendChild(div);
  });
}

function clearDetail(){
  currentDetailId = null;
  $('#detailBody').innerHTML = '<i>Chọn một thẻ ở danh sách để xem chi tiết...</i>';
}

/** ======== Detail Panel ======== */
async function showDetail(id, scrollIntoView){
  const r = await fetch('/vocab/card/' + id);
  if(!r.ok){ alert('Không tìm thấy thẻ'); return; }
  const c = await r.json();
  currentDetailId = id;

  const img = c.image_url ? `
    <div style="margin:8px 0;">
      <img src="${c.image_url}" alt="${c.word}" style="max-width:100%; border-radius:10px;">
    </div>` : '';
  const audio = c.audio_url ? `<audio controls src="${c.audio_url}" style="width:100%; margin-top:8px;"></audio>` : '';

  $('#detailBody').innerHTML = `
    <div style="font-size:22px; font-weight:700;">${c.word || ''}</div>
    ${img}
    ${audio}
    <div style="margin-top:6px;"><b>Phonetic:</b> ${c.phonetic || '—'}</div>
    <div><b>POS:</b> ${c.pos || '—'}</div>
    <div><b>Nghĩa (VI):</b> ${c.meaning_vi || '—'}</div>
    <div><b>Usage:</b> <i>${c.usage || '—'}</i></div>
    <div class="small mono" style="margin-top:8px;">
      Status: ${c.status || '—'} · Origin: ${c.origin || '—'} · Memory: ${c.memory_label || '—'}
    </div>
    <button class="btn" id="btnFillMissing" style="margin-top:8px;">Bổ sung thiếu</button>
  `;

  if(scrollIntoView){
    document.getElementById('detailPanel').scrollIntoView({behavior:'smooth', block:'start'});
  }

  $('#btnFillMissing').addEventListener('click', ()=> fillMissing(c.id));
}

/** ======== Actions ======== */
async function onEnrichAll(){
  const btn = $('#btnEnrichAll');
  btn.disabled = true;
  btn.textContent = 'Đang enrich...';
  try{
    const res = await postJSON('/vocab/enrich_all', {});
    alert(res.message || 'Đã enrich xong');
    await loadSummary();
    applyFiltersAndRender();
  }catch(e){
    alert('Lỗi enrich: ' + e.message);
  }finally{
    btn.disabled = false;
    btn.textContent = 'Enrich All';
  }
}

async function fillMissing(id){
  try{
    const res = await postJSON('/vocab/fill_missing/'+id, {});
    alert(res.updated ? 'Đã bổ sung.' : 'Không có gì để bổ sung.');
    await loadSummary();
    applyFiltersAndRender();
    showDetail(id, false);
  }catch(e){
    alert('Lỗi: '+e.message);
  }
}
