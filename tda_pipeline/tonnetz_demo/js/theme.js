/**
 * theme.js — Three-theme switcher (Default / Zinc-Pink / Carbon-Gold)
 * Applies a CSS class on <body> before first paint to avoid flash.
 * Also switches the Tonnetz canvas colorscheme when available.
 * Exposes window.themeManager.apply(name) and .applyCanvas(name).
 */
(function () {
  var VALID = ['default', 'zinc', 'carbon'];

  /* Maps UI theme name → colorscheme name registered in color-schemes/*.js */
  var SCHEME_MAP = {
    'default': 'tonnetz-dark',
    'zinc':    'tonnetz-zinc',
    'carbon':  'tonnetz-carbon'
  };

  function apply(name) {
    if (VALID.indexOf(name) === -1) name = 'default';

    /* 1. CSS class on body (instantaneous — drives all CSS variable overrides) */
    document.body.classList.remove('theme-zinc', 'theme-carbon');
    if (name !== 'default') document.body.classList.add('theme-' + name);
    localStorage.setItem('tz-theme', name);

    /* 2. Sync swatch active states */
    document.querySelectorAll('.theme-swatch').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-theme') === name);
    });

    /* 3. Switch Tonnetz canvas colorscheme if already initialized */
    applyCanvas(name);
  }

  function applyCanvas(name) {
    if (VALID.indexOf(name) === -1) name = 'default';
    var schemeName = SCHEME_MAP[name];
    if (!schemeName) return;
    if (window.colorscheme && window.tonnetz) {
      try {
        colorscheme.setScheme(schemeName);
        tonnetz.draw(true);
      } catch (e) { /* not yet initialized — main.js will call applyCanvas() after init */ }
    }
  }

  /* Apply saved CSS theme immediately (no flash of default) */
  apply(localStorage.getItem('tz-theme') || 'default');

  window.themeManager = { apply: apply, applyCanvas: applyCanvas };
})();
