/* =====================================================================
   ТРЕНИРОВКИ v2 — персональные программы (дом/зал) с прогрессией.
   Научная база: ВОЗ 2020, ACSM 2009/2026, NSCA, Schoenfeld 2016/2017,
   Bickel 2011, Bompa (anatomical adaptation), RP volume landmarks.
   ДВИЖОК ПРОГРЕССИИ (научно-скорр. спека, 11.07.2026):
   • 12 пресетов: место (дом/зал) × опыт (новичок/продолжающий) × цель.
   • Недели 1–4 — адаптация: 2 подхода, RIR 3–4, повторы слегка растут, вес не гоним.
   • Компактная double progression: повторы R0→Rmax по +1/нед → на пике сброс + вес +ΔW
     раз в цикл (4–5 нед). Подходы +1 раз в 2 цикла, cap 4. Разгрузка каждые 6 нед.
   • Дом (без веса): прогрессия по повторам/подходам + ручной переход на сложнее вариант.
   • НЕДЕЛЯ = f(ВЫПОЛНЕННЫЕ ТРЕНИРОВКИ, кнопка «Сделано»), монотонный счётчик БЕЗ капа.
     Прогрессия = чистая функция (счётчик недель, baseWeight-якорь). Продление ≠ рестарт.
   • Рычаг «повторный ввод веса»: baseWeight-якорь {вес, цикл} → всё пересчитывается от новой
     базы, ничего не сбрасывая (неделя/цикл/подходы/повторы сохраняются).
   ОСИ ПЕРСОНАЛИЗАЦИИ (11.07.2026): цель × пол × ВОЗРАСТ × СТАЖ × месяц.
   • ВОЗРАСТ (ACSM older adults; NSCA Fragala 2019): тиры young<50 / middle 50–64 / older 65+.
     Старшим — меньший шаг веса (микрозагрузка ~0.5 кг/нед), разгрузка чаще (older 4 / middle 5
     / young 6 нед), суставно-щадящий подбор (без ударных прыжков, не берём варианты сложнее нормы),
     подсказка про разминку/темп. Всё втекает в автомат через deloadEvery/ageStepFactor/pickExercise.
   • СТАЖ теперь берётся ЯВНО из профиля (онбординг: не тренировался / до года / больше года →
     новичок/продолжающий), а не выводится из частоты. Частота (gym_*) осталась для числа дней/объёма
     и как фолбэк для старых пользователей без поля стажа.
   Модуль автономен, движок питания НЕ трогает.
   ===================================================================== */
(function () {
  'use strict';

  /* ---------------- БАЗА УПРАЖНЕНИЙ ---------------- */
  // lower:true → нижняя часть тела (шаг прогрессии веса 5 кг, иначе 2.5)
  const EX = [
    /* ДОМ */
    { id:'h_squat',        place:'home', grp:'legs',      lvl:1, kind:'compound', lower:true,  name:'Приседания',                    equip:'свой вес',           cue:'Таз назад и вниз, колени по носкам, спина ровная.' },
    { id:'h_sumo',         place:'home', grp:'glutes',    lvl:1, kind:'compound', lower:true,  name:'Сумо-присед',                   equip:'свой вес / гантель', cue:'Широкая стойка, носки наружу, колени наружу.' },
    { id:'h_lunge',        place:'home', grp:'legs',      lvl:1, kind:'compound', lower:true,  name:'Выпады на месте',               equip:'свой вес',           cue:'Шаг вперёд, колено к полу, корпус вертикально.' },
    { id:'h_bulgarian',    place:'home', grp:'legs',      lvl:2, kind:'compound', lower:true,  name:'Болгарские выпады',             equip:'стул',               cue:'Задняя нога на стуле, вес на передней пятке.' },
    { id:'h_glute_bridge', place:'home', grp:'glutes',    lvl:1, kind:'compound', lower:true,  name:'Ягодичный мост',                equip:'свой вес',           cue:'Пятки под коленями, вверху сжать ягодицы на 1 сек.' },
    { id:'h_step_up',      place:'home', grp:'legs',      lvl:2, kind:'compound', lower:true,  name:'Зашагивания на возвышение',     equip:'стул / ступень',     cue:'Вставай силой передней ноги, не отталкивайся задней.' },
    { id:'h_wall_sit',     place:'home', grp:'legs',      lvl:1, kind:'core',     lower:true,  name:'Стульчик у стены',              equip:'стена',              cue:'Бёдра параллельно полу, спина прижата к стене.' },
    { id:'h_calf',         place:'home', grp:'legs',      lvl:1, kind:'iso',      lower:true,  name:'Подъёмы на носки',              equip:'ступень',            cue:'Вверху пауза, вниз растяжение — медленно.' },
    { id:'h_pushup',       place:'home', grp:'chest',     lvl:2, kind:'compound', lower:false, name:'Отжимания',                     equip:'свой вес',           cue:'Тело — одна линия, локти ~45° к корпусу.' },
    { id:'h_pushup_knee',  place:'home', grp:'chest',     lvl:1, kind:'compound', lower:false, name:'Отжимания с колен',             equip:'свой вес',           cue:'Корпус напряжён, грудью касайся пола.' },
    { id:'h_diamond',      place:'home', grp:'arms',      lvl:3, kind:'compound', lower:false, name:'Узкие отжимания',               equip:'свой вес',           cue:'Ладони вместе под грудью, локти вдоль корпуса.' },
    { id:'h_dips_chair',   place:'home', grp:'arms',      lvl:2, kind:'compound', lower:false, name:'Обратные отжимания от стула',   equip:'стул',               cue:'Спина у стула, локти назад, вниз до 90°.' },
    { id:'h_pike_pushup',  place:'home', grp:'shoulders', lvl:2, kind:'compound', lower:false, name:'Отжимания уголком',             equip:'свой вес',           cue:'Таз вверх, голова к полу между ладоней.' },
    { id:'h_band_press',   place:'home', grp:'shoulders', lvl:1, kind:'compound', lower:false, name:'Жим резинки над головой',       equip:'резинка',            cue:'Встань на резинку, жми строго вверх.' },
    { id:'h_lateral_bottle',place:'home',grp:'shoulders', lvl:1, kind:'iso',      lower:false, name:'Махи в стороны с бутылками',    equip:'бутылки / гантели',  cue:'Чуть согнутые локти, до уровня плеч, без рывков.' },
    { id:'h_backpack_row', place:'home', grp:'back',      lvl:1, kind:'compound', lower:false, name:'Тяга рюкзака в наклоне',        equip:'рюкзак с грузом',    cue:'Спина прямая, тяни к поясу, лопатки своди.' },
    { id:'h_row_band',     place:'home', grp:'back',      lvl:1, kind:'compound', lower:false, name:'Тяга резинки к поясу',          equip:'резинка',            cue:'Тяни локтями назад, плечи вниз.' },
    { id:'h_band_pull',    place:'home', grp:'back',      lvl:1, kind:'iso',      lower:false, name:'Разведение резинки',            equip:'резинка',            cue:'Руки прямые, растяни до груди, лопатки вместе.' },
    { id:'h_superman',     place:'home', grp:'back',      lvl:1, kind:'core',     lower:false, name:'Супермен',                      equip:'коврик',             cue:'Подними руки и ноги, пауза 2 сек.' },
    { id:'h_plank',        place:'home', grp:'core',      lvl:1, kind:'core',     lower:false, name:'Планка',                        equip:'коврик',             cue:'Локти под плечами, таз не провисает.' },
    { id:'h_side_plank',   place:'home', grp:'core',      lvl:2, kind:'core',     lower:false, name:'Боковая планка',                equip:'коврик',             cue:'Тело — одна линия, таз не опускай.' },
    { id:'h_crunch',       place:'home', grp:'core',      lvl:1, kind:'core',     lower:false, name:'Скручивания',                   equip:'коврик',             cue:'Поясница на полу, тянись грудью вверх.' },
    { id:'h_leg_raise',    place:'home', grp:'core',      lvl:2, kind:'core',     lower:false, name:'Подъёмы ног лёжа',              equip:'коврик',             cue:'Поясницу прижми, ноги опускай медленно.' },
    { id:'h_deadbug',      place:'home', grp:'core',      lvl:1, kind:'core',     lower:false, name:'Мёртвый жук',                   equip:'коврик',             cue:'Противоположные рука и нога, поясница прижата.' },
    { id:'h_bird_dog',     place:'home', grp:'core',      lvl:1, kind:'core',     lower:false, name:'Птица-собака',                  equip:'коврик',             cue:'Рука вперёд + нога назад, замри на 2 сек.' },
    { id:'h_mountain',     place:'home', grp:'cardio',    lvl:2, kind:'cardio',   lower:false, impact:'high', name:'Скалолаз',                      equip:'свой вес',           cue:'Планка на прямых руках, колени к груди.' },
    { id:'h_jumping_jacks',place:'home', grp:'cardio',    lvl:1, kind:'cardio',   lower:false, impact:'high', name:'Прыжки «звёздочка»',            equip:'свой вес',           cue:'Мягкие колени, дыши ровно.' },
    { id:'h_burpee',       place:'home', grp:'cardio',    lvl:3, kind:'cardio',   lower:false, impact:'high', name:'Бёрпи',                         equip:'свой вес',           cue:'Присед → упор лёжа → прыжок. Темп свой.' },
    /* Низкоударное кардио (для старших / суставно-щадящий подбор) */
    /* ЗАЛ */
    { id:'g_squat',        place:'gym', grp:'legs',      lvl:2, kind:'compound', lower:true,  name:'Приседание со штангой',          equip:'штанга',    cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_leg_press',    place:'gym', grp:'legs',      lvl:1, kind:'compound', lower:true,  name:'Жим ногами',                     equip:'свой вес',           cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_rdl',          place:'gym', grp:'glutes',    lvl:2, kind:'compound', lower:true,  name:'Румынская тяга',                 equip:'свой вес',   cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_hip_thrust',   place:'gym', grp:'glutes',    lvl:2, kind:'compound', lower:true,  name:'Становая тяга',      equip:'штанга',    cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_leg_curl',     place:'gym', grp:'legs',      lvl:1, kind:'iso',      lower:true,  name:'Сгибание ног сидя',       equip:'свой вес',           cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_leg_ext',      place:'gym', grp:'legs',      lvl:1, kind:'iso',      lower:true,  name:'Разгибание ног сидя',     equip:'свой вес',           cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_abduction',    place:'gym', grp:'glutes',    lvl:2, kind:'compound', lower:true,  name:'Становая с трап-грифом',     equip:'трап-гриф',          cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_calf_press',   place:'gym', grp:'legs',      lvl:1, kind:'iso',      lower:true,  name:'Икры',   equip:'свой вес',           cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_bench',        place:'gym', grp:'chest',     lvl:2, kind:'compound', lower:false, name:'Жим штанги лёжа',                equip:'штанга',    cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_db_press',     place:'gym', grp:'chest',     lvl:1, kind:'compound', lower:false, name:'Жим гантелей лёжа',              equip:'гантели',   cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_incline_db',   place:'gym', grp:'chest',     lvl:2, kind:'compound', lower:false, name:'Жим гантелей на наклонной',      equip:'гантели',         cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_cable_fly',    place:'gym', grp:'chest',     lvl:1, kind:'iso',      lower:false, name:'Разведение рук в тренажёре',          equip:'тренажёр',          cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_lat_pulldown', place:'gym', grp:'back',      lvl:1, kind:'compound', lower:false, name:'Тяга верхнего блока',            equip:'тренажёр',               cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_pullup',       place:'gym', grp:'back',      lvl:3, kind:'compound', lower:false, name:'Подтягивания широким хватом',                   equip:'свой вес', cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_row_cable',    place:'gym', grp:'back',      lvl:1, kind:'compound', lower:false, name:'Тяга горизонтального блока сидя',             equip:'тренажёр',               cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_db_row',       place:'gym', grp:'back',      lvl:2, kind:'compound', lower:false, name:'Тяга гантели одной рукой',         equip:'гантели',   cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_hyperext',     place:'gym', grp:'back',      lvl:2, kind:'compound', lower:false, name:'Тяга штанги в наклоне',                 equip:'штанга',           cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_ohp',          place:'gym', grp:'shoulders', lvl:2, kind:'compound', lower:false, name:'Армейский жим',                equip:'штанга',   cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_lateral',      place:'gym', grp:'shoulders', lvl:1, kind:'iso',      lower:false, name:'Махи гантелями в сторону',       equip:'гантели',            cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_face_pull',    place:'gym', grp:'shoulders', lvl:1, kind:'iso',      lower:false, name:'Тяга штанги к подбородку',             equip:'штанга',  cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_curl',         place:'gym', grp:'arms',      lvl:1, kind:'iso',      lower:false, name:'Сгибание рук со штангой',             equip:'штанга',   cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_hammer',       place:'gym', grp:'arms',      lvl:1, kind:'iso',      lower:false, name:'Молотковые сгибания',            equip:'свой вес',            cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_triceps_rope', place:'gym', grp:'arms',      lvl:1, kind:'iso',      lower:false, name:'Разгибание рук в блоке',          equip:'тренажёр',  cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_cable_crunch', place:'gym', grp:'core',      lvl:2, kind:'core',     lower:false, name:'Скручивания в тренажёре',           equip:'тренажёр',          cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_hanging_knee', place:'gym', grp:'core',      lvl:2, kind:'core',     lower:false, name:'Книжка',          equip:'свой вес',             cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_plank_w',      place:'gym', grp:'core',      lvl:1, kind:'core',     lower:false, name:'Жук',                 equip:'свой вес',      cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_treadmill',    place:'gym', grp:'cardio',    lvl:1, kind:'cardio',   lower:true,  name:'Ходьба на беговой дорожке',       equip:'тренажёр',            cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'g_bike',         place:'gym', grp:'cardio',    lvl:1, kind:'cardio',   lower:true,  name:'Велотренажёр',                   equip:'тренажёр',       cue:'Техника ровная, полный контроль амплитуды, без рывков.' },
    { id:'x11', place:'gym', grp:'shoulders', lvl:2, kind:'iso', lower:false, alt:true, name:'Махи гантелями сидя', equip:'гантели', cue:'Махи гантелями сидя — техника ровная, без рывков.' },
    { id:'x13', place:'gym', grp:'chest', lvl:2, kind:'compound', lower:false, alt:true, name:'Жим в тренажёр от груди вперед', equip:'тренажёр', cue:'Жим в тренажёр от груди вперед — техника ровная, без рывков.' },
    { id:'x16', place:'gym', grp:'chest', lvl:2, kind:'iso', lower:false, alt:true, name:'Разведение гантелей на горизонтальной скамье', equip:'гантели', cue:'Разведение гантелей на горизонтальной скамье — техника ровная, без рывков.' },
    { id:'x17', place:'gym', grp:'chest', lvl:2, kind:'compound', lower:false, alt:true, name:'Отжимания на брусьях', equip:'тренажёр', cue:'Отжимания на брусьях — техника ровная, без рывков.' },
    { id:'x18', place:'gym', grp:'chest', lvl:2, kind:'iso', lower:false, alt:true, name:'Разведение гантелей на наклонной вверх скамье', equip:'гантели', cue:'Разведение гантелей на наклонной вверх скамье — техника ровная, без рывков.' },
    { id:'x19', place:'gym', grp:'chest', lvl:2, kind:'compound', lower:false, alt:true, name:'Жим штанги на наклонной скамье вверх', equip:'штанга', cue:'Жим штанги на наклонной скамье вверх — техника ровная, без рывков.' },
    { id:'x20', place:'gym', grp:'chest', lvl:2, kind:'compound', lower:false, alt:true, name:'Брусья в тренажере', equip:'тренажёр', cue:'Брусья в тренажере — техника ровная, без рывков.' },
    { id:'x24', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Тяга штанги в наклоне обратным хватом', equip:'штанга', cue:'Тяга штанги в наклоне обратным хватом — техника ровная, без рывков.' },
    { id:'x25', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Тяга гирей к поясу', equip:'гиря', cue:'Тяга гирей к поясу — техника ровная, без рывков.' },
    { id:'x26', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Подтягивание в Гравитроне параллельным хватом', equip:'тренажёр', cue:'Подтягивание в Гравитроне параллельным хватом — техника ровная, без рывков.' },
    { id:'x27', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Горизонтальная тяга блока косичкой', equip:'тренажёр', cue:'Горизонтальная тяга блока косичкой — техника ровная, без рывков.' },
    { id:'x28', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Горизонтальная тяга блока одной рукой', equip:'тренажёр', cue:'Горизонтальная тяга блока одной рукой — техника ровная, без рывков.' },
    { id:'x29', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Горизонтальная тяга блока широким хватом', equip:'тренажёр', cue:'Горизонтальная тяга блока широким хватом — техника ровная, без рывков.' },
    { id:'x30', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Тяга рычажная прямым хватом в тренажере', equip:'тренажёр', cue:'Тяга рычажная прямым хватом в тренажере — техника ровная, без рывков.' },
    { id:'x31', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Горизонтальная тяга блока сидя узким хватом', equip:'тренажёр', cue:'Горизонтальная тяга блока сидя узким хватом — техника ровная, без рывков.' },
    { id:'x32', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Подтягивания в Гравитроне обратным хватом', equip:'тренажёр', cue:'Подтягивания в Гравитроне обратным хватом — техника ровная, без рывков.' },
    { id:'x33', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Горизонтальная тяга в тренажере', equip:'тренажёр', cue:'Горизонтальная тяга в тренажере — техника ровная, без рывков.' },
    { id:'x34', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Подтягивания параллельным хватом', equip:'свой вес', cue:'Подтягивания параллельным хватом — техника ровная, без рывков.' },
    { id:'x36', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Тяга верхнего блока в тренажёр Хаммера', equip:'тренажёр', cue:'Тяга верхнего блока в тренажёр Хаммера — техника ровная, без рывков.' },
    { id:'x38', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Вертикальная тяга в блоке одной рукой', equip:'тренажёр', cue:'Вертикальная тяга в блоке одной рукой — техника ровная, без рывков.' },
    { id:'x40', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Подтягивания в Гравитроне широким хватом', equip:'тренажёр', cue:'Подтягивания в Гравитроне широким хватом — техника ровная, без рывков.' },
    { id:'x41', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Горизонтальная тяга блока узким обратным хватом', equip:'тренажёр', cue:'Горизонтальная тяга блока узким обратным хватом — техника ровная, без рывков.' },
    { id:'x42', place:'gym', grp:'back', lvl:2, kind:'iso', lower:false, alt:true, name:'Шраги с гантелями', equip:'гантели', cue:'Шраги с гантелями — техника ровная, без рывков.' },
    { id:'x43', place:'gym', grp:'back', lvl:2, kind:'iso', lower:false, alt:true, name:'Шраги с гирями', equip:'гиря', cue:'Шраги с гирями — техника ровная, без рывков.' },
    { id:'x46', place:'gym', grp:'glutes', lvl:2, kind:'compound', lower:true, alt:true, name:'Становая тяга (сумо)', equip:'свой вес', cue:'Становая тяга (сумо) — техника ровная, без рывков.' },
    { id:'x47', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Сгибание рук в тренажере узким хватом', equip:'тренажёр', cue:'Сгибание рук в тренажере узким хватом — техника ровная, без рывков.' },
    { id:'x48', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Сгибание рук с гантелями поочередно', equip:'гантели', cue:'Сгибание рук с гантелями поочередно — техника ровная, без рывков.' },
    { id:'x50', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Сгибание рук в блоке', equip:'тренажёр', cue:'Сгибание рук в блоке — техника ровная, без рывков.' },
    { id:'x52', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Сгибание (Молот) поочередно', equip:'свой вес', cue:'Сгибание (Молот) поочередно — техника ровная, без рывков.' },
    { id:'x53', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Сгибание рук со штангой обратным хватом', equip:'штанга', cue:'Сгибание рук со штангой обратным хватом — техника ровная, без рывков.' },
    { id:'x54', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Сгибание рук в блоке косичкой', equip:'тренажёр', cue:'Сгибание рук в блоке косичкой — техника ровная, без рывков.' },
    { id:'x55', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Сгибание одной руки в тренажёре', equip:'тренажёр', cue:'Сгибание одной руки в тренажёре — техника ровная, без рывков.' },
    { id:'x56', place:'gym', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Приседание со штангой перед собой', equip:'штанга', cue:'Приседание со штангой перед собой — техника ровная, без рывков.' },
    { id:'x58', place:'gym', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Жим платформой одной ногой', equip:'тренажёр', cue:'Жим платформой одной ногой — техника ровная, без рывков.' },
    { id:'x59', place:'gym', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Гакк-приседания', equip:'свой вес', cue:'Гакк-приседания — техника ровная, без рывков.' },
    { id:'x60', place:'gym', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Обратные Гакк выпады', equip:'свой вес', cue:'Обратные Гакк выпады — техника ровная, без рывков.' },
    { id:'x61', place:'gym', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Обратные Гакк приседания', equip:'свой вес', cue:'Обратные Гакк приседания — техника ровная, без рывков.' },
    { id:'x63', place:'gym', grp:'legs', lvl:2, kind:'iso', lower:true, alt:true, name:'Разгибание одной ноги сидя', equip:'свой вес', cue:'Разгибание одной ноги сидя — техника ровная, без рывков.' },
    { id:'x65', place:'gym', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Жим ногами (узкая постановка ног)', equip:'свой вес', cue:'Жим ногами (узкая постановка ног) — техника ровная, без рывков.' },
    { id:'x66', place:'gym', grp:'legs', lvl:2, kind:'iso', lower:true, alt:true, name:'Сгибание ноги стоя', equip:'свой вес', cue:'Сгибание ноги стоя — техника ровная, без рывков.' },
    { id:'x70', place:'both', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Ходьба с гантелями', equip:'гантели', cue:'Ходьба с гантелями — техника ровная, без рывков.' },
    { id:'x71', place:'both', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Перекрестные выпады', equip:'свой вес', cue:'Перекрестные выпады — техника ровная, без рывков.' },
    { id:'x73', place:'both', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Приседание с гантелей', equip:'гантели', cue:'Приседание с гантелей — техника ровная, без рывков.' },
    { id:'x74', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Разгибание рук в блоке с V-рукоятью', equip:'тренажёр', cue:'Разгибание рук в блоке с V-рукоятью — техника ровная, без рывков.' },
    { id:'x75', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Разгибание одной руки обратным хватом', equip:'свой вес', cue:'Разгибание одной руки обратным хватом — техника ровная, без рывков.' },
    { id:'x76', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Разгибание одной руки стоя', equip:'свой вес', cue:'Разгибание одной руки стоя — техника ровная, без рывков.' },
    { id:'x77', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Разгибание рук из-за головы', equip:'свой вес', cue:'Разгибание рук из-за головы — техника ровная, без рывков.' },
    { id:'x80', place:'both', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Запрыгивание на тумбу', equip:'свой вес', cue:'Запрыгивание на тумбу — техника ровная, без рывков.' },
    { id:'x81', place:'both', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Выпады с опорой', equip:'свой вес', cue:'Выпады с опорой — техника ровная, без рывков.' },
    { id:'x82', place:'both', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Перекрестные выпады', equip:'свой вес', cue:'Перекрестные выпады — техника ровная, без рывков.' },
    { id:'x84', place:'both', grp:'legs', lvl:2, kind:'compound', lower:true, alt:true, name:'Боковые выпады', equip:'свой вес', cue:'Боковые выпады — техника ровная, без рывков.' },
    { id:'x90', place:'both', grp:'core', lvl:2, kind:'core', lower:false, alt:true, name:'Скручивания', equip:'свой вес', cue:'Скручивания — техника ровная, без рывков.' },
    { id:'x91', place:'gym', grp:'cardio', lvl:2, kind:'cardio', lower:false, alt:true, name:'Эллипс', equip:'тренажёр', cue:'Эллипс — техника ровная, без рывков.' },
    { id:'x93', place:'gym', grp:'cardio', lvl:2, kind:'cardio', lower:false, alt:true, name:'Ходьба в гору', equip:'свой вес', cue:'Ходьба в гору — техника ровная, без рывков.' },
    { id:'x95', place:'gym', grp:'cardio', lvl:2, kind:'cardio', lower:false, alt:true, name:'Велотренажер горизонтальный', equip:'тренажёр', cue:'Велотренажер горизонтальный — техника ровная, без рывков.' },
    { id:'x96', place:'gym', grp:'cardio', lvl:2, kind:'cardio', lower:false, alt:true, name:'Легкий бег', equip:'свой вес', cue:'Легкий бег — техника ровная, без рывков.' },
    { id:'x98', place:'gym', grp:'arms', lvl:2, kind:'iso', lower:false, alt:true, name:'Сгибание рук в тренажере', equip:'тренажёр', cue:'Сгибание рук в тренажере — техника ровная, без рывков.' },
    { id:'x99', place:'gym', grp:'chest', lvl:2, kind:'iso', lower:false, alt:true, name:'Сведение рук в тренажёре', equip:'тренажёр', cue:'Сведение рук в тренажёре — техника ровная, без рывков.' },
    { id:'x100', place:'gym', grp:'chest', lvl:2, kind:'compound', lower:false, alt:true, name:'Жим штанги на наклонной в Смите', equip:'тренажёр Смита', cue:'Жим штанги на наклонной в Смите — техника ровная, без рывков.' },
    { id:'x101', place:'gym', grp:'chest', lvl:2, kind:'compound', lower:false, alt:true, name:'Жим штанги лёжа в Смите', equip:'тренажёр Смита', cue:'Жим штанги лёжа в Смите — техника ровная, без рывков.' },
    { id:'x102', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Вертикальная тяга широким хватом к груди', equip:'тренажёр', cue:'Тяни к верху груди, лопатки вниз-назад, без рывка.' },
    { id:'x103', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Тяга T-образного грифа широким хватом', equip:'Т-гриф', cue:'Спина ровная, тяни к животу локтями, без рывка.' },
    { id:'x104', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Вертикальная тяга параллельным хватом к груди', equip:'тренажёр', cue:'Тяни к верху груди, лопатки вниз-назад, без рывка.' },
    { id:'x105', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Вертикальная тяга узким хватом', equip:'тренажёр', cue:'Тяни к верху груди, лопатки вниз-назад, без рывка.' },
    { id:'x106', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Вертикальная тяга обратным хватом', equip:'тренажёр', cue:'Тяни к верху груди, лопатки вниз-назад, без рывка.' },
    { id:'x107', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Горизонтальная рычажная тяга в тренажёре', equip:'тренажёр', cue:'Спина ровная, тяни ручки к корпусу, лопатки сводим.' },
    { id:'x108', place:'gym', grp:'back', lvl:2, kind:'compound', lower:false, alt:true, name:'Тяга Т-образного грифа узким хватом', equip:'Т-гриф', cue:'Спина ровная, тяни к животу локтями, без рывка.' },
    { id:'x109', place:'gym', grp:'arms', lvl:1, kind:'iso', lower:false, alt:true, name:'Разгибание рук с верёвкой', equip:'блок / канат', cue:'Локти у корпуса, внизу разведи канат, вверх медленно.' },
    { id:'x1', place:'gym', grp:'shoulders', lvl:2, kind:'compound', lower:false, alt:true, name:'Армейский жим из-за головы', equip:'штанга', cue:'Армейский жим из-за головы — техника ровная, без рывков.' },
    { id:'x3', place:'gym', grp:'shoulders', lvl:2, kind:'compound', lower:false, alt:true, name:'Жим гантелей сидя', equip:'гантели', cue:'Жим гантелей сидя — техника ровная, без рывков.' },
    { id:'x4', place:'gym', grp:'shoulders', lvl:2, kind:'compound', lower:false, alt:true, name:'Жим гантелей сидя', equip:'гантели', cue:'Жим гантелей сидя — техника ровная, без рывков.' },
    { id:'x5', place:'gym', grp:'shoulders', lvl:2, kind:'compound', lower:false, alt:true, name:'Жим Арнольда', equip:'гантели', cue:'Жим Арнольда — техника ровная, без рывков.' },
    { id:'x6', place:'gym', grp:'shoulders', lvl:2, kind:'iso', lower:false, alt:true, name:'Махи перед собой поочередно', equip:'гантели', cue:'Махи перед собой поочередно — техника ровная, без рывков.' },
    { id:'x7', place:'gym', grp:'shoulders', lvl:2, kind:'iso', lower:false, alt:true, name:'Махи перед собой', equip:'гантели', cue:'Махи перед собой — техника ровная, без рывков.' },
    { id:'x8', place:'gym', grp:'shoulders', lvl:2, kind:'iso', lower:false, alt:true, name:'Махи гантелями круговая', equip:'гантели', cue:'Махи гантелями круговая — техника ровная, без рывков.' },
  ];

  /* ---------------- ШАБЛОНЫ ДНЕЙ И НЕДЕЛЬ ---------------- */
  const DAY_TEMPLATES = {
    fullA: { title:'Всё тело · A', slots:['legs','chest','back','shoulders','core','cardio'] },
    fullB: { title:'Всё тело · B', slots:['glutes','back','chest','arms','core','cardio'] },
    fullC: { title:'Всё тело · C', slots:['legs','shoulders','back','glutes','core','cardio'] },
    upper: { title:'Верх тела',    slots:['chest','back','shoulders','arms','arms','core'] },
    lower: { title:'Низ тела',     slots:['legs','glutes','legs','glutes','core','cardio'] },
    push:  { title:'Жимовая',      slots:['chest','shoulders','chest','arms','core'] },
    pull:  { title:'Тяговая',      slots:['back','back','shoulders','arms','core'] },
    legs:  { title:'Ноги и ягодицы', slots:['legs','glutes','legs','glutes','core'] },
  };

  // 12 пресетов (иссл. 08.07.26): опыт × цель → недельная схема (место влияет на отбор упражнений)
  // Новичок = «не тренируюсь»/«1-2 р/нед» (gym_0, gym_1); продолжающий = gym_3/gym_5.
  const WEEK_PRESETS = {
    novice:   { loss:['fullA','fullB','fullC'], gain:['fullA','fullB','fullC'], maintain:['fullA','fullB'] },
    experienced: {
      loss:['upper','lower','upper','lower'],
      gain:['push','pull','legs','upper','lower'],   // gym_5; для gym_3 обрежем до 4
      maintain:['fullA','fullB','fullC'],
    },
  };

  // Цель → базовые параметры (подходы/отдых/заметка). Повторы вне адаптации задаёт автомат (REP_RANGES).
  const GOAL_SCHEMES = {
    loss:     { compound:{sets:3,reps:'10–12',rest:60},  iso:{sets:3,reps:'12–15',rest:45}, core:{sets:3,reps:'30–45 сек',rest:30}, cardio:{sets:1,reps:'12–15 мин',rest:0}, note:'Дефицит калорий уже в питании — на тренировке держим объём, отдых короткий.' },
    gain:     { compound:{sets:3,reps:'6–10',rest:120},  iso:{sets:3,reps:'10–12',rest:90}, core:{sets:3,reps:'30–45 сек',rest:45}, cardio:{sets:1,reps:'8–10 мин',rest:0},  note:'Каждую группу мышц грузим дважды в неделю — так растут лучше.' },
    maintain: { compound:{sets:3,reps:'8–12',rest:90},   iso:{sets:2,reps:'12',rest:60},    core:{sets:3,reps:'30–45 сек',rest:40}, cardio:{sets:1,reps:'10 мин',rest:0},    note:'Ровный режим: техника важнее веса.' },
  };
  // Адаптационный месяц (Bompa, ACSM: 1-2 подхода, 12-20 повт, RIR 3-4, без отказа)
  const ADAPT_SCHEME = { compound:{sets:2,reps:'12–15',rest:90}, iso:{sets:2,reps:'15',rest:60}, core:{sets:2,reps:'20–30 сек',rest:40}, cardio:{sets:1,reps:'8–10 мин',rest:0},
    note:'Работаем с запасом 3–4 повтора, до отказа не доводим.' };

  // Диапазоны повторов для двойной прогрессии (спека §2.2): [R0, Rmax] по цели и типу.
  const REP_RANGES = {
    gain:     { compound:[8,12],  iso:[10,14] },
    loss:     { compound:[12,15], iso:[12,16] },
    maintain: { compound:[10,13], iso:[12,15] },
  };
  // Инкремент веса за цикл, кг (спека §2.3). Фолбэк — по классу упражнения.
  const WEIGHT_STEP = {
    g_squat:5, g_leg_press:5, g_rdl:5, g_hip_thrust:5,
    g_bench:2.5, g_ohp:2.5, g_leg_curl:2.5, g_leg_ext:2.5, g_abduction:2.5, g_calf_press:2.5,
    g_lat_pulldown:2.5, g_row_cable:2.5, g_cable_fly:2.5, g_pullup:2.5, g_hyperext:2.5,
    g_db_press:2, g_incline_db:2, g_db_row:2,
    g_curl:1.5, g_hammer:1.5, g_lateral:1, g_triceps_rope:1.5, g_face_pull:1,
  };
  const DELOAD_EVERY = 6;   // разгрузка каждые 6 тренировочных недель автомата
  const ADAPT_WEEKS  = 4;   // недели адаптации до старта автомата

  /* ---------------- ХРАНИЛИЩЕ ---------------- */
  const LS = {
    get(k, dflt) { try { return JSON.parse(localStorage.getItem(k)) ?? dflt; } catch (e) { return dflt; } },
    // После КАЖДОЙ записи ключа тренировок дёргаем облачный сейв (cabinet.html: window._saveProgress
    // = дебаунс-обёртка с гейтом _wkCloudReady). Без сети / вне кабинета — просто no-op (хелпера нет
    // или гейт закрыт), localStorage остаётся быстрым локальным кэшем.
    set(k, v) {
      try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {}
      try { if (typeof window !== 'undefined' && typeof window._saveProgress === 'function') window._saveProgress(); } catch (e) {}
    },
  };
  const prefs    = () => LS.get('v2_workout_prefs', {});
  const doneMap  = () => LS.get('v2_workout_done', {});     // dayId → номер недели, в которую отмечено
  const weights  = () => LS.get('v2_workout_weights', {});  // exId → якорь веса {w, c} (или старое число)
  const variants = () => LS.get('v2_workout_variants', {}); // exId → id более сложного варианта (дом)
  const swaps    = () => LS.get('v2_workout_swaps', {});    // #6: exId слота → id альтернативы той же группы (ручная замена)
  const weightLog= () => LS.get('v2_workout_weight_log', {}); // #1: exId → [{t,w,reps}] журнал изменений рабочего веса

  /* ---------------- ВОЗРАСТНЫЕ ТИРЫ ----------------
     Пороги (ACSM «Exercise and Physical Activity for Older Adults»; NSCA position
     statement Fragala 2019; обзор восстановления PMC10317890): старшие = 65+ (восстановление
     удлинено, риск перетрена/перегруза выше → шаг веса меньше, разгрузка чаще, суставно-щадящий
     подбор, без ударных прыжков); средний возраст 50–64 — умеренная поправка; молодые <50 —
     стандарт. Прогрессия веса у старших в исследованиях ~0.5 кг/нед → микрозагрузка. */
  function ageTier(age) {
    const a = parseInt(age, 10) || 0;
    if (a >= 65) return 'older';
    if (a >= 50) return 'middle';
    return 'young';   // <50 или неизвестен → стандартная прогрессия
  }
  // Разгрузка чаще у старших (медленнее восстановление): young 6, middle 5, older 4 нед.
  function deloadEveryFor(tier) { return tier === 'older' ? 4 : tier === 'middle' ? 5 : DELOAD_EVERY; }
  // Множитель шага веса по возрасту (микрозагрузка у старших): older ×0.5, middle ×0.75, young ×1.
  function ageStepFactor(tier) { return tier === 'older' ? 0.5 : tier === 'middle' ? 0.75 : 1; }

  /* ---------------- ПРОФИЛЬ ---------------- */
  function getProfile() {
    const s = (typeof state === 'object' && state) ? state : {};
    let freq = null;
    try { const b = document.querySelector('.act-btn[data-grp="gym"].on'); if (b) freq = b.dataset.key; } catch (e) {}
    freq = freq || prefs().freq || 'gym_1';
    const goal = s.goalType || (s.tw && s.cw ? (s.tw < s.cw ? 'loss' : s.tw > s.cw ? 'gain' : 'maintain') : 'maintain');
    // ВОЗРАСТ: кабинет уже собирает и фиксирует его (state.age / профиль). Фолбэк — prefs.
    const age = parseInt(s.age, 10) || parseInt(prefs().age, 10) || 0;
    const tier = ageTier(age);
    // СТАЖ (прямой вопрос в онбординге): сырое значение none/lt1/gt1 → тир novice/experienced.
    // Для СТАРЫХ пользователей без поля — прежний фолбэк: вывод из частоты (gym_3/gym_5 → продолжающий).
    const rawExp = s.trainingExp || prefs().trainingExp || null;
    let exp;
    if (rawExp === 'gt1' || rawExp === 'experienced') exp = 'experienced';
    else if (rawExp === 'none' || rawExp === 'lt1' || rawExp === 'novice') exp = 'novice';
    else exp = (freq === 'gym_3' || freq === 'gym_5') ? 'experienced' : 'novice';
    // Частота тренировок (раз/нед) из нового выбора freq_1..freq_7; старые gym_* — фолбэк.
    let trainWeekly;
    if (/^gym_/.test(freq)) { const _map = {gym_0:0, gym_1:2, gym_3:3, gym_5:5}; trainWeekly = (freq in _map) ? _map[freq] : 3; }
    else { const _m = String(freq).match(/(\d+)/); trainWeekly = _m ? parseInt(_m[1], 10) : 3; }
    if (isNaN(trainWeekly)) trainWeekly = 3;
    trainWeekly = Math.max(0, Math.min(7, trainWeekly));   // 0 = «не тренируюсь» (пустая программа)
    return {
      gender: s.gender || 'female',
      goal: GOAL_SCHEMES[goal] ? goal : 'maintain',
      freq,
      trainWeekly,
      exp,
      age,
      ageTier: tier,
      deloadEvery: deloadEveryFor(tier),
      place: prefs().place || 'home',
    };
  }

  /* ===================================================================
     ДВИЖОК ПРОГРЕССИИ (спека ТРЕНИРОВКИ_прогрессия_спека.md §2–3)
     Всё — чистые функции от (номер недели, baseWeight-якорь). Продление
     бесшовно: счётчик недель монотонный, без капа, без % 90.
     =================================================================== */

  // Тренировочная неделя = монотонный счётчик, растёт по ВЫПОЛНЕННЫМ тренировкам (не по питанию).
  // 16.07 (Замир): НЕДЕЛЯ ТРЕНИРОВОК — чистая функция от зачёркнутых дней плана (7 дней = +1 неделя).
  // Источник — dayStates хоста (сервер-авторитетно у оплативших; в превью зачёркивание заперто → 0 → неделя 1).
  // Локального счётчика v2_wk_week БОЛЬШЕ НЕТ → исчезает весь класс багов с дрейфом/ре-заливкой недели
  // (недели 11/32/33 всплывали именно из застрявшего localStorage-счётчика). Кнопка «Сделано» убрана —
  // прогресс считается сам по пройденным дням меню.
  function crossedDaysCount() {
    try { if (typeof window !== 'undefined' && typeof window._crossedDaysCount === 'function') return window._crossedDaysCount() || 0; } catch (e) {}
    return 0;
  }
  function weekCounter() { return 1 + Math.floor(crossedDaysCount() / 7); }
  function setWeekCounter() { /* не храним: неделя выводится из зачёркнутых дней */ }
  function currentWeek() { return weekCounter(); }
  const isAdaptation = (week) => week <= ADAPT_WEEKS;
  const round5 = (x) => Math.round(x * 2) / 2;

  function sWork(ex, goal) {
    const sc = GOAL_SCHEMES[goal] || GOAL_SCHEMES.maintain;
    return (sc[ex.kind] || sc.compound).sets;
  }
  function repRange(goal, kind) {
    const g = REP_RANGES[goal] || REP_RANGES.maintain;
    if (kind === 'compound') return g.compound;
    if (kind === 'iso') return g.iso;
    return null; // core/cardio — по времени, числовой цикл повторов не применяем
  }
  // Инкремент веса за цикл: класс упражнения + половинный шаг, если >5% рабочего веса
  // (микроблин) + микро-шаг на верх/изоляцию у женщин (спека §2.3).
  function weightStep(ex, baseWeight, gender, tier) {
    let inc = WEIGHT_STEP[ex.id];
    if (inc == null) inc = ex.lower ? (ex.kind === 'compound' ? 5 : 2.5) : (ex.kind === 'compound' ? 2.5 : 1.5);
    if (baseWeight && baseWeight > 0) {
      if (inc > 0.05 * baseWeight) inc = inc / 2;                                   // половинный шаг
      if (gender === 'female' && !ex.lower && ex.kind === 'iso') inc = Math.min(inc, 1); // микро-шаг жен верх/изоляция
    }
    inc = inc * ageStepFactor(tier || 'young');    // возрастная микрозагрузка (старшим меньший шаг)
    inc = Math.round(inc * 2) / 2;
    return inc < 0.5 ? 0.5 : inc;
  }

  // baseWeight-якорь: {w — рабочий вес, c — индекс цикла, в котором введён}.
  // Старый формат (просто число) мигрируем как якорь c=0 (обратная совместимость).
  function baseAnchor(exId) {
    const raw = weights()[exId];
    if (raw == null || raw === '') return null;
    if (typeof raw === 'number') return { w: raw, c: 0 };
    if (typeof raw === 'object' && raw.w != null) return { w: raw.w, c: raw.c || 0 };
    const n = parseFloat(raw); return isNaN(n) ? null : { w: n, c: 0 };
  }

  // Автомат (спека §2.4). W — тренировочная неделя ПОСЛЕ адаптации (1,2,3,…), монотонна.
  function automat(ex, W, goal, deloadEvery) {
    const DE = deloadEvery || DELOAD_EVERY;       // частота разгрузки зависит от возраста (getProfile)
    const isDeload = (W % DE === 0);
    const e = W - Math.floor(W / DE);             // «эффективная» неделя без учёта разгрузок
    const rr = repRange(goal, ex.kind);
    const Swork = sWork(ex, goal);
    if (!rr) {                                     // core/cardio — без числового цикла повторов
      let sets = ex.kind === 'core' ? Math.min(3, Swork) : Swork;
      if (isDeload && ex.kind !== 'cardio') sets = Math.max(1, sets - 1);
      return { sets, reps: null, phase: isDeload ? 'deload' : 'steady', c: 0, r: 0, Lc: 0, isDeload };
    }
    const R0 = rr[0], Rmax = rr[1], Lc = Rmax - R0 + 1;
    const c = Math.floor((e - 1) / Lc);            // индекс цикла (0-based)
    const r = (e - 1) % Lc;                        // позиция внутри цикла 0..Lc-1
    let reps = R0 + r;
    const Scap = Math.min(Swork + 1, 4);
    let sets = Math.min(Scap, Swork + Math.floor(c / 2)); // +1 подход раз в 2 цикла, до cap
    let phase = (r === Lc - 1) ? 'peak' : 'build';
    if (isDeload) { sets = Math.max(2, sets - 1); reps = R0; phase = 'deload'; }
    return { sets, reps, phase, c, r, Lc, R0, Rmax, isDeload };
  }

  // Адаптация 1–4: 2 подхода, повторы слегка растут по неделям (чиним «недели 1–4 идентичны»).
  function adaptProgram(ex, week) {
    const sc = ADAPT_SCHEME[ex.kind] || ADAPT_SCHEME.compound;
    let reps = sc.reps;
    if (ex.kind === 'compound') reps = String(Math.min(15, 12 + (week - 1))); // 12→15
    else if (ex.kind === 'iso') reps = String(Math.min(15, 13 + (week - 1))); // 13→15
    return { sets: sc.sets, reps, rest: sc.rest };
  }

  // Текущий рабочий вес = якорь.w + (пройдено циклов от якоря) × шаг. Чистая функция.
  function currentWeight(ex, week, profile) {
    const a = baseAnchor(ex.id);
    if (a == null) return null;                    // дом / вес не введён
    if (isAdaptation(week)) return round5(a.w);    // адаптация: вес держим
    const p = profile || getProfile();
    const prog = automat(ex, week - ADAPT_WEEKS, p.goal, p.deloadEvery);
    const step = weightStep(ex, a.w, p.gender, p.ageTier);
    const cycles = Math.max(0, prog.c - (a.c || 0));
    return round5(a.w + cycles * step);
  }

  // Полная прогрессия одного упражнения на неделю → {sets, reps, rest, weight, phase}.
  function progressionFor(ex, week, profile) {
    const weight = currentWeight(ex, week, profile);
    if (isAdaptation(week)) {
      const a = adaptProgram(ex, week);
      return { sets: a.sets, reps: a.reps, rest: a.rest, weight, phase: 'adapt' };
    }
    const gs = GOAL_SCHEMES[profile.goal][ex.kind] || GOAL_SCHEMES[profile.goal].compound;
    const p = automat(ex, week - ADAPT_WEEKS, profile.goal, profile.deloadEvery);
    const reps = (p.reps == null) ? gs.reps : String(p.reps);
    return { sets: p.sets, reps, rest: gs.rest, weight, phase: p.phase, c: p.c, r: p.r, Lc: p.Lc, isDeload: p.isDeload };
  }

  // Статус цикла для баннера (по «типичному» compound текущей цели).
  function programStatus(profile, week) {
    if (isAdaptation(week)) return { adapt: true, week, weeksLeft: ADAPT_WEEKS - week + 1 };
    const W = week - ADAPT_WEEKS;
    const DE = profile.deloadEvery || DELOAD_EVERY;   // возрастная частота разгрузки
    const rr = repRange(profile.goal, 'compound');
    const R0 = rr[0], Rmax = rr[1], Lc = Rmax - R0 + 1;
    const isDeload = (W % DE === 0);
    const e = W - Math.floor(W / DE);
    const c = Math.floor((e - 1) / Lc);
    const r = (e - 1) % Lc;
    const weeksToDeload = isDeload ? 0 : (DE - (W % DE));
    const weeksToWeight = isDeload ? null : (Lc - 1 - r);
    const phase = isDeload ? 'deload' : (r === Lc - 1 ? 'peak' : 'build');
    return { adapt: false, isDeload, week, W, cycleNum: c + 1, c, r, R0, Rmax, repNow: R0 + r, Lc, weeksToDeload, weeksToWeight, phase };
  }

  // Дом: следующий по сложности вариант той же группы/типа (аналог «прибавки веса»).
  function harderVariant(ex) {
    const chain = EX.filter(e => e.place === ex.place && e.grp === ex.grp && e.kind === ex.kind && e.lvl > ex.lvl)
                    .sort((a, b) => a.lvl - b.lvl);
    return chain.length ? chain[0] : null;
  }
  // #6: ручная ЗАМЕНА упражнения на альтернативу той же группы/места. Ключ — id слота (исходного
  // упражнения от pickExercise), один шаг → обратимо: выбрать исходное = снять замену. Без цепочек.
  function applySwapOne(ex) {
    const v = swaps()[ex.id];
    if (!v || v === ex.id) return ex;
    const t = EX.find(e => e.id === v);
    // 25.07: альтернативы place:'both' (зал+дом бодивейт) валидны и для home, и для gym.
    return (t && (t.place === ex.place || t.place === 'both') && t.grp === ex.grp) ? t : ex;
  }
  // Список альтернатив той же группы и того же места (для меню замены), от простого к сложному.
  // 25.07: включаем и base, и alt-варианты той же группы; place:'both' годится в обоих режимах.
  function swapAlternatives(ex) {
    return EX.filter(e => e.grp === ex.grp && (e.place === ex.place || e.place === 'both')).sort((a, b) => a.lvl - b.lvl);
  }
  // Применить пользовательский переход на сложнее (по цепочке overrides).
  function applyVariant(ex) {
    let cur = ex, guard = 0;
    while (guard++ < 6) {
      const v = variants()[cur.id];
      if (!v) break;
      const t = EX.find(e => e.id === v);
      if (!t || t.place !== ex.place || t.grp !== ex.grp) break;
      cur = t;
    }
    return cur;
  }

  /* ---------------- БИЛДЕР ---------------- */
  function pickExercise(grp, place, expLvl, used, shift, tier) {
    // Суставно-щадящий подбор для старших: убираем ударные (impact:'high'); у 65+ не расширяем
    // сложность вверх (потолок lvl = expLvl, а не +1) — предпочитаем безопасные простые движения.
    const gentle = (tier === 'older' || tier === 'middle');   // без ударных прыжков
    const maxLvl = (tier === 'older') ? expLvl : expLvl + 1;   // старшим не берём варианты сложнее нормы
    // 25.07: !e.alt — альтернативы (новые видео-упражнения) в АВТО-подбор дня НЕ берём, чтобы методика
    // (day templates, ротация 58 базовых) не менялась. Они доступны только через «Заменить».
    let cands = EX.filter(e => e.place === place && e.grp === grp && !e.alt && e.lvl <= maxLvl && !(gentle && e.impact === 'high'));
    if (!cands.length) cands = EX.filter(e => e.place === place && e.grp === grp && !e.alt && !(gentle && e.impact === 'high'));
    if (!cands.length) cands = EX.filter(e => e.place === place && e.grp === grp && !e.alt);
    if (!cands.length) return null;
    cands.sort((a, b) => Math.abs(a.lvl - expLvl) - Math.abs(b.lvl - expLvl));
    for (let i = 0; i < cands.length; i++) {
      const c = cands[(i + shift) % cands.length];
      if (!used.has(c.id)) { used.add(c.id); return c; }
    }
    return cands[shift % cands.length];
  }

  function buildWeek(profile, week) {
    let keys = (WEEK_PRESETS[profile.exp] || WEEK_PRESETS.novice)[profile.goal].slice();
    // Число тренировочных дней = выбранной частоте (freq_1..7). Раньше было зашито в пресет.
    const _N = (profile.trainWeekly != null ? profile.trainWeekly : 3);
    if (_N <= 0) { keys = []; }   // «не тренируюсь» → пустая программа
    else if (keys.length) { const _out = []; for (let _i = 0; _i < _N; _i++) _out.push(keys[_i % keys.length]); keys = _out; }
    const scheme = isAdaptation(week) ? ADAPT_SCHEME : GOAL_SCHEMES[profile.goal];
    const expLvl = profile.exp === 'experienced' ? 2 : 1;
    const shift = (profile.gender === 'male' ? 1 : 0) + (profile.goal === 'gain' ? 1 : 0);
    const days = [];
    keys.forEach((key, di) => {
      const tpl = DAY_TEMPLATES[key]; if (!tpl) return;
      const used = new Set();
      let slots = tpl.slots.slice();
      if (profile.gender === 'female' && /full|lower|legs/.test(key) && !slots.includes('glutes')) slots.splice(1, 0, 'glutes');
      if (expLvl === 1) slots = slots.slice(0, 6);
      const items = [];
      slots.forEach((grp, si) => {
        let ex = pickExercise(grp, profile.place, expLvl, used, shift + di + si, profile.ageTier);
        if (!ex) return;
        const origId = ex.id;                        // #6: id слота — по нему хранится ручная замена
        ex = applySwapOne(ex);                       // #6: ручная замена на альтернативу той же группы
        ex = applyVariant(ex);                       // ручной переход дома на сложнее вариант
        used.add(ex.id);                             // не дать другому слоту выбрать то же после замены
        const prog = progressionFor(ex, week, profile);
        items.push({ ex, origId: origId, sets: prog.sets, reps: prog.reps, rest: prog.rest, weight: prog.weight, phase: prog.phase });
      });
      days.push({ key, title: tpl.title, items });
    });
    return { days, scheme };
  }

  /* ---------------- ПОПАПЫ (общий каркас) ---------------- */
  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

  function openModal(innerHtml, cls) {
    closeModal();
    const ov = document.createElement('div');
    ov.id = 'wk-modal';
    ov.className = cls || '';
    ov.innerHTML = '<div class="wk-modal-box">' + innerHtml + '</div>';
    ov.addEventListener('click', (e) => { if (e.target === ov) closeModal(); });
    document.body.appendChild(ov);
    return ov;
  }
  function closeModal() { const m = document.getElementById('wk-modal'); if (m) m.remove(); }
  window._wkCloseModal = closeModal;

  /* ---------------- ПОПАП УПРАЖНЕНИЯ ---------------- */
  const IMG = 'workout_photos/';
  const VID = 'workout_videos/';     // #43: 2-сек луп-видео упражнения (если файл есть) — иначе тихий фолбэк на фото
  const PHOTO_VER = '?v=20260729';   // cache-bust (25.07: зальные миниатюры — кадры из видео)
  const VIDEO_VER = '?v=20260729';   // cache-bust (25.07: залиты 98 реальных видео + альтернативы)
  function openExercise(exId, sets, reps, rest, origId) {
    const ex = EX.find(e => e.id === exId); if (!ex) return;
    const slotId = origId || exId;   // #6: id слота для меню замены (обратимо к исходному)
    const profile = getProfile();
    const week = currentWeek();
    const w = currentWeight(ex, week, profile);
    const isGym = ex.place === 'gym';
    const harder = ex.place === 'home' ? harderVariant(ex) : null;
    const photos = [IMG + ex.id + '.webp' + PHOTO_VER, IMG + ex.id + '_b.webp' + PHOTO_VER];
    let idx = 0;

    const html =
      '<div class="wk-photo-wrap">'
      + '<video id="wk-vid" src="' + VID + ex.id + '.mp4' + VIDEO_VER + '" muted loop playsinline autoplay preload="auto" poster="' + photos[0] + '" style="display:none"></video>'
      + '<img id="wk-ph" src="' + photos[0] + '" alt="' + esc(ex.name) + '">'
      + '<button class="wk-ph-btn wk-ph-x" onclick="_wkCloseModal()">✕</button>'
      + '<button class="wk-ph-btn wk-ph-prev" id="wk-prev" style="display:none">‹</button>'
      + '<button class="wk-ph-btn wk-ph-next" id="wk-next">›</button>'
      + '<button class="wk-ph-btn wk-ph-turtle" id="wk-turtle" title="Замедлить показ" style="display:none">🐢</button>'
      + '</div>'
      + '<div class="wk-modal-body">'
      + '<div class="wk-modal-title-row"><div class="wk-modal-title">' + esc(ex.name) + '</div>'
      + '<button class="wk-swap-ic" id="wk-swap" title="Заменить на упражнение той же группы">Заменить</button></div>'
      + '<div class="wk-modal-meta">' + sets + ' × ' + esc(reps) + (rest ? ' · отдых ' + rest + ' сек' : '') + ' · ' + esc(ex.equip) + '</div>'
      + (w != null ? '<div class="wk-modal-meta">Рабочий вес на этой неделе: <b>' + w + ' кг</b></div>' : '')
      + '<div class="wk-modal-cue">' + esc(ex.cue) + '</div>'
      + (isGym
          ? '<div class="wk-weight-row"><label>Мой рабочий вес, кг:</label>'
            + '<input type="number" min="0" step="0.5" id="wk-w-input" value="' + (w != null ? w : '') + '" placeholder="—">'
            + '<input type="text" id="wk-w-reps" placeholder="повт." title="Сколько повторов сделал (необязательно)">'
            + '<button id="wk-w-save">Сохранить</button></div>'
            + '<div class="wk-modal-cue" style="margin-top:8px;font-size:12px">Введёшь новый вес — программа пересчитает все недели от него, ничего не сбрасывая: неделя, цикл, подходы и повторы сохранятся. Поле «повт.» — необязательно (по умолчанию запишем повторы программы).</div>'
            + '<button class="wk-hist-btn" id="wk-hist">📈 История рабочего веса</button>'
          : '')
      + (harder
          ? '<button class="wk-variant-btn" id="wk-variant">💪 Стало легко? Перейти на сложнее: ' + esc(harder.name) + '</button>'
            + '<div class="wk-modal-cue" style="margin-top:6px;font-size:12px">Лучший момент — когда дошёл до верхней границы повторов с запасом. Дома это заменяет «прибавку веса».</div>'
          : '')
      + '</div>';

    const ov = openModal(html, 'wk-ex-modal');
    const img = ov.querySelector('#wk-ph');
    const prev = ov.querySelector('#wk-prev');
    const next = ov.querySelector('#wk-next');

    // #43: есть луп-видео упражнения → показываем его вместо фото; нет файла → тихо остаётся фото (как было)
    const vid = ov.querySelector('#wk-vid');
    const turtle = ov.querySelector('#wk-turtle');
    let _rate = 1;   // #5: скорость показа видео (черепашка)
    if (vid) {
      vid.addEventListener('loadeddata', () => {
        vid.style.display = 'block';
        img.style.display = 'none';
        prev.style.display = 'none';
        next.style.display = 'none';   // видео заменяет переключение фото A/B
        if (turtle) turtle.style.display = '';   // #5: кнопка «черепашка» только при наличии видео
        try { vid.playbackRate = _rate; } catch (e) {}
        vid.play().catch(() => {});
      });
      vid.addEventListener('error', () => { try { vid.remove(); } catch (e) {} });
      vid.addEventListener('click', () => closeModal());
    }
    // #5 ЧЕРЕПАШКА: циклим скорость 1× → 0.5× → 0.25× → 1×. Клик по кнопке НЕ закрывает окно.
    if (turtle) turtle.addEventListener('click', (e) => {
      e.stopPropagation();
      _rate = _rate === 1 ? 0.5 : (_rate === 0.5 ? 0.25 : 1);
      try { if (vid) vid.playbackRate = _rate; } catch (er) {}
      turtle.textContent = _rate === 1 ? '🐢' : '🐢 ' + _rate + '×';
      turtle.classList.toggle('on', _rate !== 1);
    });
    // #6 ЗАМЕНА: открыть меню альтернатив той же группы (по id слота — обратимо).
    const swapBtn = ov.querySelector('#wk-swap');
    if (swapBtn) swapBtn.addEventListener('click', (e) => { e.stopPropagation(); openSwapMenu(slotId, ex); });
    // #1 ИСТОРИЯ веса (зал): лента дата·вес·повторы.
    const histBtn = ov.querySelector('#wk-hist');
    if (histBtn) histBtn.addEventListener('click', (e) => { e.stopPropagation(); openWeightHistory(ex.id); });

    // есть ли второе фото — проверяем тихо
    let hasB = false;
    const probe = new Image();
    probe.onload = () => { hasB = true; };
    probe.onerror = () => { hasB = false; next.style.display = 'none'; };
    probe.src = photos[1];

    function show(i) {
      idx = i; img.src = photos[idx];
      prev.style.display = idx > 0 ? '' : 'none';
      next.style.display = (idx === 0 && hasB) ? '' : 'none';
    }
    next.addEventListener('click', (e) => { e.stopPropagation(); if (hasB) show(1); });
    prev.addEventListener('click', (e) => { e.stopPropagation(); show(0); });
    img.addEventListener('click', () => closeModal());

    const save = ov.querySelector('#wk-w-save');
    if (save) save.addEventListener('click', () => {
      const v = parseFloat(ov.querySelector('#wk-w-input').value);
      if (v > 0) {
        const had = baseAnchor(ex.id) != null;
        const cyc = week > ADAPT_WEEKS ? automat(ex, week - ADAPT_WEEKS, profile.goal, profile.deloadEvery).c : 0;
        const ws = weights(); ws[ex.id] = { w: v, c: cyc }; LS.set('v2_workout_weights', ws);
        // #1 ЖУРНАЛ: дата·вес·повторы. Повторы — из поля (если ввёл) либо предписанные программой на эту неделю.
        try {
          const repsField = ov.querySelector('#wk-w-reps');
          const repsVal = (repsField && repsField.value.trim()) || String(reps || '');
          const log = weightLog(); if (!log[ex.id]) log[ex.id] = [];
          log[ex.id].push({ t: Date.now(), w: v, reps: repsVal });
          if (log[ex.id].length > 200) log[ex.id] = log[ex.id].slice(-200);
          LS.set('v2_workout_weight_log', log);
        } catch (e) {}
        const _sy = window.scrollY;   // сохранить позицию прокрутки — иначе render() кидает страницу в середину
        closeModal(); render();
        try { window.scrollTo(0, _sy); } catch (e) {}
        if (had) wkToast('🔄 Программа пересчитана от нового рабочего веса ' + v + ' кг. Неделя, цикл, подходы и повторы сохранены — прогресс не сброшен.');
      }
    });
    const vbtn = ov.querySelector('#wk-variant');
    if (vbtn && harder) vbtn.addEventListener('click', () => {
      const vs = variants(); vs[ex.id] = harder.id; LS.set('v2_workout_variants', vs);
      const _sy = window.scrollY;
      closeModal(); render();
      try { window.scrollTo(0, _sy); } catch (e) {}
      wkToast('💪 Уровень повышен: ' + harder.name + '. Веди повторы в том же диапазоне — это твоя домашняя прогрессия нагрузки.');
    });
  }
  window._wkOpenExercise = openExercise;

  /* ---------------- #6 МЕНЮ ЗАМЕНЫ УПРАЖНЕНИЯ ---------------- */
  const GRP_RU = { legs:'ноги', chest:'грудь', back:'спина', arms:'руки', shoulders:'плечи', core:'пресс', glutes:'ягодицы', cardio:'кардио' };
  function openSwapMenu(slotId, curEx) {
    const alts = swapAlternatives(curEx);
    const grpRu = GRP_RU[curEx.grp] || curEx.grp;
    const list = alts.length
      ? alts.map(a => '<button class="wk-swap-opt' + (a.id === curEx.id ? ' cur' : '') + '" data-id="' + a.id + '">'
          + '<img class="wk-swap-opt-img" loading="lazy" src="' + IMG + a.id + '.webp' + PHOTO_VER + '" alt="" onerror="this.style.visibility=\'hidden\'">'
          + '<span class="wk-swap-opt-name">' + esc(a.name) + '</span>'
          + (a.id === curEx.id ? '<span class="wk-swap-cur">сейчас</span>' : '')
          + '</button>').join('')
      : '<div class="wk-modal-cue">Нет других упражнений на эту группу.</div>';
    const ov = openModal(
      '<div class="wk-modal-body">'
      + '<div class="wk-modal-title">🔄 Замена · ' + esc(grpRu) + '</div>'
      + '<div class="wk-modal-cue">Выбери упражнение на ту же группу мышц. Прогрессия, вес и недели сохранятся.</div>'
      + '<div class="wk-swap-list">' + list + '</div>'
      + '<button class="wk-ok-btn" onclick="_wkCloseModal()">Отмена</button></div>'
    );
    ov.querySelectorAll('.wk-swap-opt').forEach(b => b.addEventListener('click', function () {
      const nid = this.dataset.id;
      const sw = swaps();
      if (nid === slotId) delete sw[slotId];   // выбрал исходное упражнение слота → снять замену
      else sw[slotId] = nid;
      LS.set('v2_workout_swaps', sw);
      const _sy = window.scrollY; closeModal(); render();
      try { window.scrollTo(0, _sy); } catch (e) {}
      const t = EX.find(e => e.id === nid);
      wkToast(nid === slotId ? '↩️ Вернули исходное упражнение.' : '🔄 Заменено на «' + (t ? t.name : '') + '». Замена сохранена.');
    }));
  }
  window._wkSwapMenu = openSwapMenu;

  /* ---------------- #1 ИСТОРИЯ РАБОЧЕГО ВЕСА ---------------- */
  function openWeightHistory(exId) {
    const ex = EX.find(e => e.id === exId); if (!ex) return;
    const log = (weightLog()[exId] || []).slice().reverse();   // новые сверху
    const rows = log.length
      ? log.map(function (e) {
          const d = new Date(e.t);
          const ds = ('0' + d.getDate()).slice(-2) + '.' + ('0' + (d.getMonth() + 1)).slice(-2) + '.' + d.getFullYear();
          return '<div class="wk-hist-row"><span class="wk-hist-date">' + ds + '</span>'
               + '<span class="wk-hist-w">' + e.w + ' кг</span>'
               + '<span class="wk-hist-reps">' + (e.reps ? esc(String(e.reps)) + ' повт.' : '') + '</span></div>';
        }).join('')
      : '<div class="wk-modal-cue">Пока нет записей. Введи рабочий вес в упражнении — история появится здесь: дата, вес, повторы.</div>';
    openModal(
      '<div class="wk-modal-body">'
      + '<div class="wk-modal-title">📈 История веса · ' + esc(ex.name) + '</div>'
      + '<div class="wk-hist-list">' + rows + '</div>'
      + '<button class="wk-ok-btn" onclick="_wkCloseModal()">Закрыть</button></div>'
    );
  }
  window._wkWeightHistory = openWeightHistory;

  /* ---------------- #4 РАЗМИНКА: окно-лента видео (каркас) ----------------
     Видео пришлёт Замир: файлы warmup_videos/warmup_1.mp4 … warmup_N.mp4 (3–5 сек).
     Пробуем до WARMUP_MAX; отсутствующие тихо удаляются (onerror). Порядок — по номеру. */
  const WARMUP_VID = 'warmup_videos/';
  const WARMUP_MAX = 24;
  function openWarmup() {
    let vids = '';
    for (let i = 1; i <= WARMUP_MAX; i++) {
      vids += '<video class="wk-warm-vid" muted loop playsinline preload="metadata" style="display:none" '
            + 'src="' + WARMUP_VID + 'warmup_' + i + '.mp4' + VIDEO_VER + '" '
            + 'onloadeddata="this.style.display=\'block\';var p=this.play&&this.play();if(p&&p.catch)p.catch(function(){});" '
            + 'onerror="this.remove()"></video>';
    }
    openModal(
      '<div class="wk-warm-head"><div class="wk-modal-title">🔥 Разминка</div>'
      + '<button class="wk-ph-btn wk-warm-x" onclick="_wkCloseModal()">✕</button></div>'
      + '<div class="wk-warm-note">Сделай эти движения перед тренировкой. 5–15 минут, спокойно.</div>'
      + '<div class="wk-warm-list">' + vids
      + '<div class="wk-warm-empty wk-modal-cue">Видео разминки скоро появятся.</div></div>',
      'wk-warm-modal'
    );
  }
  window._wkOpenWarmup = openWarmup;

  /* ---------------- «20 МИНУТ С РОМАНОМ»: follow-along видео-тренировки ----------------
     Дом, но изменённый режим. Одна тренировка = РАЗМИНКА (roman_warmup) + ОСНОВНАЯ часть
     (одна из 5 полных тренировок, сменная кнопкой «Заменить»). Видео 1080p→480p СО ЗВУКОМ,
     смотришь и повторяешь за Романом (в отличие от немых лупов-упражнений). 29.07 (Замир). */
  const ROMAN_WARMUP = { file: 'roman_warmup', name: 'Разминка + разогрев (Full Body)', dur: '~10 мин', cue: 'Начни с неё: разогрей мышцы и суставы перед основной частью.' };
  const ROMAN_WORKOUTS = [
    { file: 'roman_w1', name: 'Full Body — базовая',        dur: '~6 мин',  cue: 'Короткая тренировка на всё тело.' },
    { file: 'roman_w2', name: 'На всё тело',                dur: '~10 мин', cue: 'Полная проработка всего тела.' },
    { file: 'roman_w3', name: 'Кор и пресс',                dur: '~6 мин',  cue: 'Акцент на мышцы кора и пресс.' },
    { file: 'roman_w4', name: 'Эффективная Full Body',      dur: '~6 мин',  cue: 'Интенсивная тренировка на всё тело.' },
    { file: 'roman_w5', name: 'Сложная Full Body',          dur: '~18 мин', cue: 'Продвинутый уровень, полный формат.' },
  ];

  function romanCard(v, swap) {
    return '<div class="wk-roman-card" onclick="_wkRomanPlay(\'' + v.file + '\',\'' + esc(v.name) + '\')">'
      + '<div class="wk-roman-thumb-wrap">'
      + '<img class="wk-roman-thumb" loading="lazy" src="' + IMG + v.file + '.webp' + PHOTO_VER + '" alt="" onerror="this.style.visibility=\'hidden\'">'
      + '<div class="wk-roman-play">▶</div>'
      + (swap
          ? '<button class="wk-roman-swap" onclick="event.stopPropagation();_wkRomanSwap()">Заменить</button>'
          : '<span class="wk-roman-badge">Шаг 1 · Разминка</span>')
      + '</div>'
      + '<div class="wk-roman-info"><div class="wk-roman-name">' + esc(v.name) + '</div>'
      + '<div class="wk-roman-meta">⏱ ' + esc(v.dur) + ' · ' + esc(v.cue) + '</div></div>'
      + '</div>';
  }

  function romanMode() {
    const sel = Math.min(Math.max(prefs().romanW | 0, 0), ROMAN_WORKOUTS.length - 1);
    const w = ROMAN_WORKOUTS[sel];
    let s = '<div class="wk-sub">Видео-тренировки на всё тело: смотри и повторяй за Романом. '
      + 'Одна тренировка = <b>разминка</b> + <b>основная часть</b>. Основную можно поменять кнопкой «Заменить».</div>';
    s += '<div class="wk-roman-wrap">';
    s += romanCard(ROMAN_WARMUP, false);
    s += '<div class="wk-roman-plus">＋</div>';
    s += '<div class="wk-roman-step2">Шаг 2 · Основная тренировка</div>';
    s += romanCard(w, true);
    s += '</div>';
    return s;
  }

  function openRomanVideo(file, name) {
    openModal(
      '<div class="wk-roman-pl-head"><span class="wk-roman-pl-title">' + esc(name) + '</span>'
      + '<button class="wk-ph-btn wk-roman-pl-x" onclick="_wkCloseModal()">✕</button></div>'
      + '<video class="wk-roman-pl-vid" controls playsinline autoplay preload="auto" '
      + 'poster="' + IMG + file + '.webp' + PHOTO_VER + '" '
      + 'src="' + VID + file + '.mp4' + VIDEO_VER + '"></video>'
      + '<div class="wk-roman-pl-note wk-modal-cue">Повторяй за Романом. Пауза — по кнопке на видео.</div>',
      'wk-roman-modal'
    );
  }
  window._wkRomanPlay = openRomanVideo;

  function openRomanSwap() {
    const cur = prefs().romanW | 0;
    const items = ROMAN_WORKOUTS.map((v, i) =>
      '<button class="wk-swap-opt' + (i === cur ? ' cur' : '') + '" data-i="' + i + '">'
      + '<img class="wk-swap-opt-img" loading="lazy" src="' + IMG + v.file + '.webp' + PHOTO_VER + '" alt="" onerror="this.style.visibility=\'hidden\'">'
      + '<div class="wk-swap-opt-name">' + esc(v.name) + (i === cur ? ' ✓' : '')
      + '<div class="wk-roman-meta" style="margin-top:2px">⏱ ' + esc(v.dur) + '</div></div></button>'
    ).join('');
    openModal('<div class="wk-swap-title">🎬 Выбери основную тренировку</div>'
      + '<div class="wk-swap-list">' + items + '</div>'
      + '<button class="wk-ok-btn" onclick="_wkCloseModal()">Закрыть</button>', 'wk-swap-modal');
    const ov = document.getElementById('wk-modal');
    if (ov) ov.querySelectorAll('.wk-swap-opt').forEach(b => b.addEventListener('click', function () {
      const p = prefs(); p.romanW = +this.dataset.i; LS.set('v2_workout_prefs', p); closeModal(); render();
    }));
  }
  window._wkRomanSwap = openRomanSwap;

  /* ---------------- «СДЕЛАНО»: toggle + двигатель недели ----------------
     Отметка хранит НОМЕР недели (doneMap[dayId] = week). Повторное нажатие в ту же
     неделю снимает отметку (toggle off). Когда ВСЕ тренировочные дни недели отмечены —
     монотонный счётчик недель едет вперёд (неделя считается по ВЫПОЛНЕННЫМ тренировкам,
     а не по дням питания). Прежняя отметка остаётся историей (привязана к своей неделе). */
  function markDone(dayId) {
    const d = doneMap();
    const wk = weekCounter();
    if (d[dayId] === wk) {            // уже отмечено на этой неделе → снять отметку (toggle off)
      delete d[dayId];
      LS.set('v2_workout_done', d);
      render();
      return;
    }
    d[dayId] = wk;                    // отметить выполненной на ТЕКУЩЕЙ неделе
    LS.set('v2_workout_done', d);

    // Двигатель недели: все дни недели выполнены → +1 неделя (монотонно, без капа).
    let advanced = false;
    try {
      const profile = getProfile();
      const plan = buildWeek(profile, wk);
      const ids = plan.days.map((x, i) => profile.place + '_' + i + '_' + x.key);   // #M5: id по индексу (совпадает с render)
      const doneN = ids.filter(id => d[id] === wk).length;
      if (ids.length && doneN >= ids.length) { setWeekCounter(wk + 1); advanced = true; }
    } catch (e) {}

    render();

    if (advanced) {
      wkToast('🎉 Неделя ' + wk + ' закрыта! Переходим на неделю ' + (wk + 1) + ' — программа добавит нагрузку по прогрессии.');
    } else {
      wkToast('✅ Тренировка засчитана. Нажми ещё раз, если отметил случайно.');
    }
  }
  window._wkMarkDone = markDone;   // (устар.: кнопка «Сделано» убрана; неделя считается по зачёркнутым дням)

  // 16.07 (Замир): «?» вместо «Сделано» — объясняет, как растёт неделя тренировок.
  function weekInfo() {
    openModal(
      '<div class="wk-modal-body">'
      + '<div class="wk-modal-title">Как растёт неделя тренировок</div>'
      + '<div class="wk-modal-cue">Отмечайте пройденные дни в меню — удержите кнопку дня, чтобы зачеркнуть его. '
      + 'Как только наберётся <b>7 зачёркнутых дней</b>, приложение само переведёт вас на следующую неделю '
      + 'тренировок и добавит нагрузку по прогрессии. В тренировках ничего нажимать не нужно — прогресс '
      + 'считается по вашим пройденным дням и хранится на сервере.</div>'
      + '<button class="wk-ok-btn" onclick="_wkCloseModal()">Понятно</button></div>'
    );
  }
  window._wkWeekInfo = weekInfo;
  // Закрыть блок «Адаптация кончилась» (крестик).
  window._wkDismissAdaptEnd = function(){ try { LS.set('v2_adapt_end_dismissed', true); } catch (e) {} render(); };

  /* ---------------- «РАБОЧИЙ ВЕС?» (по RIR/ACSM) ---------------- */
  function openWeightHelp() {
    openModal(
      '<div class="wk-modal-body">'
      + '<div class="wk-modal-title">Как узнать свой рабочий вес</div>'
      + '<ol class="wk-help-list">'
      + '<li>Выбери вес, который кажется <b>лёгким</b> — с ним точно сделаешь 10 повторений чисто (штанга — начни с пустого грифа).</li>'
      + '<li>Сделай подход из 10 повторений в спокойном темпе, следи за техникой.</li>'
      + '<li>Оцени запас: сколько ещё повторов смог бы сделать «с трудом, но чисто»?</li>'
      + '<li>Запас <b>4 и больше</b> → слишком легко: добавь 2–5 кг, отдохни 2–3 минуты и повтори.</li>'
      + '<li>Запас <b>0–1</b> (еле доделал) → слишком тяжело: убери 2–5 кг.</li>'
      + '<li>Запас <b>2–3 повтора</b> → это твой рабочий вес. Открой упражнение и запиши его — дальше приложение будет добавлять нагрузку само.</li>'
      + '</ol>'
      + '<div class="wk-modal-cue">Первые 2 недели не гонись за весом: сначала техника. Дома вместо веса подбирай вариант упражнения так, чтобы 10–12 повторов оставляли запас 2–3.</div>'
      + '<button class="wk-ok-btn" onclick="_wkCloseModal()">Понятно</button></div>'
    );
  }
  window._wkWeightHelp = openWeightHelp;

  /* ---------- АВТО-ИЗМЕНЕНИЯ ПРОГРАММЫ: снимок недели + уведомление ----------
     При переходе на новую неделю программа сама меняет нагрузку. Сравниваем снимок
     представительного базового упражнения с сохранённым: если что-то выросло / началась
     разгрузка — показываем понятный тост. Смену места/цели за «авто» не считаем. */
  function weekSummary(profile, week, wk) {
    let comp = null;
    (wk.days || []).forEach(day => (day.items || []).forEach(it => { if (!comp && it.ex.kind === 'compound') comp = it; }));
    const weightList = {};
    (wk.days || []).forEach(day => (day.items || []).forEach(it => { if (it.weight != null) weightList[it.ex.id] = it.weight; }));
    return {
      week, place: profile.place, goal: profile.goal,
      compSets: comp ? comp.sets : null,
      compReps: comp ? String(comp.reps) : null,
      phase: comp ? comp.phase : null,
      weights: weightList,
    };
  }
  function notifyAutoProgress(profile, week, wk) {
    const cur = weekSummary(profile, week, wk);
    const prev = LS.get('v2_workout_snapshot', null);
    LS.set('v2_workout_snapshot', cur);                 // снимок обновляем всегда
    if (!prev) return;                                   // первый заход — сравнивать не с чем
    if (prev.place !== cur.place || prev.goal !== cur.goal) return; // сменили место/цель — это не «авто»
    if (cur.week <= prev.week) return;                   // неделя не выросла
    if (prev.week <= ADAPT_WEEKS && week > ADAPT_WEEKS) return; // конец адаптации — отдельное поздравление
    if (cur.phase === 'deload' && prev.phase !== 'deload') {
      wkToast('🟦 Разгрузочная неделя ' + week + ': работаем легче — на подход меньше, повторы снизу, вес держим. Это часть плана, не откат.');
      return;
    }
    const msgs = [];
    if (cur.compSets != null && prev.compSets != null && cur.compSets > prev.compSets)
      msgs.push('подходов в базовых больше: ' + prev.compSets + ' → ' + cur.compSets);
    if (cur.compReps && prev.compReps && cur.compReps !== prev.compReps)
      msgs.push('повторы: ' + prev.compReps + ' → ' + cur.compReps);
    let wUp = 0;
    for (const id in cur.weights)
      if (prev.weights && prev.weights[id] != null && cur.weights[id] > prev.weights[id]) wUp++;
    if (wUp > 0) msgs.push('рабочий вес вырос — начался новый цикл');
    if (!msgs.length) return;
    wkToast('🔼 Программа обновилась к неделе ' + week + ': ' + msgs.join('; ') + '.');
  }
  // АВТО-ПРЕДЛОЖЕНИЕ (дом): на пике цикла приложение само предлагает перейти на сложнее
  // вариант; пользователь подтверждает кнопкой в попапе упражнения. Дедуп по циклу — без спама.
  function suggestHomeVariants(profile, week, wk) {
    if (profile.place !== 'home' || week <= ADAPT_WEEKS) return;
    const sug = LS.get('v2_workout_variant_suggested', {});  // exId → индекс цикла, для которого уже предложили
    const vs = variants();
    let shown = false;
    (wk.days || []).forEach(day => (day.items || []).forEach(it => {
      if (shown) return;
      const ex = it.ex;
      if (ex.place !== 'home' || it.phase !== 'peak') return;      // только дом и только пик цикла
      const harder = harderVariant(ex);
      if (!harder || vs[ex.id] === harder.id) return;             // некуда усложнять / уже перешли
      const cyc = automat(ex, week - ADAPT_WEEKS, profile.goal, profile.deloadEvery).c;
      if (sug[ex.id] === cyc) return;                             // для этого цикла уже предлагали
      sug[ex.id] = cyc; LS.set('v2_workout_variant_suggested', sug);
      wkToast('💪 Пик цикла по «' + ex.name + '». Стало легко? Открой упражнение и подтверди переход на сложнее: ' + harder.name + ' — это твоя домашняя прибавка нагрузки.');
      shown = true;                                              // одно предложение за заход
    }));
  }
  function wkToast(text) {
    if (typeof window.showToast === 'function') { window.showToast(text, 6000); return; }
    const old = document.getElementById('wk-toast'); if (old) old.remove();
    const t = document.createElement('div');
    t.id = 'wk-toast'; t.textContent = text;
    t.style.cssText = 'position:fixed;left:50%;bottom:96px;transform:translateX(-50%);z-index:9002;'
      + 'max-width:340px;background:rgba(20,28,26,.97);color:#F3ECDC;border:1px solid rgba(220,190,121,.5);'
      + 'border-radius:14px;padding:12px 16px;font-size:13px;line-height:1.45;box-shadow:0 12px 40px rgba(0,0,0,.5);text-align:center;';
    document.body.appendChild(t);
    setTimeout(() => { t.style.transition = 'opacity .4s'; t.style.opacity = '0'; setTimeout(() => t.remove(), 400); }, 6000);
  }

  /* ---------------- РЕНДЕР ---------------- */
  const FREQ_RU = { gym_0:'старт', gym_1:'2 тренировки/нед', gym_3:'3–4 тренировки/нед', gym_5:'5 тренировок/нед' };
  const GOAL_RU = { loss:'похудение', gain:'набор массы', maintain:'поддержание' };

  function repBar(R0, Rmax, now) {
    const total = Rmax - R0;
    const frac = total > 0 ? (now - R0) / total : 1;
    const pct = Math.max(0, Math.min(1, frac)) * 100;
    return '<div class="wk-bar"><div class="wk-bar-fill" style="width:' + pct.toFixed(0) + '%"></div></div>';
  }

  // Возрастная подсказка: объясняет пользователю, что программа мягче (разминка, темп, шаг веса).
  function ageHint(profile) {
    if (profile.ageTier === 'older')
      return '<div class="wk-agehint">🕊️ Программа настроена под возраст 65+: вес добавляем маленькими шагами, разгрузка чаще (каждые 4 недели), упражнения — суставно-щадящие, без ударных прыжков. Перед тренировкой — 5–7 минут разминки и суставной гимнастики; темп подконтрольный, всегда оставляй запас 2–3 повтора.</div>';
    if (profile.ageTier === 'middle')
      return '<div class="wk-agehint">🕊️ Небольшая возрастная поправка (50–64): шаг веса чуть меньше, разгрузка каждые 5 недель, ударные прыжки убраны. Не пропускай разминку 5 минут.</div>';
    return '';
  }

  function statusBanner(profile, week) {
    const st = programStatus(profile, week);
    if (st.adapt) {
      return '<div class="wk-banner wk-banner-adapt">'
        + '<div class="wk-banner-top">🌱 Адаптация · неделя ' + week + ' из ' + ADAPT_WEEKS + '</div>'
        + '<div class="wk-banner-sub">Тело привыкает — вес не гоним, растим только повторы. Со 2-го месяца включится полная прогрессия (повторы → подходы → вес).</div>'
        + '</div>';
    }
    // Адаптация ЗАКОНЧИЛАСЬ (первая неделя после месяца) → блок-объявление с крестиком (пока не закрыт).
    if (week === ADAPT_WEEKS + 1 && !LS.get('v2_adapt_end_dismissed', false)) {
      return '<div class="wk-banner wk-banner-adapt" style="position:relative">'
        + '<button onclick="window._wkDismissAdaptEnd&&window._wkDismissAdaptEnd()" aria-label="Закрыть" style="position:absolute;top:6px;right:10px;background:none;border:none;color:inherit;font-size:20px;line-height:1;cursor:pointer;opacity:.6">✕</button>'
        + '<div class="wk-banner-top">🎉 Адаптация кончилась!</div>'
        + '<div class="wk-banner-sub">Тренируемся в полную силу, сохраняя технику, — медленно прогрессируя в весах, подходах и повторах.</div>'
        + '</div>';
    }
    if (st.isDeload) {
      return '<div class="wk-banner wk-banner-deload">'
        + '<div class="wk-banner-top">🟦 Разгрузка · неделя ' + week + ' · цикл ' + st.cycleNum + '</div>'
        + '<div class="wk-banner-sub">Работаем легче: на подход меньше, повторы снизу диапазона, вес держим. Это часть плана — восстанавливаемся, чтобы расти дальше.</div>'
        + '</div>';
    }
    const phaseLabel = st.phase === 'peak' ? 'пик цикла — дальше +вес' : 'рост повторов';
    const bits = [];
    bits.push('до +веса: ' + (st.weeksToWeight === 0 ? 'на след. неделе' : st.weeksToWeight + ' нед'));
    bits.push('разгрузка через ' + st.weeksToDeload + ' нед');
    return '<div class="wk-banner">'
      + '<div class="wk-banner-top">Неделя ' + week + ' · Цикл ' + st.cycleNum + ' · ' + phaseLabel + '</div>'
      + repBar(st.R0, st.Rmax, st.repNow)
      + '<div class="wk-banner-sub">Повторы ' + st.repNow + ' из ' + st.Rmax + ' · ' + bits.join(' · ') + '</div>'
      + '</div>';
  }

  function render() {
    const host = document.getElementById('workouts-section');
    if (!host) return;
    const profile = getProfile();
    // «Не тренируюсь» (trainWeekly === 0): не рендерим пустую программу (был чёрный пустой
    // контейнер) — показываем короткое сообщение на фоне ТЕМЫ (карточка .card = surface).
    if (profile.trainWeekly === 0) {
      host.innerHTML = '<div class="card" id="workouts-card">'
        + '<div class="wk-head-row"><div class="card-title">🏋️ Твои тренировки</div></div>'
        + '<div class="wk-notrain">😴 Ты выбрал: <b>не тренируюсь</b>.<br>'
        + 'Раздел тренировок отключён. Захочешь программу — открой «Профиль» и укажи, '
        + 'сколько раз в неделю готов тренироваться.</div>'
        + '</div>';
      return;
    }
    const week = currentWeek();
    const wk = buildWeek(profile, week);
    const done = doneMap();
    const isCab = (typeof IS_CABINET !== 'undefined' && IS_CABINET);
    const purchased = isCab || (typeof state === 'object' && state && state.purchased);
    // 16.07 (Замир): открытое превью — тренировки показываем ПОЛНОСТЬЮ (все дни недели), а не 1 день.
    // Гейт оплаты теперь на переходе к Дню 2 плана питания, а не внутри тренировок. Блок «🔒 ещё N дней» убран.
    const visibleDays = wk.days;
    const adapt = isAdaptation(week);

    // Уведомление об АВТО-изменениях программы (прогрессия сделала это сама) — тост при заходе.
    try { notifyAutoProgress(profile, week, wk); } catch (e) {}
    try { suggestHomeVariants(profile, week, wk); } catch (e) {}

    // Поздравление с окончанием адаптации — один раз
    if (!adapt && purchased && !LS.get('v2_wk_congrats', false)) {
      LS.set('v2_wk_congrats', true);
      setTimeout(() => openModal(
        '<div class="wk-modal-body" style="text-align:center">'
        + '<div style="font-size:34px;margin-bottom:10px">🏆</div>'
        + '<div class="wk-modal-title">Первый месяц позади!</div>'
        + '<div class="wk-modal-cue" style="margin-top:10px">Он был самым тяжёлым — начинать всегда тяжело, а ты справился. Тело адаптировалось: переходим к полной прогрессии. Теперь повторы будут расти внутри цикла, затем добавится подход, затем вес — а каждые 6 недель будет разгрузка.</div>'
        + '<button class="wk-ok-btn" onclick="_wkCloseModal()">Погнали 🔥</button></div>'
      ), 600);
    }

    let h = '<div class="card" id="workouts-card">';
    h += '<div class="wk-head-row"><div class="card-title">🏋️ Твои тренировки</div>'
       + '<button class="wk-help-btn" onclick="_wkWeightHelp()">Рабочий вес?</button></div>';
    h += '<div class="wk-place">'
       + '<button class="wk-place-btn' + (profile.place === 'home' ? ' on' : '') + '" data-place="home">🏠 Дома</button>'
       + '<button class="wk-place-btn' + (profile.place === 'gym' ? ' on' : '') + '" data-place="gym">🏋️ В зале</button>'
       + '<button class="wk-place-btn wk-place-roman' + (profile.place === 'roman' ? ' on' : '') + '" data-place="roman">🎬 20 минут с Романом</button>'
       + '</div>';

    // Режим follow-along: разминка + одна сменная тренировка. Не показываем дневную программу/прогрессию.
    if (profile.place === 'roman') {
      h += romanMode();
      h += '</div>';
      host.innerHTML = h;
      host.querySelectorAll('.wk-place-btn').forEach(b => b.addEventListener('click', function (e) {
        e.stopPropagation();
        const p = prefs(); p.place = this.dataset.place; LS.set('v2_workout_prefs', p); render();
      }));
      return;
    }

    h += '<div class="wk-sub">Под твой профиль: ' + esc(GOAL_RU[profile.goal]) + ' · ' + esc(FREQ_RU[profile.freq] || '') + ' · неделя ' + week + '.<br>'
       + 'Прогрессия растёт по <b>пройденным дням меню</b>: зачеркните 7 дней — программа сама перейдёт на следующую неделю и добавит нагрузку. Отмечать что-то в тренировках не нужно.</div>';
    h += ageHint(profile);
    h += statusBanner(profile, week);
    h += '<div class="wk-note">' + esc(wk.scheme.note) + '</div>';

    visibleDays.forEach((day, di) => {
      // #M5: id дня включает ИНДЕКС позиции. Раньше был place+key, а недельный пресет размножает
      // ключи (upper/lower/upper/lower) → дни 1 и 3 имели один id → «Сделано» на одном закрывало оба,
      // неделя из 4 тренировок засчитывалась за 2 (прогрессия бежала вдвое). Индекс делает id уникальным.
      // 16.07 (Замир): «Сделано» убрана — неделя считается по зачёркнутым дням меню. Вместо неё «?» с пояснением.
      h += '<div class="wk-day">';
      h += '<div class="wk-day-head"><span class="wk-day-num">День ' + (di + 1) + '</span>'
         + '<span class="wk-day-title">' + esc(day.title) + '</span>'
         + '<button class="wk-info-btn" onclick="_wkWeekInfo()" title="Как считается неделя тренировок">?</button></div>';
      // #4 РАЗМИНКА — первой в КАЖДОМ дне (и дома, и в зале). Тап → окно-лента видео (видео пришлёт Замир).
      h += '<div class="wk-ex wk-warmup" onclick="_wkOpenWarmup()">'
         + '<div class="wk-ex-img wk-warmup-img">🔥</div>'
         + '<div class="wk-ex-body">'
         + '<div class="wk-ex-name">Разминка</div>'
         + '<div class="wk-ex-meta">5–15 минут</div>'
         + '<div class="wk-ex-cue">В блоке «Разминка» несколько упражнений.</div>'
         + '</div></div>';
      day.items.forEach(it => {
        const w = it.weight;
        h += '<div class="wk-ex" onclick="_wkOpenExercise(\'' + it.ex.id + '\',' + it.sets + ',\'' + esc(it.reps) + '\',' + it.rest + ',\'' + esc(it.origId || it.ex.id) + '\')">'
           + '<img class="wk-ex-img" loading="lazy" src="' + IMG + it.ex.id + '.webp' + PHOTO_VER + '" alt="" onerror="this.style.visibility=\'hidden\'">'
           + '<div class="wk-ex-body">'
           + '<div class="wk-ex-name">' + esc(it.ex.name) + '</div>'
           + '<div class="wk-ex-meta">' + it.sets + ' × ' + esc(it.reps) + (w != null ? ' · ' + w + ' кг' : '') + (it.rest ? ' · отдых ' + it.rest + ' сек' : '') + '</div>'
           + '<div class="wk-ex-cue">' + esc(it.ex.cue) + '</div>'
           + '</div></div>';
      });
      h += '</div>';
    });

    // 16.07 (Замир): блок «🔒 ещё N тренировочных дней» убран — в открытом превью тренировки видны целиком.
    h += '</div>';
    host.innerHTML = h;

    host.querySelectorAll('.wk-place-btn').forEach(b => b.addEventListener('click', function (e) {
      e.stopPropagation();
      const p = prefs(); p.place = this.dataset.place; LS.set('v2_workout_prefs', p); render();
    }));
  }

  /* ---------------- CSS ---------------- */
  const css = document.createElement('style');
  css.textContent = `
    #workouts-card { margin-top:16px; }
    .wk-head-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
    .wk-help-btn { padding:6px 12px; border-radius:8px; border:1px solid rgba(220,190,121,.25); background:transparent; color:var(--muted,#8E93A1); font-size:12px; font-weight:600; cursor:pointer; }
    .wk-sub { font-size:13px; color:var(--muted); margin:8px 0 12px; line-height:1.5; }
    .wk-place { display:flex; gap:8px; margin-bottom:12px; }
    .wk-place-btn { flex:1; padding:11px; border-radius:12px; border:1px solid var(--border); background:var(--surface2); color:var(--muted); font-size:14px; font-weight:600; cursor:pointer; transition:all .2s; }
    .wk-place-btn.on { background:linear-gradient(135deg,var(--accent,#DCBE79),var(--accent2,#F2D995)); color:#10131a; border-color:transparent; box-shadow:0 4px 16px rgba(220,190,121,.3); }
    .wk-place { flex-wrap:wrap; }
    .wk-place-roman { flex-basis:100%; }
    /* ── режим «20 минут с Романом» ── */
    .wk-roman-wrap { display:flex; flex-direction:column; gap:8px; margin-top:4px; }
    .wk-roman-step2 { font-size:12px; font-weight:700; color:var(--accent2,#F2D995); letter-spacing:.02em; margin:2px 2px -2px; }
    .wk-roman-plus { text-align:center; font-size:22px; color:var(--muted); line-height:1; margin:-2px 0; }
    .wk-roman-card { border:1px solid var(--border); border-radius:16px; overflow:hidden; background:var(--surface2); cursor:pointer; transition:transform .15s, box-shadow .15s; }
    .wk-roman-card:active { transform:scale(.99); }
    .wk-roman-card:hover { box-shadow:0 6px 22px rgba(0,0,0,.28); }
    .wk-roman-thumb-wrap { position:relative; width:100%; aspect-ratio:16/9; background:#0c1412; }
    .wk-roman-thumb { width:100%; height:100%; object-fit:cover; display:block; }
    .wk-roman-play { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); width:52px; height:52px; border-radius:50%; background:rgba(16,19,26,.62); color:#fff; font-size:20px; display:flex; align-items:center; justify-content:center; padding-left:4px; backdrop-filter:blur(2px); box-shadow:0 2px 12px rgba(0,0,0,.4); }
    .wk-roman-badge { position:absolute; top:10px; left:10px; padding:4px 10px; border-radius:12px; background:rgba(16,19,26,.66); color:var(--accent2,#F2D995); font-size:11px; font-weight:700; }
    .wk-roman-swap { position:absolute; top:10px; right:10px; height:30px; padding:0 14px; border-radius:15px; border:1px solid rgba(220,190,121,.5); background:rgba(16,19,26,.72); color:var(--accent2,#F2D995); font-size:12px; font-weight:700; cursor:pointer; }
    .wk-roman-swap:hover { background:rgba(220,190,121,.18); }
    .wk-roman-info { padding:11px 14px 13px; }
    .wk-roman-name { font-weight:700; font-size:15px; color:var(--text); }
    .wk-roman-meta { font-size:12px; color:var(--muted); margin-top:3px; line-height:1.4; }
    /* плеер follow-along (со звуком, во весь кадр 16:9) */
    .wk-roman-modal .wk-modal-box { padding:0; overflow:hidden; }
    .wk-roman-pl-head { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:12px 14px 8px; }
    .wk-roman-pl-title { font-weight:700; font-size:15px; color:var(--text); }
    .wk-roman-pl-x { flex-shrink:0; }
    .wk-roman-pl-vid { width:100%; max-height:74vh; background:#000; display:block; }
    .wk-roman-pl-note { padding:8px 14px 14px; }
    .wk-swap-list { display:flex; flex-direction:column; gap:8px; margin-top:12px; }
    /* статус-баннер цикла */
    .wk-banner { border:1px solid rgba(220,190,121,.28); background:linear-gradient(135deg,rgba(220,190,121,.10),rgba(242,217,149,.04)); border-radius:12px; padding:12px 14px; margin-bottom:10px; }
    .wk-banner-top { font-size:13px; font-weight:700; color:var(--accent2,#F2D995); letter-spacing:.01em; }
    .wk-banner-sub { font-size:12px; color:var(--muted); margin-top:6px; line-height:1.5; }
    .wk-banner-adapt { border-color:rgba(95,191,122,.30); background:linear-gradient(135deg,rgba(95,191,122,.12),rgba(95,191,122,.03)); }
    .wk-banner-adapt .wk-banner-top { color:#9fd3a8; }
    .wk-banner-deload { border-color:rgba(120,160,210,.35); background:linear-gradient(135deg,rgba(120,160,210,.14),rgba(120,160,210,.04)); }
    .wk-banner-deload .wk-banner-top { color:#9dc0e6; }
    .wk-bar { height:6px; border-radius:6px; background:rgba(220,190,121,.14); margin:9px 0 2px; overflow:hidden; }
    .wk-bar-fill { height:100%; border-radius:6px; background:linear-gradient(90deg,var(--accent,#DCBE79),var(--accent2,#F2D995)); transition:width .3s; }
    .wk-note { font-size:12.5px; color:var(--accent2); margin-bottom:14px; }
    .wk-notrain { font-size:13.5px; color:var(--muted); line-height:1.6; padding:4px 2px 2px; }
    .wk-agehint { font-size:12px; color:var(--muted); line-height:1.5; border:1px solid rgba(120,160,210,.28); background:linear-gradient(135deg,rgba(120,160,210,.10),rgba(120,160,210,.03)); border-radius:12px; padding:10px 12px; margin-bottom:12px; }
    .wk-day { border:1px solid rgba(220,190,121,.14); border-radius:16px; padding:14px; margin-bottom:12px; background:var(--surface); }
    .wk-day.done { opacity:.6; }
    .wk-day-head { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
    .wk-day-num { font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); font-weight:700; }
    .wk-day-title { font-family:'Inter',-apple-system,sans-serif; font-size:16px; flex:1; }
    .wk-done-btn { padding:7px 14px; border-radius:10px; border:1px solid var(--border); background:transparent; color:var(--accent2); font-size:12.5px; font-weight:600; cursor:pointer; transition:all .2s; }
    .wk-done-btn.is-done { background:var(--green); color:#08130c; border-color:transparent; }
    /* 16.07: «?» вместо «Сделано» — неделя считается по зачёркнутым дням */
    .wk-info-btn { width:28px; height:28px; flex-shrink:0; border-radius:50%; border:1px solid var(--border); background:transparent; color:var(--muted); font-size:14px; font-weight:700; cursor:pointer; display:flex; align-items:center; justify-content:center; }
    .wk-info-btn:hover { color:var(--accent2); border-color:rgba(220,190,121,.4); }
    .wk-ex { display:flex; gap:10px; padding:9px 0; border-top:1px solid rgba(220,190,121,.08); cursor:pointer; transition:background .15s; }
    .wk-ex:hover { background:rgba(220,190,121,.05); }
    .wk-ex-img { width:56px; height:56px; border-radius:10px; object-fit:cover; border:1px solid rgba(220,190,121,.15); flex-shrink:0; }
    .wk-ex-name { font-size:14px; font-weight:600; }
    .wk-ex-meta { font-size:12px; color:var(--accent2); margin-top:2px; }
    .wk-ex-cue { font-size:12px; color:var(--muted); margin-top:2px; line-height:1.4; }
    .wk-locked { text-align:center; font-size:13px; color:var(--muted); padding:14px 10px 4px; line-height:1.5; }
    .wk-buy { margin-top:10px; }
    /* модалки */
    /* 16.07 (Замир): окно прокручиваемое — высокое портретное видео не влезало, верх/низ обрезались.
       align-items:flex-start + overflow-y:auto → можно домотать до верха и низа. */
    #wk-modal { position:fixed; inset:0; z-index:700; background:rgba(0,0,0,.75); backdrop-filter:blur(6px); display:flex; align-items:flex-start; justify-content:center; padding:18px; overflow-y:auto; -webkit-overflow-scrolling:touch; }
    .wk-modal-box { margin:auto; }
    .wk-modal-box { width:100%; max-width:420px; background:linear-gradient(180deg,#141c1a,#0c1412); border:1px solid rgba(220,190,121,.35); border-radius:20px; overflow:hidden; box-shadow:0 30px 80px rgba(0,0,0,.6); }
    /* Ровная тёмная рамка вокруг видео: одинаковые поля сверху и по бокам (Замир 16.07). */
    .wk-photo-wrap { position:relative; overflow:hidden; border-top-left-radius:20px; border-top-right-radius:20px; background:#0c1412; padding:28px 14px 0; }
    /* Скругление ставим ПРЯМО на медиа: Safari не обрезает video по border-radius родителя. */
    .wk-photo-wrap img { width:100%; aspect-ratio:1; object-fit:cover; display:block; cursor:pointer; border-radius:18px; }
    /* 16.07 (Замир): видео упражнения показываем ЦЕЛИКОМ (во весь рост), с ровной рамкой-полями и скруглением. */
    .wk-photo-wrap video { width:100%; height:auto; max-height:72vh; object-fit:contain; background:#0c1412; display:block; cursor:pointer; border-radius:18px; }
    .wk-ph-btn { position:absolute; width:38px; height:38px; border-radius:50%; border:none; background:rgba(7,13,12,.72); color:#F2ECDD; font-size:19px; cursor:pointer; display:flex; align-items:center; justify-content:center; }
    .wk-ph-x { top:35px; right:34px; }   /* опущен на ~треть высоты кнопки ниже */
    .wk-ph-prev { top:10px; left:10px; }
    .wk-ph-next { top:10px; right:58px; }
    .wk-modal-body { padding:16px 18px 20px; }
    .wk-modal-title { font-family:'Inter',-apple-system,sans-serif; font-size:19px; margin-bottom:6px; }
    .wk-modal-meta { font-size:13px; color:var(--accent2); margin-top:3px; }
    .wk-modal-cue { font-size:13.5px; color:var(--muted); margin-top:10px; line-height:1.55; }
    .wk-weight-row { display:flex; align-items:center; gap:8px; margin-top:14px; flex-wrap:wrap; }
    .wk-weight-row label { font-size:13px; color:var(--muted); }
    .wk-weight-row input { width:80px; padding:9px 10px; border-radius:10px; border:1px solid var(--border); background:var(--surface2); color:var(--text); font-size:14px; }
    .wk-weight-row button { padding:9px 14px; border-radius:10px; border:none; background:linear-gradient(135deg,var(--accent,#DCBE79),var(--accent2,#F2D995)); color:#10131a; font-weight:700; font-size:13px; cursor:pointer; }
    .wk-variant-btn { display:block; width:100%; margin-top:14px; padding:11px; border-radius:12px; border:1px solid rgba(220,190,121,.35); background:rgba(220,190,121,.08); color:var(--accent2,#F2D995); font-weight:600; font-size:13px; cursor:pointer; }
    .wk-ok-btn { display:block; width:100%; margin-top:16px; padding:12px; border-radius:12px; border:none; background:linear-gradient(135deg,var(--accent,#DCBE79),var(--accent2,#F2D995)); color:#10131a; font-weight:700; font-size:14px; cursor:pointer; }
    .wk-help-list { margin:10px 0 0 18px; font-size:13.5px; line-height:1.6; color:var(--text); }
    .wk-help-list li { margin-bottom:8px; }
    /* #4 разминка — карточка */
    .wk-warmup-img { display:flex; align-items:center; justify-content:center; font-size:26px; background:linear-gradient(135deg,rgba(220,190,121,.22),rgba(242,217,149,.06)); }
    .wk-warmup .wk-ex-name { color:var(--accent2,#F2D995); }
    /* #6 иконка замены у названия */
    .wk-modal-title-row { display:flex; align-items:center; gap:10px; }
    .wk-modal-title-row .wk-modal-title { margin-bottom:0; flex:1; }
    .wk-swap-ic { flex-shrink:0; height:32px; padding:0 14px; border-radius:16px; border:1px solid rgba(220,190,121,.35); background:rgba(220,190,121,.08); color:var(--accent2,#F2D995); font-size:13px; font-weight:600; cursor:pointer; display:flex; align-items:center; justify-content:center; white-space:nowrap; }
    .wk-swap-ic:hover { background:rgba(220,190,121,.16); }
    .wk-swap-list { margin-top:12px; max-height:52vh; overflow-y:auto; display:flex; flex-direction:column; gap:8px; }
    .wk-swap-opt { display:flex; align-items:center; gap:10px; padding:8px; border-radius:12px; border:1px solid var(--border); background:var(--surface2); color:var(--text); font-size:14px; cursor:pointer; text-align:left; }
    .wk-swap-opt.cur { border-color:rgba(220,190,121,.5); background:rgba(220,190,121,.1); }
    .wk-swap-opt-img { width:44px; height:44px; border-radius:9px; object-fit:cover; flex-shrink:0; border:1px solid rgba(220,190,121,.15); }
    .wk-swap-opt-name { flex:1; }
    .wk-swap-cur { font-size:11px; color:var(--accent2); }
    /* #5 черепашка */
    .wk-ph-turtle { bottom:10px; left:34px; top:auto; width:auto; min-width:38px; padding:0 12px; border-radius:19px; font-size:15px; white-space:nowrap; }
    .wk-ph-turtle.on { background:linear-gradient(135deg,var(--accent,#DCBE79),var(--accent2,#F2D995)); color:#10131a; }
    /* #1 история веса */
    .wk-hist-btn { display:block; width:100%; margin-top:12px; padding:10px; border-radius:12px; border:1px solid var(--border); background:transparent; color:var(--accent2,#F2D995); font-weight:600; font-size:13px; cursor:pointer; }
    .wk-hist-list { margin-top:12px; max-height:52vh; overflow-y:auto; }
    .wk-hist-row { display:flex; align-items:center; gap:10px; padding:9px 2px; border-bottom:1px solid rgba(220,190,121,.1); font-size:13.5px; }
    .wk-hist-date { color:var(--muted); width:88px; flex-shrink:0; }
    .wk-hist-w { font-weight:700; color:var(--accent2,#F2D995); width:64px; }
    .wk-hist-reps { color:var(--muted); flex:1; text-align:right; }
    .wk-weight-row #wk-w-reps { width:64px; }
    /* #4 окно разминки — почти полноэкранное */
    .wk-warm-modal .wk-modal-box { max-width:560px; width:100%; height:92vh; display:flex; flex-direction:column; }
    .wk-warm-head { display:flex; align-items:center; padding:16px 18px 8px; position:relative; }
    .wk-warm-head .wk-modal-title { margin:0; }
    .wk-warm-x { position:static; margin-left:auto; }
    .wk-warm-note { padding:0 18px 12px; font-size:13px; color:var(--muted); line-height:1.5; }
    .wk-warm-list { flex:1; overflow-y:auto; padding:0 14px 16px; display:flex; flex-direction:column; gap:12px; }
    .wk-warm-vid { width:100%; border-radius:14px; background:#0c1412; aspect-ratio:1; object-fit:cover; }
    .wk-warm-list .wk-warm-empty { text-align:center; padding:20px 0; }
  `;
  document.head.appendChild(css);

  /* ---------------- ИНИЦИАЛИЗАЦИЯ ---------------- */
  function init() { try { render(); } catch (e) { console.warn('workouts init:', e); } }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  window.addEventListener('v2-workouts-refresh', init);
  window._v2RenderWorkouts = init;
  // Хук для cabinet.html: перерисовать секцию восстановленным из облака прогрессом (после restoreProgress).
  window._wkRender = init;
  // Единый источник частоты тренировок для v2-app.js (каскад «не тренируюсь» по табам/экрану «Сегодня»).
  // 0 = «не тренируюсь»; null = профиль ещё не готов (тогда ничего не отключаем — безопасный дефолт).
  window._wkTrainWeekly = function () { try { return getProfile().trainWeekly; } catch (e) { return null; } };
  // счётчик недели монотонный (меняется при «Сделано»); ловим и внешние изменения (др. вкладка)
  setInterval(() => {
    try {
      const el = document.getElementById('workouts-card');
      if (!el) return;
      const w = currentWeek();
      if (el._wkWeek !== undefined && el._wkWeek !== w) render();
      el._wkWeek = w;
    } catch (e) {}
  }, 5000);
})();
