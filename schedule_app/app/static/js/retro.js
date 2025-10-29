document.addEventListener('DOMContentLoaded', function(){
  function initRetro(container){
    const eventId = container.dataset.eventId;
    if(!eventId) return;
    const form = container.querySelector('.retro-form');
    const submit = container.querySelector('.retro-submit');
    const viewBtn = container.querySelector('.retro-view');
    const feedback = container.querySelector('.retro-feedback');
    const list = container.querySelector('.retro-list');
    const summary = container.querySelector('.retro-summary');

    async function postRetro(){
  const q1 = form.querySelector('textarea[name="q1"]').value.trim();
  const q2 = form.querySelector('textarea[name="q2"]').value.trim();
  const q3 = form.querySelector('textarea[name="q3"]').value.trim();
  const next_action = form.querySelector('input[name="next_action"]').value.trim();
  const payload = {q1, q2, q3, next_action};
      submit.disabled = true;
      feedback.textContent = '送信中…';
      try{
        const resp = await fetch(`/api/v1/events/${eventId}/retro`, {
          method: 'POST', credentials: 'same-origin', headers: {'Content-Type':'application/json'},
          body: JSON.stringify(payload)
        });
        if(resp.ok){
          const j = await resp.json();
          feedback.textContent = '送信しました。';
          // clear inputs
          form.querySelector('textarea[name="q1"]').value = '';
          form.querySelector('textarea[name="q2"]').value = '';
          form.querySelector('input[name="next_action"]').value = '';
          // if task created, show quick notice
          if(j.task_id) feedback.textContent += ' 次アクションをタスクとして登録しました。';
          // refresh summary
          fetchSummary();
        } else {
          const txt = await resp.text();
          feedback.textContent = '送信に失敗しました: ' + txt;
        }
      }catch(e){ feedback.textContent = '送信エラー'; console.error(e); }
      submit.disabled = false;
    }

    async function fetchRetros(){
      list.style.display = 'block';
      list.innerHTML = '読み込み中…';
      try{
        const resp = await fetch(`/api/v1/events/${eventId}/retro`, {credentials:'same-origin'});
        if(!resp.ok){ list.innerHTML = '取得に失敗しました'; return; }
        const arr = await resp.json();
        if(!arr.length){ list.innerHTML = '<p>過去の振り返りはありません</p>'; return; }
        const ul = document.createElement('ul');
        arr.forEach(function(r){
          const li = document.createElement('li');
          li.innerHTML = `<strong>${r.created_at} (user ${r.user_id})</strong><div>${(r.q1||'')}</div><div>${(r.q2||'')}</div><div>次: ${(r.next_action||'')}</div>`;
          ul.appendChild(li);
        });
        list.innerHTML = '';
        list.appendChild(ul);
      }catch(e){ list.innerHTML = '取得エラー'; console.error(e); }
    }

    async function fetchSummary(){
      try{
        const resp = await fetch(`/api/v1/events/${eventId}/retro`, {credentials:'same-origin'});
        if(!resp.ok){ summary.innerHTML = ''; return; }
        const arr = await resp.json();
        // aggregate next_actions top 3
        const counts = {};
        arr.forEach(r => { if(r.next_action){ counts[r.next_action] = (counts[r.next_action]||0) + 1; } });
        const entries = Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,5);
        if(entries.length===0){ summary.innerHTML = '<small>まだ次アクションは登録されていません</small>'; return; }
        const ul = document.createElement('ul'); ul.style.margin='0'; ul.style.padding='0';
        entries.forEach(e=>{ const li = document.createElement('li'); li.style.listStyle='none'; li.textContent = `${e[0]} (${e[1]})`; ul.appendChild(li); });
        summary.innerHTML = '<strong>人気の次アクション</strong>';
        summary.appendChild(ul);
      }catch(e){ console.error(e); }
    }

    // initial summary fetch
    fetchSummary();

    submit.addEventListener('click', postRetro);
    viewBtn.addEventListener('click', fetchRetros);
  }
  document.querySelectorAll('.retro-widget').forEach(initRetro);
});
