// tda-nav.js — 3개 hibari TDA 시각화 간 상단 탭 네비게이션
// 각 페이지에 <div id="tda-nav" data-active="om|tonnetz|filtration"></div> + <script src=".../shared/nav.js" defer> 만 있으면 자동 주입.
(function () {
  'use strict';

  var TABS = [
    {
      id: 'om',
      href: 'hibari_dashboard/public/',
      long: 'OM Dashboard',
      short: 'OM',
      title: 'Overlap Matrix 편집 대시보드'
    },
    {
      id: 'tonnetz',
      href: 'tonnetz_demo/',
      long: 'Tonnetz Demo',
      short: 'Tonnetz',
      title: 'Tonnetz 격자 위 H1 cycle'
    },
    {
      id: 'filtration',
      href: 'filtration_viz/',
      long: 'Filtration Viz',
      short: 'Filtration',
      title: 'Simplex filtration 진행'
    }
  ];

  function resolveSiteRoot() {
    // currentScript가 defer 환경에선 null일 수 있으니 script 태그를 직접 탐색
    var scripts = document.getElementsByTagName('script');
    for (var i = scripts.length - 1; i >= 0; i--) {
      var src = scripts[i].src || '';
      if (src.indexOf('shared/nav.js') !== -1) {
        // .../shared/nav.js → .../shared/ → 한 단계 위 = site root
        var sharedDir = src.substring(0, src.lastIndexOf('/'));
        return sharedDir.substring(0, sharedDir.lastIndexOf('/') + 1);
      }
    }
    // fallback: 현재 페이지 기준으로 상대 경로 돌려줌 (빈 문자열)
    return '';
  }

  function buildNav(activeId) {
    var root = resolveSiteRoot();
    var nav = document.createElement('nav');
    nav.className = 'tda-nav';
    nav.setAttribute('aria-label', 'TDA 시각화 탭');

    var brand = document.createElement('span');
    brand.className = 'tda-nav__brand';
    brand.innerHTML = '<span class="tda-nav__brand-glyph" aria-hidden="true">◴</span><span>hibari · TDA</span>';
    nav.appendChild(brand);

    var ul = document.createElement('ul');
    ul.className = 'tda-nav__tabs';
    ul.setAttribute('role', 'tablist');

    TABS.forEach(function (tab) {
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.className = 'tda-nav__tab';
      a.href = root + tab.href;
      a.title = tab.title;
      a.setAttribute('role', 'tab');
      if (tab.id === activeId) {
        a.setAttribute('aria-current', 'page');
      }
      a.innerHTML =
        '<span class="tda-nav__tab-label-long">' + tab.long + '</span>' +
        '<span class="tda-nav__tab-label-short">' + tab.short + '</span>';
      li.appendChild(a);
      ul.appendChild(li);
    });

    nav.appendChild(ul);
    return nav;
  }

  function inject() {
    var mount = document.getElementById('tda-nav');
    if (!mount) return;
    var active = mount.getAttribute('data-active') || '';
    var nav = buildNav(active);
    mount.replaceWith(nav);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject);
  } else {
    inject();
  }
})();
