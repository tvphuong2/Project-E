export function bindAudioHotkeys(audio){
  document.addEventListener('keydown', (e)=>{
    if(e.key === '='){ e.preventDefault(); pauseAndRewind(audio, 3); }
    if(e.key === '-'){ e.preventDefault(); rewind(audio, 10); }
  });
}
export function pauseAndRewind(audio, s){ audio.pause(); audio.currentTime = Math.max(0, audio.currentTime - s); }
export function rewind(audio, s){ audio.currentTime = Math.max(0, audio.currentTime - s); }

export function $(sel, root=document){ return root.querySelector(sel); }
export function $all(sel, root=document){ return [...root.querySelectorAll(sel)]; }

export async function postJSON(url, body){
  const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if(!r.ok) throw new Error('HTTP '+r.status);
  return await r.json();
}

export function timeNowISO(){ return new Date().toISOString(); }
