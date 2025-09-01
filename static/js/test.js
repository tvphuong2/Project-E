import { postJSON, $ } from './common.js';

let session = null;
let queue = [];
let nextRound = [];
let wrongCounts = {};
let currentItem = null;
const ANSWER_MS_MAP = window.ANSWER_MS_MAP || {};
let audioPlayer = null;
let hudRemain, hudTimer, cardArea;
let startTime = 0;
let timerInterval = null;
let maxSec = (window.MAX_MIN || 30) * 60;

function revealDelay(type){
  return ANSWER_MS_MAP[type] || ANSWER_MS_MAP['default'] || 1200;
}

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

function alignTokens(ref, hyp){
  const n = ref.length, m = hyp.length;
  const dp = Array.from({length:n+1}, ()=>Array(m+1).fill(0));
  const bt = Array.from({length:n+1}, ()=>Array(m+1).fill(null));
  for(let i=1;i<=n;i++){ dp[i][0]=i; bt[i][0]='D'; }
  for(let j=1;j<=m;j++){ dp[0][j]=j; bt[0][j]='I'; }
  for(let i=1;i<=n;i++){
    for(let j=1;j<=m;j++){
      const cost = ref[i-1]===hyp[j-1]?0:1;
      const choices = [
        [dp[i-1][j-1]+cost, cost===0?'M':'S'],
        [dp[i][j-1]+1, 'I'],
        [dp[i-1][j]+1, 'D']
      ];
      let best = choices[0];
      if(choices[1][0] < best[0]) best = choices[1];
      if(choices[2][0] < best[0]) best = choices[2];
      dp[i][j] = best[0];
      bt[i][j] = best[1];
    }
  }
  const ops=[];
  let i=n,j=m;
  while(i>0 || j>0){
    const op = bt[i][j];
    if(op==='M'){ ops.push(['M', ref[i-1], hyp[j-1]]); i--; j--; }
    else if(op==='S'){ ops.push(['S', ref[i-1], hyp[j-1]]); i--; j--; }
    else if(op==='I'){ ops.push(['I', '', hyp[j-1]]); j--; }
    else if(op==='D'){ ops.push(['D', ref[i-1], '']); i--; }
    else break;
  }
  ops.reverse();
  return ops;
}

function diffChars(user, correct){
  const ref = correct.toLowerCase().split('');
  const hyp = user.toLowerCase().split('');
  const ops = alignTokens(ref, hyp);
  const disp = correct.split('');
  let di = 0;
  let out = '';
  for(const [op, rt, ht] of ops){
    const ch = disp[di] || rt || ht;
    if(op==='M'){
      out += `<span class="ok">${ch}</span>`; di++;
    }else if(op==='S'){
      out += `<span class="wrong">${ch}</span>`; di++;
    }else if(op==='I'){
      out += `<span class="wrong">${ht}</span>`;
    }else if(op==='D'){
      out += `<span class="miss">_${rt}</span>`; di++;
    }
  }
  return out;
}

function diffWords(user, correct){
  const ref = normalizeSentence(correct).split(/\s+/);
  const hyp = normalizeSentence(user).split(/\s+/);
  const ops = alignTokens(ref, hyp);
  const disp = correct.trim().split(/\s+/);
  let di = 0;
  let out = [];
  for(const [op, rt, ht] of ops){
    const token = disp[di] || rt || ht;
    if(op==='M'){
      out.push(`<span class="ok">${token}</span>`); di++;
    }else if(op==='S'){
      out.push(`<span class="wrong">${token}</span>`); di++;
    }else if(op==='I'){
      out.push(`<span class="wrong">${ht}</span>`);
    }else if(op==='D'){
      out.push(`<span class="miss">_${rt}</span>`); di++;
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
    }else if(
      currentItem.type === 'type_from_meaning' ||
      currentItem.type === 'audio2en_input' ||
      currentItem.type === 'vi2en_mcq'
    ){
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
  setTimeout(showNext, revealDelay(currentItem.type));
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
