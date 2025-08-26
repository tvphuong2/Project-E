import { postJSON, $ } from './common.js';

let session = null;
let queue = [];
let nextRound = [];
let wrongCounts = {};
let currentItem = null;
const REVEAL_MS = window.ANSWER_REVEAL_MS || 1200;
let audioPlayer = null;
let hudRemain, hudTimer, cardArea;
let startTime = 0;
let timerInterval = null;
let maxSec = (window.MAX_MIN || 30) * 60;

function normalizeSentence(s){
  return s.toLowerCase().replace(/[.,!?]/g,'').replace(/\s+/g,' ').trim();
}

function normalizeWord(w){
  return w.toLowerCase().replace(/[.,!?]/g,'').trim();
}

function wordEquals(user, correct, pos=''){
  const u = normalizeWord(user);
  const c = normalizeWord(correct);
  if(u === c) return true;
  const p = (pos || '').toLowerCase();
  if(p.startsWith('n') || p.startsWith('v')){
    if(u + 's' === c || u === c + 's') return true;
  }
  return false;
}

function diffChars(user, correct){
  const u = user.toLowerCase();
  const c = correct.toLowerCase();
  let res = '';
  for(let i=0;i<correct.length;i++){
    const uc = u[i];
    const cc = c[i];
    const disp = correct[i];
    if(uc === cc){
      res += `<span class="ok">${disp}</span>`;
    }else if(typeof uc === 'undefined'){
      res += `<span class="miss">_${disp}</span>`;
    }else{
      res += `<span class="wrong">${disp}</span>`;
    }
  }
  return res;
}

function diffWords(user, correct){
  const u = normalizeSentence(user).split(/\s+/);
  const cClean = normalizeSentence(correct).split(/\s+/);
  const cDisp = correct.trim().split(/\s+/);
  let out = [];
  for(let i=0;i<cClean.length;i++){
    const uw = u[i];
    const cw = cClean[i];
    const disp = cDisp[i];
    if(uw === cw){
      out.push(`<span class="ok">${disp}</span>`);
    }else if(typeof uw === 'undefined'){
      out.push(`<span class="miss">_${disp}</span>`);
    }else{
      out.push(`<span class="wrong">${disp}</span>`);
    }
  }
  return out.join(' ');
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
  hudRemain = $('#remain');
  hudTimer = $('#timer');
  cardArea = $('#cardArea');
  startTime = Date.now();
  updateTimer();
  timerInterval = setInterval(updateTimer, 1000);
  updateHUD();
  showNext();
}

function showNext(){
  cardArea.innerHTML = '';
  if(queue.length === 0){
    if(nextRound.length === 0){
      finalize();
      return;
    }else{
      queue = nextRound;
      nextRound = [];
      const note = document.createElement('div');
      note.textContent = `Làm lại các câu sai (${queue.length})`;
      cardArea.appendChild(note);
      updateHUD();
      setTimeout(showNext, 1000);
      return;
    }
  }
  currentItem = queue.shift();
  renderItem(currentItem, cardArea);
  updateHUD();
}

function renderItem(it, box){
  const wrap = document.createElement('div');
  wrap.className = 'card';
  if(it.type === 'vi2en_mcq'){
    wrap.innerHTML = `<div><b>[MCQ]</b> ${it.pos ? '('+it.pos+') ' : ''}Dịch sang tiếng Anh: <i>${it.prompt_vi}</i></div>`;
    if(it.image_url){
      const img = document.createElement('img');
      img.src = it.image_url;
      img.className = 'quiz-img';
      wrap.appendChild(img);
    }
    const opts = document.createElement('div');
    it.options.forEach(opt=>{
      const btn = document.createElement('button');
      btn.className = 'btn secondary';
      btn.textContent = opt;
      btn.addEventListener('click', ()=>{
        const correct = wordEquals(opt, it.answer, it.pos);
        showFeedback(correct, it.answer, opt);
      });
      opts.appendChild(btn);
      opts.appendChild(document.createTextNode(' '));
    });
    wrap.appendChild(opts);
    }else if(it.type === 'type_from_meaning'){
      wrap.innerHTML = `<div><b>[Gõ từ]</b> ${it.pos ? '('+it.pos+') ' : ''}Viết đúng từ tiếng Anh cho nghĩa: <i>${it.prompt_vi}</i></div>`;
      if(it.image_url){
        const img = document.createElement('img');
        img.src = it.image_url;
        img.className = 'quiz-img';
        wrap.appendChild(img);
      }
      const inp = document.createElement('input');
      inp.type = 'text';
      inp.id = 'ans';
      wrap.appendChild(inp);
      const btn = document.createElement('button');
      btn.className = 'btn secondary';
      btn.textContent = 'Kiểm tra';
      btn.addEventListener('click', ()=>{
        const v = inp.value.trim();
        const correct = wordEquals(v, it.word, it.pos);
        showFeedback(correct, it.word, v);
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
        const raw = inp.value;
        const v = normalizeSentence(raw);
        const ans = normalizeSentence(it.answer);
        const correct = (v === ans);
        showFeedback(correct, it.answer, raw);
      };
      btn.addEventListener('click', check);
      inp.addEventListener('keydown', e=>{ if(e.key==='Enter' && e.ctrlKey) check(); });
      wrap.appendChild(btn);
    }else if(it.type === 'en_vi_match'){
      wrap.innerHTML = `<div><b>[Nối từ]</b> Kéo nghĩa tiếng Việt vào đúng từ tiếng Anh</div>`;
      const selects = {};
      const rows = document.createElement('div');
      it.en_words.forEach(en=>{
        const row = document.createElement('div');
        row.className = 'flex match-row';
        const sp = document.createElement('div');
        sp.textContent = en + (it.pos_map && it.pos_map[en] ? ` (${it.pos_map[en]})` : '');
        row.appendChild(sp);
        const dz = document.createElement('div');
        dz.className = 'dropzone';
        dz.dataset.en = en;
        dz.addEventListener('dragover', e=>e.preventDefault());
        dz.addEventListener('drop', e=>{
          e.preventDefault();
          const vi = e.dataTransfer.getData('text/plain');
          dz.textContent = vi;
          dz.dataset.vi = vi;
        });
        row.appendChild(dz);
        rows.appendChild(row);
        selects[en] = dz;
      });
      wrap.appendChild(rows);
      const pool = document.createElement('div');
      pool.className = 'vi-pool';
      it.vi_meanings.forEach(v=>{
        const d = document.createElement('div');
        d.className = 'drag-item';
        d.textContent = v;
        d.draggable = true;
        d.addEventListener('dragstart', e=>{
          e.dataTransfer.setData('text/plain', v);
        });
        pool.appendChild(d);
      });
      wrap.appendChild(pool);
      const btn = document.createElement('button');
      btn.className = 'btn secondary';
      btn.textContent = 'Kiểm tra';
      btn.addEventListener('click', ()=>{
        let ok = true;
        for(const en of Object.keys(selects)){
          if(selects[en].dataset.vi !== it.pairs[en]){ ok = false; break; }
        }
        const ans = Object.entries(it.pairs).map(([e,v])=>`${e}=${v}`).join(', ');
        showFeedback(ok, ans);
      });
      wrap.appendChild(btn);
    }else if(it.type === 'audio2en_input'){
      wrap.innerHTML = `<div><b>[Nghe]</b> Viết lại từ tiếng Anh nghe được${it.pos ? ' ('+it.pos+')' : ''}</div>`;
      const aud = document.createElement('audio');
      aud.src = it.audio_url;
      aud.controls = true;
      wrap.appendChild(aud);
      const inp = document.createElement('input');
      inp.type = 'text';
      inp.id = 'ans';
      wrap.appendChild(inp);
      const btn = document.createElement('button');
      btn.className = 'btn secondary';
      btn.textContent = 'Kiểm tra';
      btn.addEventListener('click', ()=>{
        const v = inp.value.trim();
        const correct = wordEquals(v, it.word, it.pos);
        showFeedback(correct, it.word, v);
      });
      inp.addEventListener('keydown', e=>{ if(e.key==='Enter') btn.click(); });
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

function showFeedback(correct, answer, userInput=''){
  const fb = $('#fb');
  fb.innerHTML = '';
  if(correct){
    fb.innerHTML = '<span class="correct">Đúng</span>';
  }else{
    let ansHTML = answer;
    if(currentItem.type === 'vi_sentence_input'){
      ansHTML = diffWords(userInput, answer);
    }else if(currentItem.type === 'type_from_meaning'){
      ansHTML = diffChars(userInput, answer);
    }
    fb.innerHTML = `<div class="wrong">Sai</div><div class="fb-ans">${ansHTML}</div>`;
    wrongCounts[currentItem.word] = (wrongCounts[currentItem.word] || 0) + 1;
    nextRound.push(currentItem);
  }
  if(currentItem.audio_url && currentItem.type !== 'vi_sentence_input'){
    audioPlayer = new Audio(currentItem.audio_url);
    audioPlayer.play().catch(()=>{});
  }
  setTimeout(showNext, REVEAL_MS);
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
  clearInterval(timerInterval);
  if(cardArea) cardArea.innerHTML = '';
  if(hudRemain) hudRemain.textContent = '0';
  if(hudTimer) hudTimer.textContent = '0:00';
}

function updateHUD(){
  if(!hudRemain) return;
  const remaining = queue.length + nextRound.length + (currentItem ? 1 : 0);
  hudRemain.textContent = remaining;
}

function updateTimer(){
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const left = Math.max(0, maxSec - elapsed);
  const m = Math.floor(left / 60);
  const s = left % 60;
  if(hudTimer){
    hudTimer.textContent = `${m}:${s.toString().padStart(2,'0')}`;
  }
  if(left <= 0){
    clearInterval(timerInterval);
    finalize();
  }
}
