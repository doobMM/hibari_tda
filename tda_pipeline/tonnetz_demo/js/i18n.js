/* i18n.js — KOR / ENG toggle */
(function () {
  var saved = localStorage.getItem('tz-lang') || 'en';
  if (saved === 'ko') document.body.classList.add('lang-ko');

  window.i18n = {
    toggle: function () {
      var isKo = document.body.classList.toggle('lang-ko');
      localStorage.setItem('tz-lang', isKo ? 'ko' : 'en');
    }
  };
})();
