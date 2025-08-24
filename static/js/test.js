import { postJSON, $ } from './common.js';

let session = null;
let queue = [];
let nextRound = [];
let wrongCounts = {};
let currentItem = null;

function normalizeSentence(s){
  return s.toLowerCase().replace(/[.,!?]/g,'').replace(/\s+/g,' ').trim();
}

window.addEventListener('DOMContentLoaded', ()=>{
  $('#btnStart').addEventListener('click', startTest);
});

async function startTest(){
  const res = await postJSON('/tests/start', {});
  session = res;
  queue = [...session.items];
  nextRound = [];
  wrongCounts = {};
  $('#startCard').classList.add('hidden');
  const quiz = $('#quiz');
  quiz.classList.remove('hidden');
  document.body.classList.add('testing');
  showNext();
}

function showNext(){
  const box = $('#quiz');
  box.innerHTML = '';
  if(queue.length === 0){
    if(nextRound.length === 0){
      finalize();
      return;
    }else{
      queue = nextRound;
      nextRound = [];
      const note = document.createElement('div');
      note.textContent = `Làm lại các câu sai (${queue.length})`;
      box.appendChild(note);
      setTimeout(showNext, 1000);
      return;
    }
  }
  currentItem = queue.shift();
  renderItem(currentItem, box);
}

function renderItem(it, box){
  const wrap = document.createElement('div');
  wrap.className = 'card';
  if(it.type === 'vi2en_mcq'){
    wrap.innerHTML = `<div><b>[MCQ]</b> ${it.pos ? '('+it.pos+') ' : ''}Dịch sang tiếng Anh: <i>${it.prompt_vi}</i></div>`;
    const opts = document.createElement('div');
    it.options.forEach(opt=>{
      const btn = document.createElement('button');
      btn.className = 'btn secondary';
      btn.textContent = opt;
      btn.addEventListener('click', ()=>{
        const correct = (opt === it.answer);
        showFeedback(correct, it.answer);
      });
      opts.appendChild(btn);
      opts.appendChild(document.createTextNode(' '));
    });
    wrap.appendChild(opts);
    }else if(it.type === 'type_from_meaning'){
      wrap.innerHTML = `<div><b>[Gõ từ]</b> ${it.pos ? '('+it.pos+') ' : ''}Viết đúng từ tiếng Anh cho nghĩa: <i>${it.prompt_vi}</i></div>`;
      const inp = document.createElement('input');
      inp.type = 'text';
      inp.id = 'ans';
      wrap.appendChild(inp);
      const btn = document.createElement('button');
      btn.className = 'btn secondary';
      btn.textContent = 'Kiểm tra';
      btn.addEventListener('click', ()=>{
        const v = inp.value.trim();
        const correct = (v.toLowerCase() === it.word.toLowerCase());
        showFeedback(correct, it.word);
      });
      inp.addEventListener('keydown', e=>{ if(e.key==='Enter') btn.click(); });
      wrap.appendChild(btn);
    }else if(it.type === 'vi_sentence_input'){
      wrap.innerHTML = `<div><b>[Dịch câu]</b> ${it.pos ? '('+it.pos+') ' : ''}${it.prompt_vi}</div>`;
      const inp = document.createElement('textarea');
      inp.id = 'ans';
      wrap.appendChild(inp);
      const btn = document.createElement('button');
      btn.className = 'btn secondary';
      btn.textContent = 'Kiểm tra';
      const check = ()=>{
        const v = normalizeSentence(inp.value);
        const ans = normalizeSentence(it.answer);
        const correct = (v === ans);
        showFeedback(correct, it.answer);
      };
      btn.addEventListener('click', check);
      inp.addEventListener('keydown', e=>{ if(e.key==='Enter' && e.ctrlKey) check(); });
      wrap.appendChild(btn);
    }else if(it.type === 'en_vi_match'){
      wrap.innerHTML = `<div><b>[Nối từ]</b> Ghép từ tiếng Anh với nghĩa tiếng Việt</div>`;
      const selects = {};
      it.en_words.forEach(en=>{
        const row = document.createElement('div');
        row.className = 'flex match-row';
        const sp = document.createElement('div');
        sp.textContent = en + (it.pos_map && it.pos_map[en] ? ` (${it.pos_map[en]})` : '');
        row.appendChild(sp);
        const sel = document.createElement('select');
        sel.innerHTML = '<option value="">--Chọn--</option>' + it.vi_meanings.map(v=>`<option value="${v}">${v}</option>`).join('');
        row.appendChild(sel);
        wrap.appendChild(row);
        selects[en] = sel;
      });
      const btn = document.createElement('button');
      btn.className = 'btn secondary';
      btn.textContent = 'Kiểm tra';
      btn.addEventListener('click', ()=>{
        let ok = true;
        for(const en of Object.keys(selects)){
          if(selects[en].value !== it.pairs[en]){ ok = false; break; }
        }
        const ans = Object.entries(it.pairs).map(([e,v])=>`${e}=${v}`).join(', ');
        showFeedback(ok, ans);
      });
      wrap.appendChild(btn);
    }else{
      wrap.textContent = '(Bài tập khác sẽ được bổ sung)';
    }
  const fb = document.createElement('div');
  fb.id = 'fb';
  fb.className = 'small mono';
  wrap.appendChild(fb);
  box.appendChild(wrap);
}

function showFeedback(correct, answer){
  const fb = $('#fb');
  fb.textContent = correct ? 'Đúng' : `Sai. Đáp án: ${answer}`;
  if(!correct){
    wrongCounts[currentItem.word] = (wrongCounts[currentItem.word] || 0) + 1;
    nextRound.push(currentItem);
  }
  setTimeout(showNext, 1200);
}

async function finalize(){
  const results = {};
  (session.picked_words || []).forEach(w=>{
    results[w] = wrongCounts[w] || 0;
  });
  const res = await postJSON('/tests/finalize', { session_id: session.session_id, results });
  alert('Hoàn tất. Nhãn: ' + JSON.stringify(res.label_summary) + `\nThời gian: ${res.duration_sec}s\nLặp lại: ${res.retakes}`);
  document.body.classList.remove('testing');
  $('#startCard').classList.remove('hidden');
  const quiz = $('#quiz');
  quiz.classList.add('hidden');
  quiz.innerHTML = '';
}
