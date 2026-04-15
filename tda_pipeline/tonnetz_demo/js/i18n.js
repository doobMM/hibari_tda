/* i18n.js — KOR / ENG two-tab switcher */
(function () {
  var saved = localStorage.getItem('tz-lang') || 'en';
  if (saved === 'ko') document.body.classList.add('lang-ko');

  window.i18n = {
    setLang: function (lang) {
      if (lang === 'ko') {
        document.body.classList.add('lang-ko');
      } else {
        document.body.classList.remove('lang-ko');
      }
      localStorage.setItem('tz-lang', lang);
    },
    toggle: function () {
      var isKo = document.body.classList.toggle('lang-ko');
      localStorage.setItem('tz-lang', isKo ? 'ko' : 'en');
    }
  };
})();
