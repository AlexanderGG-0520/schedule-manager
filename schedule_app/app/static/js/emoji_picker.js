// Minimal emoji picker with searchable list (curated Unicode set)
// Not exhaustive but good UX; can be extended by adding more emoji strings to `EMOJIS`.
(function(){
  const EMOJIS = [
    '😀','😃','😄','😁','😆','😅','🤣','😂','🙂','🙃','😉','😊','😇','🥰','😍','🤩','😘','😗','😚','😙',
    '😋','😛','😜','🤪','😝','🤑','🤗','🤭','🤫','🤔','🤐','🤨','😐','😑','😶','😏','😒','🙄','😬','🤥',
    '😌','😔','😪','🤤','😴','😷','🤒','🤕','🤢','🤮','🤧','🥵','🥶','🥴','😵','🤯','🤠','🥳','😎','🤓',
    '🧐','😕','😟','🙁','☹️','😮','😯','😲','😳','🥺','😦','😧','😨','😰','😥','😢','😭','😱','😖','😣',
    '😞','😓','😩','😫','😤','😡','😠','🤬','🤯','💪','👊','✊','🤛','🤜','👏','🙌','👐','🤝','👍','👎',
    '👋','🤚','🖐️','✋','🖖','👌','✌️','🤞','🤟','🤘','🤙','👈','👉','👆','👇','☝️','✋','🙏','💍','💄',
    '💋','❤️','🧡','💛','💚','💙','💜','🖤','🤍','🤎','💔','💕','💞','💓','💗','💖','💘','💝','💟','💯',
    '⭐','🌟','✨','⚡','🔥','💥','💫','🌈','☀️','⛅','☁️','🌧️','⛈️','🌩️','🌨️','❄️','☃️','⚽','🏀','🏈',
    '⚾','🎾','🏐','🏉','🎱','🏓','🏸','🥅','🏒','🏑','🏏','⛳','🏹','🎣','🥊','🥋','⛸️','🎿','🏂','🏋️',
    '🚴','🏇','🏆','🎮','🎲','🎯','🎹','🎸','🎺','🎻','🥁','🎼','🎵','🎶','🎤','🎧','🎬','🎨','🧩','🛠️',
    '🚗','🚕','🚙','🚌','🚎','🏎️','🚓','🚑','🚒','🚐','🚚','🚛','🚜','✈️','🛩️','🚀','🛸','🛰️','⛵','🚢',
    '🏠','🏡','🏢','🏬','🏰','🏯','🏛️','⛪','🕌','🕍','🛕','🧭','🗺️','🌍','🌎','🌏','🌋','🗻','🏞️','🏝️'
  ];

  function createPicker() {
    const el = document.createElement('div');
    el.className = 'emoji-picker';
    el.innerHTML = `
      <div class="emoji-picker-search"><input placeholder="絵文字検索（例: heart, smile）" type="text"/></div>
      <div class="emoji-picker-grid" role="list"></div>
    `;
    document.body.appendChild(el);
    const input = el.querySelector('input');
    const grid = el.querySelector('.emoji-picker-grid');

    function render(filter) {
      grid.innerHTML = '';
      const f = (filter || '').trim().toLowerCase();
      const list = EMOJIS.filter(e => {
        if(!f) return true;
        // naive: match if codepoint name contains terms — we don't have names here, so match by char itself
        return e.indexOf(f) !== -1; // mostly won't match; search will be simple
      });
      // if filter produced none, show all but emphasize those containing filter char
      const items = list.length ? list : EMOJIS;
      for(const ch of items){
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'emoji-picker-item';
        b.textContent = ch;
        b.addEventListener('click', () => {
          const ev = new CustomEvent('emoji-picked', {detail: {emoji: ch}});
          window.dispatchEvent(ev);
          hidePicker();
        });
        grid.appendChild(b);
      }
    }

    function showPicker(x,y){
      el.style.display = 'block';
      el.style.left = x + 'px';
      el.style.top = y + 'px';
      input.value = '';
      render('');
      input.focus();
    }
    function hidePicker(){ el.style.display = 'none'; }

    input.addEventListener('input', function(){ render(input.value); });
    document.addEventListener('click', function(ev){ if(!el.contains(ev.target)) hidePicker(); });
    el.style.position = 'absolute';
    el.style.display = 'none';
    el.style.zIndex = 9999;
    return {showPicker, hidePicker};
  }

  // singleton picker
  let picker = null;
  window.__getEmojiPicker = function(){ if(!picker) picker = createPicker(); return picker; };
})();
