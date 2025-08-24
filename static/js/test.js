import { postJSON, $ } from './common.js';

let session = null;
let queue = [];
let nextRound = [];
let wrongCounts = {};
let currentItem = null;

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
    wrap.innerHTML = `<div><b>[MCQ]</b> Dịch sang tiếng Anh: <i>${it.prompt_vi}</i></div>`;
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
    wrap.innerHTML = `<div><b>[Gõ từ]</b> Viết đúng từ tiếng Anh cho nghĩa: <i>${it.prompt_vi}</i></div>`;
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
  alert('Hoàn tất. Nhãn: ' + JSON.stringify(res.label_summary));
  document.body.classList.remove('testing');
  $('#startCard').classList.remove('hidden');
  const quiz = $('#quiz');
  quiz.classList.add('hidden');
  quiz.innerHTML = '';
}
