var canvas, ctx, noteLabels, triadLabels;

$(function(){
  canvas = document.getElementById("canvas");
  ctx = canvas.getContext("2d");
  noteLabels = document.getElementById("note-labels");
  triadLabels = document.getElementById("triad-labels");
  $(triadLabels).hide();

  storage.init();
  colorscheme.init('default');
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

  $('#intervalPreset').change(function() {
    var parts = $(this).val().split(',');
    tonnetz.setIntervals(parseInt(parts[0], 10), parseInt(parts[1], 10));
  });
  $('input[type=radio][name=kbd-layout]').change(function() {
    keyboard.layout = $(this).val();
    tonnetz.panic();
  });

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
