#!/usr/bin/env bash
# Сброс профиля клиента через терминал (curl → CORS не мешает, работает всегда).
# Чистит профиль (вес/рост/цель) + прогресс дней/тренировок. Оплату (доступ) НЕ трогает.
#
# Запуск:
#   bash сброс_клиента.sh почта@клиента.ру
#   bash сброс_клиента.sh                      # спросит почту интерактивно
#
# ADMIN_KEY можно задать заранее в окружении (export ADMIN_KEY=...), иначе скрипт спросит.
set -e

API="https://d5dnqp0e3vem5rs3i0iq.kocrdvxt.apigw.yandexcloud.net"

EMAIL="${1:-}"
if [ -z "$EMAIL" ]; then read -r -p "Почта клиента: " EMAIL; fi
if [ -z "$EMAIL" ]; then echo "❌ Почта не указана."; exit 1; fi

if [ -z "$ADMIN_KEY" ]; then read -r -s -p "Админ-ключ: " ADMIN_KEY; echo; fi
if [ -z "$ADMIN_KEY" ]; then echo "❌ Ключ не указан."; exit 1; fi

echo "▶ Сбрасываю профиль: $EMAIL …"
RESP=$(curl -s -X POST "$API/admin-reset" \
  -H "Content-Type: application/json" \
  -d "{\"admin_key\":\"$ADMIN_KEY\",\"email\":\"$EMAIL\"}")

echo "   Ответ сервера: $RESP"
case "$RESP" in
  *'"ok":true'*)     echo "✅ Готово. Профиль и прогресс обнулены. Оплата/доступ сохранены." ;;
  *forbidden*)       echo "❌ Неверный админ-ключ (или лишние пробелы)." ;;
  *no_email*)        echo "❌ Почта не распознана — проверь адрес." ;;
  *'unknown route'*) echo "❌ Путь /admin-reset не заведён в API-шлюзе." ;;
  *)                 echo "⚠ Непонятный ответ — смотри строку выше." ;;
esac
echo ""
echo "Клиент при следующем входе заполнит данные заново. На его устройстве"
echo "старое состояние сотрётся при загрузке (сервер = источник правды)."
