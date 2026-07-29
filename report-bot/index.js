/**
 * Ежедневный отчёт в Telegram-группу.
 * Отдельная Yandex Cloud Function (Node 18+), запускается ТАЙМЕРОМ (cron).
 * Читает YDB `subscriptions` и шлёт сводку ботом в группу.
 *
 * ENV (задать в настройках функции):
 *   YDB_ENDPOINT  — как у auth-бэкенда (grpcs://ydb.serverless.yandexcloud.net:2135)
 *   YDB_DATABASE  — как у auth-бэкенда
 *   BOT_TOKEN     — токен @Roman_Pitanie_bot
 *   CHAT_ID       — -1003911790590 (группа «Анна, Роман и Zamir»)
 * Сервисный аккаунт функции — ТОТ ЖЕ, что у auth-бэкенда (нужен доступ к YDB).
 * Entrypoint: index.handler
 */
const { Driver, getCredentialsFromEnv, TypedValues, TypedData } = require('ydb-sdk');

const YDB_ENDPOINT = process.env.YDB_ENDPOINT || 'grpcs://ydb.serverless.yandexcloud.net:2135';
const YDB_DATABASE = process.env.YDB_DATABASE;
const BOT_TOKEN    = process.env.BOT_TOKEN;
const CHAT_ID      = process.env.CHAT_ID;

let _driver = null;
async function getDriver() {
  if (_driver) return _driver;
  _driver = new Driver({ endpoint: YDB_ENDPOINT, database: YDB_DATABASE, authService: getCredentialsFromEnv() });
  if (!await _driver.ready(10000)) throw new Error('YDB driver not ready');
  return _driver;
}

// Границы "вчера" по Алматы (UTC+5), возвращаем как UTC-Date для параметров Timestamp.
const TZ = 5 * 3600 * 1000; // Алматы UTC+5
function yesterdayRange() {
  const tzNow = new Date(Date.now() + TZ);
  const todayStartUtc = new Date(Date.UTC(tzNow.getUTCFullYear(), tzNow.getUTCMonth(), tzNow.getUTCDate()) - TZ);
  const yStartUtc = new Date(todayStartUtc.getTime() - 24 * 3600 * 1000);
  return { yStartUtc, yEndUtc: todayStartUtc };
}

async function queryCounts() {
  const driver = await getDriver();
  const { yStartUtc, yEndUtc } = yesterdayRange();
  const soonEnd = new Date(Date.now() + 3 * 24 * 3600 * 1000); // истекают в ближайшие 3 дня
  let active = 0, newY = 0, renewY = 0, expSoon = 0, total = 0, paidToday = 0;
  await driver.tableClient.withSession(async (session) => {
    // periods: 1 (или NULL у старых) = первая оплата, >=2 = продление. paid_at = дата ПОСЛЕДНЕЙ оплаты
    // (UPSERT перезаписывает её при каждом платеже — точного посуточного лога платежей мы не храним).
    const q = `
      DECLARE $yStart AS Timestamp; DECLARE $yEnd AS Timestamp; DECLARE $soon AS Timestamp;
      SELECT COUNT(*) AS c FROM subscriptions WHERE expires_at > CurrentUtcTimestamp();
      SELECT COUNT(*) AS c FROM subscriptions WHERE paid_at >= $yStart AND paid_at < $yEnd AND (periods IS NULL OR periods <= 1);
      SELECT COUNT(*) AS c FROM subscriptions WHERE paid_at >= $yStart AND paid_at < $yEnd AND periods >= 2;
      SELECT COUNT(*) AS c FROM subscriptions WHERE expires_at > CurrentUtcTimestamp() AND expires_at < $soon;
      SELECT COUNT(*) AS c FROM subscriptions;
      SELECT COUNT(*) AS c FROM subscriptions WHERE paid_at >= $yEnd;`;
    const { resultSets } = await session.executeQuery(q, {
      '$yStart': TypedValues.timestamp(yStartUtc),
      '$yEnd':   TypedValues.timestamp(yEndUtc),
      '$soon':   TypedValues.timestamp(soonEnd),
    });
    const g = (i) => Number(TypedData.createNativeObjects(resultSets[i])[0].c);
    active = g(0); newY = g(1); renewY = g(2); expSoon = g(3); total = g(4); paidToday = g(5);
  });
  return { active, newY, renewY, paidYesterday: newY + renewY, expSoon, total, paidToday };
}

async function sendTelegram(text) {
  const r = await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: CHAT_ID, text, parse_mode: 'HTML' }),
  });
  return r.json();
}

exports.handler = async () => {
  let stage = 'start';
  try {
    stage = 'ydb';                       // подключение к базе + запросы
    const c = await queryCounts();
    stage = 'telegram';                  // отправка в группу
    const d = new Date(Date.now() + TZ);
    const dateStr = `${String(d.getUTCDate()).padStart(2, '0')}.${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
    const text =
      `📊 <b>Отчёт по приложению — ${dateStr}</b>\n\n` +
      `💳 Оплат за вчера: <b>${c.paidYesterday}</b>\n` +
      `   🆕 новых: <b>${c.newY}</b> · 🔄 продлений: <b>${c.renewY}</b>\n` +
      `💰 Оплат сегодня: <b>${c.paidToday}</b>\n` +
      `✅ Активных подписок: <b>${c.active}</b>\n` +
      `⏳ Истекают за 3 дня: <b>${c.expSoon}</b>\n` +
      `👥 Всего в базе: <b>${c.total}</b>`;
    const res = await sendTelegram(text);
    return { statusCode: 200, body: JSON.stringify({ ok: res.ok, tg: res, counts: c }) };
  } catch (e) {
    // Диагностика: на каком этапе упало и что за сетевая причина (ENOTFOUND/ETIMEDOUT/ECONNREFUSED…)
    const cause = e && e.cause ? (e.cause.code || e.cause.errno || e.cause.message) : '';
    const info = `stage=${stage} | ${e && e.name}: ${e && e.message}${cause ? ' | cause=' + cause : ''}`;
    console.error('REPORT_FAIL', info, e && e.stack);
    return { statusCode: 500, body: info };
  }
};
