/* =====================================================================
   V2-APP — кабинет, таб-структура + скин на токенах (обновлено 09.07.2026).
   Принцип: разметку ДВИЖКА НЕ трогаем — секции переезжают в экраны-табы
   (appendChild сохраняет id и обработчики), сверху новый экран «Сегодня».
   Табы: Сегодня · Питание · Тренировки · Покупки · Профиль.
   Питание: сразу исключения → приёмы пищи (сетка 90 дней скрыта,
   текущий день открывается сам). Зачёркивание дней — на «Сегодня»:
   удержание чипа ИЛИ авто-режим от кнопки «Начать план».
   До фиксации данных доступен только «Профиль» (гейтинг).
   Дизайн-токены в :root — смена скина = замена блока переменных.
   ===================================================================== */
(function () {
  'use strict';
  // Работает на ДВУХ страницах:
  //  • кабинет   (cabinet.html, IS_CABINET=true)  — полная таб-оболочка с гейтом/локами;
  //  • витрина   (index.html,   IS_CABINET=false) — та же оболочка в «витрин-режиме»
  //    (V2_STORE): БЕЗ локов, с пробным меню, превью тренировок и CTA на оплату.
  // Раньше выходили при !IS_CABINET, поэтому витрина оставалась плоской «лентой».
  if (typeof IS_CABINET === 'undefined') return;
  const V2_STORE = (IS_CABINET === false);

  /* ---------------- ДИЗАЙН-ТОКЕНЫ (скин В1) ---------------- */
  const css = document.createElement('style');
  css.textContent = `
  :root{
    /* СКИН С2 «Полночь и шампанское». Откат на С1: см. app-v2/ТЕМЫ.md */
    --v2-bg:#0A0E14; --v2-surface:#131A25; --v2-line:rgba(220,190,121,.16);
    --v2-gold:#DCBE79; --v2-gold2:#F2D995; --v2-cream:#EFDDB0; --v2-green:#5FBF7A;
    --v2-text:#F1EFEA; --v2-muted:#8E93A1;
    --v2-radius:10px; --v2-serif:'Inter',-apple-system,sans-serif;
  }
  .v2-screen{display:none;animation:v2fade .25s ease}
  .v2-screen.on{display:block}
  @keyframes v2fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
  body{padding-bottom:calc(110px + env(safe-area-inset-bottom,0px)) !important}
  /* таб-бар.
     БАГ «улетает на середину при скролле» (моб. Chromium/WebKit): position:fixed + transform
     + backdrop-filter — известная связка, из-за которой фикс-слой рассинхронизируется со
     скроллом (на десктопе не воспроизводится; лечится перезагрузкой = транзиентно). Убраны
     ОБА триггера: центрируем без transform (left/right + margin:auto), backdrop-filter снят
     (фон и так .97 — почти непрозрачный, блюр за ним не виден). Так бар железно висит внизу. */
  #v2-tabbar{
    position:fixed;bottom:0;left:0;right:0;margin:0 auto;width:100%;max-width:480px;
    height:calc(76px + env(safe-area-inset-bottom,0px));z-index:500;display:flex;padding:4px 6px calc(10px + env(safe-area-inset-bottom,0px));
    background:#080B12;   /* сплошной (был .97 — сквозь него просвечивал фон тонкой линией при листании) */
    border-top:1px solid var(--v2-line);
    box-shadow:0 6px 0 0 #080B12;   /* дотягивает фон бара вниз — закрывает тонкую щель под баром (просвет при листании) */
  }
  .v2-tab{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;
    color:var(--v2-muted);font-size:9.5px;font-weight:600;letter-spacing:.03em;cursor:pointer;
    border:none;background:none;font-family:inherit;transition:color .2s,opacity .2s,transform .12s;position:relative;border-radius:10px;margin:4px 2px}
  .v2-tab .i{font-size:20px;transition:transform .2s}
  .v2-tab:active{transform:scale(.88);background:rgba(220,190,121,.1)}
  .v2-tab.on{color:var(--v2-cream);background:rgba(220,190,121,.13);box-shadow:inset 0 0 0 1px rgba(220,190,121,.3)}
  .v2-tab.on .i{transform:translateY(-2px) scale(1.12);filter:drop-shadow(0 0 8px rgba(242,217,149,.5))}
  .v2-tab.locked{opacity:.35;pointer-events:auto}
  .v2-tab.locked::after{content:'🔒';position:absolute;top:2px;right:16%;font-size:9px}
  /* Онбординг-гейт витрины: пока нет данных — «Профиль» подсвечен «дышит», остальные приглушены (.locked) */
  .v2-tab.gate-hi{color:var(--v2-gold2)}
  .v2-tab.gate-hi .i{animation:v2breathe 1.6s ease-in-out infinite}
  @keyframes v2breathe{0%,100%{transform:scale(1);filter:none}50%{transform:scale(1.16);filter:drop-shadow(0 0 6px var(--v2-gold))}}
  /* После «Подтвердить» — короткая вспышка разблокировки (~2с), потом успокаивается */
  .v2-tab.unlock-pulse{animation:v2unlock .85s ease-in-out 3}
  @keyframes v2unlock{
    0%,100%{filter:none;color:var(--v2-muted);transform:none;background:transparent}
    50%{filter:drop-shadow(0 0 12px var(--v2-gold2));color:var(--v2-gold2);transform:translateY(-3px) scale(1.12);background:rgba(220,190,121,.18)}
  }
  /* Карточки на «Сегодня» под гейтом — приглушены + замок; клик уводит в «Профиль» */
  .v2-link-card.locked-card{opacity:.4;position:relative}
  .v2-link-card.locked-card .arr{opacity:0}
  .v2-link-card.locked-card::after{content:'🔒';position:absolute;right:14px;top:50%;transform:translateY(-50%);font-size:13px}
  /* Инфо-блоки под гейтом (серия «0 дн.», «0/90 дней», «твоя цель») — тоже приглушены до ввода данных */
  .v2-dim{opacity:.4}
  /* «Не тренируюсь» (trainWeekly===0): таб «Тренировки» приглушён и некликабелен (ведёт к подсказке) */
  .v2-tab.notrain{opacity:.35;pointer-events:auto}
  .v2-tab.notrain::after{content:'😴';position:absolute;top:2px;right:16%;font-size:9px}
  /* шапка «Сегодня» */
  #v2-hero{position:relative;overflow:hidden;margin-bottom:14px}
  #v2-hero img{width:100%;display:block;max-height:300px;object-fit:cover;object-position:top}
  #v2-hero::after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(8,11,18,.05) 30%,var(--v2-bg) 97%)}
  #v2-hero .in{position:absolute;left:18px;right:18px;bottom:10px;z-index:2}
  #v2-hero .hi{font-size:13px;color:var(--v2-muted)}
  #v2-hero .t{font-family:var(--v2-serif);font-size:24px;margin-top:3px}
  #v2-hero .t em{color:var(--v2-gold2);font-style:italic}
  .v2-pwrap{display:flex;align-items:center;gap:10px;margin-top:9px}
  .v2-pbar{flex:1;height:7px;border-radius:7px;background:rgba(241,239,234,.13);overflow:hidden}
  .v2-pbar i{display:block;height:100%;background:linear-gradient(90deg,var(--v2-gold),var(--v2-gold2));border-radius:7px;transition:width .6s ease}
  .v2-pct{font-size:12px;color:var(--v2-gold2);font-weight:700}
  .v2-pad{padding:0 16px}
  .v2-kbju{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin-bottom:14px}
  .v2-kb{background:var(--v2-surface);border:1px solid var(--v2-line);border-radius:14px;padding:10px 8px;text-align:center}
  .v2-kb .v{font-family:var(--v2-serif);font-size:17px;font-weight:700;color:var(--v2-gold2)}
  .v2-kb .t{font-size:9.5px;color:var(--v2-muted);margin-top:2px;text-transform:uppercase;letter-spacing:.06em}
  /* лента дней + удержание */
  .v2-days{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;margin-bottom:6px;scrollbar-width:none}
  .v2-days::-webkit-scrollbar{display:none}
  .v2-dchip{min-width:52px;padding:10px 0;border-radius:9px;text-align:center;flex-shrink:0;
    background:var(--v2-surface);border:1px solid var(--v2-line);cursor:pointer;user-select:none;-webkit-user-select:none;position:relative;overflow:hidden}
  .v2-dchip .dw{font-size:9px;letter-spacing:.12em;color:var(--v2-muted);text-transform:uppercase}
  .v2-dchip .dn{font-family:var(--v2-serif);font-size:17px;font-weight:700;margin-top:2px}
  .v2-dchip.past{opacity:.42}
  .v2-dchip.past .dn{text-decoration:line-through}
  .v2-dchip.cur{background:linear-gradient(160deg,var(--v2-gold),var(--v2-gold2));border-color:transparent;color:#10131a}
  .v2-dchip.cur .dw{color:#6a5d3f}
  .v2-dchip .hold{position:absolute;left:0;bottom:0;top:auto;height:3px;width:0;background:var(--v2-green)}
  .v2-dchip.holding .hold{width:100%;transition:width .75s linear}
  .v2-hint{font-size:11px;color:var(--v2-muted);margin:0 0 12px;line-height:1.4}
  /* блок плана (старт/пауза/режим) */
  .v2-plan{background:var(--v2-surface);border:1px solid var(--v2-line);border-radius:var(--v2-radius);padding:13px 14px;margin-bottom:10px}
  .v2-plan .row{display:flex;align-items:center;gap:10px}
  .v2-plan .tt{font-size:13.5px;font-weight:600;flex:1}
  .v2-plan .ss{font-size:11px;color:var(--v2-muted);margin-top:2px}
  .v2-plan button{border:none;border-radius:11px;padding:9px 15px;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit}
  .v2-plan .go{background:linear-gradient(135deg,var(--v2-gold),var(--v2-gold2));color:#10131a}
  .v2-plan .stop{background:transparent;border:1px solid var(--v2-line);color:var(--v2-muted)}
  .v2-plan .mode{display:flex;gap:6px;margin-top:10px}
  .v2-plan .m{flex:1;padding:8px;border-radius:10px;border:1px solid var(--v2-line);background:transparent;color:var(--v2-muted);font-size:11px;font-weight:600;text-align:center;cursor:pointer}
  .v2-plan .m.on{background:rgba(220,190,121,.15);color:var(--v2-gold2);border-color:rgba(220,190,121,.4)}
  /* карточки-ссылки, стрик, статы */
  .v2-link-card{display:flex;align-items:center;gap:12px;background:var(--v2-surface);border:1px solid var(--v2-line);
    border-radius:var(--v2-radius);padding:14px;margin-bottom:10px;cursor:pointer;transition:border-color .2s,transform .15s}
  .v2-link-card:active{transform:scale(.985)}
  .v2-link-card .ic{width:46px;height:46px;border-radius:13px;background:rgba(220,190,121,.12);
    border:1px solid var(--v2-line);display:flex;align-items:center;justify-content:center;font-size:21px;flex-shrink:0}
  .v2-link-card .tt{font-size:15px;font-weight:600}
  .v2-link-card .ss{font-size:12px;color:var(--v2-muted);margin-top:2px}
  .v2-link-card .arr{margin-left:auto;color:var(--v2-gold2);font-size:18px}
  .v2-streak{display:flex;align-items:center;gap:12px;background:linear-gradient(135deg,rgba(220,190,121,.15),rgba(242,217,149,.05));
    border:1px solid rgba(220,190,121,.35);border-radius:var(--v2-radius);padding:15px;margin-bottom:10px}
  .v2-streak .f{font-size:26px;filter:saturate(.45) brightness(.95)}
  .v2-streak .v{font-family:var(--v2-serif);font-size:16px;font-weight:700}
  .v2-streak .t{font-size:11.5px;color:var(--v2-muted);margin-top:2px}
  .v2-stats{display:grid;grid-template-columns:1fr 1fr;gap:9px}
  .v2-st{background:var(--v2-surface);border:1px solid var(--v2-line);border-radius:14px;padding:13px;display:flex;gap:10px;align-items:center}
  .v2-st .i{width:36px;height:36px;border-radius:10px;background:rgba(220,190,121,.12);display:flex;align-items:center;justify-content:center;font-size:17px;filter:saturate(.5)}
  .v2-st .v{font-family:var(--v2-serif);font-size:15px;font-weight:700}
  .v2-st .t{font-size:10px;color:var(--v2-muted);margin-top:1px}
  .v2-screen-head{padding:20px 16px 4px}
  .v2-screen-head h2{font-family:var(--v2-serif);font-size:23px}
  .v2-screen-head .m{font-size:12.5px;color:var(--v2-muted);margin-top:3px}
  /* плавающие бары движка над таббаром */
  .sticky-bar{bottom:80px !important}
  #inlineBar{z-index:499}
  #installBanner{bottom:86px !important}
  .hero-banner{display:none}
  /* ПИТАНИЕ: сетка 90 дней и старые подсказки скрыты (лента дней — сверху) */
  #v2-screen-food #daysGrid{display:none !important}
  #v2-screen-food .v2-clp-btn{display:none !important}
  #v2-screen-food .days-hint-marquee,#v2-screen-food .marquee-hint{display:none !important}
  #v2-screen-food #days-section > .section-label{display:none !important}
  #v2-screen-food .meal-count-label{display:none !important}
  /* «Исключено из меню» — только один блок, ПОД меню (копию внутри дня прячем) */
  #v2-screen-food #dayMealsContainer #exclusion-banner,
  #v2-screen-food #mealsContainer #exclusion-banner{display:none !important}
  #v2-screen-food #meal-section > .section-label{display:none !important}
  #v2-food-days{padding:6px 16px 0}
  /* общий модал */
  #v2-modal{position:fixed;inset:0;z-index:800;background:rgba(0,0,0,.72);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:20px}
  #v2-modal .box{width:100%;max-width:360px;background:linear-gradient(180deg,#141c1a,#0c1412);border:1px solid rgba(220,190,121,.35);border-radius:20px;padding:24px 20px;text-align:center;box-shadow:0 30px 80px rgba(0,0,0,.6)}
  #v2-modal .em{font-size:32px;margin-bottom:10px}
  #v2-modal .tt{font-family:var(--v2-serif);font-size:18px;margin-bottom:8px}
  #v2-modal .ss{font-size:13.5px;color:var(--v2-muted);line-height:1.55}
  #v2-modal .ok{display:block;width:100%;margin-top:16px;padding:12px;border-radius:12px;border:none;background:linear-gradient(135deg,var(--v2-gold),var(--v2-gold2));color:#10131a;font-weight:700;font-size:14px;cursor:pointer;font-family:inherit}
  /* ---- ВИТРИН-РЕЖИМ (без локов; тизер платного, пробный день, метка на табе) ---- */
  .v2-tab.store-pro::after{content:'🔒';position:absolute;top:2px;right:16%;font-size:9px;opacity:.6;pointer-events:none}
  .v2-store-teaser{margin:8px 16px 14px;background:var(--v2-surface);border:1px solid rgba(220,190,121,.35);border-radius:16px;padding:22px 18px;text-align:center}
  .v2-store-teaser .em{font-size:34px;margin-bottom:8px}
  .v2-store-teaser .tt{font-family:var(--v2-serif);font-size:18px;margin-bottom:6px;color:var(--v2-gold2)}
  .v2-store-teaser .ss{font-size:13px;color:var(--v2-muted);line-height:1.55;margin-bottom:16px}
  .v2-store-teaser .cta{border:none;border-radius:12px;padding:12px 18px;font-size:14px;font-weight:700;cursor:pointer;font-family:inherit;background:linear-gradient(135deg,var(--v2-gold),var(--v2-gold2));color:#10131a}
  .v2-store-trial{margin:8px 16px 12px;font-size:12.5px;color:var(--v2-cream);background:rgba(220,190,121,.1);border:1px solid rgba(220,190,121,.3);border-radius:12px;padding:10px 12px;line-height:1.5}
  #v2-store-note{margin:0 16px 12px;font-size:12.5px;color:var(--v2-cream);background:rgba(220,190,121,.1);border:1px solid rgba(220,190,121,.3);border-radius:12px;padding:10px 12px;line-height:1.5}
  `;
  document.head.appendChild(css);

  /* ---------------- КАРКАС ---------------- */
  const TABS = [
    { id:'food',     icon:'🍽',  label:'Питание' },
    { id:'workouts', icon:'🏋️', label:'Тренировки' },
    { id:'today',    icon:'✨',  label:'Сегодня' },
    { id:'shop',     icon:'🛒',  label:'Покупки' },
    { id:'profile',  icon:'👤',  label:'Профиль' },
  ];
  const MOVE = {
    food:     ['inlineBarPlaceholder','meal-section','inlineBarPlaceholderBelow','days-section'],
    workouts: ['workouts-section'],
    shop:     ['shopping-list-section'],
    profile:  ['fixedParamsCard','activityCard','trainingExpCard','results','purchase-section'],
  };
  let heroImgSrc = 'design/bg_hero.webp';
  let _gateLocked = null; // null = ещё не знаем
  const _bootTs = Date.now();

  function build() {
    const main = document.getElementById('page-main');
    if (!main || document.getElementById('v2-tabbar')) return;
    const hb = document.querySelector('.hero-banner img');
    if (hb) heroImgSrc = hb.getAttribute('src') || heroImgSrc;

    const host = document.createElement('div');
    host.id = 'v2-screens';
    TABS.forEach(t => {
      const s = document.createElement('div');
      s.className = 'v2-screen'; s.id = 'v2-screen-' + t.id;
      host.appendChild(s);
    });
    main.insertBefore(host, main.firstChild);

    Object.entries(MOVE).forEach(([screen, ids]) => {
      const s = document.getElementById('v2-screen-' + screen);
      ids.forEach(id => { const el = document.getElementById(id); if (el) s.appendChild(el); });
    });

    addHead('food', 'Питание', V2_STORE
      ? 'Пробное меню одного дня — полный план на 90 дней после оплаты'
      : 'Исключения, приёмы пищи и готовое меню дня');
    const foodScreen = document.getElementById('v2-screen-food');
    if (!V2_STORE) {
      // лента дней 1–90 — в самый верх Питания (под заголовком). На витрине дней нет (только пробный).
      const strip = document.createElement('div');
      strip.id = 'v2-food-days';
      strip.innerHTML = '<div class="v2-days" id="v2-food-days-strip"></div>'
        + '<div class="v2-hint">Листай дни. Удержание (~1 сек) — зачеркнуть пройденный, повторно — вернуть.</div>';
      const fh = foodScreen.querySelector('.v2-screen-head');
      fh ? fh.after(strip) : foodScreen.prepend(strip);
    }
    // исключения — в самый низ Питания
    const exc = document.getElementById('exclusion-banner-top');
    if (exc) foodScreen.appendChild(exc);
    if (!V2_STORE) renderFoodDays();
    // попап при смене количества приёмов (5/6/замочек)
    wrapMealCountFns();
    addHead('workouts', 'Тренировки', 'Программа под твой профиль с прогрессией');
    addHead('shop', 'Покупки', 'Продукты по твоему меню — на выбранное число дней');
    addHead('profile', 'Профиль', 'Данные, активность, норма и доступ');

    const bar = document.createElement('div');
    bar.id = 'v2-tabbar';
    bar.innerHTML = TABS.map(t =>
      '<button class="v2-tab" data-tab="' + t.id + '"><span class="i">' + t.icon + '</span>' + t.label + '</button>'
    ).join('');
    document.body.appendChild(bar);
    bar.querySelectorAll('.v2-tab').forEach(b => b.addEventListener('click', () => {
      if (b.classList.contains('notrain')) {
        pulse(b);
        v2Modal('😴', 'Ты выбрал: не тренируюсь',
          'Раздел тренировок отключён. Захочешь программу — открой «Профиль» и укажи, сколько раз в неделю готов тренироваться.');
        return;
      }
      if (b.classList.contains('locked')) { pulse(b); return; }
      show(b.dataset.tab);
    }));

    renderToday();
    applyTrainState();
    if (V2_STORE) { storefrontSetup(); show('today'); applyGate(true); }
    else {
      // 16.07 (просьба Замира): открываем СРАЗУ на «Сегодня» (а не пустой синий экран).
      // Раньше applyGate(true) для готового профиля не активировал ни одну вкладку → пусто, пока не тапнешь
      // (и тап по «Профилю» давал прыжки скролла). Теперь: показываем «Сегодня» сразу; если профиль ещё
      // НЕ зафиксирован (новичок), applyGate уведёт на «Профиль». Возвращающийся — остаётся на «Сегодня».
      show('today');
      applyGate(true);
    }
    setInterval(() => {
      renderToday();
      applyTrainState();
      applyGate(false);   // и витрина, и кабинет: гейт снимается сам, когда появились данные (KБЖУ/фиксация)
      const f = document.getElementById('v2-screen-food');
      if (!V2_STORE && f && f.classList.contains('on')) renderFoodDays();
    }, 4000);
  }

  function pulse(el){ el.style.transform='scale(1.08)'; setTimeout(()=>el.style.transform='',180); }

  /* ---- КАСКАД «НЕ ТРЕНИРУЮСЬ» (trainWeekly===0) ----
     Единый источник — workouts.js (window._wkTrainWeekly). 0 → выключаем таб «Тренировки»
     и убираем карточку «Тренировка дня» с экрана «Сегодня». null (профиль не готов) →
     ничего не отключаем. Персистентность общая с профилем (freq хранится там же), так что
     каскад переживает F5/смену устройства и обновляется на лету (интервал 4с). */
  function trainWeeklyVal(){
    try { return (typeof window._wkTrainWeekly === 'function') ? window._wkTrainWeekly() : null; }
    catch (e) { return null; }
  }
  function applyTrainState(){
    const off = (trainWeeklyVal() === 0);
    document.querySelectorAll('.v2-tab[data-tab="workouts"]').forEach(b => b.classList.toggle('notrain', off));
    // если пользователь оказался на выключенной вкладке (напр. сменил активность, будучи в ней) — увести на «Сегодня»
    if (off) {
      const w = document.getElementById('v2-screen-workouts');
      if (w && w.classList.contains('on')) show('today');
    }
  }

  function addHead(screen, title, sub) {
    const s = document.getElementById('v2-screen-' + screen);
    const h = document.createElement('div');
    h.className = 'v2-screen-head';
    h.innerHTML = '<h2>' + title + '</h2><div class="m">' + sub + '</div>';
    s.insertBefore(h, s.firstChild);
  }

  function show(tab) {
    document.querySelectorAll('.v2-screen').forEach(s => s.classList.toggle('on', s.id === 'v2-screen-' + tab));
    document.querySelectorAll('.v2-tab').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
    window.scrollTo(0, 0);
    if (tab === 'workouts' && typeof window._v2RenderWorkouts === 'function') window._v2RenderWorkouts();
    if (!V2_STORE && tab === 'food') { renderFoodDays(true); openDayInFood(currentDay()); }
  }
  window._v2ShowTab = show;

  /* ---------------- ОБЩИЙ МОДАЛ ---------------- */
  function v2Modal(emoji, title, text) {
    const old = document.getElementById('v2-modal'); if (old) old.remove();
    const m = document.createElement('div');
    m.id = 'v2-modal';
    m.innerHTML = '<div class="box"><div class="em">' + emoji + '</div><div class="tt">' + title + '</div>'
      + '<div class="ss">' + text + '</div><button class="ok">Понятно</button></div>';
    m.addEventListener('click', e => { if (e.target === m || e.target.classList.contains('ok')) m.remove(); });
    document.body.appendChild(m);
  }

  /* ------ попап при смене числа приёмов (5/6/замочек) ------ */
  function wrapMealCountFns() {
    if (typeof window.setMealCount === 'function' && !window.setMealCount._v2wrapped) {
      const orig = window.setMealCount;
      window.setMealCount = function (n) {
        const r = orig.apply(this, arguments);
        v2Modal('🍽', 'Приёмов пищи: ' + n,
          'Меню дня пересобрано под твою норму КБЖУ с новым количеством приёмов.');
        return r;
      };
      window.setMealCount._v2wrapped = true;
    }
    if (typeof window.toggleMealCountLock === 'function' && !window.toggleMealCountLock._v2wrapped) {
      const orig = window.toggleMealCountLock;
      window.toggleMealCountLock = function () {
        const r = orig.apply(this, arguments);
        const locked = !!(typeof state === 'object' && state && state.mealCountLocked);
        v2Modal(locked ? '🔒' : '🔓',
          locked ? 'Количество приёмов зафиксировано' : 'Фиксация снята',
          locked ? 'Теперь во всех днях будет одинаковое число приёмов — пока не снимешь замок.'
                 : 'Число приёмов снова можно менять для каждого дня.');
        return r;
      };
      window.toggleMealCountLock._v2wrapped = true;
    }
  }

  /* ------ лента дней 1–90 в Питании ------ */
  let _v2ViewDay = 0;      // #48: какой день пользователь СЕЙЧАС смотрит (не обязательно «сегодня»)
  let _v2DaysSig = '';     // подпись состояния ленты — чтобы фоновый 4-сек интервал не пересобирал её без изменений
  let _v2Pressing = false; // #49: идёт удержание чипа — ленту не пересобирать (иначе чип отрывается, таймер дожигает зачёркивание)
  function renderFoodDays(scrollToCur) {
    if (V2_STORE) return; // на витрине ленты дней нет (только пробный день)
    const wrap = document.getElementById('v2-food-days-strip');
    if (!wrap) return;
    const DS = (typeof dayStates === 'object' && dayStates) ? dayStates : {};

    const total = (typeof PLAN_DAYS !== 'undefined') ? PLAN_DAYS : 90;
    // #48: подсвечиваем день, который смотрит пользователь; если он не выбран или зачёркнут — «сегодня».
    let hi = _v2ViewDay;
    if (!hi || (DS[hi] && DS[hi].used)) hi = currentDay();
    // Подпись состояния ленты. Если ничего не изменилось (и не форс-скролл) — НЕ трогаем innerHTML.
    // Иначе фоновый интервал (каждые 4с): (а) сбрасывал подсветку на «сегодня» [#48]; (б) рвал чип
    // посреди нажатия → pointerup терялся, таймер 750мс дожигал crossDay [#49].
    let usedSig = '';
    for (let d = 1; d <= total; d++) if (DS[d] && DS[d].used) usedSig += d + ',';
    const sig = total + '|' + hi + '|' + usedSig;
    if (_v2Pressing) return;                                                    // идёт удержание — DOM не трогаем
    if (!scrollToCur && sig === _v2DaysSig && wrap.children.length) return;     // без изменений — выходим
    _v2DaysSig = sig;
    let h = '';
    for (let d = 1; d <= total; d++) {
      const past = (DS[d] && DS[d].used);
      h += '<div class="v2-dchip ' + (d === hi ? 'cur' : past ? 'past' : '') + '" data-day="' + d + '">'
        + '<div class="dw">день</div><div class="dn">' + d + '</div><span class="hold"></span></div>';
    }
    wrap.innerHTML = h;
    wrap.querySelectorAll('.v2-dchip').forEach(ch => {
      const d = parseInt(ch.dataset.day, 10);
      let t = null, fired = false, sx = 0, sy = 0;
      const onMove = (ev) => { if (Math.abs(ev.clientX - sx) > 8 || Math.abs(ev.clientY - sy) > 8) cancel(); };
      function cancel() { clearTimeout(t); _v2Pressing = false; ch.classList.remove('holding');
        document.removeEventListener('pointermove', onMove);
        window.removeEventListener('scroll', cancel, true); }
      ch.addEventListener('pointerdown', (e) => {
        fired = false; sx = e.clientX; sy = e.clientY; _v2Pressing = true; ch.classList.add('holding');
        document.addEventListener('pointermove', onMove);
        window.addEventListener('scroll', cancel, true);      // #49: прокрутка ленты во время удержания = листание, не зачёркивание
        t = setTimeout(() => { fired = true; _v2Pressing = false; ch.classList.remove('holding');
          document.removeEventListener('pointermove', onMove); window.removeEventListener('scroll', cancel, true);
          crossDay(d); renderFoodDays(); renderToday(); }, 750);
      });
      ch.addEventListener('pointerup', () => { const wf = fired; cancel(); if (!wf) openDayInFood(d); });
      ch.addEventListener('pointerleave', cancel);
    });
    // прокрутка: к текущему дню при открытии вкладки; при фоновом обновлении — не трогаем
    if (scrollToCur) {
      const curEl = wrap.querySelector('.v2-dchip.cur');
      if (curEl) curEl.scrollIntoView({ inline: 'center', block: 'nearest' });
    }
  }

  // открыть меню дня d (сетка скрыта, но кнопки движка живы)
  function openDayInFood(d) {
    setTimeout(() => {
      try {
        const btn = document.getElementById('day-btn-' + d);
        if (btn && typeof dayStates === 'object' && dayStates[d] && !dayStates[d].used) {
          _v2ViewDay = d;                    // #48: лента будет держать подсветку на этом дне (а не сбрасывать на «сегодня»)
          if (!dayStates[d].open) btn.click();
          // подсветить выбранный день в ленте
          document.querySelectorAll('#v2-food-days-strip .v2-dchip').forEach(c => c.classList.toggle('cur', +c.dataset.day === d));
          // движок после рендера дня скроллит к меню — возвращаем страницу наверх,
          // чтобы вкладка открывалась с ленты дней
          setTimeout(() => window.scrollTo(0, 0), 250);
          setTimeout(() => window.scrollTo(0, 0), 600);
        }
      } catch (e) {}
    }, 120);
  }

  /* ---------------- ГЕЙТИНГ: до фиксации — только Профиль ---------------- */
  function applyGate(first) {
    const st = (typeof state === 'object' && state) ? state : {};
    let locked;
    if (V2_STORE) {
      // Витрина (Замир 16.07): онбординг-гейт — пока не введены данные (нет нормы КБЖУ), доступен только
      // «Профиль». Остальные табы приглушены + замок; на «Сегодня» гаснут карточки (см. renderToday).
      locked = !(st.kcal > 0);
    } else {
      // Пока авторизация/профиль ещё грузятся (первые секунды) — ничего не решаем.
      const authPending = !st.loggedInEmail && !st.profileLocked && (Date.now() - _bootTs < 12000);
      if (authPending) return;
      locked = !st.profileLocked;
    }
    if (locked === _gateLocked) return;
    const wasLocked = _gateLocked;
    _gateLocked = locked;
    document.querySelectorAll('.v2-tab').forEach(b => {
      if (b.dataset.tab !== 'profile') b.classList.toggle('locked', locked);
      else b.classList.toggle('gate-hi', locked);   // «Профиль» подсвечен, пока гейт активен
    });
    if (locked) {
      if (!V2_STORE) {   // кабинет уводит в «Профиль»; витрина остаётся на «Сегодня» (карточки там сами гаснут)
        show('profile');
        const s = document.getElementById('v2-screen-profile');
        if (s && !document.getElementById('v2-gate-note')) {
          const n = document.createElement('div');
          n.id = 'v2-gate-note';
          n.style.cssText = 'margin:0 16px 12px;font-size:12.5px;color:var(--v2-gold2);background:rgba(220,190,121,.1);border:1px solid rgba(220,190,121,.3);border-radius:12px;padding:10px 12px;line-height:1.5';
          n.textContent = 'Заполни и зафиксируй свои данные — после этого откроются все разделы: меню, тренировки и покупки.';
          const head = s.querySelector('.v2-screen-head');
          head ? head.after(n) : s.prepend(n);
        }
      }
    } else {
      const n = document.getElementById('v2-gate-note'); if (n) n.remove();
      if (wasLocked === true) pulseUnlockTabs();   // разблокировали → короткая вспышка на пару секунд
    }
    try { renderToday(); } catch (e) {}   // перерисовать «Сегодня» под текущий гейт
  }
  // Короткая вспышка всех табов после разблокировки (~2с), затем успокаивается.
  function pulseUnlockTabs() {
    document.querySelectorAll('.v2-tab').forEach(b => {
      b.classList.add('unlock-pulse');
      setTimeout(() => { b.classList.remove('unlock-pulse'); }, 2700);
    });
  }
  // Хук для index.html: после «Подтвердить» (посчитан КБЖУ) — сразу снять гейт со вспышкой.
  window._v2Refresh = function () { try { applyGate(false); } catch (e) {} };

  /* ---------------- ВИТРИН-РЕЖИМ: без локов, пробное меню, CTA ---------------- */
  function gotoPricing() {
    show('profile');
    setTimeout(() => {
      const p = document.getElementById('purchase-section');
      if (p) p.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 90);
  }
  function storeTeaser(screen, emoji, title, text) {
    const s = document.getElementById('v2-screen-' + screen);
    if (!s || s.querySelector('.v2-store-teaser')) return;
    const t = document.createElement('div');
    t.className = 'v2-store-teaser';
    t.innerHTML = '<div class="em">' + emoji + '</div>'
      + '<div class="tt">' + title + '</div>'
      + '<div class="ss">' + text + '</div>'
      + '<button class="cta" type="button">Оформить план за 1499 ₽</button>';
    t.querySelector('.cta').addEventListener('click', gotoPricing);
    const head = s.querySelector('.v2-screen-head');
    head ? head.after(t) : s.prepend(t);
  }
  function storefrontSetup() {
    const total = (typeof PLAN_DAYS !== 'undefined') ? PLAN_DAYS : 90;
    // Покупки — полностью платный раздел: метка на табе (НЕ лочим — клик ведёт к тизеру) + тизер.
    // Тренировки НЕ метим: workouts.js сам показывает 1 день-превью + CTA «Открыть всё».
    document.querySelectorAll('.v2-tab[data-tab="shop"]').forEach(b => b.classList.add('store-pro'));
    storeTeaser('shop', '🛒', 'Список покупок — в полном плане',
      'Продукты по твоему меню на выбранное число дней собираются автоматически после оплаты.');
    // Пробный день в «Питании».
    const food = document.getElementById('v2-screen-food');
    if (food && !food.querySelector('.v2-store-trial')) {
      const n = document.createElement('div');
      n.className = 'v2-store-trial';
      n.innerHTML = '🎁 <b>Пробный день бесплатно.</b> Заполни данные в «Профиле» и возвращайся — соберём меню точно в твою норму КБЖУ. '
        + 'Полное меню на ' + total + ' дней — после оплаты.';
      const head = food.querySelector('.v2-screen-head');
      head ? head.after(n) : food.prepend(n);
    }
    // Подсказка в «Профиле».
    const prof = document.getElementById('v2-screen-profile');
    if (prof && !document.getElementById('v2-store-note')) {
      const n = document.createElement('div');
      n.id = 'v2-store-note';
      n.textContent = 'Заполни данные — бесплатно узнаешь свою норму КБЖУ и получишь пробное меню. '
        + 'Полный план на ' + total + ' дней, тренировки и список покупок — после оплаты (ниже).';
      const head = prof.querySelector('.v2-screen-head');
      head ? head.after(n) : prof.prepend(n);
    }
  }

  /* ---------------- ДАННЫЕ ---------------- */
  function crossedCount() {
    let n = 0;
    try { if (typeof dayStates === 'object') for (const k in dayStates) if (dayStates[k] && dayStates[k].used) n++; } catch (e) {}
    return n;
  }
  function currentDay() {
    const total = (typeof PLAN_DAYS !== 'undefined') ? PLAN_DAYS : 90;
    try {
      if (typeof dayStates === 'object')
        for (let d = 1; d <= total; d++) if (!(dayStates[d] && dayStates[d].used)) return d;
    } catch (e) {}
    return Math.min(crossedCount() + 1, total);
  }
  function streak() {
    let n = 0;
    try { for (let d = currentDay() - 1; d >= 1; d--) { if (dayStates[d] && dayStates[d].used) n++; else break; } } catch (e) {}
    return n;
  }
  function crossDay(d, val) { // единая точка зачёркивания — как long-press в сетке движка
    try {
      if (typeof dayStates !== 'object') return;
      if (!dayStates[d]) dayStates[d] = { used:false, open:false };
      dayStates[d].used = (val === undefined) ? !dayStates[d].used : !!val;
      const b = document.getElementById('day-btn-' + d);
      if (b) b.classList.toggle('used', dayStates[d].used);
      if (typeof renderShoppingList === 'function') renderShoppingList();
      if (typeof saveProgressDebounced === 'function') saveProgressDebounced();
    } catch (e) {}
  }

  /* ---------------- ЭКРАН «СЕГОДНЯ» ---------------- */
  function renderToday() {
    const s = document.getElementById('v2-screen-today');
    if (!s) return;
    const st = (typeof state === 'object' && state) ? state : {};
    const total = (typeof PLAN_DAYS !== 'undefined') ? PLAN_DAYS : 90;
    const day = currentDay();
    const pct = (crossedCount() >= total) ? 100 : Math.round((day - 1) / total * 100);
    const kcal = st.kcal || 0;
    // Витрина-онбординг: пока нет данных (нормы КБЖУ) — все карточки-разделы приглушены (кроме «заполни данные»).
    const gated = V2_STORE && !(kcal > 0);
    const _lk = gated ? ' locked-card' : '';

    s.innerHTML =
      '<div id="v2-hero"><img src="' + heroImgSrc + '" alt="">'
      + '<div class="in"><div class="t">Сегодня — <em>день ' + day + ' из ' + total + '</em></div>'
      + '<div class="v2-pwrap"><div class="v2-pbar"><i style="width:' + pct + '%"></i></div><span class="v2-pct">' + pct + '%</span></div>'
      + '</div></div>'
      + '<div class="v2-pad">'
      // P3a: нудж перевзвешивания (только кабинет — на витрине window.weighInEligible не определён)
      + ((typeof window !== 'undefined' && window.weighInEligible && window.weighInEligible())
          ? '<div class="v2-link-card" data-go="profile" style="border:1px solid rgba(220,190,121,.5);background:rgba(220,190,121,.12);"><div class="ic">📅</div><div><div class="tt">Прошёл месяц — обнови вес</div><div class="ss">Задай новый вес и цель — план и КБЖУ пересчитаются</div></div><span class="arr">›</span></div>'
          : '')
      + (kcal ? (
          '<div class="v2-kbju">'
        + '<div class="v2-kb"><div class="v">' + kcal + '</div><div class="t">ккал/день</div></div>'
        + '<div class="v2-kb"><div class="v">' + (st.protein || '—') + '</div><div class="t">белки, г</div></div>'
        + '<div class="v2-kb"><div class="v">' + (st.fat || '—') + '</div><div class="t">жиры, г</div></div>'
        + '<div class="v2-kb"><div class="v">' + (st.carbs || '—') + '</div><div class="t">углеводы, г</div></div>'
        + '</div>')
        : '<div class="v2-link-card" data-go="profile"><div class="ic">📝</div><div><div class="tt">Заполни свои данные</div><div class="ss">Пол, параметры и активность — норма посчитается за минуту</div></div><span class="arr">›</span></div>')
      + '<div class="v2-link-card' + _lk + '" data-go="food"><div class="ic">🍽</div><div><div class="tt">Меню на день ' + day + '</div><div class="ss">Готовые блюда точно в твою норму</div></div><span class="arr">›</span></div>'
      // «Тренировка дня» скрыта, если выбрано «не тренируюсь» (trainWeekly===0)
      + (trainWeeklyVal() === 0 ? ''
          : '<div class="v2-link-card' + _lk + '" data-go="workouts"><div class="ic">🏋️</div><div><div class="tt">Тренировка дня</div><div class="ss">Дом или зал — под твой уровень</div></div><span class="arr">›</span></div>')
      + '<div class="v2-link-card' + _lk + '" data-go="shop"><div class="ic">🛒</div><div><div class="tt">Список покупок</div><div class="ss">Скоропорт и запасы — раздельно</div></div><span class="arr">›</span></div>'
      + '<div class="v2-streak' + (gated ? ' v2-dim' : '') + '"><span class="f">🔥</span><div><div class="v">' + streak() + ' дн. подряд</div><div class="t">Держи серию — прогрессия тренировок растёт с неделями.</div></div></div>'
      + '<div class="v2-stats' + (gated ? ' v2-dim' : '') + '">'
      + '<div class="v2-st"><span class="i" style="color:var(--v2-gold2);font-weight:800">✓</span><div><div class="v">' + crossedCount() + ' / ' + total + '</div><div class="t">дней пройдено</div></div></div>'
      + '<div class="v2-st"><span class="i">⚖️</span><div><div class="v">' + (st.cw ? (st.cw + ' → ' + st.tw + ' кг') : '—') + '</div><div class="t">твоя цель</div></div></div>'
      + '</div>'
      + '</div>';

    s.querySelectorAll('[data-go]').forEach(el => el.addEventListener('click', () => {
      const go = el.dataset.go;
      // Под гейтом приглушённые карточки уводят в «Профиль» (там надо заполнить данные), а не в свой раздел.
      if (gated && go !== 'profile') { show('profile'); return; }
      show(go);
    }));

    // чипы: клик = открыть меню дня; удержание 0.75с = зачеркнуть/вернуть
    s.querySelectorAll('.v2-dchip').forEach(ch => {
      const d = parseInt(ch.dataset.day, 10);
      let t = null, fired = false;
      ch.addEventListener('pointerdown', () => {
        fired = false; ch.classList.add('holding');
        t = setTimeout(() => { fired = true; ch.classList.remove('holding'); crossDay(d); renderToday(); }, 750);
      });
      const cancel = () => { clearTimeout(t); ch.classList.remove('holding'); };
      ch.addEventListener('pointerup', () => { cancel(); if (!fired) { show('food'); openDayInFood(d); } });
      ch.addEventListener('pointerleave', cancel);
    });
  }

  /* ---------------- ИНИЦИАЛИЗАЦИЯ ---------------- */
  function init() { try { build(); } catch (e) { console.warn('v2-app init:', e); } }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
