#!/usr/bin/env python3
# Выгрузка отзывов «Нашли ошибку?» в читаемый текст.
#
# ШАГ 1 — выгрузить активные (неразобранные) и запомнить их:
#   ADMIN_KEY='ключ' python3 pull_feedback.py > отзывы.txt
#   (показывает активные и записывает их id в .feedback_pulled.json)
#
# ШАГ 2 — после того как ПОЧИНИЛИ по отзывы.txt, пометить разобранными:
#   ADMIN_KEY='ключ' python3 pull_feedback.py --archive
#   (архивирует РОВНО те id из .feedback_pulled.json, что были в отзывы.txt.
#    Новые отзывы, пришедшие пока чинили, НЕ трогает — они останутся активными.)
#
# Посмотреть архив:
#   ADMIN_KEY='ключ' python3 pull_feedback.py --archived
#
# ADMIN_KEY — тот же, что у /admin-reset (в переменных окружения функции).

import os, sys, json, urllib.request
from datetime import datetime

BASE = 'https://d5dnqp0e3vem5rs3i0iq.kocrdvxt.apigw.yandexcloud.net'
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.feedback_pulled.json')

key = os.environ.get('ADMIN_KEY', '').strip()
if not key:
    raise SystemExit("Задайте ADMIN_KEY:  ADMIN_KEY='ваш_ключ' python3 pull_feedback.py")

show_archived = '--archived' in sys.argv
do_archive    = '--archive' in sys.argv

def local_time(iso):
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone().strftime('%d.%m.%Y %H:%M')
    except Exception:
        return iso

def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def print_items(items, title):
    print('=== {}: {} шт ==='.format(title, len(items)))
    for i, it in enumerate(items, 1):
        print('\n--- #{} | {} | {} ---'.format(i, local_time(it.get('created_at', '?')), it.get('email') or 'аноним'))
        print('ТЕКСТ: ' + (it.get('text') or '').strip())
        diag = (it.get('diag') or '').strip()
        if diag:
            print('ДИАГНОСТИКА:\n' + diag)

# --- РЕЖИМ АРХИВАЦИИ: берём id из отзывы.txt (сохранённые при выгрузке), не делаем свежий pull ---
if do_archive:
    if not os.path.exists(STATE):
        raise SystemExit('Нет .feedback_pulled.json — сначала выгрузи активные:\n'
                         "  ADMIN_KEY='ключ' python3 pull_feedback.py > отзывы.txt")
    saved = json.load(open(STATE, encoding='utf-8'))
    ids = saved.get('ids', [])
    if not ids:
        raise SystemExit('В .feedback_pulled.json нет id — нечего архивировать.')
    res = post('/feedback-done', {'admin_key': key, 'ids': ids})
    print('>>> В архив помечено разобранными: {} шт (ровно те, что были в отзывы.txt).'.format(res.get('archived', 0)))
    print('    Отзывы, пришедшие после выгрузки, остались активными — увидишь их следующей выгрузкой.')
    # состояние отработано — чистим, чтобы повторный --archive не сработал случайно
    try:
        os.remove(STATE)
    except OSError:
        pass
    sys.exit(0)

# --- РЕЖИМ ПРОСМОТРА (активные или архив) ---
data = post('/feedback-list', {'admin_key': key, 'archived': show_archived})
if not data.get('ok'):
    raise SystemExit('Ошибка: ' + str(data))

items = data.get('items', [])
print_items(items, 'АРХИВ (разобранные)' if show_archived else 'АКТИВНЫЕ отзывы')

# При обычной выгрузке активных — запоминаем показанные id для последующего --archive.
if not show_archived:
    ids = [it.get('id') for it in items if it.get('id')]
    json.dump({'ids': ids, 'pulled_at': datetime.now().isoformat()},
              open(STATE, 'w', encoding='utf-8'), ensure_ascii=False)
