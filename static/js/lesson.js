import { postJSON, $, timeNowISO } from './common.js';

let session = null;
let timerId = null;

window.addEventListener('DOMContentLoaded', async ()=>{
  const audio = document.querySelector('audio');
  bindHotkeys(audio);

  // start 30' session from server
  session = await postJSON(location.pathname.replace('/lesson/', '/lesson/') + '/start', {});
  startCountdown(new Date(session.expires_at));

  $('#btnCheck').addEventListener('click', onCheck);
  $('#btnSaveWord').addEventListener('click', onSaveWord);
});

function bindHotkeys(audio){
  document.addEventListener('keydown', (e)=>{
    if(e.key === '='){
      e.preventDefault();
      if(audio.paused){
        audio.play(); // nếu đang dừng -> phát
      }else{
        audio.pause(); // nếu đang phát -> pause + lùi 3s
        audio.currentTime = Math.max(0, audio.currentTime - 3);
      }
    }
    if(e.key === '-'){
      e.preventDefault();
      audio.currentTime = Math.max(0, audio.currentTime - 10);
    }
  });
}

function startCountdown(expiresAt){
  const cd = $('#countdown');
  function tick(){
    const now = new Date();
    let sec = Math.max(0, Math.floor((expiresAt - now)/1000));
    const mm = String(Math.floor(sec/60)).padStart(2,'0');
    const ss = String(sec%60).padStart(2,'0');
    cd.textContent = `${mm}:${ss}`;
    if(sec <= 0){
      clearInterval(timerId);
      finalize(); // tự động chốt khi hết giờ
    }
  }
  tick();
  timerId = setInterval(tick, 1000);
}

async function onCheck(){
  if(!session){ alert('Chưa có session'); return; }
  const user_text = $('#transcript').value;
  try{
    const res = await postJSON(location.pathname + '/check', {
      session_id: session.session_id,
      user_text
    });
    renderResult(res);
  }catch(e){
    alert('Hết thời gian hoặc lỗi phiên.');
  }
}

function renderResult(res){
  const box = $('#result');
  box.innerHTML = '';
  const stats = res.stats;
  const meta = document.createElement('div');
  meta.className = 'card';
  meta.innerHTML = `
    <div><b>WER:</b> ${(stats.WER*100).toFixed(1)}% &nbsp; 
      <span class="badge">S ${stats.S}</span> 
      <span class="badge">D ${stats.D}</span> 
      <span class="badge">I ${stats.I}</span>
    </div>
    <div><b>Speed:</b> ${stats.speed_score.toFixed(3)}</div>
    <div class="small mono">N_ref=${stats.n_ref_words}, N_hyp=${stats.n_hyp_words}, duration=${Math.round(stats.duration_sec)}s</div>
  `;
  box.appendChild(meta);

  const spans = document.createElement('div');
  spans.className = 'card';
  (res.spans || []).forEach(s => {
    const el = document.createElement('span');
    el.className = 'hl ' + s.status;
    el.textContent = s.token;
    if(s.correct !== undefined){
      el.title = s.correct || '(thừa)';
    }
    spans.appendChild(el);
    spans.appendChild(document.createTextNode(' '));
  });
  box.appendChild(spans);
}

async function finalize(){
  if(!session) return;
  $('#btnCheck').disabled = true;

  const user_text = $('#transcript').value;
  try{
    const res = await postJSON(location.pathname + '/finalize', {
      session_id: session.session_id,
      user_text
    });
    // show answer
    $('#answerText').textContent = res.answer || '';
    $('#answerBox').style.display = 'block';
  }catch(e){
    console.error(e);
    alert('Không thể finalize phiên.');
  }finally{
    session = null; // kết thúc phiên
  }
}

async function onSaveWord(){
  const ta = $('#transcript');
  const start = ta.selectionStart, end = ta.selectionEnd;
  const selected = ta.value.slice(start, end).trim();
  if(!selected){ alert('Hãy bôi đen một từ trong vùng nhập.'); return; }
  const word = selected.split(/\s+/)[0];
  const res = await postJSON('/vocab/save_selection', { word });
  alert(res.message || 'Đã lưu từ');
}
