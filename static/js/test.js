import { postJSON, $, $all } from './common.js';

let session = null;
let wrongIndices = new Set();
let phase = 'main'; // 'main' or 'retake'

window.addEventListener('DOMContentLoaded', async ()=>{
  $('#btnStart').addEventListener('click', startTest);
  $('#btnFinalize').addEventListener('click', finalizeTest);
});

async function startTest(){
  const res = await postJSON('/tests/start', {});
  session = res;
  wrongIndices = new Set();
  renderItems(session.items);
}

function renderItems(items){
  const box = $('#items');
  box.innerHTML = '';
  items.forEach((it, idx)=>{
    const card = document.createElement('div');
    card.className = 'card';
    if(it.type === 'vi2en_mcq'){
      card.innerHTML = `
        <div><b>[MCQ]</b> Dịch sang tiếng Anh: <i>${it.prompt_vi}</i></div>
        <div id="opts-${idx}"></div>
        <div id="fb-${idx}" class="small mono"></div>
      `;
      const opts = card.querySelector('#opts-'+idx);
      it.options.forEach(opt => {
        const btn = document.createElement('button');
        btn.className = 'btn secondary'; btn.textContent = opt;
        btn.addEventListener('click', ()=>{
          const correct = (opt === it.answer);
          $('#fb-'+idx).textContent = correct ? 'Đúng' : 'Sai';
          if(!correct) wrongIndices.add(idx);
          else wrongIndices.delete(idx);
        });
        opts.appendChild(btn);
        opts.appendChild(document.createTextNode(' '));
      });
    }else if(it.type === 'type_from_meaning'){
      card.innerHTML = `
        <div><b>[Gõ từ]</b> Viết đúng từ tiếng Anh cho nghĩa: <i>${it.prompt_vi}</i></div>
        <input type="text" id="in-${idx}"/>
        <button class="btn secondary" id="chk-${idx}">Kiểm tra</button>
        <div id="fb-${idx}" class="small mono"></div>
      `;
      card.querySelector('#chk-'+idx).addEventListener('click', ()=>{
        const v = card.querySelector('#in-'+idx).value.trim();
        const correct = (v.toLowerCase() === it.word.toLowerCase());
        $('#fb-'+idx).textContent = correct ? 'Đúng' : 'Sai (đáp án: '+it.word+')';
        if(!correct) wrongIndices.add(idx);
        else wrongIndices.delete(idx);
      });
    }else{
      card.textContent = '(Bài tập khác sẽ được bổ sung)';
    }
    box.appendChild(card);
  });
}

async function finalizeTest(){
  if(!session){ alert('Chưa bắt đầu bài test'); return; }
  if(phase === 'main' && wrongIndices.size > 0){
    // Retake wrong-only
    const items = session.items.filter((_,i)=> wrongIndices.has(i));
    wrongIndices = new Set();
    phase = 'retake';
    alert('Làm lại các câu sai ('+items.length+')');
    renderItems(items);
    session.items = items; // update to current subset for final scoring simplicity
    return;
  }
  // compute labels
  const labelSummary = {LTM:0, STM:0, REVIEW:0};
  // naive: any item wrong -> word wrong
  const wordWrong = new Map(); // word -> wrong count
  (session.items || []).forEach((it, idx)=>{
    // In this minimal demo we cannot track per-item correctness here;
    // We'll approximate based on no remaining wrongIndices after retake -> all correct in retake
  });
  // For demo: mark all as LTM after retake; in real app track per-question results
  session.picked_words.forEach(w => labelSummary.LTM++);
  const res = await postJSON('/tests/finalize', { session_id: session.session_id, label_summary: labelSummary });
  alert('Đã cập nhật nhãn ghi nhớ. Tóm tắt: ' + JSON.stringify(labelSummary));
}
