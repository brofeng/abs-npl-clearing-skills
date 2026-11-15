/* =====================================================================
   NPL ABS WORKBENCH · V3.1 "CREDIT TAPE"
   Behaviour layer:
   - ink top bar + mobile index
   - 74-deal recovery tape, hover/click -> report
   - ECharts figures that respond to the variety / year slice
   - dynamic insights, slice summary, clear controls
   - clickable bank variety slices
   - report viewer returns to the same scroll position
   ===================================================================== */
(function () {
  'use strict';

  var FONT = '"Segoe UI","Microsoft YaHei UI","Microsoft YaHei","PingFang SC",sans-serif';
  var BC = { '中信银行': '#175CD3', '招商银行': '#B54708', '建设银行': '#067647', '兴业银行': '#6941C6', '农业银行': '#D92D20' };
  var BSHORT = { '中信银行': '中信', '招商银行': '招商', '建设银行': '建设', '兴业银行': '兴业', '农业银行': '农行', '工商银行': '工行' };
  var VC = { '个人消费不良': '#F79009', '个人经营不良': '#D92D20', '住房抵押不良': '#067647', '信用卡不良': '#175CD3', '小微经营不良': '#6941C6', '个人经营性不良': '#D92D20' };
  var BANKS = ['中信银行', '招商银行', '建设银行', '兴业银行', '农业银行'];

  var REDUCED = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  var FULL = (typeof V3_FULL !== 'undefined' && Array.isArray(V3_FULL)) ? V3_FULL : [];
  var allRows = [];
  var chartMounts = [];
  var tapeEl = null;
  var origInsightsHTML = '';
  var origTakeawaysHTML = '';
  var kpiRaf = null;
  var ROW_BY_NAME = {};
  var yearPlayTimer = null;

  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function isNum(v) { return typeof v === 'number' && !isNaN(v); }
  function median(arr) {
    var a = arr.filter(isNum).sort(function (x, y) { return x - y; });
    if (!a.length) return null;
    var m = a.length >> 1;
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  }
  function sum(arr) { return arr.reduce(function (a, b) { return a + (isNum(b) ? b : 0); }, 0); }
  function pct(v) { return (v == null || isNaN(v)) ? '—' : (v * 100).toFixed(1) + '%'; }
  function x2(v) { return (v == null || isNaN(v)) ? '—' : Number(v).toFixed(2) + 'x'; }
  function pp(v) { return (v == null || isNaN(v)) ? '—' : ((v - 1) * 100).toFixed(1) + 'pp'; }
  function bankColor(b) { return BC[b] || '#667085'; }
  function catColor(v) { return VC[v] || '#667085'; }
  function barGradient(c1, c2, vertical) {
    return new window.echarts.graphic.LinearGradient(0, 0, vertical ? 0 : 1, vertical ? 1 : 0, [
      { offset: 0, color: c1 }, { offset: 1, color: c2 }
    ]);
  }
  function firstNonEmptySeries(opt) {
    if (!opt || !opt.series) return null;
    for (var i = 0; i < opt.series.length; i++) {
      if (opt.series[i].data && opt.series[i].data.length) return opt.series[i];
    }
    return opt.series[0] || null;
  }
  function addQuadrant(opt, xs, ys, xFmt, yFmt) {
    var mx = median(xs), my = median(ys);
    if (mx == null || my == null) return;
    var first = firstNonEmptySeries(opt);
    if (!first) return;
    var lineStyle = { color: '#98A2B3', type: 'dashed', width: 1 };
    var label = { color: '#667085', fontSize: 9.5, backgroundColor: 'rgba(255,255,255,.86)', padding: [2, 3] };
    var data = [
      { xAxis: +mx.toFixed(2), label: { formatter: '中位 ' + xFmt(mx), position: 'insideEndBottom' } },
      { yAxis: +my.toFixed(2), label: { formatter: '中位 ' + yFmt(my), position: 'insideEndTop' } }
    ];
    if (first.markLine && first.markLine.data) {
      first.markLine.data = first.markLine.data.concat(data);
    } else {
      first.markLine = { silent: true, symbol: 'none', animation: false, lineStyle: lineStyle, label: label, data: data };
    }
  }
  function isOpen(r) { return r.st !== 'settled'; }

  function emptySlice() {
    return { varieties: [], years: [], tenor: [], sec: [], ach: [], state: [], buyback: [] };
  }
  function slice() {
    var s = window.__slice;
    if (!s || !Array.isArray(s.varieties)) { s = emptySlice(); window.__slice = s; }
    ['tenor', 'sec', 'ach', 'state', 'buyback'].forEach(function (k) { if (!Array.isArray(s[k])) s[k] = []; });
    return s;
  }
  function sliceActive() {
    var s = slice();
    return !!(s.varieties.length || s.years.length || s.tenor.length || s.sec.length || s.ach.length || s.state.length || s.buyback.length);
  }
  function tenorOf(r) {
    if (!isNum(r.life)) return '';
    return r.life < 12 ? 'lt12' : (r.life <= 24 ? '12to24' : 'ge24');
  }
  function secOf(r) {
    if (!isNum(r.s)) return '';
    return r.s < 0.10 ? 'lt10' : (r.s <= 0.20 ? '10to20' : 'ge20');
  }
  function achOf(r) {
    if (!isNum(r.a)) return '';
    return r.a < 0.95 ? 'lt95' : (r.a <= 1.05 ? '95to105' : 'gt105');
  }
  function labelOf(k, v) {
    var map = {
      tenor: { lt12: '<12月', '12to24': '12–24月', ge24: '≥24月' },
      sec: { lt10: '<10%', '10to20': '10–20%', ge20: '≥20%' },
      ach: { lt95: '<95%', '95to105': '95–105%', gt105: '>105%' },
      state: { settled: '已清算', open: '存续' },
      buyback: { yes: '有回购', no: '无回购' }
    };
    return (map[k] && map[k][v]) || v;
  }
  function sliceLabel(sep) {
    var s = slice(), a = [];
    if (s.varieties.length) a.push(s.varieties.map(function (v) { return String(v).replace('不良', ''); }).join('/'));
    if (s.years.length) a.push(s.years.join('/'));
    ['tenor', 'sec', 'ach', 'state', 'buyback'].forEach(function (k) {
      if (s[k].length) a.push(s[k].map(function (v) { return labelOf(k, v); }).join('/'));
    });
    return a.join(sep || ' · ');
  }
  function rowMatch(r) {
    if (!r) return true;
    var s = slice();
    if (s.varieties.length && s.varieties.indexOf(r.v) < 0) return false;
    if (s.years.length && s.years.indexOf(String(r.y)) < 0) return false;
    if (s.tenor.length && s.tenor.indexOf(tenorOf(r)) < 0) return false;
    if (s.sec.length && s.sec.indexOf(secOf(r)) < 0) return false;
    if (s.ach.length && s.ach.indexOf(achOf(r)) < 0) return false;
    if (s.state.length && s.state.indexOf(r.st) < 0) return false;
    if (s.buyback.length && s.buyback.indexOf(r.buyback) < 0) return false;
    return true;
  }
  function filteredRows() { return allRows.filter(rowMatch); }

  /* ================= 1 · TOP BAR ================= */
  function topbarSvg(name) {
    var map = {
      search: '<circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.6-3.6"></path>',
      print: '<path d="M6 9V3h12v6"></path><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="7" rx="1"></rect>',
      guide: '<circle cx="12" cy="12" r="9"></circle><path d="m15.5 8.5-2.1 5-5 2.1 2.1-5 5-2.1Z"></path>',
      menu: '<path d="M3 6h18M3 12h18M3 18h18"></path>',
      export: '<path d="M12 3v12"></path><path d="m7 10 5 5 5-5"></path><path d="M4 21h16"></path>',
      night: '<path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.5 6.5 0 0 0 9.8 9.8Z"></path>',
      link: '<path d="M10 13a5 5 0 0 0 7.1 0l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"></path><path d="M14 11a5 5 0 0 0-7.1 0l-2 2A5 5 0 0 0 12 20.1l1.1-1.1"></path>'
    };
    return '<svg viewBox="0 0 24 24" aria-hidden="true">' + (map[name] || '') + '</svg>';
  }

  function buildTopbar() {
    if ($('#v3-top')) return;
    var el = document.createElement('div');
    el.id = 'v3-top';
    el.innerHTML =
      '<div class="v3-brand"><span class="v3-mark">NPL</span>' +
      '<span class="v3-title">不良ABS 多行工作台<small>74 单 · 5 家银行 · 数据截至 2026-10-31</small></span></div>' +
      '<div id="v3-crumb">工作台<i>/</i><b>各行对比</b></div>' +
      '<span id="v3-pill" hidden></span>' +
      '<div class="v3-actions">' +
      '<button class="v3-btn" id="v3-search" type="button" title="搜索项目 / 银行 / 品种">' + topbarSvg('search') + '<span>搜索</span><kbd>Ctrl K</kbd></button>' +
      '<button class="v3-btn" id="v3-export" type="button" title="导出当前切片">' + topbarSvg('export') + '<span>导出</span></button>' +
      '<button class="v3-btn" id="v3-print" type="button" title="打印当前视图">' + topbarSvg('print') + '<span>打印</span></button>' +
      '<button class="v3-btn" id="v3-guide" type="button" title="快速导览">' + topbarSvg('guide') + '<span>导览</span></button>' +
      '<button class="v3-btn icon-only" id="v3-night" type="button" aria-label="切换夜盘模式" title="夜盘模式">' + topbarSvg('night') + '</button>' +
      '<button class="v3-btn icon-only" id="v3-menu" type="button" aria-label="打开目录">' + topbarSvg('menu') + '</button>' +
      '<div id="v3-export-menu" class="v3-menu-pop" hidden>' +
      '<button data-act="csv" type="button">CSV · 当前切片</button>' +
      '<button data-act="png" type="button">PNG · 全部图表</button>' +
      '<button data-act="pdf" type="button">PDF / 打印</button>' +
      '<button data-act="share" type="button">复制切片链接</button>' +
      '</div>' +
      '</div>';
    document.body.insertBefore(el, document.body.firstChild);

    var scrim = document.createElement('div');
    scrim.id = 'v3-scrim';
    document.body.appendChild(scrim);

    $('#v3-search').addEventListener('click', function () { var b = $('#cmdk-trigger'); if (b) b.click(); });
    $('#v3-print').addEventListener('click', function () { var b = $('#print-view'); if (b) b.click(); });
    $('#v3-guide').addEventListener('click', function () { var b = $('#tour-start'); if (b) b.click(); });
    $('#v3-menu').addEventListener('click', function () { document.body.classList.toggle('v3-nav-open'); });

    var exp = $('#v3-export'), menu = $('#v3-export-menu');
    if (exp && menu) {
      exp.addEventListener('click', function (e) {
        e.preventDefault(); e.stopPropagation();
        menu.hidden = !menu.hidden;
      });
      menu.addEventListener('click', function (e) {
        var b = e.target.closest('[data-act]');
        if (!b) return;
        e.preventDefault(); menu.hidden = true;
        if (b.dataset.act === 'csv') exportSliceCsv();
        if (b.dataset.act === 'png') exportSlicePng();
        if (b.dataset.act === 'pdf') window.print();
        if (b.dataset.act === 'share') copySliceLink();
      });
      document.addEventListener('click', function (e) {
        if (!e.target.closest('#v3-export') && !e.target.closest('#v3-export-menu')) menu.hidden = true;
      });
      document.addEventListener('keydown', function (e) { if (e.key === 'Escape') menu.hidden = true; });
    }

    var night = $('#v3-night');
    if (night) {
      var saved = '0';
      try { saved = localStorage.getItem('v3-night') || '0'; } catch (e) {}
      var setNight = function (on) {
        document.body.classList.toggle('night-desk', !!on);
        night.classList.toggle('on', !!on);
        night.setAttribute('aria-pressed', on ? 'true' : 'false');
        try { localStorage.setItem('v3-night', on ? '1' : '0'); } catch (e) {}
      };
      setNight(saved === '1');
      night.addEventListener('click', function () { setNight(!document.body.classList.contains('night-desk')); });
    }
    scrim.addEventListener('click', function () { document.body.classList.remove('v3-nav-open'); });
    $$('nav a').forEach(function (a) { a.addEventListener('click', function () { document.body.classList.remove('v3-nav-open'); }); });

    var main = $('main');
    if (main && 'MutationObserver' in window) {
      new MutationObserver(updateCrumb).observe(main, { attributes: true, attributeFilter: ['class'], subtree: true });
    }
    updateCrumb();
  }

  function updateCrumb() {
    var v = $('.view:not(.hidden)');
    var label = '各行对比';
    if (v) {
      if (v.id === 'view-table') label = sliceActive() ? ('切片内 ' + filteredRows().length + ' 单明细') : '74 单明细';
      else if (v.id.indexOf('view-bank-') === 0) {
        var key = v.id.replace(/^view-/, '');
        var a = $('nav a.nv[data-view="' + key + '"]');
        label = a ? (a.textContent || '').replace(/（\d+）\s*$/, '').trim() : key.replace('bank-', '');
      }
    }
    var box = $('#v3-crumb b');
    if (box) box.textContent = label;
  }

  /* ================= 2 · TAPE ================= */
  function buildTape() {
    if ($('#v3-tape')) { tapeEl = $('#v3-tape'); return; }
    var hero = $('#view-cmp header.hero');
    if (!hero || !allRows.length) return;
    var rs = allRows.map(function (r) { return r.r; }).filter(isNum).sort(function (a, b) { return a - b; });
    if (!rs.length) return;
    var med = rs[Math.floor(rs.length / 2)];
    var max = rs[rs.length - 1] || 0.01;
    var settled = allRows.filter(function (r) { return !isOpen(r); }).length;
    var open = allRows.length - settled;

    var ticks = allRows.map(function (r, i) {
      var v = isNum(r.r) ? r.r : 0;
      var h = Math.max(4, Math.round(6 + (v / max) * 48));
      var cls = 'v3-tick' + (isOpen(r) ? ' open' : '');
      return '<button type="button" class="' + cls + '" style="--h:' + h + 'px;--c:' + bankColor(r.b) + ';--d:' + Math.min(i * 7, 500) + 'ms" ' +
        'data-name="' + esc(r.n) + '" data-bank="' + esc(r.b) + '" data-variety="' + esc(r.v) + '" data-year="' + esc(r.y) + '" data-date="' + esc(r.d) + '" ' +
        'data-r="' + (r.r == null ? '' : r.r) + '" data-a="' + (r.a == null ? '' : r.a) + '" data-dp="' + (r.dp == null ? '' : r.dp) + '" ' +
        'data-m="' + (r.m == null ? '' : r.m) + '" data-x="' + (r.x == null ? '' : r.x) + '" data-st="' + esc(r.st) + '" ' +
        'aria-label="' + esc(r.n + '，' + r.b + '，回收率 ' + pct(r.r)) + '"><i></i></button>';
    }).join('');

    var legend = BANKS.map(function (b) {
      var list = allRows.filter(function (r) { return r.b === b; });
      if (!list.length) return '';
      var vals = list.map(function (r) { return r.r; }).filter(isNum);
      return '<span class="v3-leg" style="--c:' + bankColor(b) + '"><i></i><b>' + esc(BSHORT[b] || b) + '</b><span>' +
        list.length + ' 单 · 中位 ' + pct(median(vals)) + '</span></span>';
    }).join('');

    var tape = document.createElement('div');
    tape.id = 'v3-tape';
    tape.innerHTML =
      '<div class="v3-tape-head"><div class="l"><b>组合回收带</b><span>按发行日排列 · 每根竖条 = 1 单</span></div>' +
      '<div class="r"><span id="v3-tape-count">全样本 ' + allRows.length + ' 单</span><span>中位回收 <em>' + pct(med) + '</em></span><span>' + settled + ' 已清算 · ' + open + ' 存续</span></div></div>' +
      '<div class="v3-tape-scroll"><div class="v3-tape-body" style="--med:' + Math.max(6, Math.round(6 + (med / max) * 48)) + 'px">' + ticks +
      '<div class="v3-tape-mid"><span>全样本中位 ' + pct(med) + '</span></div></div></div>' +
      '<div class="v3-tape-legend">' + legend + '<span class="v3-tape-note">虚线 = 全样本回收率中位 · 点按任一单查看报告</span></div>';
    hero.insertAdjacentElement('afterend', tape);
    tapeEl = tape;

    if (!REDUCED) {
      var dust = document.createElement('div');
      dust.className = 'v3-particles';
      dust.setAttribute('aria-hidden', 'true');
      for (var di = 0; di < 18; di++) {
        var dot = document.createElement('i');
        dot.className = 'v3-p';
        var ds = (Math.random() * 2.2 + 1.4).toFixed(1);
        dot.style.width = ds + 'px';
        dot.style.height = ds + 'px';
        dot.style.left = (Math.random() * 100).toFixed(1) + '%';
        dot.style.bottom = (-Math.random() * 18 - 4).toFixed(1) + 'px';
        dot.style.setProperty('--dx', ((Math.random() * 64 - 32).toFixed(0)) + 'px');
        dot.style.animationDuration = (Math.random() * 8 + 10).toFixed(1) + 's';
        dot.style.animationDelay = (-Math.random() * 16).toFixed(1) + 's';
        dust.appendChild(dot);
      }
      tape.appendChild(dust);
    }

    var tip = document.createElement('div');
    tip.id = 'v3-tip';
    document.body.appendChild(tip);

    function showTip(btn, e) {
      tip.innerHTML = '<div class="t">' + esc(btn.getAttribute('data-name')) + '</div>' +
        '<div class="s">' + esc(btn.getAttribute('data-bank')) + ' · ' + esc(btn.getAttribute('data-variety')) + ' · ' + esc(btn.getAttribute('data-date')) + '</div>' +
        '<div class="g"><span>回收率</span><b>' + pct(+btn.getAttribute('data-r')) + '</b><span>达成率</span><b>' + pct(+btn.getAttribute('data-a')) + '</b>' +
        '<span>处置费率</span><b>' + pct(+btn.getAttribute('data-dp')) + '</b><span>次级倍数</span><b>' + x2(+btn.getAttribute('data-m')) + '</b>' +
        '<span>次级XIRR</span><b>' + pct(+btn.getAttribute('data-x')) + '</b></div>' +
        '<span class="st ' + (btn.getAttribute('data-st') === 'settled' ? 'ok' : 'wait') + '">' + (btn.getAttribute('data-st') === 'settled' ? '已清算' : '存续') + '</span>';
      tip.classList.add('show');
      moveTip(e);
    }
    function moveTip(e) {
      if (!e) return;
      var pad = 14, w = tip.offsetWidth || 240, h = tip.offsetHeight || 120;
      var x = e.clientX + pad, y = e.clientY + pad;
      if (x + w > window.innerWidth - 8) x = e.clientX - w - pad;
      if (y + h > window.innerHeight - 8) y = e.clientY - h - pad;
      tip.style.left = Math.max(8, x) + 'px';
      tip.style.top = Math.max(8, y) + 'px';
    }
    function hideTip() { tip.classList.remove('show'); }

    $$('.v3-tick', tape).forEach(function (btn) {
      btn.addEventListener('mouseenter', function (e) { showTip(btn, e); });
      btn.addEventListener('mousemove', moveTip);
      btn.addEventListener('mouseleave', hideTip);
      btn.addEventListener('focus', function () { var bb = btn.getBoundingClientRect(); showTip(btn, { clientX: bb.left + bb.width / 2, clientY: bb.top }); });
      btn.addEventListener('blur', hideTip);
      btn.addEventListener('click', function () {
        var n = btn.getAttribute('data-name');
        if (typeof openReport === 'function') openReport(n);
      });
    });
  }

  function refreshTape() {
    if (!tapeEl) return;
    var s = slice(), active = sliceActive(), n = 0;
    $$('.v3-tick', tapeEl).forEach(function (b) {
      var row = ROW_BY_NAME[b.getAttribute('data-name')] || {
        v: b.getAttribute('data-variety'), y: b.getAttribute('data-year'), b: b.getAttribute('data-bank')
      };
      var match = rowMatch(row);
      b.classList.toggle('dim', active && !match);
      b.classList.toggle('on-slice', active && match);
      if (match) n++;
    });
    var count = $('#v3-tape-count');
    if (count) count.textContent = active ? ('切片内 ' + n + ' 单') : ('全样本 ' + allRows.length + ' 单');
  }

  /* ================= 3 · ECHARTS ================= */
  function hasEcharts() { return typeof window.echarts !== 'undefined'; }

  function baseOption() {
    return {
      textStyle: { fontFamily: FONT, color: '#344054', fontSize: 11 },
      animationDuration: REDUCED ? 0 : 460,
      animationDurationUpdate: REDUCED ? 0 : 300,
      animationEasing: 'cubicOut',
      tooltip: {
        trigger: 'item', backgroundColor: '#FFFFFF', borderColor: '#E4E7EC', borderWidth: 1, padding: [9, 11],
        textStyle: { color: '#0A0F1A', fontSize: 11.5, fontFamily: FONT },
        extraCssText: 'box-shadow:0 10px 28px rgba(16,24,40,.12);border-radius:7px;'
      },
      legend: { top: 4, left: 0, itemWidth: 8, itemHeight: 8, icon: 'circle', itemGap: 12, type: 'scroll', width: '92%', textStyle: { color: '#667085', fontSize: 10, fontFamily: FONT } },
      grid: { left: 8, right: 16, top: 38, bottom: 10, containLabel: true }
    };
  }
  function axisLabel() { return { color: '#667085', fontSize: 10, fontFamily: FONT }; }
  function axisLine() { return { lineStyle: { color: '#E4E7EC' } }; }
  function splitLine() { return { lineStyle: { color: '#F2F4F7' } }; }
  function pctAxis() {
    return { type: 'value', axisLine: axisLine(), axisTick: { show: false }, axisLabel: axisLabel(), splitLine: splitLine(), axisPointer: { lineStyle: { color: '#D0D5DD' } } };
  }
  function emptyOption(msg) {
    return {
      graphic: { type: 'text', left: 'center', top: 'middle', style: { text: msg || '当前切片无匹配项目', fill: '#98A2B3', fontSize: 12, fontFamily: FONT } },
      xAxis: { show: false }, yAxis: { show: false }, series: []
    };
  }
  function tooltipRows(r) {
    return '<div style="font-size:10px;color:#667085;margin-bottom:5px">' + esc(r.b) + ' · ' + esc(r.v) + ' · ' + esc(r.d) + '</div>' +
      '<div style="display:grid;grid-template-columns:auto auto;gap:2px 14px;font-variant-numeric:tabular-nums">' +
      '<span style="color:#667085">回收率</span><b style="text-align:right">' + pct(r.r) + '</b>' +
      '<span style="color:#667085">处置费率</span><b style="text-align:right">' + pct(r.dp) + '</b>' +
      '<span style="color:#667085">达成率</span><b style="text-align:right">' + pct(r.a) + '</b>' +
      '<span style="color:#667085">次级倍数</span><b style="text-align:right">' + x2(r.m) + '</b>' +
      '<span style="color:#667085">次级XIRR</span><b style="text-align:right">' + pct(r.x) + '</b></div>' +
      '<div style="font-size:9px;color:#98A2B3;margin-top:6px;border-top:1px solid #F2F4F7;padding-top:4px">点击气泡打开单项目报告</div>';
  }

  function scatterBase(data, opt) {
    var banks = BANKS;
    var series = banks.map(function (b) {
      return {
        name: b, type: 'scatter', cursor: 'pointer',
        data: data.filter(function (r) { return r.b === b; }).map(function (r) {
          return {
            name: r.n, value: [opt.x(r), opt.y(r), r.i], bank: r.b, variety: r.v, date: r.d,
            r: r.r, a: r.a, dp: r.dp, m: r.m, x: r.x, st: r.st,
            pool: r.p, life: r.life, sp: r.sp, sen: r.sen_xirr, coupon: r.coupon,
            pred: (isNum(r.a) && r.a !== 0 ? r.r / r.a : null)
          };
        }),
        symbolSize: function (v) { return Math.max(6, Math.min(30, Math.sqrt((v[2] || 0) / 1e8) * 7)); },
        itemStyle: { color: BC[b], opacity: .8, borderColor: '#FFFFFF', borderWidth: 1 },
        emphasis: { focus: 'series', itemStyle: { opacity: 1, borderColor: '#0A0F1A', borderWidth: 1.2 } }
      };
    });
    var base = baseOption();
    base.legend.data = banks;
    base.grid = { left: 56, right: 20, top: 38, bottom: 44, containLabel: false };
    base.tooltip.formatter = function (p) { return '<div style="font-size:12px;font-weight:650;margin-bottom:2px">' + esc(p.data.name) + '</div>' + tooltipRows(p.data); };
    base.xAxis = Object.assign(pctAxis(), {
      name: opt.xName, nameLocation: 'middle', nameGap: 28,
      nameTextStyle: { color: '#667085', fontSize: 10.5, fontFamily: FONT },
      min: opt.xMin != null ? opt.xMin : 0, max: opt.xMax != null ? opt.xMax : null
    });
    base.yAxis = Object.assign(pctAxis(), {
      name: opt.yName, nameLocation: 'middle', nameGap: 48,
      nameTextStyle: { color: '#667085', fontSize: 10.5, fontFamily: FONT },
      min: opt.yMin != null ? opt.yMin : 0, max: opt.yMax != null ? opt.yMax : null
    });
    base.series = series;
    return base;
  }

  function mountChart(svg, title, height, build, onClick) {
    if (!svg || !hasEcharts() || svg.dataset.v3mounted) return;
    var tools = document.createElement('div');
    tools.className = 'v3-chart-tools';
    tools.innerHTML = '<b>' + esc(title) + '</b><span></span>';
    var host = document.createElement('div');
    host.className = 'v3-chart';
    host.style.height = (height || 380) + 'px';
    svg.parentNode.insertBefore(tools, svg);
    svg.parentNode.insertBefore(host, svg);
    svg.style.display = 'none';
    svg.dataset.v3mounted = '1';
    var chart = window.echarts.init(host, null, { renderer: 'canvas' });
    chart.setOption(build(allRows), true);
    chart.on('click', function (p) {
      if (typeof onClick === 'function') { onClick(p); return; }
      if (p && p.data && p.data.name && typeof openReport === 'function') openReport(p.data.name);
    });
    chartMounts.push({ chart: chart, build: build, tools: tools, host: host });
  }

  function buildStrategy(data) {
    var has = data.filter(function (r) { return isNum(r.r) && isNum(r.dp); });
    if (!has.length) return emptyOption();
    var valsR = has.map(function (r) { return r.r; });
    var valsD = has.map(function (r) { return r.dp; });
    var medR = median(valsR), medD = median(valsD);
    var opt = scatterBase(has, {
      xName: '实际回收率', yName: '处置费率',
      xMax: Math.ceil(Math.max.apply(null, valsR) * 100 / 10) * 10,
      yMax: Math.ceil(Math.max.apply(null, valsD) * 100 / 5) * 5,
      x: function (r) { return +(r.r * 100).toFixed(2); },
      y: function (r) { return +(r.dp * 100).toFixed(2); }
    });
    opt.grid.top = 42;
    var first = firstNonEmptySeries(opt);
    if (first) first.markLine = {
      silent: true, symbol: 'none', animation: false,
      lineStyle: { color: '#98A2B3', type: 'dashed', width: 1 },
      label: { color: '#667085', fontSize: 9.5, backgroundColor: 'rgba(255,255,255,.85)', padding: [2, 3] },
      data: [
        { xAxis: +(medR * 100).toFixed(1), label: { formatter: '中位 ' + pct(medR), position: 'insideEndBottom' } },
        { yAxis: +(medD * 100).toFixed(1), label: { formatter: '中位 ' + pct(medD), position: 'insideEndTop' } }
      ]
    };

    /* outlier callouts: top recovery (2) + largest issue (1), recomputed per slice */
    var outliers = [];
    var byRec = has.slice().sort(function (a, b) { return (b.r || 0) - (a.r || 0); }).slice(0, 2);
    var byIssue = has.slice().sort(function (a, b) { return (b.i || 0) - (a.i || 0); }).slice(0, 1);
    byRec.concat(byIssue).forEach(function (r) {
      if (!outliers.some(function (x) { return x.n === r.n; })) outliers.push(r);
    });
    if (outliers.length) {
      opt.series.push({
        name: 'outlier', type: 'scatter', z: 8, symbol: 'circle', symbolSize: 1,
        data: outliers.map(function (r) {
          return { name: r.n, value: [r.r * 100, r.dp * 100], r: r.r, dp: r.dp, bank: r.b, variety: r.v, date: r.d, a: r.a, m: r.m, x: r.x, st: r.st, i: r.i };
        }),
        itemStyle: { color: 'transparent' },
        label: {
          show: true, position: 'top', distance: 5,
          formatter: function (p) { return p.data.name + '\n' + pct(p.data.r) + ' / ' + pct(p.data.dp); },
          color: '#0A0F1A', fontSize: 8.5, lineHeight: 11, fontFamily: FONT,
          backgroundColor: 'rgba(255,255,255,.94)', borderColor: 'rgba(176,138,87,.65)',
          borderWidth: 1, borderRadius: 3, padding: [2, 4]
        },
        emphasis: { label: { show: true } }
      });
    }
    return opt;
  }

  function buildSub(data) {
    var has = data.filter(function (r) { return isNum(r.sp) && isNum(r.m); });
    if (!has.length) return emptyOption();
    var xs = has.map(function (r) { return r.sp * 100; });
    var ys = has.map(function (r) { return r.m; });
    var xLo = Math.min.apply(null, xs), xHi = Math.max.apply(null, xs);
    var yLo = Math.min.apply(null, ys), yHi = Math.max.apply(null, ys);
    var xPad = Math.max(2, (xHi - xLo) * 0.18);
    var yPad = Math.max(0.05, (yHi - yLo) * 0.18);
    var opt = scatterBase(has, {
      xName: '次级占比', yName: '次级回报倍数',
      xMin: Math.max(0, Math.floor((xLo - xPad) / 5) * 5),
      xMax: Math.max(Math.max(0, Math.floor((xLo - xPad) / 5) * 5) + 5, Math.ceil((xHi + xPad) / 5) * 5),
      yMin: Math.max(0, Math.floor((yLo - yPad) * 10) / 10),
      yMax: Math.max(Math.max(0, Math.floor((yLo - yPad) * 10) / 10) + 0.1, Math.ceil((yHi + yPad) * 10) / 10),
      x: function (r) { return +(r.sp * 100).toFixed(2); },
      y: function (r) { return +r.m.toFixed(2); }
    });
    opt.yAxis.axisLabel.formatter = '{value}x';
    addQuadrant(opt, has.map(function (r) { return r.sp * 100; }), has.map(function (r) { return r.m; }),
      function (v) { return v.toFixed(1) + '%'; }, function (v) { return v.toFixed(2) + 'x'; });
    return opt;
  }

  function buildForecast(data) {
    var has = data.filter(function (r) { return r.a > 0 && isNum(r.r); });
    if (!has.length) return emptyOption();
    var preds = has.map(function (r) { return r.r / r.a; });
    var maxP = Math.ceil(Math.max.apply(null, preds.concat(has.map(function (r) { return r.r; }))) * 100 / 10) * 10;
    var opt = scatterBase(has, {
      xName: '预测回收率', yName: '实际回收率', xMax: maxP, yMax: maxP,
      x: function (r) { return +((r.r / r.a) * 100).toFixed(2); },
      y: function (r) { return +(r.r * 100).toFixed(2); }
    });
    opt.series.push({
      name: '完全准确', type: 'line', data: [[0, 0], [maxP, maxP]], symbol: 'none', silent: true,
      lineStyle: { color: '#98A2B3', type: 'dashed', width: 1 }, tooltip: { show: false }, z: 1
    });
    opt.legend.data = BANKS;
    addQuadrant(opt, has.map(function (r) { return (r.r / r.a) * 100; }), has.map(function (r) { return r.r * 100; }),
      function (v) { return v.toFixed(1) + '%'; }, function (v) { return v.toFixed(1) + '%'; });
    return opt;
  }

  function buildHist(data) {
    if (!data.length) return emptyOption();
    var labels = [], counts = [];
    for (var i = 0; i < 12; i++) { labels.push(i * 5 + '–' + (i + 1) * 5 + '%'); counts.push(0); }
    data.forEach(function (r) {
      if (!isNum(r.r)) return;
      var idx = Math.min(11, Math.max(0, Math.floor(r.r * 100 / 5)));
      counts[idx]++;
    });
    var opt = baseOption();
    opt.legend.show = false;
    opt.tooltip.trigger = 'axis';
    opt.tooltip.formatter = function (ps) {
      var p = ps[0];
      return '<div style="font-size:11px;color:#667085">回收率区间 ' + labels[p.dataIndex] + '</div><div style="font-size:18px;font-weight:650;margin-top:2px">' + p.value + ' 单</div>';
    };
    opt.grid = { left: 8, right: 16, top: 18, bottom: 8, containLabel: true };
    opt.xAxis = { type: 'category', data: labels, axisLine: axisLine(), axisTick: { show: false }, axisLabel: { color: '#667085', fontSize: 9.5, fontFamily: FONT, interval: 1 }, splitLine: { show: false } };
    opt.yAxis = { type: 'value', name: '单数', nameTextStyle: { color: '#667085', fontSize: 10, fontFamily: FONT }, axisLine: { show: false }, axisTick: { show: false }, axisLabel: axisLabel(), splitLine: splitLine() };
    opt.series = [{
      type: 'bar', data: counts, barWidth: '62%',
      itemStyle: { borderRadius: [2, 2, 0, 0], color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#175CD3' }, { offset: 1, color: '#84ADFF' }]) },
      emphasis: { itemStyle: { color: '#0A0F1A' } }
    }];
    return opt;
  }

  function buildIssuance(data) {
    if (!data.length) return emptyOption();
    var allYears = Array.from(new Set(allRows.map(function (r) { return String(r.y || ''); }))).filter(Boolean).sort();
    var vars = ['个人消费不良', '个人经营不良', '住房抵押不良', '信用卡不良'];
    var series = vars.map(function (v) {
      return {
        name: v, type: 'bar', stack: 'issuance', barMaxWidth: 40,
        itemStyle: { color: barGradient(catColor(v), 'rgba(255,255,255,.45)', true), borderRadius: [4, 4, 0, 0] },
        emphasis: { focus: 'series' },
        data: allYears.map(function (y) {
          return +(sum(data.filter(function (r) { return String(r.y) === y && r.v === v; }).map(function (r) { return r.i; })) / 1e8).toFixed(1);
        })
      };
    });
    var counts = allYears.map(function (y) { return data.filter(function (r) { return String(r.y) === y; }).length; });
    var totals = allYears.map(function (y) { return sum(data.filter(function (r) { return String(r.y) === y; }).map(function (r) { return r.i; })) / 1e8; });
    var countSeries = {
      name: '单数', type: 'scatter', data: allYears.map(function (y, i) { return [i, totals[i]]; }),
      symbolSize: 1, itemStyle: { color: 'transparent' }, silent: true, tooltip: { show: false },
      label: { show: true, position: 'top', color: '#667085', fontSize: 10.5, fontWeight: 600, fontFamily: FONT, formatter: function (p) { return counts[p.dataIndex] + ' 单'; } }
    };
    var opt = baseOption();
    opt.tooltip.trigger = 'axis';
    opt.tooltip.axisPointer = { type: 'shadow' };
    opt.tooltip.formatter = function (ps) {
      var idx = ps[0].dataIndex, y = allYears[idx];
      var lines = ps.filter(function (p) { return p.seriesType === 'bar' && p.value > 0; }).map(function (p) {
        return '<div style="display:flex;justify-content:space-between;gap:18px"><span>' + p.marker + p.seriesName + '</span><b>' + p.value.toFixed(1) + ' 亿</b></div>';
      }).join('');
      return '<div style="font-size:11px;color:#667085;margin-bottom:4px">' + y + ' · ' + counts[idx] + ' 单</div>' + lines +
        '<div style="display:flex;justify-content:space-between;gap:18px;border-top:1px solid #E4E7EC;margin-top:5px;padding-top:5px"><span>合计</span><b>' + totals[idx].toFixed(1) + ' 亿</b></div>';
    };
    opt.legend = Object.assign({}, opt.legend, {
      top: 2, left: 'center', width: '86%', type: 'scroll', itemGap: 10,
      textStyle: { color: '#667085', fontSize: 10.5, fontFamily: FONT }
    });
    opt.legend.data = vars;
    opt.grid = { left: 56, right: 24, top: 64, bottom: 44, containLabel: false };
    opt.xAxis = {
      type: 'category', name: '发行年份', nameLocation: 'middle', nameGap: 26,
      nameTextStyle: { color: '#667085', fontSize: 10.5, fontFamily: FONT },
      data: allYears, axisLine: axisLine(), axisTick: { show: false },
      axisLabel: { color: '#344054', fontSize: 11, fontFamily: FONT }
    };
    opt.yAxis = {
      type: 'value', name: '发行规模（亿元）', nameLocation: 'middle', nameGap: 48,
      nameTextStyle: { color: '#667085', fontSize: 10.5, fontFamily: FONT },
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#667085', fontSize: 10.5, fontFamily: FONT }, splitLine: splitLine()
    };
    opt.series = series.concat([countSeries]);
    return opt;
  }

  function buildScorecard(data) {
    var banks = BANKS.filter(function (b) { return data.some(function (r) { return r.b === b; }); });
    if (!banks.length) return emptyOption();
    var metrics = [
      { label: '回收率', fmt: pct, get: function (rs) { return median(rs.map(function (r) { return r.r; })); } },
      { label: '达成率', fmt: pct, get: function (rs) { return median(rs.map(function (r) { return r.a; })); } },
      { label: '处置费率', fmt: pct, get: function (rs) { return median(rs.map(function (r) { return r.dp; })); } },
      { label: '次级占比', fmt: pct, get: function (rs) { return median(rs.map(function (r) { return r.sp; })); } },
      { label: '次级倍数', fmt: function (v) { return v == null ? '—' : Number(v).toFixed(2) + 'x'; }, get: function (rs) { return median(rs.map(function (r) { return r.m; })); } },
      { label: '次级XIRR', fmt: pct, get: function (rs) { return median(rs.filter(function (r) { return r.st === 'settled'; }).map(function (r) { return r.x; })); } }
    ];
    var cells = [], labels = [];
    metrics.forEach(function (m, yi) {
      var vals = banks.map(function (b) { return m.get(data.filter(function (r) { return r.b === b; })); });
      var valid = vals.filter(isNum);
      var mn = valid.length ? Math.min.apply(null, valid) : 0;
      var mx = valid.length ? Math.max.apply(null, valid) : 0;
      vals.forEach(function (v, xi) {
        var norm = isNum(v) ? (mx > mn ? (v - mn) / (mx - mn) : 0.5) : 0;
        cells.push({ value: [xi, yi, norm], bank: banks[xi], metric: m.label, actual: isNum(v) ? m.fmt(v) : '—' });
      });
      labels.push(m.label);
    });
    var opt = baseOption();
    opt.legend.show = false;
    opt.tooltip.formatter = function (p) {
      var d = p.data;
      return '<div style="font-size:10px;color:#667085">' + d.metric + ' · ' + esc(d.bank) + '</div>' +
        '<div style="font-size:17px;font-weight:650;margin-top:2px">' + d.actual + '</div>' +
        '<div style="font-size:9px;color:#98A2B3;margin-top:3px">颜色 = 该指标内相对位置（横向比较，不跨指标）</div>';
    };
    opt.grid = { left: 8, right: 8, top: 28, bottom: 8, containLabel: true };
    opt.xAxis = {
      type: 'category', data: banks.map(function (b) { return BSHORT[b] || b; }),
      axisLine: axisLine(), axisTick: { show: false },
      axisLabel: { color: '#344054', fontSize: 10.5, fontFamily: FONT }
    };
    opt.yAxis = {
      type: 'category', data: labels,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#667085', fontSize: 10, fontFamily: FONT }
    };
    opt.visualMap = { show: false, min: 0, max: 1, inRange: { color: ['#FBF7EE', '#F0E2C6', '#D9BE8E', '#B08A57'] } };
    opt.series = [{
      type: 'heatmap', data: cells,
      label: { show: true, color: '#2A2115', fontSize: 10, fontFamily: FONT, formatter: function (p) { return p.data.actual; } },
      itemStyle: { borderColor: '#FFFFFF', borderWidth: 2, borderRadius: 3 },
      emphasis: { itemStyle: { borderColor: '#0A0F1A', borderWidth: 2 } }
    }];
    return opt;
  }

  function buildCoupon(data) {
    var banks = BANKS.filter(function (b) {
      return data.some(function (r) { return r.b === b && isNum(r.coupon) && isNum(r.sen_xirr); });
    });
    if (!banks.length) return emptyOption();
    var rows = banks.map(function (b, i) {
      var rs = data.filter(function (r) { return r.b === b && isNum(r.coupon) && isNum(r.sen_xirr); });
      return {
        value: [i, median(rs.map(function (r) { return r.coupon; })) * 100, median(rs.map(function (r) { return r.sen_xirr; })) * 100],
        bank: b, n: rs.length
      };
    });
    var vals = [];
    rows.forEach(function (r) { vals.push(r.value[1], r.value[2]); });
    var lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
    var pad = Math.max(0.05, (hi - lo) * 0.18);
    var opt = baseOption();
    opt.legend.show = false;
    opt.tooltip.trigger = 'item';
    opt.tooltip.formatter = function (p) {
      var d = p.data;
      return '<div style="font-size:10px;color:#667085">' + esc(d.bank) + ' · ' + d.n + ' 单</div>' +
        '<div style="display:grid;grid-template-columns:auto auto;gap:2px 14px;margin-top:4px">' +
        '<span style="color:#667085">票面中位</span><b style="text-align:right">' + d.value[1].toFixed(2) + '%</b>' +
        '<span style="color:#667085">优先XIRR中位</span><b style="text-align:right">' + d.value[2].toFixed(2) + '%</b>' +
        '<span style="color:#667085">差</span><b style="text-align:right">' + (d.value[2] - d.value[1]).toFixed(2) + 'pp</b></div>';
    };
    opt.title = {
      text: '○ 票面中位     ● 优先档 XIRR 中位', left: 6, top: 0,
      textStyle: { color: '#667085', fontSize: 10, fontWeight: 'normal', fontFamily: FONT }
    };
    opt.grid = { left: 8, right: 28, top: 36, bottom: 8, containLabel: true };
    opt.xAxis = {
      type: 'value', name: '%', min: +(lo - pad).toFixed(2), max: +(hi + pad).toFixed(2),
      nameTextStyle: { color: '#667085', fontSize: 10, fontFamily: FONT },
      axisLine: axisLine(), axisTick: { show: false }, axisLabel: axisLabel(), splitLine: splitLine()
    };
    opt.yAxis = {
      type: 'category', data: banks.map(function (b) { return BSHORT[b] || b; }),
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#344054', fontSize: 10.5, fontFamily: FONT }
    };
    opt.series = [{
      type: 'custom', name: '优先档', data: rows, encode: { x: [1, 2], y: 0 },
      renderItem: function (params, api) {
        var y = api.value(0), c = api.value(1), x = api.value(2);
        var d = params.data || rows[params.dataIndex] || {};
        var color = BC[d.bank] || '#667085';
        var p1 = api.coord([c, y]), p2 = api.coord([x, y]);
        var w = (api.getWidth && api.getWidth()) || 820;
        var labelX = Math.max(p1[0], p2[0]) + 10;
        if (labelX > w - 44) labelX = Math.min(p1[0], p2[0]) - 50;
        return {
          type: 'group', children: [
            { type: 'line', shape: { x1: p1[0], y1: p1[1], x2: p2[0], y2: p2[1] }, style: { stroke: '#D0D5DD', lineWidth: 3 } },
            { type: 'circle', shape: { cx: p1[0], cy: p1[1], r: 5 }, style: { fill: '#fff', stroke: color, lineWidth: 2 } },
            { type: 'circle', shape: { cx: p2[0], cy: p2[1], r: 5 }, style: { fill: color } },
            { type: 'text', style: { text: ((x - c) * 100).toFixed(0) + 'bp', x: labelX, y: (p1[1] + p2[1]) / 2 + 3, fill: '#667085', font: '10px ' + FONT } }
          ]
        };
      }
    }];
    return opt;
  }

  function buildAssetQuality(data, groupKey) {
    if (!data.length) return emptyOption();
    var groups = groupKey === 'bank'
      ? BANKS.filter(function (b) { return data.some(function (r) { return r.b === b; }); })
      : Array.from(new Set(data.map(function (r) { return r.v; }))).sort();
    if (!groups.length) return emptyOption();
    var rows = groups.map(function (g) {
      var rs = data.filter(function (r) { return (groupKey === 'bank' ? r.b : r.v) === g; });
      var a = sum(rs.map(function (r) { return r.sub_amt; }));
      var b = sum(rs.map(function (r) { return r.doubt_amt; }));
      var c = sum(rs.map(function (r) { return r.loss_amt; }));
      var s = a + b + c || 1;
      return { g: g, n: rs.length, a: a / s * 100, b: b / s * 100, c: c / s * 100 };
    });
    var labels = groups.map(function (g) { return groupKey === 'bank' ? (BSHORT[g] || g) : String(g).replace('不良', ''); });
    var opt = baseOption();
    opt.legend = Object.assign({}, opt.legend, { top: 2, itemGap: 12, textStyle: { color: '#667085', fontSize: 10.5, fontFamily: FONT } });
    opt.legend.data = ['次级类', '可疑类', '损失类'];
    opt.tooltip.trigger = 'axis';
    opt.tooltip.axisPointer = { type: 'shadow' };
    opt.tooltip.formatter = function (ps) {
      var idx = ps[0].dataIndex, r = rows[idx];
      var lines = ps.map(function (p) {
        return '<div style="display:flex;justify-content:space-between;gap:16px"><span>' + p.marker + p.seriesName + '</span><b>' + Number(p.value).toFixed(1) + '%</b></div>';
      }).join('');
      return '<div style="font-size:11px;color:#667085;margin-bottom:4px">' + esc(r.g) + ' · ' + r.n + ' 单</div>' + lines;
    };
    opt.grid = { left: 8, right: 16, top: 42, bottom: 10, containLabel: true };
    opt.xAxis = {
      type: 'value', max: 100,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#667085', fontSize: 10.5, fontFamily: FONT, formatter: '{value}%' },
      splitLine: splitLine()
    };
    opt.yAxis = {
      type: 'category', data: labels, inverse: true,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#344054', fontSize: 11, fontFamily: FONT }
    };
    var defs = [
      ['次级类', '#2F4570', 'a'],
      ['可疑类', '#B08A57', 'b'],
      ['损失类', '#B42318', 'c']
    ];
    var series = [];
    defs.forEach(function (def, di) {
      var radius = di === 0 ? [5, 0, 0, 5] : (di === defs.length - 1 ? [0, 5, 5, 0] : 0);
      series.push({
        name: def[0], type: 'bar', stack: 'g', barMaxWidth: 28,
        showBackground: di === 0,
        backgroundStyle: { color: '#F3EFE6', borderRadius: 5 },
        itemStyle: { color: def[1], borderRadius: radius },
        data: rows.map(function (r) { return { value: +r[def[2]].toFixed(1), group: r.g }; }),
        label: {
          show: true, color: def[0] === '可疑类' ? '#2A2115' : '#FFFFFF', fontSize: 10.5, fontWeight: 600, fontFamily: FONT,
          textBorderColor: 'rgba(10,15,26,.18)', textBorderWidth: 1,
          formatter: function (p) { return p.value > 7 ? Number(p.value).toFixed(1) + '%' : ''; }
        },
        emphasis: { focus: 'series' }
      });
    });
    opt.series = series;
    return opt;
  }

  function buildSecLife(data) {
    var has = data.filter(function (r) { return isNum(r.s) && isNum(r.life); });
    if (!has.length) return emptyOption();
    var banks = BANKS.filter(function (b) { return has.some(function (r) { return r.b === b; }); });
    var xs = has.map(function (r) { return r.s * 100; });
    var ys = has.map(function (r) { return r.life; });
    var xMax = Math.max(5, Math.ceil(Math.max.apply(null, xs) / 10) * 10);
    var yMax = Math.max(10, Math.ceil(Math.max.apply(null, ys) / 10) * 10);
    var opt = baseOption();
    opt.legend = Object.assign({}, opt.legend, {
      top: 2, left: 'center', width: '88%', type: 'scroll', itemGap: 10,
      textStyle: { color: '#667085', fontSize: 10, fontFamily: FONT }
    });
    opt.legend.data = banks;
    opt.grid = { left: 56, right: 24, top: 58, bottom: 44, containLabel: false };
    opt.xAxis = Object.assign(pctAxis(), {
      name: '证券化率', nameLocation: 'middle', nameGap: 28,
      nameTextStyle: { color: '#667085', fontSize: 10.5, fontFamily: FONT },
      min: 0, max: xMax, axisLabel: { color: '#667085', fontSize: 9.5, fontFamily: FONT }
    });
    opt.yAxis = {
      type: 'value', name: '存续期（月）', nameLocation: 'middle', nameGap: 48,
      nameTextStyle: { color: '#667085', fontSize: 10.5, fontFamily: FONT },
      min: 0, max: yMax, axisLine: axisLine(), axisTick: { show: false },
      axisLabel: { color: '#667085', fontSize: 9.5, fontFamily: FONT }, splitLine: splitLine()
    };
    opt.tooltip.formatter = function (p) {
      var d = p.data;
      return '<div style="font-size:12px;font-weight:650;margin-bottom:2px">' + esc(d.name) + '</div>' +
        '<div style="font-size:10px;color:#667085;margin-bottom:5px">' + esc(d.bank) + ' · ' + esc(d.variety) + ' · ' + (d.state === 'settled' ? '已清算' : '存续') + '</div>' +
        '<div style="display:grid;grid-template-columns:auto auto;gap:2px 14px">' +
        '<span style="color:#667085">证券化率</span><b style="text-align:right">' + d.value[0].toFixed(1) + '%</b>' +
        '<span style="color:#667085">存续期</span><b style="text-align:right">' + d.value[1] + ' 月</b>' +
        '<span style="color:#667085">发行规模</span><b style="text-align:right">' + ((d.value[2] || 0) / 1e8).toFixed(1) + ' 亿</b>' +
        '<span style="color:#667085">回收率</span><b style="text-align:right">' + pct(d.r) + '</b></div>' +
        '<div style="font-size:9px;color:#98A2B3;margin-top:6px;border-top:1px solid #F2F4F7;padding-top:4px">点击气泡打开单项目报告</div>';
    };
    opt.series = banks.map(function (b) {
      return {
        name: b, type: 'scatter', cursor: 'pointer',
        data: has.filter(function (r) { return r.b === b; }).map(function (r) {
          return { name: r.n, value: [r.s * 100, r.life, r.p], bank: r.b, variety: r.v, state: r.st, r: r.r };
        }),
        symbolSize: function (val) { return Math.max(6, Math.min(26, Math.sqrt((val[2] || 0) / 1e8) * 4)); },
        itemStyle: { color: BC[b], opacity: .82, borderColor: '#FFFFFF', borderWidth: 1 },
        emphasis: { focus: 'series', itemStyle: { opacity: 1, borderColor: '#0A0F1A', borderWidth: 1.2 } }
      };
    });
    addQuadrant(opt, has.map(function (r) { return r.s * 100; }), has.map(function (r) { return r.life; }),
      function (v) { return v.toFixed(1) + '%'; }, function (v) { return v + '月'; });
    return opt;
  }

  function showBank(bank) {
    if (!bank || typeof showView !== 'function') return;
    showView('bank-' + bank);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function sliceVariety(v) {
    if (!v) return;
    var chip = findChip($('#view-cmp'), 'variety', v);
    if (chip) chip.click();
  }

  function buildMatrix() {
    var s = slice();
    var saved = s.varieties.slice();
    s.varieties = [];
    var base = allRows.filter(rowMatch);
    s.varieties = saved;
    var banks = BANKS;
    var vars = ['个人消费不良', '个人经营不良', '住房抵押不良', '信用卡不良'];
    Array.from(new Set(allRows.map(function (r) { return r.v; }))).forEach(function (v) {
      if (vars.indexOf(v) < 0) vars.push(v);
    });
    var cells = [], max = 1;
    banks.forEach(function (b, yi) {
      vars.forEach(function (v, xi) {
        var rs = base.filter(function (r) { return r.b === b && r.v === v; });
        var n = rs.length;
        if (n > max) max = n;
        cells.push({
          value: [xi, yi, n], bank: b, variety: v, n: n,
          rec: median(rs.map(function (r) { return r.r; })),
          issue: sum(rs.map(function (r) { return r.i; })),
          active: s.varieties.indexOf(v) >= 0
        });
      });
    });
    var opt = baseOption();
    opt.legend.show = false;
    opt.grid = { left: 62, right: 12, top: 20, bottom: 12, containLabel: false };
    opt.xAxis = {
      type: 'category', data: vars.map(function (v) { return String(v).replace('不良', ''); }),
      axisLine: axisLine(), axisTick: { show: false },
      axisLabel: { color: '#344054', fontSize: 11, fontFamily: FONT, interval: 0 }
    };
    opt.yAxis = {
      type: 'category', data: banks.map(function (b) { return BSHORT[b] || b; }), inverse: true,
      axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#344054', fontSize: 11.5, fontFamily: FONT }
    };
    opt.visualMap = { show: false, min: 0, max: max, inRange: { color: ['#FBF7EE', '#F0E2C6', '#D9BE8E', '#B08A57'] } };
    opt.tooltip.formatter = function (p) {
      var d = p.data;
      return '<div style="font-size:11px;font-weight:650">' + esc(d.bank) + ' · ' + esc(d.variety) + '</div>' +
        '<div style="font-size:10px;color:#667085;margin-top:2px">' + d.n + ' 单 · 回收率中位 ' + pct(d.rec) +
        ' · 发行 ' + (d.issue / 1e8).toFixed(1) + ' 亿</div>' +
        '<div style="font-size:9px;color:#98A2B3;margin-top:4px">点击进入该银行并带上该品种切片</div>';
    };
    opt.series = [{
      type: 'heatmap', data: cells,
      label: {
        show: true, color: '#2A2115', fontSize: 11.5, lineHeight: 16, fontFamily: FONT,
        formatter: function (p) { var d = p.data; return d.n ? (d.n + ' 单\n' + pct(d.rec)) : '—'; }
      },
      itemStyle: {
        borderColor: '#FFFFFF', borderWidth: 2, borderRadius: 3
      },
      emphasis: { itemStyle: { borderColor: '#0A0F1A', borderWidth: 2 } }
    }];
    /* mark the active variety columns after setOption builds item styles */
    cells.forEach(function (c) {
      if (c.active) c.itemStyle = { borderColor: '#D92D20', borderWidth: 2 };
    });
    return opt;
  }

  function mountMatrixCard() {
    if (document.getElementById('v3-matrix-card') || !hasEcharts()) return;
    var card = document.createElement('div');
    card.className = 'card v3-matrix-card';
    card.id = 'v3-matrix-card';
    card.innerHTML = '<div class="v3-chart-tools"><b>银行 × 品种矩阵</b><span>按年份 / 期限切片 · 点格子进入银行 + 品种</span></div>'
      + '<div class="v3-chart" id="v3-matrix-chart" style="height:360px"></div>'
      + '<div class="note">格子 = 该银行该品种单数 / 回收率中位；颜色 = 单数。点格子进入银行页并带上该品种切片；已选品种列用红框标出。</div>';
    var fr = document.getElementById('filter-results');
    if (fr && fr.parentNode) fr.insertAdjacentElement('beforebegin', card);
    else {
      var ins = document.getElementById('insights');
      if (ins) ins.insertAdjacentElement('afterend', card);
    }
    var host = document.getElementById('v3-matrix-chart');
    var chart = window.echarts.init(host, null, { renderer: 'canvas' });
    chart.setOption(buildMatrix());
    chart.on('click', function (p) {
      var d = p && p.data;
      if (!d || !d.n) return;
      setMultiSlice('variety', d.variety, true);
      showBank(d.bank);
    });
    chartMounts.push({ chart: chart, build: buildMatrix, tools: card.querySelector('.v3-chart-tools'), host: host, matrix: true });
    window.__v3charts = chartMounts.map(function (m) { return m.chart; });
  }

  function buildSeniorSub(data) {
    var has = data.filter(function (r) { return isNum(r.sen_xirr) && isNum(r.x); });
    if (!has.length) return emptyOption();
    var xs = has.map(function (r) { return r.sen_xirr * 100; });
    var ys = has.map(function (r) { return r.x * 100; });
    var xLo = Math.min.apply(null, xs), xHi = Math.max.apply(null, xs);
    var yLo = Math.min.apply(null, ys), yHi = Math.max.apply(null, ys);
    var padX = Math.max(.05, (xHi - xLo) * .18), padY = Math.max(5, (yHi - yLo) * .16);
    var opt = scatterBase(has, {
      xName: '优先档 XIRR', yName: '次级档 XIRR',
      xMin: Math.max(0, Math.floor((xLo - padX) * 10) / 10),
      xMax: Math.ceil((xHi + padX) * 10) / 10,
      yMin: Math.floor((yLo - padY) / 10) * 10,
      yMax: Math.ceil((yHi + padY) / 10) * 10,
      x: function (r) { return +(r.sen_xirr * 100).toFixed(2); },
      y: function (r) { return +(r.x * 100).toFixed(2); }
    });
    opt.xAxis.axisLabel.formatter = '{value}%';
    opt.yAxis.axisLabel.formatter = '{value}%';
    opt.tooltip.formatter = function (p) {
      var d = p.data;
      return '<div style="font-size:12px;font-weight:650;margin-bottom:2px">' + esc(d.name) + '</div>' +
        '<div style="font-size:10px;color:#667085;margin-bottom:5px">' + esc(d.bank) + ' · ' + esc(d.variety) + ' · ' + (d.st === 'settled' ? '已清算' : '存续') + '</div>' +
        '<div style="display:grid;grid-template-columns:auto auto;gap:2px 14px">' +
        '<span style="color:#667085">优先档 XIRR</span><b style="text-align:right">' + pct(d.sen) + '</b>' +
        '<span style="color:#667085">次级档 XIRR</span><b style="text-align:right">' + pct(d.x) + '</b>' +
        '<span style="color:#667085">回收率</span><b style="text-align:right">' + pct(d.r) + '</b>' +
        '<span style="color:#667085">次级倍数</span><b style="text-align:right">' + x2(d.m) + '</b></div>';
    };
    var first = firstNonEmptySeries(opt);
    if (first) {
      first.markLine = {
        silent: true, symbol: 'none', lineStyle: { color: '#D0D5DD', type: 'dashed', width: 1 },
        label: { color: '#98A2B3', fontSize: 9, backgroundColor: 'rgba(255,255,255,.85)', padding: [2, 3] },
        data: [{ yAxis: 0, label: { formatter: '次级 IRR = 0', position: 'insideEndTop' } }]
      };
    }
    addQuadrant(opt, xs, ys, function (v) { return v.toFixed(2) + '%'; }, function (v) { return v.toFixed(1) + '%'; });
    return opt;
  }

  function buildPoolPred(data) {
    var has = data.filter(function (r) { return isNum(r.p) && isNum(r.r) && isNum(r.a) && r.a > 0; });
    if (!has.length) return emptyOption();
    var xs = has.map(function (r) { return r.p / 1e8; });
    var preds = has.map(function (r) { return r.r / r.a * 100; });
    var opt = scatterBase(has, {
      xName: '资产池本息费（亿元）', yName: '预计回收率',
      xMin: 0, yMin: 0,
      xMax: Math.max(10, Math.ceil(Math.max.apply(null, xs) / 10) * 10),
      yMax: Math.max(5, Math.ceil(Math.max.apply(null, preds) / 5) * 5),
      x: function (r) { return +(r.p / 1e8).toFixed(2); },
      y: function (r) { return +(r.r / r.a * 100).toFixed(2); }
    });
    opt.yAxis.axisLabel.formatter = '{value}%';
    opt.tooltip.formatter = function (p) {
      var d = p.data;
      return '<div style="font-size:12px;font-weight:650;margin-bottom:2px">' + esc(d.name) + '</div>' +
        '<div style="font-size:10px;color:#667085;margin-bottom:5px">' + esc(d.bank) + ' · ' + esc(d.variety) + ' · ' + (d.st === 'settled' ? '已清算' : '存续') + '</div>' +
        '<div style="display:grid;grid-template-columns:auto auto;gap:2px 14px">' +
        '<span style="color:#667085">资产池本息费</span><b style="text-align:right">' + (d.pool / 1e8).toFixed(1) + ' 亿</b>' +
        '<span style="color:#667085">预计回收率</span><b style="text-align:right">' + pct(d.pred) + '</b>' +
        '<span style="color:#667085">实际回收率</span><b style="text-align:right">' + pct(d.r) + '</b>' +
        '<span style="color:#667085">处置费率</span><b style="text-align:right">' + pct(d.dp) + '</b>' +
        '<span style="color:#667085">达成率</span><b style="text-align:right">' + pct(d.a) + '</b></div>';
    };
    addQuadrant(opt, xs, preds, function (v) { return v.toFixed(0) + ' 亿'; }, function (v) { return v.toFixed(1) + '%'; });
    return opt;
  }

  function buildCashflow(data) {
    var has = data.filter(function (r) { return r.cf && r.cf.total > 0; });
    if (!has.length) return emptyOption('当前切片没有可解析的现金流分配矩阵');
    var rows = [];
    BANKS.forEach(function (b) {
      var vars = Array.from(new Set(has.filter(function (r) { return r.b === b; }).map(function (r) { return r.v; }))).sort();
      vars.forEach(function (v) {
        var rs = has.filter(function (r) { return r.b === b && r.v === v; });
        if (!rs.length) return;
        var sen = sum(rs.map(function (r) { return r.cf.sen; }));
        var sub = sum(rs.map(function (r) { return r.cf.sub; }));
        var fee = sum(rs.map(function (r) { return r.cf.fee; }));
        var other = sum(rs.map(function (r) { return r.cf.other; }));
        var total = sen + sub + fee + other;
        if (!(total > 0)) return;
        rows.push({
          bank: b, variety: v, n: rs.length,
          sen: sen / total * 100, sub: sub / total * 100,
          fee: fee / total * 100, other: other / total * 100,
          senAmt: sen, subAmt: sub, feeAmt: fee, otherAmt: other, totalAmt: total
        });
      });
    });
    if (!rows.length) return emptyOption('当前切片没有可解析的现金流分配矩阵');
    var labels = rows.map(function (r) { return (BSHORT[r.bank] || r.bank) + ' · ' + String(r.variety).replace('不良', ''); });
    var opt = baseOption();
    opt.legend = Object.assign({}, opt.legend, { top: 2, itemGap: 12, width: '92%', type: 'scroll', textStyle: { color: '#667085', fontSize: 10.5, fontFamily: FONT } });
    opt.legend.data = ['优先档', '次级档', '费用', '其他'];
    opt.tooltip.trigger = 'axis';
    opt.tooltip.axisPointer = { type: 'shadow' };
    opt.tooltip.formatter = function (ps) {
      var idx = ps[0].dataIndex, r = rows[idx];
      var line = function (name, p, amt, color) {
        return '<div style="display:flex;justify-content:space-between;gap:14px"><span><i style="display:inline-block;width:7px;height:7px;border-radius:2px;background:' + color + ';margin-right:5px"></i>' + name + '</span><b>' + p.toFixed(1) + '% · ' + (amt / 1e8).toFixed(2) + ' 亿</b></div>';
      };
      return '<div style="font-size:11px;color:#667085;margin-bottom:4px">' + esc(r.bank) + ' · ' + esc(r.variety) + ' · ' + r.n + ' 单</div>'
        + line('优先档', r.sen, r.senAmt, '#2F6FBE') + line('次级档', r.sub, r.subAmt, '#C9964E')
        + line('费用', r.fee, r.feeAmt, '#D92D20') + line('其他', r.other, r.otherAmt, '#98A2B3')
        + '<div style="display:flex;justify-content:space-between;gap:14px;border-top:1px solid #E4E7EC;margin-top:5px;padding-top:5px"><span>合计</span><b>' + (r.totalAmt / 1e8).toFixed(2) + ' 亿</b></div>';
    };
    opt.grid = { left: 8, right: 18, top: 44, bottom: 10, containLabel: true };
    opt.xAxis = {
      type: 'value', max: 100, axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#667085', fontSize: 10.5, fontFamily: FONT, formatter: '{value}%' },
      splitLine: splitLine()
    };
    opt.yAxis = {
      type: 'category', data: labels, inverse: true, axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: '#344054', fontSize: 11, fontFamily: FONT }
    };
    var defs = [
      ['优先档', '#8FB9E8', '#2F6FBE', 'sen'],
      ['次级档', '#E8C98D', '#B9853D', 'sub'],
      ['费用', '#E59A96', '#B42318', 'fee'],
      ['其他', '#C7CDD6', '#7A8798', 'other']
    ];
    opt.series = defs.map(function (def, di) {
      var radius = di === 0 ? [5, 0, 0, 5] : (di === defs.length - 1 ? [0, 5, 5, 0] : 0);
      return {
        name: def[0], type: 'bar', stack: 'cf', barMaxWidth: 26,
        showBackground: di === 0, backgroundStyle: { color: '#F5F7FA', borderRadius: 5 },
        itemStyle: { color: barGradient(def[1], def[2]), borderRadius: radius },
        data: rows.map(function (r) {
          return { value: +r[def[3]].toFixed(1), bank: r.bank, variety: r.variety, n: r.n };
        }),
        label: {
          show: true, color: '#fff', fontSize: 10.5, fontWeight: 600, fontFamily: FONT,
          textBorderColor: 'rgba(10,15,26,.25)', textBorderWidth: 1,
          formatter: function (p) { return p.value > 7 ? Number(p.value).toFixed(0) + '%' : ''; }
        },
        emphasis: { focus: 'series' }
      };
    });
    return opt;
  }

  function mountNewChartCard(card, title, height, build, note, onClick) {
    var tools = document.createElement('div');
    tools.className = 'v3-chart-tools';
    tools.innerHTML = '<b>' + esc(title) + '</b><span></span>';
    var host = document.createElement('div');
    host.className = 'v3-chart';
    host.style.height = (height || 390) + 'px';
    var noteEl = document.createElement('div');
    noteEl.className = 'note';
    noteEl.textContent = note || '';
    card.appendChild(tools);
    card.appendChild(host);
    if (note) card.appendChild(noteEl);
    var chart = window.echarts.init(host, null, { renderer: 'canvas' });
    chart.setOption(build(allRows), true);
    chart.on('click', function (p) {
      if (typeof onClick === 'function') { onClick(p); return; }
      if (p && p.data && p.data.name && typeof openReport === 'function') openReport(p.data.name);
    });
    chartMounts.push({ chart: chart, build: build, tools: tools, host: host, noFull: true });
    window.__v3charts = chartMounts.map(function (m) { return m.chart; });
  }

  function mountPoolTable() {
    if (document.getElementById('v3-pool-card')) return;
    var s2 = document.getElementById('s2');
    if (!s2) return;
    var ref = s2.querySelector('.card.is-chart');
    var card = document.createElement('div');
    card.className = 'card v3-pool-card';
    card.id = 'v3-pool-card';
    card.innerHTML = '<div class="v3-chart-tools"><b>银行资产池 × 预计回收率</b><span>横轴：资产池本息费规模 · 纵轴：预计回收率</span></div>'
      + '<div class="tablewrap" style="overflow:auto"><table class="tbl2" id="v3-pool-table"></table></div>'
      + '<div class="note">按预计回收率中位排序；预计回收率 = 实际回收率 ÷ 达成率；资产池本息费 = Σ单项目入池本息费。表内金额单位：亿元。</div>';
    if (ref) ref.insertAdjacentElement('beforebegin', card); else s2.appendChild(card);
  }

  function renderPoolTable() {
    var table = document.getElementById('v3-pool-table');
    if (!table) return;
    var data = filteredRows();
    var banks = BANKS.filter(function (b) { return data.some(function (r) { return r.b === b; }); });
    var rows = banks.map(function (b) {
      var rs = data.filter(function (r) { return r.b === b; });
      var pred = rs.filter(function (r) { return isNum(r.a) && r.a > 0 && isNum(r.r); }).map(function (r) { return r.r / r.a; });
      var rec = median(rs.map(function (r) { return r.r; }));
      var p = median(pred);
      return {
        bank: b, n: rs.length,
        pool: sum(rs.map(function (r) { return r.p; })) / 1e8,
        pred: p, rec: rec,
        dp: median(rs.map(function (r) { return r.dp; })),
        recovered: sum(rs.map(function (r) { return r.rc; })) / 1e8,
        gap: (rec != null && p != null) ? (rec - p) * 100 : null
      };
    }).sort(function (a, b) { return (b.pred == null ? -1 : b.pred) - (a.pred == null ? -1 : a.pred); });
    table.innerHTML = '<thead><tr><th>银行</th><th>单数</th><th>资产池本息费（亿）</th><th>预计回收率中位</th><th>实际回收率中位</th><th>处置费率中位</th><th>回收额（亿）</th><th>实际−预计</th></tr></thead><tbody>'
      + (rows.length ? rows.map(function (r) {
        return '<tr><td class="l"><b>' + esc(r.bank) + '</b></td><td>' + r.n + '</td><td>' + r.pool.toFixed(1) + '</td><td>' + pct(r.pred) + '</td><td>' + pct(r.rec) + '</td><td>' + pct(r.dp) + '</td><td>' + r.recovered.toFixed(1) + '</td><td>' + (r.gap == null ? '—' : (r.gap >= 0 ? '+' : '') + r.gap.toFixed(1) + 'pp') + '</td></tr>';
      }).join('') : '<tr><td colspan="8" style="text-align:center;color:#98A2B3">当前切片无匹配项目</td></tr>')
      + '</tbody>';
  }

  function mountSeniorSubCard() {
    if (document.getElementById('v3-senior-sub-card')) return;
    var s3 = document.getElementById('s3');
    if (!s3) return;
    var cards = $$('#s3 .card.is-chart');
    var coupon = null;
    cards.forEach(function (c) { if (c.textContent.indexOf('优先档票面') >= 0) coupon = c; });
    var card = document.createElement('div');
    card.className = 'card is-chart';
    card.id = 'v3-senior-sub-card';
    if (coupon) coupon.insertAdjacentElement('afterend', card); else s3.appendChild(card);
    mountNewChartCard(card, '优先档 XIRR × 次级档 XIRR', 390, buildSeniorSub,
      '每点 = 1 单；横轴优先档 XIRR，纵轴次级档 XIRR；颜色 = 银行，气泡 = 发行规模。悬停只看该银行；虚线为次级 IRR = 0。');
  }

  function mountPoolScatterCard() {
    if (document.getElementById('v3-pool-chart-card')) return;
    var s2 = document.getElementById('s2');
    if (!s2) return;
    var ref = s2.querySelector('.card.is-chart');
    var card = document.createElement('div');
    card.className = 'card is-chart';
    card.id = 'v3-pool-chart-card';
    if (ref) ref.insertAdjacentElement('beforebegin', card); else s2.appendChild(card);
    mountNewChartCard(card, '资产池本息费 × 预计回收率', 390, buildPoolPred,
      '每点 = 1 单；横轴资产池本息费规模，纵轴预计回收率（实际回收 ÷ 达成率）；颜色 = 银行，气泡 = 发行规模。');
  }

  function renderCashflowBoard() {
    var board = document.getElementById('v3-cashflow-board');
    if (!board) return;
    var sub = document.getElementById('v3-cf-sub');
    var has = filteredRows().filter(function (r) { return r.cf && r.cf.total > 0; });
    if (!has.length) {
      board.innerHTML = '<div class="cf-empty">当前切片没有可解析的现金流分配矩阵</div>';
      if (sub) sub.textContent = (sliceActive() ? '切片 · ' + sliceLabel() : '全样本') + ' · 0 单';
      return;
    }
    var groups = [];
    BANKS.forEach(function (b) {
      var rs = has.filter(function (r) { return r.b === b; });
      if (!rs.length) return;
      var vars = Array.from(new Set(rs.map(function (r) { return r.v; }))).sort();
      var rows = vars.map(function (v) {
        var xs = rs.filter(function (r) { return r.v === v; });
        var sen = sum(xs.map(function (r) { return r.cf.sen; }));
        var subAmt = sum(xs.map(function (r) { return r.cf.sub; }));
        var fee = sum(xs.map(function (r) { return r.cf.fee; }));
        var other = sum(xs.map(function (r) { return r.cf.other; }));
        var total = sen + subAmt + fee + other;
        if (!(total > 0)) return null;
        return { bank: b, variety: v, n: xs.length, sen: sen, sub: subAmt, fee: fee, other: other, total: total };
      }).filter(Boolean);
      if (rows.length) {
        groups.push({
          bank: b, rows: rows, n: sum(rows.map(function (r) { return r.n; })),
          total: sum(rows.map(function (r) { return r.total; }))
        });
      }
    });
    var total = sum(groups.map(function (g) { return g.total; }));
    if (!(total > 0)) { board.innerHTML = '<div class="cf-empty">当前切片没有可解析的现金流分配矩阵</div>'; return; }
    var senAll = sum(has.map(function (r) { return r.cf.sen; }));
    var subAll = sum(has.map(function (r) { return r.cf.sub; }));
    var feeAll = sum(has.map(function (r) { return r.cf.fee; }));
    var otherAll = sum(has.map(function (r) { return r.cf.other; }));
    var settled = has.filter(function (r) { return r.st === 'settled'; }).length;
    var yi = function (v) { return (v / 1e8).toFixed(1) + ' 亿'; };
    var p = function (v) { return (v / total * 100).toFixed(1) + '%'; };
    var rp = function (v, t) { return (v / t * 100).toFixed(1) + '%'; };
    var seg = function (cls, amt, rowTotal, name) {
      var w = rowTotal > 0 ? Math.max(0, Math.min(100, amt / rowTotal * 100)) : 0;
      if (w <= 0) return '';
      var label = w >= 6 ? '<em>' + w.toFixed(0) + '%</em>' : '';
      return '<i class="cf-seg ' + cls + '" style="width:' + w.toFixed(2) + '%" title="' + esc(name) + ' ' + w.toFixed(1) + '% · ' + yi(amt) + '">' + label + '</i>';
    };
    var rowHtml = groups.map(function (g) {
      var head = '<div class="cf-group"><span class="cf-bank">' + esc(g.bank) + '</span><em>' + g.n + ' 单</em><b>' + yi(g.total) + '</b></div>';
      var rows = g.rows.map(function (r) {
        var active = slice().varieties.indexOf(r.variety) >= 0 ? ' on' : '';
        var title = r.bank + ' · ' + r.variety + '｜优先 ' + rp(r.sen, r.total) + ' / 次级 ' + rp(r.sub, r.total) + ' / 费用 ' + rp(r.fee, r.total) + ' / 其他 ' + rp(r.other, r.total) + '｜合计 ' + yi(r.total);
        return '<button type="button" class="cf-row' + active + '" data-bank="' + esc(r.bank) + '" data-variety="' + esc(r.variety) + '" title="' + esc(title) + '">'
          + '<span class="cf-name"><b>' + esc(String(r.variety).replace('不良', '')) + '</b><i>' + r.n + ' 单</i></span>'
          + '<span class="cf-track">' + seg('p', r.sen, r.total, '优先档') + seg('s', r.sub, r.total, '次级档') + seg('f', r.fee, r.total, '费用') + seg('o', r.other, r.total, '其他') + '</span>'
          + '<span class="cf-val"><b>' + yi(r.total) + '</b><i>100%</i></span></button>';
      }).join('');
      return head + rows;
    }).join('');
    board.innerHTML = '<div class="cf-sum">'
      + '<div class="c"><span>可分配现金</span><b>' + yi(total) + '</b><i>' + has.length + ' 单 · ' + settled + ' 已清算</i></div>'
      + '<div class="c"><span>优先档</span><b>' + p(senAll) + '</b><i>' + yi(senAll) + '</i></div>'
      + '<div class="c"><span>次级档</span><b>' + p(subAll) + '</b><i>' + yi(subAll) + '</i></div>'
      + '<div class="c"><span>费用</span><b>' + p(feeAll) + '</b><i>' + yi(feeAll) + '</i></div>'
      + '</div>'
      + '<div class="cf-legend">'
      + '<span><i class="p"></i>优先档 <b>' + p(senAll) + '</b></span>'
      + '<span><i class="s"></i>次级档 <b>' + p(subAll) + '</b></span>'
      + '<span><i class="f"></i>费用 <b>' + p(feeAll) + '</b></span>'
      + '<span><i class="o"></i>其他 <b>' + p(otherAll) + '</b></span>'
      + '</div>'
      + '<div class="cf-head"><span>银行 · 品种</span><span>资金分配结构（100%）</span><span>金额 / 单数</span></div>'
      + '<div class="cf-body">' + rowHtml + '</div>';
    if (sub) sub.textContent = (sliceActive() ? '切片 · ' + sliceLabel() + ' · ' : '全样本 · ') + has.length + ' 单';
  }

  function mountCashflowCard() {
    if (document.getElementById('v3-cashflow-card')) return;
    var s3 = document.getElementById('s3');
    if (!s3) return;
    var cards = $$('#s3 .card.is-chart');
    var sub = null;
    cards.forEach(function (c) { if (c.textContent.indexOf('次级厚度') >= 0) sub = c; });
    var card = document.createElement('div');
    card.className = 'card v3-cashflow-card';
    card.id = 'v3-cashflow-card';
    card.style.gridColumn = '1 / -1';
    card.innerHTML = '<div class="v3-chart-tools"><b>现金流去向 · 银行 × 品种</b><span id="v3-cf-sub">清算分配矩阵累计金额</span></div>'
      + '<div id="v3-cashflow-board" class="cashflow-board"></div>'
      + '<div class="note">按单项目清算分配矩阵的累计金额汇总；优先档 / 次级档 / 费用（税费、处置费、服务费、中介等）/ 其他（发行费用、其他费用）。占比按该银行 × 品种合计归一；点横条进入银行并带上品种切片。</div>';
    if (sub) sub.insertAdjacentElement('afterend', card); else s3.appendChild(card);
    var board = document.getElementById('v3-cashflow-board');
    board.addEventListener('click', function (e) {
      var row = e.target.closest('.cf-row');
      if (!row) return;
      setMultiSlice('variety', row.dataset.variety, true);
      showBank(row.dataset.bank);
    });
    renderCashflowBoard();
  }

  function pairCards(a, b) {
    if (!a || !b || a === b || a.parentNode !== b.parentNode) return null;
    if (a.closest('.v3-pair') || b.closest('.v3-pair')) return null;
    var wrap = document.createElement('div');
    wrap.className = 'v3-pair';
    a.parentNode.insertBefore(wrap, a);
    wrap.appendChild(a);
    wrap.appendChild(b);
    return wrap;
  }

  function findCard(section, text) {
    var out = null;
    $$('#' + section + ' .card').forEach(function (c) {
      if (!out && c.textContent.indexOf(text) >= 0) out = c;
    });
    return out;
  }

  function reorderLayout() {
    var s2 = document.getElementById('s2');
    var s3 = document.getElementById('s3');
    var s4 = document.getElementById('s4');
    var s5 = document.getElementById('s5');
    var s7 = document.getElementById('s7');
    var matrix = document.getElementById('v3-matrix-card');
    var score = s2 ? findCard('s2', '各行中位数计分卡') : null;
    if (matrix && score) {
      matrix.insertAdjacentElement('afterend', score);
      pairCards(matrix, score);
    }

    var pool = document.getElementById('v3-pool-chart-card');
    var strategy = s2 ? findCard('s2', '各行 · 回收率 × 处置费率') : null;
    if (pool && strategy) pairCards(pool, strategy);

    var coupon = s3 ? findCard('s3', '优先档票面 vs 优先档 XIRR') : null;
    var senior = document.getElementById('v3-senior-sub-card');
    if (coupon && senior) pairCards(coupon, senior);

    if (s4) {
      var s4cards = $$('#s4 .card.is-chart');
      if (s4cards.length >= 2) {
        var p4 = pairCards(s4cards[0], s4cards[1]);
        var hist = s4cards[1];
        var tbl = hist.querySelector('table');
        var muted = hist.querySelector('.muted');
        if (p4 && tbl) {
          var extra = document.createElement('div');
          extra.className = 'card v3-s4-table';
          extra.innerHTML = '<div class="v3-chart-tools"><b>银行预测偏差</b><span>实际 − 预测</span></div>';
          var wrap = document.createElement('div');
          wrap.className = 'tablewrap';
          wrap.style.overflow = 'auto';
          wrap.appendChild(tbl);
          extra.appendChild(wrap);
          if (muted) extra.appendChild(muted);
          p4.insertAdjacentElement('afterend', extra);
        }
      }
    }
    if (s5) {
      var s5cards = $$('#s5 .card.is-chart');
      if (s5cards.length >= 2) {
        pairCards(s5cards[0], s5cards[1]);
        var bankCard = s5cards[0];
        if (!bankCard.querySelector('.note')) {
          var bankNote = document.createElement('div');
          bankNote.className = 'note';
          bankNote.textContent = '按入池本息费余额加权；次级 / 可疑 / 损失三类合计 100%。';
          bankCard.appendChild(bankNote);
        }
      }
    }

    var cash = document.getElementById('v3-cashflow-card');
    var s3grid = s3 ? s3.querySelector('.grid2') : null;
    if (cash && s3grid && cash.parentNode === s3grid) {
      cash.style.gridColumn = '';
      s3grid.parentNode.insertBefore(cash, s3grid.nextSibling);
    }
    if (s3grid) {
      var topCard = null;
      $$('.card', s3grid).forEach(function (c) {
        if (!topCard && c.textContent.indexOf('Top / Bottom') >= 0) topCard = c;
      });
      if (topCard && !topCard.querySelector('.note')) {
        var topNote = document.createElement('div');
        topNote.className = 'note';
        topNote.textContent = 'Top / Bottom 取已清算项目；次级 XIRR 为货币加权年化，与回报倍数同看，避免单看年化被存续期带偏。';
        topCard.appendChild(topNote);
      }
    }

    if (s7) {
      var chart = s7.querySelector('.card.is-chart');
      var grid = s7.querySelector('.grid2');
      if (chart && grid) {
        var tcards = $$('.card', grid).filter(function (c) { return c.parentNode === grid; });
        if (tcards.length >= 2) {
          var year = tcards[0], bank = tcards[1];
          var wrap = document.createElement('div');
          wrap.className = 'v3-pair';
          s7.insertBefore(wrap, chart);
          wrap.appendChild(chart);
          wrap.appendChild(year);
          grid.parentNode.insertBefore(bank, grid);
          grid.remove();
        }
      }
    }
  }

  function mountCharts() {
    mountChart($('#s2 svg[aria-label*="处置策略"]'), '各行 · 回收率 × 处置费率', 390, buildStrategy);
    mountChart($('#s2 svg[aria-label*="计分卡"]'), '各行中位数计分卡', 360, buildScorecard, function (p) {
      if (p.data && p.data.bank) showBank(p.data.bank);
    });
    mountChart($('#s3 svg[aria-label*="次级厚度"]'), '次级厚度 × 回报倍数', 390, buildSub);
    mountChart($('#s3 svg[aria-label*="票面"]'), '优先档票面 vs 优先档 XIRR', 390, buildCoupon, function (p) {
      if (p.data && p.data.bank) showBank(p.data.bank);
    });
    mountChart($('#s4 svg[aria-label*="预测"]'), '预测回收率 × 实际回收率', 390, buildForecast);

    /* the recovery histogram lives in s4, not s5; fall back to the second svg */
    var hist = $('#s4 svg[aria-label*="分布"]');
    if (!hist) { var s4svgs = $$('#s4 svg'); hist = s4svgs[1] || null; }
    mountChart(hist, '回收率分布', 390, buildHist);

    mountChart($('#s5 svg[aria-label*="按银行"]'), '资产质量结构 · 按银行', 360, function (d) { return buildAssetQuality(d, 'bank'); }, function (p) {
      if (p.data && p.data.group) showBank(p.data.group);
    });
    mountChart($('#s5 svg[aria-label*="按品种"]'), '资产质量结构 · 按品种', 360, function (d) { return buildAssetQuality(d, 'variety'); }, function (p) {
      if (p.data && p.data.group) sliceVariety(p.data.group);
    });

    mountChart($('#s6 svg'), '品种 · 证券化率 · 存续期', 410, buildSecLife);

    /* the issuance chart is the single svg in s7 */
    var s7svg = $('#s7 svg[aria-label*="发行"]') || $('#s7 svg');
    mountChart(s7svg, '发行规模 · 年 × 品种', 340, buildIssuance);
    window.__v3charts = chartMounts.map(function (m) { return m.chart; });
  }

  function refreshCharts() {
    if (!chartMounts.length) return;
    var data = filteredRows();
    var label = sliceActive() ? ('切片 · ' + sliceLabel() + ' · ' + data.length + ' 单') : ('全样本 ' + allRows.length + ' 单');
    chartMounts.forEach(function (m) {
      try {
        m.chart.setOption(m.build(data), true);
        var sub = m.tools.querySelector('span');
        if (sub) {
          if (m.matrix) {
            sub.textContent = '年份 ' + (slice().years.join('/') || '全部') + ' · 点格子进入银行 + 品种';
          } else {
            sub.textContent = label;
          }
        }
        var card = m.host.closest('.card');
        var note = card ? card.querySelector('.note') : null;
        if (note && !m.matrix && !m.noFull) note.classList.toggle('v3-note-full', sliceActive());
        if (note && (m.matrix || m.noFull)) note.classList.remove('v3-note-full');
        m.chart.resize();
      } catch (e) { /* keep last chart */ }
    });
  }

  /* ================= 4 · INSIGHTS ================= */
  function buildInsightCards(data, isSlice) {
    if (!data.length) {
      return '<div class="insight"><div class="ins-k">当前切片</div><div class="ins-t">没有匹配项目</div>' +
        '<div class="ins-p">当前切片下没有项目。可以清除切片，或换一个品种 / 年份。</div>' +
        '<div class="ins-chips"><span>0 单</span><span>点击上方清除切片</span></div></div>';
    }
    var banks = Array.from(new Set(data.map(function (r) { return r.b; })));
    var stats = banks.map(function (b) {
      var rs = data.filter(function (r) { return r.b === b; });
      var settled = rs.filter(function (r) { return r.st === 'settled'; });
      return {
        bank: b, n: rs.length,
        rec: median(rs.map(function (r) { return r.r; })),
        disp: median(rs.map(function (r) { return r.dp; })),
        ach: median(rs.map(function (r) { return r.a; })),
        mult: median(settled.map(function (r) { return r.m; })),
        subx: median(settled.map(function (r) { return r.x; })),
        issue: sum(rs.map(function (r) { return r.i; })) / 1e8
      };
    });
    var recList = stats.filter(function (x) { return x.rec != null; }).sort(function (a, b) { return b.rec - a.rec; });
    var dispList = stats.filter(function (x) { return x.disp != null; }).sort(function (a, b) { return b.disp - a.disp; });
    var achList = stats.filter(function (x) { return x.ach != null; }).sort(function (a, b) { return Math.abs(b.ach - 1) - Math.abs(a.ach - 1); });
    var cards = [];
    var prefix = isSlice ? '切片内' : '';
    if (recList.length) {
      var t = recList[0];
      cards.push('<div class="insight" data-ins-bank="' + esc(t.bank) + '"><div class="ins-k">' + prefix + '回收率 · 银行中位</div>' +
        '<div class="ins-t">' + esc(t.bank) + ' 在' + (isSlice ? '切片内' : '样本内') + '回收率最高</div>' +
        '<div class="ins-n">' + pct(t.rec) + '</div>' +
        '<p class="ins-p">' + t.n + ' 单中位；处置费率 ' + pct(t.disp) + '；发行 ' + t.issue.toFixed(1) + ' 亿。高回收是否靠高成本，还要拆到品种。</p>' +
        '<div class="ins-chips"><span>' + t.n + ' 单</span><span>处置费 ' + pct(t.disp) + '</span><span>点击看银行</span></div></div>');
    }
    if (dispList.length > 1) {
      var hi = dispList[0], lo = dispList[dispList.length - 1];
      cards.push('<div class="insight" data-ins-bank="' + esc(hi.bank) + '"><div class="ins-k">' + prefix + '处置成本 · 银行中位</div>' +
        '<div class="ins-t">' + esc(hi.bank) + ' 最高，' + esc(lo.bank) + ' 最低</div>' +
        '<div class="ins-n">' + pct(hi.disp) + ' <span style="font-size:12px;color:#98A2B3">vs ' + pct(lo.disp) + '</span></div>' +
        '<p class="ins-p">处置费率 = 处置费用 ÷ 累计回收。高费率不等于低效，可能对应抵押物处置或诉讼为主。</p>' +
        '<div class="ins-chips"><span>' + esc(BSHORT[hi.bank]) + ' ' + pct(hi.disp) + '</span><span>' + esc(BSHORT[lo.bank]) + ' ' + pct(lo.disp) + '</span><span>' + hi.n + ' 单</span></div></div>');
    }
    if (achList.length) {
      var d = achList[0];
      cards.push('<div class="insight" data-ins-bank="' + esc(d.bank) + '"><div class="ins-k">' + prefix + '预测偏差 · 银行中位</div>' +
        '<div class="ins-t">' + esc(d.bank) + ' 的达成率偏离 100% 最远</div>' +
        '<div class="ins-n">' + pct(d.ach) + '</div>' +
        '<p class="ins-p">达成率 = 实际回收 ÷ 预测回收。偏离可能来自预测机构口径、品种结构或回收节奏，不直接等于清收能力。</p>' +
        '<div class="ins-chips"><span>偏离 ' + pp(d.ach) + '</span><span>' + d.n + ' 单</span><span>点击看明细</span></div></div>');
    }
    return cards.join('');
  }

  function renderInsights() {
    var box = $('#insights');
    if (!box) return;
    if (!sliceActive()) {
      box.classList.remove('v3-sliced');
      box.innerHTML = origInsightsHTML || buildInsightCards(allRows, false);
      return;
    }
    box.classList.add('v3-sliced');
    box.innerHTML = buildInsightCards(filteredRows(), true);
  }

  function corr(rows, k1, k2) {
    var xs = [], ys = [];
    rows.forEach(function (r) {
      var a = r[k1], b = r[k2];
      if (isNum(a) && isNum(b)) { xs.push(a); ys.push(b); }
    });
    var n = xs.length;
    if (n < 3) return null;
    var mx = sum(xs) / n, my = sum(ys) / n, sxy = 0, sxx = 0, syy = 0;
    for (var i = 0; i < n; i++) {
      var dx = xs[i] - mx, dy = ys[i] - my;
      sxy += dx * dy; sxx += dx * dx; syy += dy * dy;
    }
    return (sxx > 0 && syy > 0) ? sxy / Math.sqrt(sxx * syy) : null;
  }

  function bankStatsOf(data) {
    var banks = Array.from(new Set(data.map(function (r) { return r.b; })));
    return banks.map(function (b) {
      var rs = data.filter(function (r) { return r.b === b; });
      var settled = rs.filter(function (r) { return r.st === 'settled'; });
      return {
        bank: b, n: rs.length,
        rec: median(rs.map(function (r) { return r.r; })),
        disp: median(rs.map(function (r) { return r.dp; })),
        ach: median(rs.map(function (r) { return r.a; })),
        mult: median(settled.map(function (r) { return r.m; })),
        subx: median(settled.map(function (r) { return r.x; })),
        sp: median(rs.map(function (r) { return r.sp; })),
        issue: sum(rs.map(function (r) { return r.i; }))
      };
    });
  }

  function renderTakeaways() {
    var box = document.querySelector('#s1 .takeaways');
    if (!box) return;
    if (!sliceActive()) {
      if (origTakeawaysHTML) box.innerHTML = origTakeawaysHTML;
      return;
    }
    var data = filteredRows();
    if (!data.length) {
      box.innerHTML = '<div class="tk"><b><span class="tag">切片</span>没有匹配项目</b>' +
        '<p>当前切片（' + esc(sliceLabel()) + '）在 74 单中没有交集。换一个品种或年份，或清除切片恢复全样本结论。</p></div>';
      return;
    }
    var bs = bankStatsOf(data);
    var recSorted = bs.filter(function (x) { return x.rec != null; }).sort(function (a, b) { return b.rec - a.rec; });
    var dispSorted = bs.filter(function (x) { return x.disp != null; }).sort(function (a, b) { return b.disp - a.disp; });
    var achSorted = bs.filter(function (x) { return x.ach != null; })
      .map(function (x) { return { bank: x.bank, n: x.n, ach: x.ach, dev: Math.abs(x.ach - 1) }; })
      .sort(function (a, b) { return b.dev - a.dev; });
    var settled = data.filter(function (r) { return r.st === 'settled'; });
    var med = function (arr) { return median(arr); };
    var label = sliceLabel();
    var issue = sum(data.map(function (r) { return r.i; })) / 1e8;
    var pool = sum(data.map(function (r) { return r.p; })) / 1e8;
    var multMed = med(settled.map(function (r) { return r.m; }));
    var subxMed = med(settled.map(function (r) { return r.x; }));
    var rSp = corr(settled, 'sp', 'm');
    var rLifeA = corr(settled, 'life', 'a');
    var byMult = settled.slice().sort(function (a, b) { return (b.m || 0) - (a.m || 0); });
    var byRec = data.slice().sort(function (a, b) { return (b.r || 0) - (a.r || 0); });
    var link = function (r, val) { return '<span class="proj-link" data-report="' + esc(r.n) + '">' + esc(r.n) + '</span> ' + val; };
    var cards = [];

    cards.push('<div class="tk"><b><span class="tag">概况</span>' + esc(label) + ' · ' + data.length + ' 单</b>' +
      '<p>发行规模 <b>' + issue.toFixed(2) + ' 亿</b>；入池本息费 <b>' + pool.toFixed(0) + ' 亿</b>；' +
      '回收率中位 <b>' + pct(med(data.map(function (r) { return r.r; }))) + '</b>；' +
      '达成率中位 <b>' + pct(med(data.map(function (r) { return r.a; }))) + '</b>；' +
      '处置费率中位 ' + pct(med(data.map(function (r) { return r.dp; }))) + '；' +
      '已清算次级倍数中位 ' + (multMed == null ? '—' : multMed.toFixed(2) + 'x') + '、次级XIRR中位 ' + pct(subxMed) + '。</p></div>');

    if (recSorted.length) {
      var topRec = recSorted[0], botRec = recSorted[recSorted.length - 1];
      cards.push('<div class="tk"><b><span class="tag">回收</span>切片内行际：' + esc(BSHORT[topRec.bank] || topRec.bank) + ' vs ' + esc(BSHORT[botRec.bank] || botRec.bank) + '</b>' +
        '<p>回收率中位 ' + esc(BSHORT[topRec.bank] || topRec.bank) + ' <b>' + pct(topRec.rec) + '</b>（' + topRec.n + ' 单）对 ' +
        esc(BSHORT[botRec.bank] || botRec.bank) + ' <b>' + pct(botRec.rec) + '</b>（' + botRec.n + ' 单）。' +
        '同一切片内差距来自品种内部资产成色与处置节奏，比全样本横比更可比。</p></div>');
    }
    if (dispSorted.length > 1) {
      var hi = dispSorted[0], lo = dispSorted[dispSorted.length - 1];
      cards.push('<div class="tk"><b><span class="tag">成本</span>费率：' + esc(BSHORT[hi.bank] || hi.bank) + ' 最高、' + esc(BSHORT[lo.bank] || lo.bank) + ' 最低</b>' +
        '<p>' + esc(BSHORT[hi.bank] || hi.bank) + ' 处置费率中位 <b>' + pct(hi.disp) + '</b>，' +
        esc(BSHORT[lo.bank] || lo.bank) + ' <b>' + pct(lo.disp) + '</b>。' +
        '高费率可能是抵押物 / 诉讼驱动，也可能是报销科目口径；先对齐分母（处置费用 ÷ 累计回收）再下判断。</p></div>');
    }
    if (achSorted.length > 1) {
      var worst = achSorted[0], best = achSorted[achSorted.length - 1];
      cards.push('<div class="tk"><b><span class="tag">达成</span>预测偏差：' + esc(BSHORT[worst.bank] || worst.bank) + ' 偏离最远</b>' +
        '<p>达成率中位 ' + esc(BSHORT[worst.bank] || worst.bank) + ' <b>' + pct(worst.ach) + '</b>、' +
        esc(BSHORT[best.bank] || best.bank) + ' <b>' + pct(best.ach) + '</b>（最贴近 100%）。' +
        '偏差含预测机构口径差（中债 vs 主承销商）；切片内 <b>存续期 × 达成率 r = ' + (rLifeA == null ? '—（样本不足）' : (rLifeA >= 0 ? '+' : '') + rLifeA.toFixed(2)) + '</b>。' +
        '提前退出/缩短窗口会截断现金流，但不能单独解释低达成，需同时看预测基数与资产成色。</p></div>');
    }
    cards.push('<div class="tk"><b><span class="tag">结构</span>次级厚度 vs 次级回报</b>' +
      '<p>切片内次级占比中位 ' + pct(med(data.map(function (r) { return r.sp; }))) + '，已清算次级倍数中位 ' +
      (multMed == null ? '—' : multMed.toFixed(2) + 'x') + '、次级XIRR中位 ' + pct(subxMed) + '；' +
      '次级占比 × 倍数相关 r = ' + (rSp == null ? '—（样本不足）' : (rSp >= 0 ? '+' : '') + rSp.toFixed(2)) +
      '。厚次级是让给优先级的安全垫，成本由次级承担。</p></div>');
    if (byMult.length || byRec.length) {
      var multTop = byMult.slice(0, 2).map(function (r) { return link(r, r.m == null ? '—' : r.m.toFixed(2) + 'x'); }).join('、');
      var recTop = byRec.slice(0, 2).map(function (r) { return link(r, pct(r.r)); }).join('、');
      cards.push('<div class="tk"><b><span class="tag">个案</span>切片内两端项目</b>' +
        '<p>' + (multTop ? '次级倍数最高：' + multTop + '；' : '') +
        (recTop ? '回收率最高：' + recTop + '。' : '') +
        '点项目名打开报告，「← 返回」回到本页。</p></div>');
    }
    box.innerHTML = cards.join('');
  }

  /* ================= 5 · SLICE UI / CONTROLS ================= */
  function refreshPill() {
    var pill = $('#v3-pill');
    if (!pill) return;
    if (!sliceActive()) { pill.hidden = true; pill.innerHTML = ''; return; }
    pill.hidden = false;
    pill.innerHTML = '<i></i><span>' + esc(sliceLabel()) + '</span><button type="button" aria-label="清除切片" title="清除切片">×</button>';
  }

  function refreshSummaryChrome() {
    var sum = $('#filter-summary');
    if (!sum) return;
    if (!sliceActive()) {
      sum.classList.remove('on');
      document.body.classList.remove('v3-show-results');
      var t = sum.querySelector('.v3-slice-tag'); if (t) t.remove();
      var b = sum.querySelector('#v3-clear-slice'); if (b) b.remove();
      var tb = sum.querySelector('#v3-toggle-results'); if (tb) tb.remove();
      return;
    }
    sum.classList.add('on');
    if (!sum.querySelector('.v3-slice-tag')) sum.insertAdjacentHTML('afterbegin', '<span class="v3-slice-tag">切片</span>');
    if (!sum.querySelector('#v3-clear-slice')) sum.insertAdjacentHTML('beforeend', '<button id="v3-clear-slice" type="button" class="v3-slice-btn">清除切片</button>');
    if (!sum.querySelector('#v3-toggle-results')) {
      var toggle = document.createElement('button');
      toggle.id = 'v3-toggle-results';
      toggle.type = 'button';
      toggle.className = 'v3-slice-btn';
      var clear = sum.querySelector('#v3-clear-slice');
      sum.insertBefore(toggle, clear || null);
    }
    var btn = sum.querySelector('#v3-toggle-results');
    if (btn) {
      var showing = document.body.classList.contains('v3-show-results');
      btn.textContent = (showing ? '收起匹配项目' : '查看匹配项目') + '（' + filteredRows().length + '）';
      btn.setAttribute('aria-expanded', showing ? 'true' : 'false');
    }
  }

  function refreshNote() {
    var s1 = $('#s1');
    if (!s1) return;
    var n = $('#v3-slice-note');
    if (!sliceActive()) { if (n) n.remove(); return; }
    var data = filteredRows();
    var label = sliceLabel() + ' · ' + data.length + ' 单';
    if (!n) {
      n = document.createElement('div');
      n.id = 'v3-slice-note';
      s1.insertBefore(n, s1.querySelector('.takeaways'));
    }
    n.innerHTML = '当前切片：<b>' + esc(label) + '</b>。KPI、三条结论卡、六条核心结论与全部对比图表会随切片重算；带「全样本参考」标记的说明文字 / 策略综述仍为全样本。';
  }

  function refreshChips() {
    syncMultiChips();
  }

  function refreshTableChrome() {
    var view = document.getElementById('view-table');
    if (!view) return;
    var data = filteredRows(), counts = {};
    BANKS.forEach(function (b) { counts[b] = data.filter(function (r) { return r.b === b; }).length; });
    $$('.filters button[data-f]', view).forEach(function (btn) {
      var f = btn.getAttribute('data-f');
      var n = f === 'all' ? data.length : (counts[f] || 0);
      btn.textContent = (f === 'all' ? '全部' : (BSHORT[f] || f)) + ' ' + n;
    });
    var h2 = view.querySelector('.pagehead h2');
    if (h2) h2.textContent = sliceActive() ? ('切片内 ' + data.length + ' 单明细') : '74 单明细';
    var old = view.querySelector('.v3-table-slice');
    if (old) old.remove();
    if (sliceActive()) {
      var ph = view.querySelector('.ph-row');
      if (ph) {
        var chip = document.createElement('span');
        chip.className = 'v3-table-slice';
        chip.innerHTML = '切片：' + esc(sliceLabel()) + ' · ' + data.length + ' 单 <button type="button" id="v3-table-clear">清除</button>';
        ph.insertBefore(chip, ph.querySelector('.backlink'));
      }
    }
  }

  function refreshBankChrome() {
    BANKS.forEach(function (b) {
      var view = document.getElementById('view-bank-' + b);
      if (!view) return;
      var p = view.querySelector('.pagehead p');
      if (!p) return;
      if (!p.dataset.v3orig) p.dataset.v3orig = p.textContent;
      var n = filteredRows().filter(function (r) { return r.b === b; }).length;
      p.textContent = p.dataset.v3orig + (sliceActive() ? (' · 切片内 ' + n + ' 单') : '');
    });
  }

  function refreshVslice() {
    var s = slice();
    $$('.vslice').forEach(function (vs) {
      $$('[data-v]', vs).forEach(function (el) {
        var on = s.varieties.indexOf(el.getAttribute('data-v')) >= 0;
        el.classList.toggle('active', !!on);
        el.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      var reset = vs.querySelector('.vs-reset');
      if (reset) reset.disabled = !s.varieties.length;
    });
  }

  /* ================= 5b · MULTI-SLICE ENGINE ================= */
  function applyTableFilter() {
    var tbl = document.getElementById('tbl');
    if (!tbl) return;
    var on = document.querySelector('#view-table .filters button.on');
    var f = on ? on.dataset.f : 'all';
    var qel = document.getElementById('q');
    var kw = qel ? (qel.value || '').trim() : '';
    $$('#tbl tbody tr').forEach(function (tr) {
      var nm = (tr.querySelector('td.pn') || {}).textContent || '';
      var row = ROW_BY_NAME[nm] || { v: tr.dataset.variety, y: tr.dataset.year };
      var okB = f === 'all' || tr.dataset.bank === f;
      var okQ = !kw || (tr.dataset.q || '').indexOf(kw) >= 0;
      var okS = rowMatch(row);
      tr.style.display = (okB && okQ && okS) ? '' : 'none';
    });
  }

  function writeSliceUrl() {
    try {
      var s = slice();
      var params = new URLSearchParams(location.search);
      var map = { sv: 'varieties', sy: 'years', st: 'tenor', ss: 'sec', sa: 'ach', sstate: 'state', sbb: 'buyback' };
      Object.keys(map).forEach(function (q) {
        var arr = s[map[q]];
        if (arr && arr.length) params.set(q, arr.join(','));
        else params.delete(q);
      });
      var qs = params.toString();
      var url = location.pathname + (qs ? '?' + qs : '') + location.hash;
      history.replaceState(history.state || {}, '', url);
    } catch (e) {}
  }

  function readSliceUrl() {
    try {
      var params = new URLSearchParams(location.search);
      var map = { sv: 'varieties', sy: 'years', st: 'tenor', ss: 'sec', sa: 'ach', sstate: 'state', sbb: 'buyback' };
      var s = emptySlice();
      Object.keys(map).forEach(function (q) {
        var raw = params.get(q);
        if (raw) s[map[q]] = raw.split(',').filter(Boolean);
      });
      window.__slice = s;
    } catch (e) {}
  }

  function updateMultiCounts() {
    var s = slice();
    var active = sliceActive();
    $$('.filterbar').forEach(function (bar) {
      var scope = bar.dataset.scope, bank = bar.dataset.bank;
      var list = allRows.filter(function (x) {
        return (scope !== 'bank' || x.b === bank) && rowMatch(x);
      });
      var el = bar.querySelector('.fb-count');
      if (el) {
        el.textContent = (active ? '匹配 ' : (scope === 'bank' ? '全行 ' : '全样本 ')) + list.length + ' 单';
      }
    });
  }

  function syncMultiChips() {
    var s = slice();
    var map = { variety: 'varieties', year: 'years', tenor: 'tenor', sec: 'sec', ach: 'ach', state: 'state', buyback: 'buyback' };
    $$('.fb-chip').forEach(function (ch) {
      var arr = s[map[ch.dataset.k]];
      if (!arr) return;
      var v = ch.dataset.v || '';
      var on = v ? arr.indexOf(v) >= 0 : arr.length === 0;
      ch.classList.toggle('on', on);
      ch.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  function applyMultiSlice() {
    var s = slice();
    var active = sliceActive();
    var matched = allRows.filter(rowMatch);

    $$('.pcard[data-report]').forEach(function (card) {
      var row = ROW_BY_NAME[card.dataset.report];
      var ok = row ? rowMatch(row)
        : (!s.varieties.length || s.varieties.indexOf(card.dataset.variety) >= 0)
          && (!s.years.length || s.years.indexOf(card.dataset.year) >= 0);
      card.style.display = ok ? '' : 'none';
    });

    window.filt = applyTableFilter;
    applyTableFilter();

    var kpi = function (k) { return document.querySelector('[data-kpi="' + k + '"]'); };
    var medv = function (arr) { return median(arr); };
    if (kpi('count')) {
      var issue = sum(matched.map(function (x) { return x.i; }));
      var rec = sum(matched.map(function (x) { return x.rc; }));
      var settled = matched.filter(function (x) { return x.st === 'settled'; });
      var mult = medv(settled.map(function (x) { return x.m; }));
      var subx = medv(settled.map(function (x) { return x.x; }));
      kpi('count').textContent = matched.length;
      kpi('count-note').textContent = new Set(matched.map(function (x) { return x.b; })).size + ' 家银行 · '
        + new Set(matched.map(function (x) { return x.v; })).size + ' 个品种';
      kpi('issue').innerHTML = (issue / 1e8).toFixed(1) + '<small style="font-size:12px"> 亿</small>';
      kpi('pool-note').textContent = '入池本息费 '
        + (sum(matched.map(function (x) { return x.p; })) / 1e8).toFixed(0) + ' 亿';
      kpi('rec').innerHTML = (rec / 1e8).toFixed(1) + '<small style="font-size:12px"> 亿</small>';
      kpi('rec-note').textContent = '回收率中位 ' + pct(medv(matched.map(function (x) { return x.r; })));
      kpi('achieve').textContent = pct(medv(matched.map(function (x) { return x.a; })));
      kpi('mult').textContent = mult == null ? '—' : mult.toFixed(2) + 'x';
      kpi('mult-note').textContent = '已清算 ' + settled.length + ' 单中位 ｜ 次级XIRR中位 ' + pct(subx);
    }

    $$('.filterbar[data-scope=bank]').forEach(function (bar) {
      var bank = bar.dataset.bank;
      var view = document.getElementById('view-bank-' + bank);
      if (!view) return;
      var mx = allRows.filter(function (x) { return x.b === bank && rowMatch(x); });
      var settled = mx.filter(function (x) { return x.st === 'settled'; });
      var setB = function (key, val) {
        var el = view.querySelector('[data-bkpi="' + key + '"] .v');
        if (el) el.textContent = val;
      };
      setB('count', mx.length);
      setB('recovery', pct(medv(mx.map(function (x) { return x.r; }))));
      setB('achieve', pct(medv(mx.map(function (x) { return x.a; }))));
      setB('dispose', pct(medv(mx.map(function (x) { return x.dp; }))));
      setB('sub_pct', pct(medv(mx.map(function (x) { return x.sp; }))));
      var m = medv(settled.map(function (x) { return x.m; }));
      var sx = medv(settled.map(function (x) { return x.x; }));
      setB('mult', m == null ? '—' : m.toFixed(2) + 'x');
      setB('sub_xirr', pct(sx));
    });

    var sumBox = document.getElementById('filter-summary');
    if (sumBox) {
      if (!active) { sumBox.hidden = true; sumBox.innerHTML = ''; }
      else {
        sumBox.hidden = false;
        sumBox.innerHTML = '<span>匹配 <b>' + matched.length + '</b> 单</span>'
          + '<span>发行规模 <b>' + (sum(matched.map(function (x) { return x.i; })) / 1e8).toFixed(2) + ' 亿</b></span>'
          + '<span>回收率中位 <b>' + pct(medv(matched.map(function (x) { return x.r; }))) + '</b></span>'
          + '<span>达成率中位 <b>' + pct(medv(matched.map(function (x) { return x.a; }))) + '</b></span>'
          + '<span>次级XIRR中位 <b>' + pct(medv(matched.map(function (x) { return x.x; }))) + '</b></span>'
          + '<span>证券化率中位 <b>' + pct(medv(matched.map(function (x) { return x.s; }))) + '</b></span>';
      }
    }

    var box = document.getElementById('filter-results');
    if (box) {
      if (!active) { box.hidden = true; box.innerHTML = ''; }
      else {
        var list = matched.slice().sort(function (a, b) { return String(a.d || '').localeCompare(String(b.d || '')); });
        box.hidden = false;
        box.innerHTML = list.map(function (x) {
          return '<div class="fr-item" data-report="' + esc(x.n) + '" role="button" tabindex="0">'
            + '<b>' + esc(x.n) + '</b>'
            + '<span>' + esc(x.b) + ' · ' + esc(x.v) + ' · ' + esc(x.d) + '</span>'
            + '<span>回收 <em>' + pct(x.r) + '</em> · 证券化 <em>' + pct(x.s) + '</em> · 次级XIRR <em>' + (x.x == null ? '—' : (x.x * 100).toFixed(1) + '%') + '</em></span>'
            + '</div>';
        }).join('');
      }
    }

    s.variety = s.varieties.length === 1 ? s.varieties[0] : '';
    s.year = s.years.length === 1 ? s.years[0] : '';
    updateMultiCounts();
    syncMultiChips();
    writeSliceUrl();
    document.body.classList.toggle('v3-sliced', active);
    if (typeof window.__v3AfterSlice === 'function') window.__v3AfterSlice();
  }

  function setMultiSlice(k, v, single) {
    var map = { variety: 'varieties', year: 'years', tenor: 'tenor', sec: 'sec', ach: 'ach', state: 'state', buyback: 'buyback' };
    var key = map[k];
    if (!key) return;
    var s = slice();
    var arr = s[key];
    if (single) s[key] = v ? [v] : [];
    else if (!v) s[key] = [];
    else {
      var i = arr.indexOf(v);
      if (i >= 0) arr.splice(i, 1); else arr.push(v);
    }
    applyMultiSlice();
  }

  function stopYearPlay() {
    if (yearPlayTimer) { clearInterval(yearPlayTimer); yearPlayTimer = null; }
    var btn = document.getElementById('v3-year-play');
    if (btn) { btn.textContent = '▶ 播放'; btn.classList.remove('on'); }
  }

  function startYearPlay() {
    stopYearPlay();
    var order = ['2021', '2022', '2023', '2024'];
    var i = 0;
    setMultiSlice('year', order[i], true);
    i++;
    var btn = document.getElementById('v3-year-play');
    if (btn) { btn.textContent = '■ 停止'; btn.classList.add('on'); }
    yearPlayTimer = setInterval(function () {
      if (i >= order.length) { stopYearPlay(); return; }
      setMultiSlice('year', order[i], true);
      i++;
      if (i >= order.length) stopYearPlay();
    }, 1200);
  }

  function refreshAll() {
    if (kpiRaf) { cancelAnimationFrame(kpiRaf); kpiRaf = null; }
    if (!origInsightsHTML) { var ib = $('#insights'); origInsightsHTML = ib ? ib.innerHTML : ''; }
    document.body.classList.toggle('v3-sliced', sliceActive());
    if (sliceActive()) document.body.classList.remove('v3-show-results');
    refreshPill();
    refreshSummaryChrome();
    refreshChips();
    renderInsights();
    refreshCharts();
    renderCashflowBoard();
    refreshTape();
    refreshNote();
    renderTakeaways();
    refreshVslice();
    refreshTableChrome();
    refreshBankChrome();
    renderPoolTable();
    refreshPrintHead();
    updateCrumb();
  }

  function findChip(root, k, v) {
    var chips = $$('.fb-chip[data-k="' + k + '"]', root || document);
    for (var i = 0; i < chips.length; i++) if ((chips[i].dataset.v || '') === v) return chips[i];
    return null;
  }

  function clearAll() {
    var s = slice();
    Object.keys(s).forEach(function (k) { if (Array.isArray(s[k])) s[k] = []; });
    s.variety = ''; s.year = '';
    stopYearPlay();
    applyMultiSlice();
  }

  function clearVariety() {
    var s = slice();
    if (!s.varieties.length) { refreshAll(); return; }
    s.varieties = [];
    applyMultiSlice();
  }

  function setupVslice() {
    $$('.vslice').forEach(function (vs) {
      var spans = $$('.vs-bar span', vs);
      var items = $$('.vs-item', vs);
      spans.forEach(function (sp, i) {
        var title = sp.getAttribute('title') || '';
        var v = title.split('：')[0].split(':')[0].trim();
        if (!v) return;
        sp.dataset.v = v;
        sp.setAttribute('role', 'button');
        sp.setAttribute('tabindex', '0');
        sp.setAttribute('aria-label', '筛选本行品种：' + v);
        sp.title = '点击筛选：' + v;
        if (items[i]) {
          items[i].dataset.v = v;
          items[i].setAttribute('role', 'button');
          items[i].setAttribute('tabindex', '0');
          items[i].setAttribute('aria-label', '筛选本行品种：' + v);
          items[i].title = '点击筛选：' + v;
        }
      });
      var head = vs.querySelector('.vs-head');
      var hint = head ? head.querySelector('span') : null;
      if (hint && hint.textContent.indexOf('点击') < 0) hint.textContent += ' · 点击筛选';
      if (head && !head.querySelector('.vs-reset')) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'vs-reset';
        btn.textContent = '全部';
        btn.title = '清除品种切片';
        btn.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); clearVariety(); });
        head.appendChild(btn);
      }
      vs.addEventListener('click', function (e) {
        var t = e.target.closest('[data-v]');
        if (!t) return;
        e.preventDefault();
        e.stopPropagation();
        var v = t.getAttribute('data-v');
        setMultiSlice('variety', v, !(e.ctrlKey || e.metaKey));
      });
      vs.addEventListener('keydown', function (e) {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        var t = e.target.closest('[data-v]');
        if (!t) return;
        e.preventDefault();
        t.click();
      });
    });
  }

  /* ================= 6 · REPORT RETURN / SCROLL MEMORY ================= */
  function wrapOpenReport() {
    if (window.__v3openWrapped) return;
    var orig = window.openReport;
    if (typeof orig !== 'function') return;
    window.openReport = function () {
      window.__v3scrollY = window.scrollY || window.pageYOffset || 0;
      var r = orig.apply(this, arguments);
      try {
        var cur = document.querySelector('.view:not(.hidden)');
        var back = document.getElementById('vback');
        if (back && cur && cur.id === 'view-cmp') {
          back.textContent = '← 返回各行对比';
          back.title = '返回各行对比，并回到打开报告前的位置';
        }
      } catch (e) {}
      return r;
    };
    window.__v3openWrapped = true;
  }

  function setupReturnMemory() {
    var viewer = $('#viewer');
    if (!viewer || !('MutationObserver' in window)) return;
    new MutationObserver(function () {
      if (!viewer.classList.contains('open') && window.__v3scrollY != null) {
        var y = window.__v3scrollY;
        window.__v3scrollY = null;
        setTimeout(function () { window.scrollTo(0, y); }, 40);
      }
    }).observe(viewer, { attributes: true, attributeFilter: ['class'] });
  }

  /* ================= 7 · STATIC FIGURE MARKERS / RECOLOUR ================= */
  function markStaticFigures() {
    $$('.card.is-chart').forEach(function (c) {
      if (!c.querySelector('.v3-chart')) c.classList.add('v3-static-fig');
    });
    $$('.pm-synth').forEach(function (c) { c.classList.add('v3-static-fig'); });
  }

  function recolorSvg() {
    var MAP = {
      '#2F6F8F': '#175CD3', '#C07A3B': '#B54708', '#4E8F6D': '#067647', '#7D5BA6': '#6941C6', '#B03A2E': '#B42318',
      '#E7ECF3': '#EAECF0', '#FBFCFE': '#FFFFFF', '#6B7785': '#667085', '#3D4A5C': '#344054', '#2A3546': '#101828',
      '#F0F3F8': '#F2F4F7', '#9A6B36': '#B54708', '#2A7A5C': '#067647', '#A5342C': '#B42318', '#EEF2F6': '#F2F4F7',
      '#D6DEE9': '#D0D5DD', '#B9CAD8': '#98A2B3', '#41506A': '#344054', '#0F2233': '#0A0F1A', '#1C7C86': '#175CD3',
      '#48A6B8': '#F04438', '#A5814C': '#D92D20', '#D9BE8E': '#FDA29B', '#C7A871': '#F04438', '#EBD9B8': '#FECDCA'
    };
    $$('svg [fill], svg [stroke], svg stop').forEach(function (el) {
      ['fill', 'stroke', 'stop-color'].forEach(function (a) {
        var v = el.getAttribute(a);
        if (!v) return;
        var key = v.trim().toUpperCase();
        if (MAP[key]) el.setAttribute(a, MAP[key]);
      });
    });
    $$('svg text').forEach(function (t) { if (!t.getAttribute('font-family')) t.setAttribute('font-family', FONT); });
  }

  /* ================= 8 · INIT ================= */
  function animateKpis() {
    if (REDUCED) return;
    var nodes = $$('.kpi .v[data-kpi]').map(function (el) {
      var html = el.innerHTML;
      var m = html.match(/^([0-9]+(?:\.[0-9]+)?)([\s\S]*)$/);
      if (!m) return null;
      return { el: el, target: parseFloat(m[1]), dec: (m[1].split('.')[1] || '').length, rest: m[2] };
    }).filter(Boolean);
    if (!nodes.length) return;
    var start = null;
    function frame(ts) {
      if (start === null) start = ts;
      var p = Math.min(1, (ts - start) / 900);
      var e = 1 - Math.pow(1 - p, 3);
      nodes.forEach(function (n) { n.el.innerHTML = (n.target * e).toFixed(n.dec) + n.rest; });
      if (p < 1) { kpiRaf = requestAnimationFrame(frame); } else { kpiRaf = null; }
    }
    kpiRaf = requestAnimationFrame(frame);
  }

  function setFavicon() {
    try {
      var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#D92D20"/><text x="32" y="45" font-family="Arial,Helvetica,sans-serif" font-size="34" font-weight="700" fill="#FFFFFF" text-anchor="middle">N</text></svg>';
      var link = document.querySelector('link[rel="icon"]');
      if (!link) { link = document.createElement('link'); link.rel = 'icon'; document.head.appendChild(link); }
      link.setAttribute('href', 'data:image/svg+xml,' + encodeURIComponent(svg));
    } catch (e) {}
  }

  /* ================= 5c · EXPORT / COMPARE / REPORT THEME ================= */
  function toast(msg) {
    var t = document.getElementById('v3-toast');
    if (!t) { t = document.createElement('div'); t.id = 'v3-toast'; document.body.appendChild(t); }
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(t.__timer);
    t.__timer = setTimeout(function () { t.classList.remove('on'); }, 2300);
  }

  function stamp() {
    var d = new Date();
    return d.getFullYear() + String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0')
      + '_' + String(d.getHours()).padStart(2, '0') + String(d.getMinutes()).padStart(2, '0');
  }

  function downloadBlob(blob, name) {
    var a = document.createElement('a');
    var url = URL.createObjectURL(blob);
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1600);
  }

  function csvCell(v) {
    return '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
  }

  function exportSliceCsv() {
    var data = filteredRows();
    if (!data.length) { toast('当前切片没有项目，无法导出'); return; }
    var head = ['项目', '银行', '品种', '发行日', '发行规模(亿)', '回收率', '预测回收率', '达成率', '处置费率', '次级占比', '票面', '优先XIRR', '次级倍数', '次级XIRR', '存续月', '状态'];
    var lines = [head.map(csvCell).join(',')].concat(data.map(function (r) {
      var pred = (isNum(r.a) && r.a !== 0) ? (r.r / r.a) : '';
      return [
        r.n, r.b, r.v, r.d, (r.i / 1e8).toFixed(2), isNum(r.r) ? (r.r * 100).toFixed(2) : '',
        isNum(pred) ? (pred * 100).toFixed(2) : '', isNum(r.a) ? (r.a * 100).toFixed(2) : '',
        isNum(r.dp) ? (r.dp * 100).toFixed(2) : '', isNum(r.sp) ? (r.sp * 100).toFixed(2) : '',
        isNum(r.coupon) ? (r.coupon * 100).toFixed(2) : '', isNum(r.sen_xirr) ? (r.sen_xirr * 100).toFixed(2) : '',
        isNum(r.m) ? r.m.toFixed(3) : '', isNum(r.x) ? (r.x * 100).toFixed(2) : '',
        isNum(r.life) ? r.life : '', r.st === 'settled' ? '已清算' : '存续'
      ].map(csvCell).join(',');
    }));
    downloadBlob(new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' }), '不良ABS_切片_' + stamp() + '.csv');
    toast('已导出 ' + data.length + ' 单 CSV');
  }

  function exportSlicePng() {
    if (!chartMounts.length) { toast('图表尚未就绪'); return; }
    var shots = [];
    chartMounts.forEach(function (m) {
      try {
        var title = (m.tools.querySelector('b') || {}).textContent || '图表';
        shots.push({ title: title, url: m.chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#FFFFFF' }) });
      } catch (e) {}
    });
    if (!shots.length) { toast('PNG 生成失败'); return; }
    Promise.all(shots.map(function (o) {
      return new Promise(function (resolve) {
        var im = new Image();
        im.onload = function () { o.im = im; resolve(); };
        im.onerror = function () { resolve(); };
        im.src = o.url;
      });
    })).then(function () {
      var W = 1600, pad = 42, top = 86, drawW = 1516;
      var items = [];
      shots.forEach(function (o) {
        if (!o.im) return;
        items.push({ title: o.title, im: o.im, h: drawW * o.im.height / o.im.width });
      });
      var H = top + items.reduce(function (a, x) { return a + x.h + 34; }, 0) + pad;
      var c = document.createElement('canvas');
      c.width = W; c.height = Math.max(400, Math.ceil(H));
      var g = c.getContext('2d');
      g.fillStyle = '#F5F6F8'; g.fillRect(0, 0, c.width, c.height);
      g.fillStyle = '#0A0F1A';
      g.font = '700 26px "Microsoft YaHei UI","Microsoft YaHei",sans-serif';
      g.fillText('不良ABS 多行工作台 · 当前切片图表', pad, 42);
      g.fillStyle = '#667085';
      g.font = '13px "Microsoft YaHei UI","Microsoft YaHei",sans-serif';
      g.fillText((sliceActive() ? sliceLabel() : '全样本') + ' · ' + filteredRows().length + ' 单 · 数据截至 2026-10-31', pad, 66);
      var y = top;
      items.forEach(function (x) {
        g.fillStyle = '#344054';
        g.font = '600 12px "Microsoft YaHei UI","Microsoft YaHei",sans-serif';
        g.fillText(x.title, pad, y + 12);
        y += 20;
        g.drawImage(x.im, pad, y, drawW, x.h);
        y += x.h + 14;
      });
      c.toBlob(function (blob) {
        if (!blob) { toast('PNG 生成失败'); return; }
        downloadBlob(blob, '不良ABS_切片图表_' + stamp() + '.png');
        toast('已导出 ' + items.length + ' 张图表 PNG');
      }, 'image/png');
    });
  }

  function copySliceLink() {
    var url = location.href;
    var done = function () { toast('切片链接已复制'); };
    var fallback = function () {
      try {
        var ta = document.createElement('textarea');
        ta.value = url; ta.style.cssText = 'position:fixed;left:-9999px;top:0';
        document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); done();
      } catch (e) { toast('复制失败，请手动复制地址栏'); }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(done).catch(fallback);
    } else fallback();
  }

  function setupPrintHead() {
    var cmp = document.getElementById('view-cmp');
    if (!cmp || document.getElementById('v3-print-head')) return;
    var ph = document.createElement('div');
    ph.id = 'v3-print-head';
    cmp.insertBefore(ph, cmp.firstChild);
  }

  function refreshPrintHead() {
    var ph = document.getElementById('v3-print-head');
    if (!ph) return;
    ph.innerHTML = '<div class="v3-ph-brand">NPL · 不良ABS 多行工作台</div>'
      + '<h1>切片报告</h1>'
      + '<p>' + (sliceActive() ? esc(sliceLabel()) : '全样本') + ' · ' + filteredRows().length + ' 单 · 数据截至 2026-10-31</p>';
  }

  function renderCompareInsight() {
    var checks = $$('.cmp-td input:checked');
    var names = checks.map(function (x) { return x.dataset.proj; });
    if (names.length < 2) return;
    var rows = names.map(function (n) {
      var r = ROW_BY_NAME[n];
      if (r) return r;
      var m = (typeof META !== 'undefined' && META) ? META[n] : null;
      if (!m) return null;
      return { n: n, b: m.bank, v: m.variety, r: m.recovery, a: m.achieve, dp: m.dispose, m: m.mult, x: m.sub_xirr, sp: m.sub_pct, i: m.issue, st: m.state, life: m.life };
    }).filter(Boolean);
    if (rows.length < 2) return;
    var drawer = document.getElementById('cmp-drawer');
    if (!drawer) return;
    var old = document.getElementById('v3-cmp-insight');
    if (old) old.remove();

    var recs = rows.filter(function (r) { return isNum(r.r); });
    var disps = rows.filter(function (r) { return isNum(r.dp); });
    var mults = rows.slice().filter(function (r) { return isNum(r.m); });
    var best = recs.slice().sort(function (a, b) { return b.r - a.r; });
    var lowDisp = disps.slice().sort(function (a, b) { return a.dp - b.dp; });
    var topMult = mults.sort(function (a, b) { return b.m - a.m; });
    var sampleRec = median(allRows.map(function (r) { return r.r; }));
    var sampleDisp = median(allRows.map(function (r) { return r.dp; }));
    var sampleMult = median(allRows.filter(function (r) { return r.st === 'settled'; }).map(function (r) { return r.m; }));
    var bits = [];
    if (best.length > 1) bits.push('回收率最高 <b>' + esc(best[0].n) + '</b> ' + pct(best[0].r) + '，最低 <b>' + esc(best[best.length - 1].n) + '</b> ' + pct(best[best.length - 1].r));
    if (lowDisp.length) bits.push('处置费率最低 <b>' + esc(lowDisp[0].n) + '</b> ' + pct(lowDisp[0].dp));
    if (topMult.length) bits.push('次级倍数最高 <b>' + esc(topMult[0].n) + '</b> ' + x2(topMult[0].m));
    var vs = '相对全样本中位：回收 ' + pct(sampleRec) + '、处置 ' + pct(sampleDisp) + '、次级倍数 ' + (sampleMult == null ? '—' : sampleMult.toFixed(2) + 'x') + '。';
    var text = bits.length ? bits.join('；') + '。' + vs : '这组项目缺少可比较的回报字段。';

    var metrics = [['r', '回收率', pct], ['dp', '处置费率', pct], ['a', '达成率', pct], ['m', '次级倍数', x2]];
    var mini = metrics.map(function (mt) {
      var vals = rows.map(function (r) { return isNum(r[mt[0]]) ? r[mt[0]] : null; });
      var max = Math.max.apply(null, vals.filter(function (v) { return v != null; }).concat([0.0001]));
      var bars = rows.map(function (r) {
        var v = r[mt[0]];
        if (!isNum(v)) return '';
        return '<div class="v3-cm-deal"><i style="width:' + Math.max(3, Math.min(100, v / max * 100)).toFixed(1) + '%;background:' + bankColor(r.b) + '"></i>'
          + '<b>' + mt[2](v) + '</b><span>' + esc(r.n.replace(/20\d\d年?/, '')) + '</span></div>';
      }).join('');
      return '<div class="v3-cm-row"><span class="v3-cm-lab">' + mt[1] + '</span><div class="v3-cm-bars">' + bars + '</div></div>';
    }).join('');

    var box = document.createElement('div');
    box.id = 'v3-cmp-insight';
    box.innerHTML = '<div class="v3-cm-head">对比结论 <span>' + rows.length + ' 单</span></div>'
      + '<p>' + text + '</p><div class="v3-cm-mini">' + mini + '</div>';
    var table = document.getElementById('cmp-table');
    if (table && table.parentNode) table.insertAdjacentElement('afterend', box);
    else drawer.querySelector('.drawer-body').appendChild(box);
  }

  function upgradeCompare() {
    var btn = document.getElementById('cmp-open');
    if (!btn || btn.dataset.v3) return;
    btn.dataset.v3 = '1';
    btn.addEventListener('click', function () { setTimeout(renderCompareInsight, 0); });
  }

  var REPORT_THEME = [
    ':root{',
    '--canvas:#F5F6F8 !important;--card:#FFFFFF !important;--surface:#F8F9FB !important;--surface2:#EEF1F5 !important;--hover:#F8FAFC !important;--soft:#F5F7F9 !important;',
    '--ink:#0A0F1A !important;--ink2:#344054 !important;--ink3:#667085 !important;--ink4:#98A2B3 !important;--sub:#667085 !important;--mute:#98A2B3 !important;',
    '--line:rgba(10,15,26,.10) !important;--line2:rgba(10,15,26,.06) !important;--line3:rgba(10,15,26,.18) !important;',
    '--r:6px !important;--r-card:8px !important;--r-chip:4px !important;',
    '--serif:"Microsoft YaHei UI","Microsoft YaHei","PingFang SC",sans-serif !important;',
    '--accent:#D92D20 !important;--accent-soft:#FEF3F2 !important;--accent-line:#FECDCA !important;',
    '--pos:#B42318 !important;--neg:#067647 !important;--warn:#B54708 !important;',
    '--grad:linear-gradient(150deg,#1F2937,#0A0F1A) !important;--grad-soft:none !important;',
    '--sh:0 1px 2px rgba(16,24,40,.05) !important;--sh-h:0 2px 8px rgba(16,24,40,.07) !important;',
    '}',
    'html,body{font-family:"Microsoft YaHei UI","Microsoft YaHei","PingFang SC",sans-serif !important;background:#F5F6F8 !important;color:#0A0F1A !important}',
    'body{background-image:none !important}',
    '.sidebar{background:#F8F9FB !important;border-right:1px solid rgba(10,15,26,.08) !important}',
    '.sidebar .sb-title,.sidebar .sb-sub{color:#0A0F1A !important}',
    '.sidebar .sb-item,.sidebar .sb-type,.sidebar .sb-ghead,.sidebar .sb-search{color:#344054 !important}',
    '.sidebar .sb-item:hover,.sidebar .sb-item.on{background:#FEF3F2 !important;color:#B42318 !important}',
    '.topbar{background:#FFFFFF !important;color:#0A0F1A !important;border-bottom:1px solid rgba(10,15,26,.08) !important}',
    '.topbar .crumb,.topbar .crumb *{color:#667085 !important}',
    '.card,.fold,.accm,.panel{background:#FFFFFF !important;border-color:rgba(10,15,26,.10) !important;box-shadow:0 1px 2px rgba(16,24,40,.04) !important;border-radius:8px !important}',
    '.hero{background:linear-gradient(180deg,#FFFFFF,#FBF7EE) !important;border:1px solid rgba(176,138,87,.18) !important;border-radius:8px !important}',
    'h1,h2,h3,h4,.hero h1,.fold-h .ft{color:#0A0F1A !important;font-family:"Microsoft YaHei UI","Microsoft YaHei",sans-serif !important}',
    'section.view{--accent:#D92D20 !important;--accent-soft:#FEF3F2 !important;--accent-line:#FECDCA !important}',
    '.pill,.tag,.hbadge,.chip{border-radius:4px !important}',
    'table th{background:#FBF7EE !important;color:#6B4E1F !important}',
    '.num,.bigno,.kpi .v,.tbl th,.tbl td{font-variant-numeric:tabular-nums !important}',
    '.btn,button{border-radius:4px !important}',
    '@media(min-width:900px){.topbar{display:none !important}.main,.view{padding-top:0 !important}}'
  ].join('\n');

  function injectReportTheme() {
    var vf = document.getElementById('vframe');
    if (!vf) return;
    try {
      var d = vf.contentDocument;
      if (!d || !d.head || d.getElementById('v3-report-theme')) return;
      var st = d.createElement('style');
      st.id = 'v3-report-theme';
      st.textContent = REPORT_THEME;
      d.head.appendChild(st);
    } catch (e) {}
  }

  function setupReportTheme() {
    var vf = document.getElementById('vframe');
    if (!vf || vf.dataset.v3theme) return;
    vf.dataset.v3theme = '1';
    vf.addEventListener('load', injectReportTheme);
  }

  function setupReportPrint() {
    var vacts = document.querySelector('#viewer .vacts');
    if (!vacts || document.getElementById('v3-report-print')) return;
    var b = document.createElement('button');
    b.id = 'v3-report-print';
    b.className = 'vbtn';
    b.type = 'button';
    b.textContent = '打印';
    b.addEventListener('click', function () {
      var f = document.getElementById('vframe');
      try { f.contentWindow.focus(); f.contentWindow.print(); }
      catch (e) { window.print(); }
    });
    var close = vacts.querySelector('#vclose');
    if (close) vacts.insertBefore(b, close); else vacts.appendChild(b);
  }

  function setupSliceExtras() {
    var bar = document.querySelector('#view-cmp .filterbar[data-scope="cmp"]');
    if (bar && !bar.querySelector('[data-k="tenor"]')) {
      var count = bar.querySelector('.fb-count');
      var groups = [
        ['tenor', '期限', [['', '全部'], ['lt12', '<12月'], ['12to24', '12–24月'], ['ge24', '≥24月']]],
        ['sec', '证券化率', [['', '全部'], ['lt10', '<10%'], ['10to20', '10–20%'], ['ge20', '≥20%']]],
        ['ach', '达成率', [['', '全部'], ['lt95', '<95%'], ['95to105', '95–105%'], ['gt105', '>105%']]],
        ['state', '状态', [['', '全部'], ['settled', '已清算'], ['open', '存续']]],
        ['buyback', '回购', [['', '全部'], ['yes', '有回购'], ['no', '无回购']]]
      ];
      groups.forEach(function (g) {
        var div = document.createElement('div');
        div.className = 'fb-group';
        var html = '<span class="fb-lab">' + g[1] + '</span>';
        g[2].forEach(function (o) {
          html += '<button class="fb-chip' + (o[0] ? '' : ' on') + '" data-k="' + g[0] + '" data-v="' + o[0] + '">' + o[1] + '</button>';
        });
        div.innerHTML = html;
        if (count) bar.insertBefore(div, count); else bar.appendChild(div);
      });
      var hint = document.createElement('span');
      hint.className = 'fb-hint';
      hint.textContent = 'Ctrl/⌘ 多选 · 预测机构/评级字段未入库';
      if (count) bar.insertBefore(hint, count); else bar.appendChild(hint);

      var y0 = bar.querySelector('[data-k="year"]');
      var yg = y0 ? y0.closest('.fb-group') : null;
      if (yg) {
        var play = document.createElement('button');
        play.id = 'v3-year-play';
        play.type = 'button';
        play.className = 'v3-play-btn';
        play.textContent = '▶ 播放';
        play.title = '2021 → 2024 自动播放发行年份';
        yg.appendChild(play);
        play.addEventListener('click', function (e) {
          e.preventDefault(); e.stopPropagation();
          if (yearPlayTimer) stopYearPlay(); else startYearPlay();
        });
      }
    }

    if (!window.__v3SliceCapture) {
      document.addEventListener('click', function (e) {
        var ch = e.target && e.target.closest ? e.target.closest('.fb-chip') : null;
        if (!ch) return;
        var k = ch.dataset.k;
        if (['variety', 'year', 'tenor', 'sec', 'ach', 'state', 'buyback'].indexOf(k) < 0) return;
        e.preventDefault();
        e.stopImmediatePropagation();
        if (yearPlayTimer) stopYearPlay();
        setMultiSlice(k, ch.dataset.v || '', !(e.ctrlKey || e.metaKey));
      }, true);
      window.__v3SliceCapture = true;
    }

    $$('.fb-chip').forEach(function (ch) {
      if (!ch.title) ch.title = '点击单选；Ctrl/⌘ 点击多选';
    });

    $$('#view-table .filters button').forEach(function (btn) {
      if (btn.dataset.v3bound) return;
      btn.dataset.v3bound = '1';
      btn.addEventListener('click', function () { setTimeout(applyTableFilter, 0); });
    });
    var qel = document.getElementById('q');
    if (qel && !qel.dataset.v3bound) {
      qel.dataset.v3bound = '1';
      qel.addEventListener('input', function () { setTimeout(applyTableFilter, 0); });
    }
  }

  function init() {
    if (typeof SLICE_ROWS !== 'undefined' && SLICE_ROWS && SLICE_ROWS.length) {
      allRows = SLICE_ROWS.slice().sort(function (a, b) { return String(a.d || '').localeCompare(String(b.d || '')); });
    } else if (typeof META !== 'undefined' && META) {
      allRows = Object.keys(META).map(function (k) {
        var m = META[k];
        return { n: k, b: m.bank, v: m.variety, y: String(m.issue_date || '').slice(0, 4), d: m.issue_date, r: m.recovery, a: m.achieve, dp: m.dispose, m: m.mult, x: m.sub_xirr, i: m.issue, st: m.state };
      }).sort(function (a, b) { return String(a.d || '').localeCompare(String(b.d || '')); });
    }

    /* merge the full raw row fields needed by the remaining comparison charts */
    var byName = {};
    FULL.forEach(function (f) { byName[String(f.proj || '').replace(/\s+/g, '')] = f; });
    var merged = 0;
    allRows.forEach(function (r) {
      var f = byName[String(r.n || '').replace(/\s+/g, '')];
      if (!f) return;
      merged++;
      ['life', 'loss', 'doubt', 'sub_bal', 'coupon', 'sen_xirr', 'sub_amt', 'doubt_amt', 'loss_amt', 'recovered', 'pool', 'sec_rate'].forEach(function (k) {
        if (f[k] !== undefined) r[k] = f[k];
      });
    });
    window.__v3fullMerged = merged;

    /* repurchase flag is present in the single-project report text, not META */
    if (typeof REPORTS !== 'undefined' && REPORTS) {
      allRows.forEach(function (r) {
        var rep = REPORTS[r.n];
        if (!rep || !rep.b) return;
        var m = String(rep.b).match(/是否回购(?:[^是|否]{0,24})(是|否)/);
        r.buyback = m ? (m[1] === '是' ? 'yes' : 'no') : '';
      });
    }

    /* cash-flow allocation: parse the report's 存续期分配明细矩阵 (data-label/data-cum rows) */
    var cfParsed = 0;
    if (typeof REPORTS !== 'undefined' && REPORTS) {
      allRows.forEach(function (r) {
        var rep = REPORTS[r.n];
        if (!rep || !rep.b) return;
        var txt = String(rep.b);
        var re = /<tr data-label="([^"]*)" data-cum="([^"]*)"[^>]*>([\s\S]*?)<\/tr>/g;
        var match, cf = { sen: 0, sub: 0, fee: 0, other: 0, total: 0 };
        while ((match = re.exec(txt))) {
          var label = match[1];
          var amount = parseFloat(match[2]);
          if (!isFinite(amount) || amount <= 0) continue;
          var cm = match[3].match(/<td[^>]*class="l"[^>]*>([^<]*)<\/td>\s*<td[^>]*class="l"[^>]*>([^<]*)<\/td>/);
          var cat = cm ? cm[2] : '';
          if (label.indexOf('优先档') === 0) cf.sen += amount;
          else if (label.indexOf('次级档') === 0) cf.sub += amount;
          else if (cat === '费用') cf.fee += amount;
          else cf.other += amount;
          cf.total += amount;
        }
        if (cf.total > 0) { r.cf = cf; cfParsed++; }
      });
    }
    window.__v3cashflowParsed = cfParsed;

    ROW_BY_NAME = {};
    allRows.forEach(function (r) { ROW_BY_NAME[r.n] = r; });
    window.__rowByName = ROW_BY_NAME;

    setFavicon();
    buildTopbar();
    /* the full-screen report viewer must escape main's stacking context */
    var viewer = document.getElementById('viewer');
    if (viewer && viewer.parentNode !== document.body) document.body.appendChild(viewer);
    recolorSvg();
    buildTape();
    mountCharts();
    mountPoolTable();
    mountPoolScatterCard();
    mountSeniorSubCard();
    mountCashflowCard();
    var s6note = $('#s6 .note');
    if (s6note) s6note.textContent = s6note.textContent.replace('颜色 = 品种', '颜色 = 银行');
    var ib = $('#insights');
    origInsightsHTML = ib ? ib.innerHTML : '';
    var tk = document.querySelector('#s1 .takeaways');
    origTakeawaysHTML = tk ? tk.innerHTML : '';
    var fr = $('#filter-results');
    if (fr && ib && fr.parentNode === ib.parentNode) ib.insertAdjacentElement('afterend', fr);
    mountMatrixCard();
    reorderLayout();
    setupVslice();
    setupSliceExtras();
    setupPrintHead();
    upgradeCompare();
    setupReportTheme();
    setupReportPrint();
    wrapOpenReport();
    setupReturnMemory();
    markStaticFigures();
    window.__v3AfterSlice = refreshAll;
    window.__applySlice = applyMultiSlice;
    window.__setSlice = setMultiSlice;
    window.__clearSlice = clearAll;
    readSliceUrl();
    applyMultiSlice();
    animateKpis();
    setTimeout(function () { chartMounts.forEach(function (m) { try { m.chart.resize(); } catch (e) {} }); }, 180);
    window.addEventListener('resize', function () {
      clearTimeout(window.__v3rz);
      window.__v3rz = setTimeout(function () { chartMounts.forEach(function (m) { try { m.chart.resize(); } catch (e) {} }); }, 120);
    });
  }

  /* delegated slice controls (the legacy filter handler runs first) */
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    if (t.closest('.fb-chip')) { setTimeout(refreshAll, 0); return; }
    if (t.closest('#v3-toggle-results')) {
      e.preventDefault();
      document.body.classList.toggle('v3-show-results');
      var showing = document.body.classList.contains('v3-show-results');
      var tb = $('#v3-toggle-results');
      if (tb) {
        tb.textContent = (showing ? '收起匹配项目' : '查看匹配项目') + '（' + filteredRows().length + '）';
        tb.setAttribute('aria-expanded', showing ? 'true' : 'false');
      }
      if (showing) {
        var fr = $('#filter-results');
        if (fr) setTimeout(function () { fr.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 60);
      }
      return;
    }
    if (t.closest('#v3-clear-slice')) { e.preventDefault(); clearAll(); return; }
    if (t.closest('#v3-table-clear')) { e.preventDefault(); clearAll(); return; }
    if (t.closest('#v3-pill button')) { e.preventDefault(); clearAll(); return; }
  }, false);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(init, 90); });
  } else {
    setTimeout(init, 90);
  }
})();
