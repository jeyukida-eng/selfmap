(() => {
  const button = document.getElementById('install-app');
  const dialog = document.getElementById('install-help');
  const instructions = document.getElementById('install-instructions');
  const standalone = window.matchMedia('(display-mode: standalone)');
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  let installPrompt = null;
  const updateButton = () => {
    button.hidden = standalone.matches || navigator.standalone === true;
  };
  updateButton();
  standalone.addEventListener('change', updateButton);
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    installPrompt = event;
    updateButton();
  });
  window.addEventListener('appinstalled', () => {
    installPrompt = null;
    button.hidden = true;
  });
  button.addEventListener('click', async () => {
    if (installPrompt) {
      const prompt = installPrompt;
      installPrompt = null;
      await prompt.prompt();
      const choice = await prompt.userChoice;
      if (choice.outcome === 'accepted') button.hidden = true;
      return;
    }
    instructions.textContent = isIOS
      ? '① Safari에서 이 페이지를 열어 주세요.\n② 공유 버튼(위로 향한 화살표)을 누르세요.\n③ “홈 화면에 추가” → “추가”를 누르세요.\n\n다음부터 홈 화면의 제육이다 아이콘으로 열 수 있어요.'
      : '① Chrome 또는 삼성 인터넷에서 이 페이지를 열어 주세요.\n② 브라우저 메뉴(⋮ 또는 ≡)를 누르세요.\n③ “앱 설치” 또는 “홈 화면에 추가”를 선택해 주세요.\n\n카카오톡 안에서 열었다면 먼저 “다른 브라우저로 열기”를 선택해 주세요.';
    dialog.showModal();
  });
  const note = document.getElementById('connection-note');
  const updateConnection = () => { note.hidden = navigator.onLine; };
  window.addEventListener('online', updateConnection);
  window.addEventListener('offline', updateConnection);
  updateConnection();
  document.querySelector('.cta').addEventListener('click', event => {
    if (!navigator.onLine) {
      event.preventDefault();
      note.hidden = false;
    }
  });
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('./sw.js', { scope: './', updateViaCache: 'none' })
        .catch(error => console.warn('앱 준비를 완료하지 못했습니다.', error));
    });
  }
})();
