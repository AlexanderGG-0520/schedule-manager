document.addEventListener('DOMContentLoaded', function(){
  // Simple reaction chips component.
  // Usage: provide a container with data-event-id and a template of possible emojis.
  function initReactionContainer(container){
    const eventId = container.dataset.eventId;
    if(!eventId) return;
    const list = document.createElement('div');
    list.className = 'reaction-chips';
    container.appendChild(list);

    async function refresh(){
      const res = await fetch(`/api/v1/events/${eventId}/reactions`, {credentials: 'same-origin'});
      if(!res.ok) return;
      const j = await res.json();
      // j: { counts: {emoji: count...}, you: [emoji...] }
      list.innerHTML = '';
      const available = container.dataset.emojiList ? container.dataset.emojiList.split(',') : ['👍','❤️','👏','😄','🎉'];
      available.forEach(function(emoji){
        const count = j.counts[emoji] || 0;
        const you = j.you && j.you.indexOf(emoji) !== -1;
        const chip = document.createElement('button');
        chip.className = 'reaction-chip' + (you ? ' active' : '');
        chip.type = 'button';
        chip.innerHTML = `<span class="emoji">${emoji}</span> <span class="count">${count}</span>`;
        chip.addEventListener('click', async function(){
          chip.disabled = true;
          try{
            const resp = await fetch(`/api/v1/events/${eventId}/reactions`, {
              method: 'POST',
              credentials: 'same-origin',
              headers: {'Content-Type':'application/json'},
              body: JSON.stringify({emoji})
            });
            if(resp.ok){
              await refresh();
            }
          }catch(e){ console.error(e); }
          chip.disabled = false;
        });
        list.appendChild(chip);
      });
    }

    refresh();
  }

  document.querySelectorAll('.reactions-container').forEach(initReactionContainer);
  // repropose buttons
  document.querySelectorAll('.repropose-btn').forEach(function(btn){
    btn.addEventListener('click', async function(){
      const eventId = btn.dataset.eventId;
      if(!eventId) return;
      btn.disabled = true;
      try{
        const resp = await fetch(`/events/${eventId}/repropose`, {method:'POST', credentials:'same-origin'});
        if(resp.ok){
          const j = await resp.json();
          alert('再提案を作成しました: ' + j.id);
        } else {
          const txt = await resp.text();
          alert('再提案に失敗しました: ' + txt);
        }
      }catch(e){ console.error(e); alert('再提案エラー'); }
      btn.disabled = false;
    });
  });
});

// emoji picker integration: listen for picker events and open picker when trigger clicked
document.addEventListener('DOMContentLoaded', function(){
  // ensure picker exists
  const picker = window.__getEmojiPicker && window.__getEmojiPicker();
  document.querySelectorAll('.open-emoji-picker').forEach(function(btn){
    btn.addEventListener('click', function(ev){
      const rect = btn.getBoundingClientRect();
      const x = rect.left;
      const y = rect.bottom + window.scrollY;
      if(picker && picker.showPicker){
        picker.showPicker(x,y);
        // when emoji picked, forward to toggle endpoint for the nearest reactions-container
        const onPick = async function(e){
          const emoji = e.detail.emoji;
          // find nearest container
          const container = btn.closest('.reactions-controls-row')?.querySelector('.reactions-container');
          const eventId = container?.dataset?.eventId;
          if(!eventId) return;
          try{
            await fetch(`/api/v1/events/${eventId}/reactions`, {
              method: 'POST', credentials: 'same-origin', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({emoji})
            });
            // refresh
            container && container.dispatchEvent(new CustomEvent('refresh-reactions'));
          }catch(err){ console.error(err); }
          window.removeEventListener('emoji-picked', onPick);
        };
        window.addEventListener('emoji-picked', onPick);
      }
    });
  });
});
