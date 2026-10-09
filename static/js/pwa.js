(function () {
  var swUrl = document.documentElement.dataset.swUrl;
  var standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

  // Register the service worker (browsers only allow this on HTTPS or localhost)
  if ('serviceWorker' in navigator && swUrl) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register(swUrl, { scope: '/' }).catch(function (error) {
        console.warn('Service worker was not registered:', error);
      });
    });
  }

  // "Install app" button (Chrome, Edge and similar browsers)
  var installButton = document.getElementById('install-app');
  var deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    deferredPrompt = event;
    if (installButton && !standalone) { installButton.classList.remove('d-none'); }
  });

  if (installButton) {
    installButton.addEventListener('click', function () {
      if (!deferredPrompt) { return; }
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(function () {
        deferredPrompt = null;
        installButton.classList.add('d-none');
      });
    });
  }

  window.addEventListener('appinstalled', function () {
    if (installButton) { installButton.classList.add('d-none'); }
  });

  // iPhone / iPad have no install prompt, so show a short how-to once
  var hint = document.getElementById('ios-hint');
  var isIos = /iphone|ipad|ipod/i.test(window.navigator.userAgent);
  if (hint && isIos && !standalone) {
    var dismissed = false;
    try { dismissed = localStorage.getItem('ios-hint-dismissed') === '1'; } catch (e) { /* storage blocked */ }
    if (!dismissed) {
      hint.classList.remove('d-none');
      hint.querySelector('button').addEventListener('click', function () {
        hint.classList.add('d-none');
        try { localStorage.setItem('ios-hint-dismissed', '1'); } catch (e) { /* storage blocked */ }
      });
    }
  }
})();