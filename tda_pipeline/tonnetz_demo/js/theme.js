/**
 * theme.js — Three-theme switcher (Default / Zinc-Pink / Carbon-Gold)
 * Applies a class on <body> before first paint to avoid flash.
 * Exposes window.themeManager.apply(name).
 */
(function () {
  var VALID = ['default', 'zinc', 'carbon'];

  function apply(name) {
    if (VALID.indexOf(name) === -1) name = 'default';
    document.body.classList.remove('theme-zinc', 'theme-carbon');
    if (name !== 'default') document.body.classList.add('theme-' + name);
    localStorage.setItem('tz-theme', name);

    // Sync swatch active states (safe to call before DOM ready)
    document.querySelectorAll('.theme-swatch').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-theme') === name);
    });
  }

  // Apply saved theme immediately (avoids flash of default)
  apply(localStorage.getItem('tz-theme') || 'default');

  window.themeManager = { apply: apply };
})();
