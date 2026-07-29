#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Собирает два самодостаточных HTML-листа: ЗАЛ (101 ролик с миниатюрами) и ДОМ (25 к досъёмке)."""
import base64, html, os, re, sys

BASE = os.path.expanduser('~/Claude/Projects/nutrition-app/_new_videos')
THUMBS = os.path.join(BASE, '_thumbs')
OUT = BASE

# ---------- 1. видео ----------
vids = {}
for f in sorted(os.listdir(BASE)):
    if not f.endswith('.mp4'):
        continue
    m = re.match(r'^(\d+)_(.+)\.mp4$', f)
    if not m:
        print('!! не разобрал имя:', f); continue
    num = int(m.group(1))
    vids[num] = {'num': num, 'file': f, 'name': m.group(2).replace('_', ' ')}

# ---------- 2. группы из _видео_по_группам.txt ----------
raw = open(os.path.join(BASE, '_видео_по_группам.txt'), encoding='utf-8').read()
cur = None
for line in raw.splitlines():
    h = re.match(r'^=== (\w+) \(', line)
    if h:
        cur = h.group(1); continue
    r = re.match(r'^\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$', line)
    if r and cur:
        n = int(r.group(1))
        if n in vids:
            vids[n]['grp'] = cur
            vids[n]['place'] = r.group(3).strip()

# ---------- 3. дораскладка: ролики вне _видео_по_группам.txt + бицепс/трицепс/икры ----------
# 99-101 — доснятые к первой партии, 102-108 — вторая партия (все спина, 29.07.2026)
LATE = {99: 'chest', 100: 'chest', 101: 'chest',
        102: 'back', 103: 'back', 104: 'back', 105: 'back',
        106: 'back', 107: 'back', 108: 'back',
        109: 'triceps'}                       # разгибание на блоке с канатом
for n, g in LATE.items():
    if n in vids and 'grp' not in vids[n]:
        vids[n]['grp'] = g
        vids[n]['place'] = 'зал'

for v in vids.values():
    if v.get('grp') == 'arms':
        v['grp'] = 'triceps' if v['name'].startswith('Разгибание') else 'biceps'
    if v['num'] == 69:                      # «Икры»
        v['grp'] = 'calves'

missing = [v for v in vids.values() if 'grp' not in v]
if missing:
    print('!! без группы:', [(v['num'], v['name']) for v in missing]); sys.exit(1)

GROUPS = [
    ('chest',     'Грудь',    '#e8624a'),
    ('back',      'Спина',    '#3f8fd6'),
    ('shoulders', 'Плечи',    '#d9a13b'),
    ('biceps',    'Бицепс',   '#8b6ed6'),
    ('triceps',   'Трицепс',  '#a8558f'),
    ('legs',      'Ноги',     '#3fa87a'),
    ('calves',    'Икры',     '#6fae4a'),
    ('glutes',    'Ягодицы',  '#c76b3a'),
    ('core',      'Пресс',    '#4fb0a8'),
    ('cardio',    'Кардио',   '#7d8a95'),
]

# ---------- 4. раскладка по колонкам (упаковка в пикселях) ----------
ROW_H, HEAD_H, GAP = 72, 25, 8   # высота строки / шапки группы / зазора между блоками
COL_H = 926                      # рабочая высота колонки: 108 упражнений в экран 1080
SPLITTABLE = 9                   # группы меньше этого не рвём между колонками
MIN_CHUNK = 3                    # огрызок меньше трёх строк не оставляем

by_grp = {k: sorted([v for v in vids.values() if v['grp'] == k], key=lambda v: v['num'])
          for k, _, _ in GROUPS}

columns, col, used = [], [], 0
def flush():
    global col, used
    if col:
        columns.append(col); col, used = [], 0

for key, title, color in GROUPS:
    items, part = by_grp[key], 0
    while items:
        free = COL_H - used - (GAP if col else 0)
        fits = max(0, (free - HEAD_H) // ROW_H)          # сколько строк влезет сюда
        if fits < len(items):                            # целиком не помещается
            if len(items) < SPLITTABLE or fits < MIN_CHUNK:
                flush(); continue                        # мелкую группу — целиком в новую колонку
        take = min(len(items), fits)
        part += 1
        col.append({'title': title, 'color': color, 'total': len(by_grp[key]),
                    'cont': part > 1, 'items': items[:take]})
        used += (GAP if len(col) > 1 else 0) + HEAD_H + take * ROW_H
        items = items[take:]
flush()

# ---------- 5. HTML ----------
def b64(num_file):
    p = os.path.join(THUMBS, num_file.replace('.mp4', '.jpg'))
    with open(p, 'rb') as fh:
        return base64.b64encode(fh.read()).decode('ascii')

total = len(vids)
tail = total % 100
word = ('упражнение' if total % 10 == 1 and tail != 11 else
        'упражнения' if total % 10 in (2, 3, 4) and tail not in (12, 13, 14) else
        'упражнений')
both = sum(1 for v in vids.values() if 'дом' in v.get('place', ''))

cols_html = []
for c in columns:
    blocks = []
    for b in c:
        rows = []
        for v in b['items']:
            tag = '<span class="dom">дом</span>' if 'дом' in v.get('place', '') else ''
            rows.append(
                f'<div class="row" data-file="{html.escape(v["file"])}" '
                f'data-num="{v["num"]}" data-name="{html.escape(v["name"])}">'
                f'<img src="data:image/jpeg;base64,{b64(v["file"])}" alt="">'
                f'<div class="txt"><span class="num">{v["num"]}</span>'
                f'{html.escape(v["name"])}{tag}</div></div>')
        cont = ' <span class="cont">· продолжение</span>' if b['cont'] else \
               f' <span class="cnt">{b["total"]}</span>'
        blocks.append(f'<div class="grp" style="--c:{b["color"]}">'
                      f'<div class="gh">{b["title"]}{cont}</div>{"".join(rows)}</div>')
    cols_html.append(f'<div class="col">{"".join(blocks)}</div>')

DAYS = 5      # отсеков
SLOTS = 8     # упражнений в отсеке
ALTS = 4      # замен на одно упражнение

PANEL_CSS = '''
/* ---------- тренерское окно ---------- */
#tw{position:fixed;left:0;top:0;z-index:200;touch-action:none;
    -webkit-user-select:none;user-select:none;-webkit-touch-callout:none}
#tw .sc{width:780px;transform-origin:top left;transform:scale(var(--s,1));
    background:#0e141a;border:1px solid #33414d;border-radius:12px;overflow:visible;
    box-shadow:0 22px 60px #000b}
#tw .bar{display:flex;align-items:center;gap:9px;padding:8px 11px;background:#1b2530;
    cursor:grab;border-bottom:1px solid #2a3642;border-radius:11px 11px 0 0}
#tw.moving .bar{cursor:grabbing}
#tw .ttl{font-size:14px;font-weight:650;color:#e6edf3}
#tw .cnt{font-size:12px;color:#8b98a5}
#tw .bar .sp{margin-left:auto}
#tw button{font:inherit;font-size:11.5px;color:#c3cdd6;background:#26323d;border:1px solid #38454f;
    border-radius:6px;padding:4px 9px;cursor:pointer}
#tw button:hover{background:#31404c}
#tw .days{display:flex;gap:7px;padding:9px 11px}
#tw .day{flex:1 1 0;min-width:0;border:1px solid #26323d;border-radius:8px;background:#131b22;
    position:relative}
#tw .day.over{border-color:#4fb0a8;background:#16242a}
#tw .day.openday{z-index:7}
#tw .day.full .dh b{color:#6fbf9a}          /* день укомплектован — без opacity,
                                              иначе всплывающее окно тоже полупрозрачное */
#tw .dh{display:flex;font-size:11px;font-weight:700;letter-spacing:.4px;padding:4px 7px;
    background:#202c37;color:#cfd8e0;text-transform:uppercase}
#tw .dh b{margin-left:auto;font-weight:600;color:#8b98a5}
#tw .slots{padding:4px;display:flex;flex-direction:column;gap:4px}
#tw .it{display:flex;align-items:center;gap:6px;height:42px;padding:3px 4px;border-radius:6px;
    background:#1b242c;position:relative;cursor:grab}
#tw .it.empty{background:#151c23;border:1px dashed #2b3742;justify-content:center;cursor:default}
#tw .it.empty i{font-style:normal;font-size:13px;color:#3a4854;font-weight:700}
#tw .it img{width:26px;height:35px;object-fit:cover;border-radius:4px;flex:0 0 auto}
#tw .it .n{font-size:10px;font-weight:700;color:#7f8b96;flex:0 0 auto}
#tw .it .t{font-size:11px;line-height:1.16;color:#dbe4ec;overflow:hidden;overflow-wrap:anywhere;
    display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
#tw .it .x{position:absolute;right:2px;top:2px;width:15px;height:15px;padding:0;line-height:13px;
    text-align:center;font-size:12px;border-radius:4px;opacity:0;background:#3a2226;
    border-color:#5c3138;color:#ffb4b4}
#tw .it:hover .x{opacity:1}
/* плюсик в углу ячейки + окно замен */
#tw .plus{position:absolute;right:2px;bottom:2px;width:16px;height:16px;padding:0;line-height:14px;
    text-align:center;font-size:12px;font-weight:700;border-radius:4px;background:#243542;
    border-color:#35505f;color:#8fd4c4}
#tw .plus.has{background:#1f4038;border-color:#2f6355;color:#8ff0cd;width:auto;padding:0 4px;
    font-size:10px}
#tw .plus.off,#tw .reps.off{opacity:.3;cursor:default;color:#6b7783;border-color:#2b3742;
    background:#1a222a}
#tw .it.open{outline:2px solid #4fb0a8;outline-offset:-1px}
#tw .reps{position:absolute;left:2px;bottom:2px;height:16px;padding:0 4px;line-height:14px;
    font-size:9.5px;font-weight:700;border-radius:4px;background:#1a222a;border-color:#2b3742;
    color:#6b7783;letter-spacing:.2px}
#tw .reps.has{background:#2a2438;border-color:#463a63;color:#c8b6f0}
#tw .repsbox{position:absolute;left:calc(100% + 7px);top:-3px;width:196px;z-index:6;
    background:#191430;border:1px solid #4b3f78;border-radius:8px;box-shadow:0 16px 40px #000b;
    cursor:default}
#tw .day:nth-child(4) .repsbox,#tw .day:nth-child(5) .repsbox{left:auto;right:calc(100% + 7px)}
#tw .repsbox .ah{background:#2a2350;color:#c8b6f0}
#tw .rb{display:flex;gap:7px;padding:8px}
#tw .rb label{flex:1 1 0;display:flex;align-items:center;gap:4px;font-size:12px;
    font-weight:700;color:#c8b6f0}
#tw .rb input{width:100%;min-width:0;font:inherit;font-size:13px;font-weight:600;text-align:center;
    color:#e6edf3;background:#0f0c1e;border:1px solid #4b3f78;border-radius:5px;padding:5px 2px;
    -webkit-user-select:text;user-select:text;touch-action:auto}
#tw .rb input:focus{outline:none;border-color:#8b6ed6;background:#141029}
#tw .rh{padding:0 8px 8px;font-size:9.5px;color:#7a6ba8}
#tw .altbox{position:absolute;left:calc(100% + 7px);top:-3px;width:196px;z-index:6;
    background:#12202a;border:1px solid #3a5a66;border-radius:8px;box-shadow:0 16px 40px #000b;
    cursor:default}
#tw .day:nth-child(4) .altbox,#tw .day:nth-child(5) .altbox{left:auto;right:calc(100% + 7px)}
#tw .altbox.over{border-color:#4fb0a8;background:#16303a}
#tw .ah{display:flex;align-items:center;gap:6px;padding:4px 7px;background:#1c3540;
    border-radius:7px 7px 0 0;font-size:10.5px;font-weight:700;text-transform:uppercase;
    letter-spacing:.4px;color:#a9d8d0}
#tw .ah b{margin-left:auto;font-weight:600;color:#7fa9a2}
#tw .ah button{width:15px;height:15px;padding:0;line-height:13px;font-size:12px;text-align:center}
#tw .asl{padding:4px;display:flex;flex-direction:column;gap:4px}
#tw .as{display:flex;align-items:center;gap:5px;height:36px;padding:2px 4px;border-radius:5px;
    background:#1b2a33;position:relative}
#tw .as.empty{background:#15222a;border:1px dashed #31505c;justify-content:center}
#tw .as.empty i{font-style:normal;font-size:9.5px;color:#4a6a76}
#tw .as img{width:22px;height:29px;object-fit:cover;border-radius:3px;flex:0 0 auto}
#tw .as .n{font-size:9.5px;font-weight:700;color:#7f8b96;flex:0 0 auto}
#tw .as .t{font-size:10px;line-height:1.12;color:#cfd8e0;overflow:hidden;overflow-wrap:anywhere;
    display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
#tw .as .x{position:absolute;right:1px;top:1px;width:14px;height:14px;padding:0;line-height:12px;
    text-align:center;font-size:11px;border-radius:3px;opacity:0;background:#3a2226;
    border-color:#5c3138;color:#ffb4b4}
#tw .as:hover .x{opacity:1}
#tw .foot{display:flex;gap:10px;align-items:center;padding:0 11px 9px;font-size:10.5px;
    color:#6b7783;border-radius:0 0 11px 11px}
#tw .foot .ok{color:#6fbf9a}
#tw .foot .warn{color:#e0a35c}
#tw .rz{position:absolute;right:-5px;bottom:-5px;width:26px;height:26px;cursor:nwse-resize;
    border-radius:0 0 9px 0;background:linear-gradient(135deg,transparent 48%,#5a6b78 48%,#5a6b78 60%,
    transparent 60%,transparent 70%,#5a6b78 70%,#5a6b78 82%,transparent 82%)}
#tw.folded .days,#tw.folded .foot{display:none}
/* призрак при перетаскивании */
.tw-ghost{position:fixed;left:0;top:0;z-index:400;pointer-events:none;display:flex;gap:7px;
    align-items:center;max-width:230px;padding:5px 8px;border-radius:8px;background:#1b242cf2;
    border:1px solid #4b5b68;box-shadow:0 14px 34px #000a;transform:translate(-50%,-50%)}
.tw-ghost img{width:30px;height:40px;object-fit:cover;border-radius:4px}
.tw-ghost span{font-size:11px;color:#e6edf3;line-height:1.15}
body.dragging .row::after,body.dragging .row::before{display:none!important}
.row.picked{outline:2px solid #4fb0a8;outline-offset:-2px;border-radius:6px}
@media print{#tw{display:none}}
'''

PANEL_HTML = f'''
<div id="tw">
  <div class="sc">
    <div class="bar">
      <span class="ttl">Тренировка на неделю</span>
      <span class="cnt" id="twCnt">0 / {DAYS * SLOTS}</span>
      <span class="sp"></span>
      <button data-act="save">Сохранить в файл</button>
      <button data-act="load">Загрузить</button>
      <button data-act="clear">Очистить</button>
      <button data-act="fold" title="свернуть">–</button>
    </div>
    <div class="days" id="twDays"></div>
    <div class="foot">
      <span id="twStore"></span>
      <span>тащи упражнение в день · плюс справа — замены · «п:_ р:_» слева — подходы и разы · угол — размер</span>
    </div>
  </div>
  <div class="rz" id="twRz"></div>
</div>
<input type="file" id="twFile" accept="application/json,.json" style="display:none">
'''

PANEL_JS = '''
(function(){
  var DAYS=__DAYS__, SLOTS=__SLOTS__, ALTS=__ALTS__, BASE=780, KEY='zal101_plan_v1';
  var pop=null;   // какая ячейка раскрыта и чем: {d,i,mode:'alt'|'reps'}

  /* каталог упражнений из самой таблицы: номер -> {name, img} */
  var CAT={};
  document.querySelectorAll('.row[data-num]').forEach(function(r){
    CAT[r.dataset.num]={name:r.dataset.name, img:r.querySelector('img').src};
  });

  /* хранилище: localStorage -> sessionStorage -> память */
  var store=(function(){
    var mode='memory', mem=null;
    function probe(s){ try{ s.setItem('__p','1'); s.removeItem('__p'); return true; }catch(e){ return false; } }
    if(probe(window.localStorage)) mode='local';
    else if(probe(window.sessionStorage)) mode='session';
    return {mode:mode,
      get:function(){ try{
          if(mode==='local') return JSON.parse(localStorage.getItem(KEY)||'null');
          if(mode==='session') return JSON.parse(sessionStorage.getItem(KEY)||'null');
          return mem;
        }catch(e){ return null; } },
      set:function(v){ try{
          var s=JSON.stringify(v);
          if(mode==='local') localStorage.setItem(KEY,s);
          else if(mode==='session') sessionStorage.setItem(KEY,s);
          else mem=v;
        }catch(e){} }};
  })();

  var tw=document.getElementById('tw'), sc=tw.querySelector('.sc'),
      daysEl=document.getElementById('twDays'), cntEl=document.getElementById('twCnt'),
      rzEl=document.getElementById('twRz'), fileEl=document.getElementById('twFile');

  var st=store.get();
  if(!st||!st.days||st.days.length!==DAYS){
    st={x:Math.round(innerWidth/2-BASE/2), y:Math.round(innerHeight/2-170), s:1, fold:false,
        days:[]};
    for(var i=0;i<DAYS;i++) st.days.push([]);
  }

  function norm(x){ return (typeof x==='number') ? {n:x, alt:[], s:'', r:''}
                    : {n:x.n, alt:(x.alt||[]).slice(0,ALTS), s:x.s||'', r:x.r||''}; }
  st.days=st.days.map(function(l){ return (l||[]).map(norm); });

  function save(){ store.set(st); }

  function place(){
    var w=BASE*st.s, h=sc.offsetHeight*st.s;
    st.x=Math.min(Math.max(st.x, -(w-110)), innerWidth-110);
    st.y=Math.min(Math.max(st.y, 0), innerHeight-34);
    tw.style.transform='translate('+st.x+'px,'+st.y+'px)';
    tw.style.width=w+'px'; tw.style.height=h+'px';
    tw.style.setProperty('--s', st.s);
  }

  function render(){
    var total=0, html='';
    for(var d=0; d<DAYS; d++){
      var list=st.days[d]; total+=list.length;
      var rows='';
      for(var i=0;i<SLOTS;i++){
        if(i<list.length){
          var o=list[i], num=o.n, ex=CAT[num]||{name:'№'+num,img:''};
          var open=pop&&pop.d===d&&pop.i===i;
          var rp=(o.s||o.r) ? ('п:'+(o.s||'_')+' р:'+(o.r||'_')) : 'п:_ р:_';
          rows+='<div class="it'+(open?' open':'')+'" data-d="'+d+'" data-i="'+i+'" data-num="'+num+'">'
              + '<img src="'+ex.img+'" alt="">'
              + '<span class="n">'+num+'</span><span class="t">'+ex.name+'</span>'
              + '<button class="x" data-act="del">×</button>'
              + '<button class="plus'+(o.alt.length?' has':'')+'" data-act="alt" '
              + 'title="замены на выбор">'+(o.alt.length?'+'+o.alt.length:'+')+'</button>'
              + '<button class="reps'+((o.s||o.r)?' has':'')+'" data-act="reps" '
              + 'title="подходы и разы">'+rp+'</button>'
              + (open ? (pop.mode==='reps' ? repsbox(d,i,o) : altbox(d,i,o)) : '')
              + '</div>';
        } else {
          rows+='<div class="it empty"><i>'+(i+1)+'</i>'
              + '<button class="reps off" title="сначала перетащи сюда упражнение">п:_ р:_</button>'
              + '<button class="plus off" title="сначала перетащи сюда упражнение">+</button></div>';
        }
      }
      html+='<div class="day'+(list.length>=SLOTS?' full':'')
          + (pop&&pop.d===d?' openday':'')+'" data-d="'+d+'">'
          + '<div class="dh">День '+(d+1)+' <b>'+list.length+'/'+SLOTS+'</b></div>'
          + '<div class="slots">'+rows+'</div></div>';
    }
    daysEl.innerHTML=html;
    cntEl.textContent=total+' / '+(DAYS*SLOTS);
    tw.classList.toggle('folded', !!st.fold);
    place();
  }

  function altbox(d,i,o){
    var s='';
    for(var k=0;k<ALTS;k++){
      if(k<o.alt.length){
        var e=CAT[o.alt[k]]||{name:'№'+o.alt[k],img:''};
        s+='<div class="as"><img src="'+e.img+'" alt="">'
         + '<span class="n">'+o.alt[k]+'</span><span class="t">'+e.name+'</span>'
         + '<button class="x" data-act="altdel" data-k="'+k+'">×</button></div>';
      } else {
        s+='<div class="as empty"><i>перетащи сюда</i></div>';
      }
    }
    return '<div class="altbox" data-d="'+d+'" data-i="'+i+'">'
         + '<div class="ah">Замены <b>'+o.alt.length+'/'+ALTS+'</b>'
         + '<button data-act="altclose">×</button></div>'
         + '<div class="asl">'+s+'</div></div>';
  }

  function esc(v){ return String(v).replace(/"/g,'&quot;'); }

  function repsbox(d,i,o){
    return '<div class="repsbox" data-d="'+d+'" data-i="'+i+'">'
         + '<div class="ah">Подходы и разы<button data-act="repsclose">×</button></div>'
         + '<div class="rb">'
         + '<label>п:<input type="text" maxlength="5" data-f="s" value="'+esc(o.s)+'"></label>'
         + '<label>р:<input type="text" maxlength="5" data-f="r" value="'+esc(o.r)+'"></label>'
         + '</div>'
         + '<div class="rh">п — подходы, р — разы. Можно диапазон: 8-12</div></div>';
  }

  /* ---------- перетаскивание упражнений ---------- */
  var drag=null, hold=null;

  function ghost(num){
    var ex=CAT[num]||{name:'№'+num,img:''};
    var g=document.createElement('div'); g.className='tw-ghost';
    g.innerHTML='<img src="'+ex.img+'"><span>'+num+' · '+ex.name+'</span>';
    document.body.appendChild(g); return g;
  }

  function begin(num, src, x, y){
    drag={num:num, src:src, from:src&&src.classList.contains('it')?
          {d:+src.dataset.d, i:+src.dataset.i}:null, g:ghost(num)};
    document.body.classList.add('dragging');
    if(src&&src.classList.contains('row')) src.classList.add('picked');
    move(x,y);
  }

  function move(x,y){
    if(!drag) return;
    drag.g.style.transform='translate('+x+'px,'+y+'px) translate(-50%,-50%)';
    var el=document.elementFromPoint(x,y);
    var box=el&&el.closest?el.closest('.altbox'):null;
    var day=(!box&&el&&el.closest)?el.closest('.day'):null;
    daysEl.querySelectorAll('.day').forEach(function(n){ n.classList.toggle('over', n===day); });
    var ab=daysEl.querySelector('.altbox'); if(ab) ab.classList.toggle('over', ab===box);
    drag.day=day; drag.box=box;
  }

  function finish(){
    if(!drag) return;
    if(drag.box){                                     // бросили в окно замен
      var bd=+drag.box.dataset.d, bi=+drag.box.dataset.i, o=st.days[bd]&&st.days[bd][bi];
      if(o && o.alt.length<ALTS && o.n!==drag.num && o.alt.indexOf(drag.num)<0) o.alt.push(drag.num);
    } else if(drag.day){                              // бросили в день
      var d=+drag.day.dataset.d;
      if(drag.from){
        var item=st.days[drag.from.d][drag.from.i];
        if(drag.from.d!==d && st.days[d].length<SLOTS){
          st.days[drag.from.d].splice(drag.from.i,1);
          st.days[d].push(item);
          pop=null;
        }
      } else if(st.days[d].length<SLOTS){
        st.days[d].push({n:drag.num, alt:[], s:'', r:''});
      }
    }
    cancel(); save(); render();
  }

  function cancel(){
    if(hold){ clearTimeout(hold.t); hold=null; }
    if(!drag) return;
    drag.g.remove();
    if(drag.src) drag.src.classList.remove('picked');
    daysEl.querySelectorAll('.day').forEach(function(n){ n.classList.remove('over'); });
    document.body.classList.remove('dragging');
    drag=null;
  }

  document.addEventListener('pointerdown', function(e){
    if(e.button) return;
    if(e.target.closest('.altbox, .repsbox')) return;   // внутри окошек не тащим ячейку
    var src=e.target.closest('.row[data-num], #tw .it[data-num]');
    if(!src) return;
    if(e.target.closest('[data-act="del"]')) return;
    var num=+src.dataset.num;
    if(e.pointerType==='mouse'){                       // мышь — тянем сразу
      hold={num:num, src:src, x:e.clientX, y:e.clientY, ready:true};
    } else {                                           // палец — после удержания
      hold={num:num, src:src, x:e.clientX, y:e.clientY, ready:false};
      hold.t=setTimeout(function(){
        if(hold){ hold.ready=true; begin(hold.num, hold.src, hold.x, hold.y); }
      }, 260);
    }
  }, true);

  document.addEventListener('pointermove', function(e){
    if(drag){ e.preventDefault(); move(e.clientX,e.clientY); return; }
    if(!hold) return;
    var far=Math.abs(e.clientX-hold.x)>8 || Math.abs(e.clientY-hold.y)>8;
    if(!far) return;
    if(hold.ready) begin(hold.num, hold.src, e.clientX, e.clientY);   // мышь
    else { clearTimeout(hold.t); hold=null; }                          // палец повёл — это скролл
  }, {passive:false});

  document.addEventListener('pointerup', function(){ if(drag) finish(); else if(hold){ clearTimeout(hold.t); hold=null; } });
  document.addEventListener('pointercancel', cancel);

  /* ---------- перемещение и размер окна ---------- */
  function grip(el, onMove){
    el.addEventListener('pointerdown', function(e){
      if(e.target.closest('button')) return;
      e.preventDefault(); el.setPointerCapture(e.pointerId);
      var s={x:e.clientX, y:e.clientY, px:st.x, py:st.y, ps:st.s};
      tw.classList.add('moving');
      function mv(ev){ onMove(ev.clientX-s.x, ev.clientY-s.y, s); place(); }
      function up(ev){ el.releasePointerCapture(e.pointerId);
        el.removeEventListener('pointermove',mv); el.removeEventListener('pointerup',up);
        tw.classList.remove('moving'); save(); }
      el.addEventListener('pointermove',mv); el.addEventListener('pointerup',up);
    });
  }
  grip(tw.querySelector('.bar'), function(dx,dy,s){ st.x=s.px+dx; st.y=s.py+dy; });
  grip(rzEl, function(dx,dy,s){
    st.s=Math.min(1.8, Math.max(0.45, s.ps*(BASE*s.ps+dx)/(BASE*s.ps)));
  });

  /* ---------- кнопки ---------- */
  document.addEventListener('click', function(e){
    var b=e.target.closest('[data-act]'); if(!b) return;
    var a=b.dataset.act;
    if(a==='del'){ var it=b.closest('.it'); st.days[+it.dataset.d].splice(+it.dataset.i,1);
                   pop=null; save(); render(); }
    if(a==='alt'||a==='reps'){
      var t=b.closest('.it'), d=+t.dataset.d, i=+t.dataset.i, m=(a==='reps')?'reps':'alt';
      pop=(pop&&pop.d===d&&pop.i===i&&pop.mode===m)?null:{d:d,i:i,mode:m};
      render();
      if(pop&&pop.mode==='reps'){ var inp=daysEl.querySelector('.repsbox input'); if(inp) inp.focus(); }
    }
    if(a==='altclose'||a==='repsclose'){ pop=null; render(); }
    if(a==='altdel'){ var bx=b.closest('.altbox');
                      st.days[+bx.dataset.d][+bx.dataset.i].alt.splice(+b.dataset.k,1);
                      save(); render(); }
    if(a==='fold'){ st.fold=!st.fold; b.textContent=st.fold?'+':'–'; save(); render(); }
    if(a==='clear'){ if(confirm('Очистить всю неделю?')){ st.days=[]; for(var i=0;i<DAYS;i++) st.days.push([]); save(); render(); } }
    if(a==='save'){
      var blob=new Blob([JSON.stringify(st,null,1)],{type:'application/json'});
      var u=URL.createObjectURL(blob), a2=document.createElement('a');
      a2.href=u; a2.download='тренировка.json'; a2.click(); setTimeout(function(){URL.revokeObjectURL(u);},2000);
    }
    if(a==='load') fileEl.click();
  });

  daysEl.addEventListener('input', function(e){
    var inp=e.target.closest('.repsbox input'); if(!inp) return;
    var bx=inp.closest('.repsbox'), d=+bx.dataset.d, i=+bx.dataset.i, o=st.days[d]&&st.days[d][i];
    if(!o) return;
    inp.value=inp.value.replace(/[^0-9-]/g,'').slice(0,5);
    o[inp.dataset.f]=inp.value;
    save();
    var badge=daysEl.querySelector('.it[data-d="'+d+'"][data-i="'+i+'"] .reps');
    if(badge){
      badge.textContent=(o.s||o.r)?('п:'+(o.s||'_')+' р:'+(o.r||'_')):'п:_ р:_';
      badge.classList.toggle('has', !!(o.s||o.r));
    }
  });

  fileEl.addEventListener('change', function(){
    var f=fileEl.files[0]; if(!f) return;
    var r=new FileReader();
    r.onload=function(){ try{
        var v=JSON.parse(r.result);
        if(v&&v.days&&v.days.length===DAYS){ st=v; save(); render(); }
        else alert('Файл не похож на сохранённую тренировку.');
      }catch(err){ alert('Не смог прочитать файл.'); } };
    r.readAsText(f); fileEl.value='';
  });

  var sEl=document.getElementById('twStore');
  if(store.mode==='local') sEl.innerHTML='<span class="ok">автосохранение включено</span>';
  else sEl.innerHTML='<span class="warn">браузер запретил автосохранение — жми «Сохранить в файл»</span>';

  document.addEventListener('pointerdown', function(e){
    // клик по пустому месту закрывает окно замен, но тащить в него из таблицы можно
    if(pop && !e.target.closest('#tw') && !e.target.closest('.row[data-num]')){ pop=null; render(); }
  });

  addEventListener('resize', place);
  render();
})();
'''.replace('__DAYS__', str(DAYS)).replace('__SLOTS__', str(SLOTS)).replace('__ALTS__', str(ALTS))

gym = f'''<meta charset="utf-8">
<title>Зал — {total} {word}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#11161a;color:#e6edf3;font:400 13px/1.3 -apple-system,"Segoe UI",Roboto,sans-serif;
     padding:10px 12px 12px;overflow-x:auto}}
header{{display:flex;align-items:baseline;gap:14px;margin-bottom:9px}}
h1{{font-size:16px;font-weight:650;letter-spacing:.2px}}
header .sub{{font-size:11.5px;color:#8b98a5}}
header .hint{{margin-left:auto;font-size:11px;color:#6b7783}}
.sheet{{display:flex;gap:9px;align-items:flex-start}}
.col{{flex:1 1 0;min-width:0;display:flex;flex-direction:column;gap:7px}}
.grp{{border:1px solid #232c34;border-radius:7px;background:#161d23;overflow:hidden}}
.gh{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;
    padding:4px 7px;background:var(--c);color:#0d1114}}
.gh .cnt{{opacity:.65;font-weight:600}}
.gh .cont{{opacity:.7;font-weight:500;text-transform:none;letter-spacing:0}}
.row{{display:flex;gap:6px;padding:3px 5px;border-top:1px solid #1e262d;align-items:center;
     cursor:grab;position:relative;-webkit-user-select:none;user-select:none;
     -webkit-touch-callout:none}}
.row img{{-webkit-user-drag:none;pointer-events:none}}
.row:first-of-type{{border-top:none}}
.row:hover{{background:#1e262d}}
.row img{{width:48px;height:64px;object-fit:cover;border-radius:4px;flex:0 0 auto;background:#0b0f12}}
.txt{{font-size:11.5px;line-height:1.25;color:#cfd8e0;min-width:0;word-break:break-word}}
.num{{display:inline-block;min-width:20px;color:#66727d;font-size:10.5px;font-weight:600}}
.dom{{display:inline-block;margin-left:4px;padding:0 4px;border-radius:3px;background:#2b3a44;
     color:#8fd4c4;font-size:9px;font-weight:700;vertical-align:1px}}
/* увеличение по наведению */
.row::after{{content:"";position:fixed;left:50%;top:50%;transform:translate(-50%,-50%) scale(.96);
    width:384px;height:683px;max-height:88vh;background:var(--bg) center/cover no-repeat;
    border-radius:12px;box-shadow:0 24px 70px #000c,0 0 0 1px #ffffff22;
    opacity:0;pointer-events:none;transition:opacity .12s,transform .12s;z-index:50}}
.row:hover::after{{opacity:1;transform:translate(-50%,-50%) scale(1)}}
.row::before{{content:attr(data-file);position:fixed;left:50%;bottom:4vh;transform:translateX(-50%);
    background:#0d1114ee;border:1px solid #2a343d;border-radius:6px;padding:5px 10px;
    font-size:12px;color:#cfd8e0;white-space:nowrap;opacity:0;pointer-events:none;
    transition:opacity .12s;z-index:51}}
.row:hover::before{{opacity:1}}
@media print{{body{{background:#fff;color:#000}}.row::after,.row::before{{display:none}}}}
{PANEL_CSS}
</style>
<header>
  <h1>ЗАЛ — {total} {word}</h1>
  <span class="sub">снято, миниатюры — кадры из роликов · {both} помечены «дом» (можно и дома с гантелями)</span>
  <span class="hint">наведи — фото крупно · зажми и тащи — в тренировку</span>
</header>
<div class="sheet">{"".join(cols_html)}</div>
{PANEL_HTML}
<script>
document.querySelectorAll('.row').forEach(r=>{{
  const src=r.querySelector('img').src;
  r.style.setProperty('--bg','url('+src+')');
}});
</script>
<script>{PANEL_JS}</script>'''

gym_name = f'ЗАЛ_{total}.html'          # имя следует за числом упражнений
open(os.path.join(OUT, gym_name), 'w', encoding='utf-8').write(gym)

# ---------- 6. домашний лист ----------
HOME = [
    ('Грудь', ['Отжимания', 'Отжимания с колен', 'Узкие отжимания']),
    ('Спина', ['Тяга резинки к поясу', 'Тяга рюкзака в наклоне', 'Разведение резинки', 'Супермен']),
    ('Плечи', ['Отжимания уголком', 'Жим резинки над головой', 'Махи в стороны с бутылками']),
    ('Руки', ['Обратные отжимания от стула']),
    ('Пресс', ['Планка', 'Боковая планка', 'Подъёмы ног лёжа', 'Птица-собака']),
    ('Ноги', ['Стульчик у стены', 'Подъёмы на носки']),
    ('Ягодицы', ['Ягодичный мост', 'Сумо-присед']),
    ('Кардио', ['Скалолаз', 'Бёрпи', 'Ходьба на месте с подъёмом колен', 'Приставные шаги']),
    ('Пересъём бодивейтом<br><span class="note">сейчас сняты с гантелями</span>',
     ['Болгарские выпады', 'Выпады']),
]
COLORS = ['#e8624a', '#3f8fd6', '#d9a13b', '#8b6ed6', '#4fb0a8',
          '#3fa87a', '#c76b3a', '#7d8a95', '#a8558f']
n_home = sum(len(x[1]) for x in HOME)
cards = []
for (t, items), c in zip(HOME, COLORS):
    li = ''.join(f'<li><span>{i+1}</span>{html.escape(x)}</li>' for i, x in enumerate(items))
    cards.append(f'<div class="grp" style="--c:{c}"><div class="gh">{t}'
                 f'<b>{len(items)}</b></div><ol>{li}</ol></div>')

home = f'''<meta charset="utf-8">
<title>Доснять для дома — {n_home} видео</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#11161a;color:#e6edf3;font:400 15px/1.35 -apple-system,"Segoe UI",Roboto,sans-serif;
     padding:30px 34px;min-height:100vh}}
header{{display:flex;align-items:baseline;gap:18px;margin-bottom:24px}}
h1{{font-size:29px;font-weight:650}}
.sub{{font-size:15px;color:#8b98a5}}
.sheet{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px;
       align-items:start}}
.grp{{border:1px solid #232c34;border-radius:11px;background:#161d23;overflow:hidden}}
.gh{{font-size:15px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;
    padding:11px 16px;background:var(--c);color:#0d1114;display:flex;align-items:center;gap:8px}}
.gh b{{margin-left:auto;font-size:14px;opacity:.7}}
.gh .note{{display:block;font-size:11px;font-weight:600;text-transform:none;letter-spacing:0;opacity:.8}}
ol{{list-style:none;padding:7px 0}}
li{{display:flex;gap:11px;padding:8px 16px;font-size:17px;color:#dbe4ec}}
li span{{color:#66727d;font-size:13px;min-width:16px;padding-top:3px}}
@media print{{body{{background:#fff;color:#000}}}}
</style>
<header>
  <h1>ДОСНЯТЬ ДЛЯ ДОМА — {n_home} видео</h1>
  <span class="sub">миниатюр нет — ролики ещё не сняты</span>
</header>
<div class="sheet">{"".join(cards)}</div>'''

open(os.path.join(OUT, 'ДОМ_доснять_25.html'), 'w', encoding='utf-8').write(home)

print('ЗАЛ:', total, 'упражнений,', len(columns), 'колонок')
for k, t, _ in GROUPS:
    print(f'  {t}: {sum(1 for v in vids.values() if v["grp"] == k)}')
print('ДОМ:', n_home)
for f in (gym_name, 'ДОМ_доснять_25.html'):
    print(f, round(os.path.getsize(os.path.join(OUT, f)) / 1e6, 2), 'МБ')
