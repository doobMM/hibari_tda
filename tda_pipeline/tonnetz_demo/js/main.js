var canvas, ctx, noteLabels, triadLabels;

$(function(){
  canvas = document.getElementById("canvas");
  ctx = canvas.getContext("2d");
  noteLabels = document.getElementById("note-labels");
  triadLabels = document.getElementById("triad-labels");
  $(triadLabels).hide();

  storage.init();
  colorscheme.init('tonnetz-dark');   /* dark canvas as default */
  audio.init();
  tonnetz.init();
  midi.init();
  keyboard.init('piano');

  // Load TDA data (barcode + overlap matrix)
  if (window.hibariData) hibariData.init();

  // Expose tonnetz globally so midifile.js can call noteOn/noteOff
  window.tonnetz = tonnetz;

  $('#tonnetz').mousewheel(function(event) {
    tonnetz.setDensity(tonnetz.density - event.deltaY);
    return false;
  });
  $(window).keypress(function(event) {
    if (somethingHasFocus()) return;

    var c = String.fromCharCode(event.which);
    if (c == '+') {
      tonnetz.setDensity(tonnetz.density - 2);
    } else if (c == '-') {
      tonnetz.setDensity(tonnetz.density + 2);
    }
  });

  // Rate slider
  $('#rateSlider').on('input change', function() {
    var rate = parseFloat($(this).val());
    $('#rateValue').text(rate.toFixed(1));
    if (window.hibariData) hibariData.applyRate(rate);
  });

  // Redraw canvases when the TDA tab becomes visible
  $('#navbar a[data-toggle="tab"]').on('shown.bs.tab', function() {
    if ($(this).attr('href') === '#tda' && window.hibariData) {
      setTimeout(function() {
        hibariData.renderBarcodeChart();
        hibariData.renderOverlapHeatmap();
      }, 50);
    }
  });

  // Overlap matrix playback cursor — update ~10fps
  setInterval(function() {
    if (typeof Tone === 'undefined') return;
    var dur = window._midiDuration || 0;
    if (dur <= 0 || Tone.Transport.state !== 'started') return;
    var frac = Tone.Transport.seconds / dur;
    if (window.hibariData) hibariData.updatePlaybackCursor(frac);
  }, 100);

  $('#navbar a[data-toggle="tab"]').on('shown.bs.tab', function() {
    if ($(this).attr('href') != "#")
      $('#tabs').collapse('show');
      collapseNav();
  });

  $('#navbar a[data-toggle="tab"]').click(function() {
    if ($(this).parent().hasClass('active')) {
      $('#tabs').collapse('hide');
    }
  });

  $('.tab-link').click(function(event) {
    event.preventDefault();
    var href = $(this).attr('href');
    $('#navbar a[data-toggle="tab"][href="' + href + '"]').tab('show');
  });

  $('#tabs').on('hidden.bs.collapse', noTab);
  $('#tonnetz').click(collapseNavAndTabs);
  $('.navbar-brand').click(function(event) {
    event.preventDefault();
    collapseNavAndTabs();
  });

  $('#panic').click(function() { tonnetz.panic(); });
  $('#enable-sustain').click(function() { tonnetz.toggleSustainEnabled(); });
  $('#showCycles').change(function() {
    tonnetz.cyclesVisible = $(this).is(':checked');
    tonnetz.draw(true);
  });

  $('#show-note-names').click(function() { $(noteLabels).toggle(); });
  $('#show-triad-names').click(function() { $(triadLabels).toggle(); });
  $('#show-unit-cell').click(function() { tonnetz.toggleUnitCell(); });
  $('#ghost-duration').on('input change propertychange paste', function() {
    if(!tonnetz.setGhostDuration($(this).val())) {
      $(this).closest('.form-group').addClass('has-error');
    } else {
      $(this).closest('.form-group').removeClass('has-error');
    }
  });
  $('input[type=radio][name=layout]').change(function() {
    tonnetz.setLayout($(this).val());
  });

  $('#interval-overlay').on('click', '.int-btn', function() {
    $('#interval-overlay .int-btn').removeClass('active');
    $(this).addClass('active');
    var parts = $(this).data('ab').split(',');
    tonnetz.setIntervals(parseInt(parts[0], 10), parseInt(parts[1], 10));
  });

  // ── Transform overlay ────────────────────────────────────────────
  // Group 1: Neo-Riemannian P/L/R/N/S/H
  $('#transform-overlay').on('click', '.plr-btn', function() {
    if (window.transforms) window.transforms.applyPLR($(this).data('op'));
  });

  // Group 2: Transpositions
  $('#txM12').click(function() { if (window.transforms) window.transforms.setTranspose(window.transforms.offset - 12); });
  $('#txM7').click(function()  { if (window.transforms) window.transforms.setTranspose(window.transforms.offset - 7);  });
  $('#txM1').click(function()  { if (window.transforms) window.transforms.setTranspose(window.transforms.offset - 1);  });
  $('#txReset').click(function(){ if (window.transforms) window.transforms.reset(); });
  $('#txP1').click(function()  { if (window.transforms) window.transforms.setTranspose(window.transforms.offset + 1);  });
  $('#txP7').click(function()  { if (window.transforms) window.transforms.setTranspose(window.transforms.offset + 7);  });
  $('#txP12').click(function() { if (window.transforms) window.transforms.setTranspose(window.transforms.offset + 12); });

  // Group 3: Inversions — generate 12 axis buttons dynamically
  (function() {
    var axisRow = document.getElementById('txAxisRow');
    if (!axisRow) return;
    var NOTE_NAMES = ['C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B'];
    for (var i = 0; i < 12; i++) {
      (function(axis) {
        var btn = document.createElement('button');
        btn.id = 'txAxis' + axis;
        btn.className = 'tx-btn tx-axis';
        btn.textContent = NOTE_NAMES[axis];
        btn.title = 'Invert around ' + NOTE_NAMES[axis] + ' axis (I_' + axis + ')';
        btn.addEventListener('click', function() {
          if (window.transforms) window.transforms.setInvert(true, axis);
        });
        axisRow.appendChild(btn);
      })(i);
    }
  })();

  $('#txInvToggle').click(function() {
    if (window.transforms) window.transforms.setInvert(!window.transforms.invEnabled);
  });

  $('input[type=radio][name=kbd-layout]').change(function() {
    keyboard.layout = $(this).val();
    tonnetz.panic();
  });

  // Language tabs — two always-visible buttons (ENG / KOR)
  $('#langTabs').on('click', '.lang-tab', function() {
    if (window.i18n) window.i18n.setLang($(this).data('lang'));
  });

  // Theme swatch picker — Default / Zinc-Pink / Carbon-Gold
  $('#themePicker').on('click', '.theme-swatch', function() {
    if (window.themeManager) window.themeManager.apply($(this).data('theme'));
  });

  // Overlay collapse buttons
  $('#txCollapseBtn').click(function() {
    var overlay = document.getElementById('transform-overlay');
    var collapsed = overlay.classList.toggle('tz-collapsed');
    this.textContent = collapsed ? '+' : '−';
  });
  $('#intCollapseBtn').click(function() {
    var overlay = document.getElementById('interval-overlay');
    var collapsed = overlay.classList.toggle('tz-collapsed');
    this.textContent = collapsed ? '+' : '−';
  });

  /* Sync Tonnetz canvas colorscheme with persisted theme (theme.js runs
     before colorscheme/tonnetz are initialized, so we apply canvas here) */
  if (window.themeManager) {
    themeManager.applyCanvas(localStorage.getItem('tz-theme') || 'default');
  }

  // ── Mobile: auto-collapse both overlays so the canvas is unobstructed ──
  if (window.innerWidth < 600) {
    var txOv  = document.getElementById('transform-overlay');
    var intOv = document.getElementById('interval-overlay');
    var txColBtn  = document.getElementById('txCollapseBtn');
    var intColBtn = document.getElementById('intCollapseBtn');
    if (txOv  && !txOv.classList.contains('tz-collapsed'))  {
      txOv.classList.add('tz-collapsed');
      if (txColBtn)  txColBtn.textContent  = '+';
    }
    if (intOv && !intOv.classList.contains('tz-collapsed')) {
      intOv.classList.add('tz-collapsed');
      if (intColBtn) intColBtn.textContent = '+';
    }
  }

  $('[data-toggle="tooltip"]').tooltip();

  // Open links with data-popup="true" in a new window.
  $('body').on('click', 'a[data-popup]', function(event) {
    window.open($(this)[0].href);
    event.preventDefault();
  });
});

function collapseNav() {
  if($('.navbar-toggle').is(':visible') && $('.navbar-collapse').hasClass('in')) {
    $('.navbar-toggle').click();
  }
}

function collapseNavAndTabs() {
  $('#tabs').collapse('hide');
  collapseNav();
}

function noTab() {
  $('#dummy-tab').tab('show');
}

function somethingHasFocus() {
  return $(':focus').is('input, select, button, textarea');
}

function showAlert(text, type) {
  var a = $('<div class="alert alert-'+type+' alert-dismissible fade" role="alert">' +
           '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
           '<span aria-hidden="true">×</span></button></div>');
  a.append(document.createTextNode(text));
  $('#messages').append(a);
  a.addClass('in');

  var numMessages = $('#messages').children().length;
  if (numMessages > 3) {
    $('#messages').children().slice(0, numMessages-3).alert('close');
  }
}

function showWarning(text) { showAlert(text, 'warning'); }
function showError(text) { showAlert(text, 'danger'); }
function showSuccess(text) { showAlert(text, 'success'); }
