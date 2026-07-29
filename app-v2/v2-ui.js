/* =====================================================================
   V2-UI: сворачиваемые блоки (правки 1–4).
   После фиксации данных / подтверждения активности блоки сворачиваются
   вдвое с кнопкой «Развернуть» (как список покупок). Меню на 90 дней и
   «Твои тренировки» свёрнуты по умолчанию. Движок не трогаем.
   ===================================================================== */
(function () {
  'use strict';

  const css = document.createElement('style');
  css.textContent = `
    .v2-clp { position:relative; overflow:hidden; }
    .v2-clp.v2-closed { max-height:var(--clp-h,170px); }
    .v2-clp.v2-closed::after {
      content:''; position:absolute; left:0; right:0; bottom:0; height:80px;
      background:linear-gradient(to bottom, rgba(8,11,18,0), rgba(8,11,18,.96));
      pointer-events:none;
    }
    .v2-clp-btn {
      display:block; width:100%; margin:8px 0 14px; padding:10px;
      border-radius:12px; border:1px solid rgba(220,190,121,.28);
      background:rgba(19,26,37,.72); color:#F2D995;
      font-size:13px; font-weight:600; cursor:pointer; text-align:center;
      transition:background .2s;
    }
    .v2-clp-btn:hover { background:rgba(220,190,121,.12); }
  `;
  document.head.appendChild(css);

  // el — сворачиваемый блок; h — высота в свёрнутом виде; label — подпись кнопки
  function makeCollapsible(el, h, label) {
    if (!el || el._v2clp) return;
    el._v2clp = true;
    el.classList.add('v2-clp', 'v2-closed');
    el.style.setProperty('--clp-h', h + 'px');
    const btn = document.createElement('button');
    btn.className = 'v2-clp-btn';
    btn.type = 'button';
    const set = () => {
      const closed = el.classList.contains('v2-closed');
      btn.textContent = closed ? ('▾ Развернуть' + (label ? ': ' + label : '')) : '▴ Свернуть';
    };
    btn.addEventListener('click', () => { el.classList.toggle('v2-closed'); set(); });
    el.parentNode.insertBefore(btn, el.nextSibling);
    set();
  }

  function tick() {
    // В таб-версии кабинета (v2-app) сворачивания не нужны: профиль всегда
    // развёрнут, сетка 90 дней скрыта, тренировки на своём экране.
    if (document.getElementById('v2-tabbar')) return;
    const st = (typeof state === 'object' && state) ? state : {};

    // 1. Блок данных (пол+параметры) — сворачиваем ПОСЛЕ фиксации плана
    try {
      const g = document.getElementById('genderGrid');
      const card = g && g.closest('.card');
      if (card && st.profileLocked) makeCollapsible(card, 150, 'мои данные');
    } catch (e) {}

    // 2. Уровень активности — после подтверждения
    try {
      const a = document.getElementById('activityCard');
      if (a && st.activityConfirmed) makeCollapsible(a, 150, 'активность');
    } catch (e) {}

    // 3. Сетка 90 дней — сворачиваем ТОЛЬКО сетку с числами; меню открытого дня
    //    и исключения — отдельные блоки ниже, всегда видимы (правка Замира 08.07).
    try {
      const g = document.getElementById('daysGrid');
      if (g && g.offsetHeight > 260) makeCollapsible(g, 160, 'все 90 дней');
    } catch (e) {}

    // 4. Тренировки — свёрнуты по умолчанию (только если НЕТ таб-структуры:
    //    в v2-app тренировки живут на своём экране, сворачивать нечего)
    try {
      if (!document.getElementById('v2-tabbar')) {
        const w = document.getElementById('workouts-card');
        if (w && w.offsetHeight > 380) makeCollapsible(w, 300, 'тренировки');
      }
    } catch (e) {}
  }

  // блоки появляются асинхронно (после входа/расчёта) — мягкий поллинг
  setInterval(tick, 1200);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tick);
  else tick();
})();
