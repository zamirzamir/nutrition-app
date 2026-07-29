/**
 * Функция-роутер авторизации и оплаты — ВЕРСИЯ EMAIL (без SMS/Telegram).
 * Yandex Cloud Function (Node.js), YDB serverless.
 *
 * НОВАЯ СХЕМА ВХОДА (email + код):
 *   КОД ДОСТУПА = номер заказа Продамуса (order_num). Приходит клиенту в письме.
 *   Клиент вводит email + номер заказа → впускаем. Никаких SMS/Telegram/OTP.
 *
 * Маршруты (event.path через API Gateway):
 *   POST /prodamus-webhook   — приём оплаты: сохраняем подписку по EMAIL (+order_num, +срок 31д)
 *   POST /login-verify       — вход: { email, code } где code = номер заказа → ставим куку
 *   GET  /check              — гейт: валидна ли кука + активна ли подписка
 *   POST /profile-get|save   — профиль клиента (ключ — email)
 *   POST /progress-get|save  — прогресс клиента (ключ — email)
 *   POST /admin-reset        — сброс профиля (по email)
 *
 * Переменные окружения:
 *   SESSION_SECRET   — секрет подписи куки
 *   PRODAMUS_SECRET  — секрет формы Продамуса (проверка подписи webhook)
 *   ADMIN_KEY        — ключ админ-сброса
 *   YDB_DATABASE, YDB_ENDPOINT — доступ к базе
 */

const crypto = require('crypto');

let _ydb = null;
function ydb() { if (!_ydb) _ydb = require('ydb-sdk'); return _ydb; }

// ---- Конфиг ----
const YDB_ENDPOINT   = process.env.YDB_ENDPOINT || 'grpcs://ydb.serverless.yandexcloud.net:2135';
const YDB_DATABASE   = process.env.YDB_DATABASE;
const SESSION_SECRET = process.env.SESSION_SECRET || 'change-me';
const PRODAMUS_SECRET= process.env.PRODAMUS_SECRET || '';
const ADMIN_KEY      = process.env.ADMIN_KEY || '';
const ACCESS_DAYS    = 31;   // срок доступа после оплаты

// последний webhook — для отладки имени поля
let _lastWebhook = null;

// ---- Драйвер YDB ----
let _driver = null;
async function getDriver() {
  if (_driver) return _driver;
  const { Driver, getCredentialsFromEnv } = ydb();
  _driver = new Driver({ endpoint: YDB_ENDPOINT, database: YDB_DATABASE, authService: getCredentialsFromEnv() });
  const ready = await _driver.ready(10000);
  if (!ready) throw new Error('YDB driver not ready');
  return _driver;
}

// ===================== УТИЛИТЫ =====================

// email приводим к нижнему регистру и тримим (ключ должен совпадать всегда)
function normEmail(raw) { return String(raw || '').trim().toLowerCase(); }
// номер заказа: только цифры/буквы, без пробелов и символа №
function normCode(raw)  { return String(raw || '').replace(/[№\s]/g, '').trim(); }

// Подписанная кука: email.expires.HMAC
function makeCookie(email, expiresMs) {
  const payload = `${email}.${expiresMs}`;
  const sig = crypto.createHmac('sha256', SESSION_SECRET).update(payload).digest('hex');
  return `${payload}.${sig}`;
}
function verifyCookie(cookie) {
  if (!cookie) return null;
  // email может содержать точки — поэтому режем по ПОСЛЕДНИМ двум точкам
  const i2 = cookie.lastIndexOf('.');
  const i1 = cookie.lastIndexOf('.', i2 - 1);
  if (i1 < 0 || i2 < 0) return null;
  const email = cookie.slice(0, i1);
  const expires = cookie.slice(i1 + 1, i2);
  const sig = cookie.slice(i2 + 1);
  const expect = crypto.createHmac('sha256', SESSION_SECRET).update(`${email}.${expires}`).digest('hex');
  if (sig !== expect) return null;
  if (Date.now() > Number(expires)) return null;
  return { email, expires: Number(expires) };
}
function readCookie(headers, name) {
  const raw = headers?.cookie || headers?.Cookie || '';
  const m = raw.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]+)'));
  return m ? decodeURIComponent(m[1]) : null;
}
function readSession(headers) {
  const fromCookie = readCookie(headers, 'nutri_session');
  if (fromCookie) return fromCookie;
  const auth = headers?.authorization || headers?.Authorization || '';
  const m = auth.match(/^Bearer\s+(.+)$/i);
  return m ? m[1] : null;
}
function authEmail(headers) {
  const v = verifyCookie(readSession(headers));
  return v ? v.email : null;
}
function json(status, body, extraHeaders = {}) {
  return { statusCode: status, headers: { 'Content-Type': 'application/json', ...extraHeaders },
    body: JSON.stringify(body), isBase64Encoded: false };
}
function safeJson(s) { try { return JSON.parse(s || '{}'); } catch { return {}; } }

// ===================== ОБРАБОТЧИК =====================

module.exports.handler = async function (event) {
  try {
    const path = (event.path || event.url || '').replace(/\/+$/, '');
    const headers = event.headers || {};
    let body = event.body || '';
    if (event.isBase64Encoded && body) body = Buffer.from(body, 'base64').toString('utf8');

    if (path.endsWith('/prodamus-webhook')) return await handleWebhook(body, headers);
    if (path.endsWith('/login-verify'))     return await handleLoginVerify(body);
    if (path.endsWith('/check')) {
      const q = event.queryStringParameters || {};
      if (q.debug === 'webhook') return json(200, { last: _lastWebhook });
      return await handleCheck(headers);
    }
    if (path.endsWith('/debug-last'))     return json(200, { last: _lastWebhook });
    if (path.endsWith('/profile-get'))    return await handleProfileGet(headers);
    if (path.endsWith('/profile-save'))   return await handleProfileSave(body, headers);
    if (path.endsWith('/progress-get'))   return await handleProgressGet(headers);
    if (path.endsWith('/progress-save'))  return await handleProgressSave(body, headers);
    if (path.endsWith('/admin-reset'))    return await handleAdminReset(body);

    return json(404, { ok: false, error: 'unknown route', path });
  } catch (e) {
    console.error('handler error', e);
    return json(500, { ok: false, error: String(e && e.message || e) });
  }
};

// ===================== БАЗА (ключ — EMAIL) =====================

// Записать/ПРОДЛИТЬ подписку по email.
// Продление: новый срок = max(старый_срок, сейчас) + 31 день (оплата в середине месяца не сгорает).
async function dbUpsertSubscription(email, phone, orderId) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  const now = Date.now();

  // читаем текущий срок (если есть) — чтобы продлить, а не обнулить
  let base = now;
  await driver.tableClient.withSession(async (session) => {
    const sel = `DECLARE $email AS Utf8;
      SELECT expires_at FROM subscriptions WHERE email = $email;`;
    const { resultSets } = await session.executeQuery(sel, { '$email': TypedValues.utf8(email) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (rows.length) {
      const cur = new Date(rows[0].expires_at).getTime();
      if (cur > now) base = cur; // ещё активна → продлеваем от старой даты
    }
  });
  const expires = base + ACCESS_DAYS * 24 * 60 * 60 * 1000;

  await driver.tableClient.withSession(async (session) => {
    const q = `
      DECLARE $email AS Utf8; DECLARE $phone AS Utf8; DECLARE $order AS Utf8;
      DECLARE $paid AS Timestamp; DECLARE $expires AS Timestamp; DECLARE $upd AS Timestamp;
      UPSERT INTO subscriptions (email, phone, prodamus_order_id, paid_at, expires_at, updated_at)
      VALUES ($email, $phone, $order, $paid, $expires, $upd);`;
    await session.executeQuery(q, {
      '$email': TypedValues.utf8(email),
      '$phone': TypedValues.utf8(phone || ''),
      '$order': TypedValues.utf8(orderId || ''),
      '$paid': TypedValues.timestamp(new Date(now)),
      '$expires': TypedValues.timestamp(new Date(expires)),
      '$upd': TypedValues.timestamp(new Date(now)),
    });
  });
  return expires;
}

// Найти подписку по email. Вернёт {email, orderId, expires, active} или null.
async function dbGetSubByEmail(email) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  let result = null;
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $email AS Utf8;
      SELECT email, prodamus_order_id, expires_at FROM subscriptions WHERE email = $email;`;
    const { resultSets } = await session.executeQuery(q, { '$email': TypedValues.utf8(email) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (rows.length) {
      const exp = new Date(rows[0].expires_at).getTime();
      result = { email, orderId: String(rows[0].prodamus_order_id || ''), expires: exp, active: Date.now() < exp };
    }
  });
  return result;
}

// ===================== ОБРАБОТЧИКИ =====================

// (А) WEBHOOK Продамуса — приём оплаты
async function handleWebhook(body, headers) {
  let data = {};
  const ct = (headers['content-type'] || headers['Content-Type'] || '').toLowerCase();
  if (ct.includes('application/json')) {
    data = JSON.parse(body || '{}');
  } else {
    for (const pair of (body || '').split('&')) {
      const [k, v] = pair.split('=');
      if (k) data[decodeURIComponent(k)] = decodeURIComponent((v || '').replace(/\+/g, ' '));
    }
  }
  console.log('PRODAMUS_WEBHOOK_RAW', JSON.stringify({ data }));
  _lastWebhook = { at: new Date().toISOString(), data, rawBody: body };

  // Проверка подписи
  const calibrate = process.env.PRODAMUS_CALIBRATE === '1';
  const sign = data.signature || data.sign || headers['sign'] || headers['Sign'] || '';
  if (PRODAMUS_SECRET && !calibrate) {
    if (!sign) return json(403, { ok: false, error: 'no sign' });
    const copy = { ...data }; delete copy.signature; delete copy.sign;
    if (!verifyProdamusSign(copy, sign, PRODAMUS_SECRET)) return json(403, { ok: false, error: 'bad sign' });
  }

  const email   = normEmail(data.customer_email || data.email || data.payer_email);
  const phone   = String(data.customer_phone || data.phone || data.payer_phone || '');
  // КОД ДОСТУПА = номер заказа. ВАЖНО: в webhook Продамуса номер лежит в order_id
  // (поле order_num приходит ПУСТЫМ — проверено по логам 28.06). Берём order_id первым.
  const orderId = normCode(data.order_id || data.order_num || data.id || '');
  const status  = (data.payment_status || data.status || 'success').toLowerCase();

  if (!email)   return json(400, { ok: false, error: 'no email in webhook' });
  if (!orderId) return json(400, { ok: false, error: 'no order_num in webhook' });
  if (status && !['success', 'paid', 'ok', 'оплачен', ''].includes(status)) {
    return json(200, { ok: true, ignored: true, status });
  }

  const expires = await dbUpsertSubscription(email, phone, orderId);
  console.log('payment recorded', email, 'order', orderId, 'until', new Date(expires).toISOString());
  return json(200, { ok: true });
}

function verifyProdamusSign(params, sign, secret) {
  function sortDeep(obj) {
    if (Array.isArray(obj)) return obj.map(sortDeep);
    if (obj && typeof obj === 'object') {
      const out = {}; for (const k of Object.keys(obj).sort()) out[k] = sortDeep(obj[k]); return out;
    }
    return obj === null || obj === undefined ? '' : String(obj);
  }
  const payload = JSON.stringify(sortDeep(params));
  const hmac = crypto.createHmac('sha256', secret).update(payload, 'utf8').digest('hex');
  return hmac === String(sign).toLowerCase();
}

// (Б) ВХОД: { email, code } где code = номер заказа. Проверяем пару email+order.
async function handleLoginVerify(body) {
  const data = safeJson(body);
  const email = normEmail(data.email);
  const code  = normCode(data.code);
  if (!email || !code) return json(400, { ok: false, error: 'no email/code' });

  const sub = await dbGetSubByEmail(email);
  if (!sub)                 return json(403, { ok: false, error: 'not_paid' });   // нет оплаты по email
  if (sub.orderId !== code) return json(403, { ok: false, error: 'wrong' });      // неверный номер заказа
  if (!sub.active)          return json(403, { ok: false, error: 'expired' });    // срок истёк

  const cookieVal = makeCookie(email, sub.expires);
  const maxAge = Math.floor((sub.expires - Date.now()) / 1000);
  const cookie = `nutri_session=${encodeURIComponent(cookieVal)}; Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=None`;
  return json(200, { ok: true, token: cookieVal, expires: sub.expires }, { 'Set-Cookie': cookie });
}

// (В) ГЕЙТ: проверка сессии + активной подписки
async function handleCheck(headers) {
  const v = verifyCookie(readSession(headers));
  if (!v) return json(401, { ok: false, error: 'no_session' });
  const sub = await dbGetSubByEmail(v.email);
  if (!sub || !sub.active) return json(403, { ok: false, error: 'expired' });
  return json(200, { ok: true, email: v.email, expires: sub.expires });
}

// ===================== ПРОФИЛЬ + ПРОГРЕСС (ключ — email) =====================

const FIXED_FIELDS = ['gender', 'height', 'age', 'current_weight', 'desired_weight'];
const EDITABLE_FIELDS = ['activity', 'goal', 'exclusions'];

async function dbGetProfileRow(email) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  let row = null;
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $email AS Utf8;
      SELECT email, data, locked, created_at FROM user_profiles WHERE email = $email;`;
    const { resultSets } = await session.executeQuery(q, { '$email': TypedValues.utf8(email) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (rows.length) row = rows[0];
  });
  return row;
}
async function dbSaveProfileRow(email, dataObj, locked, createdAt) {
  const driver = await getDriver();
  const { TypedValues } = ydb();
  const now = Date.now();
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $email AS Utf8; DECLARE $data AS Utf8; DECLARE $locked AS Utf8;
      DECLARE $created AS Timestamp; DECLARE $upd AS Timestamp;
      UPSERT INTO user_profiles (email, data, locked, created_at, updated_at)
      VALUES ($email, $data, $locked, $created, $upd);`;
    await session.executeQuery(q, {
      '$email': TypedValues.utf8(email),
      '$data': TypedValues.utf8(JSON.stringify(dataObj)),
      '$locked': TypedValues.utf8(locked ? '1' : '0'),
      '$created': TypedValues.timestamp(createdAt),
      '$upd': TypedValues.timestamp(new Date(now)),
    });
  });
}
function profileFromRow(row) {
  if (!row) return null;
  let d = {}; try { d = JSON.parse(row.data || '{}'); } catch { d = {}; }
  d.locked = (row.locked === '1' || row.locked === 1 || row.locked === true);
  return d;
}
async function handleProfileGet(headers) {
  const email = authEmail(headers);
  if (!email) return json(401, { ok: false, error: 'no_session' });
  const row = await dbGetProfileRow(email);
  return json(200, { ok: true, profile: profileFromRow(row) });
}
async function handleProfileSave(body, headers) {
  const email = authEmail(headers);
  if (!email) return json(401, { ok: false, error: 'no_session' });
  const p = safeJson(body);
  const row = await dbGetProfileRow(email);
  const existing = row ? (() => { try { return JSON.parse(row.data || '{}'); } catch { return {}; } })() : null;
  const wasLocked = row && (row.locked === '1' || row.locked === 1 || row.locked === true);
  const createdAt = row ? new Date(row.created_at) : new Date();
  const out = {};
  for (const f of FIXED_FIELDS)    out[f] = wasLocked ? (existing ? existing[f] : undefined) : p[f];
  for (const f of EDITABLE_FIELDS) out[f] = (p[f] !== undefined && p[f] !== null) ? p[f] : (existing ? existing[f] : undefined);
  await dbSaveProfileRow(email, out, true, createdAt);
  const saved = await dbGetProfileRow(email);
  return json(200, { ok: true, profile: profileFromRow(saved) });
}

async function dbGetProgress(email) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  let data = null;
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $email AS Utf8; SELECT data FROM user_progress WHERE email = $email;`;
    const { resultSets } = await session.executeQuery(q, { '$email': TypedValues.utf8(email) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (rows.length) data = rows[0].data;
  });
  return data;
}
async function dbSaveProgress(email, dataStr) {
  const driver = await getDriver();
  const { TypedValues } = ydb();
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $email AS Utf8; DECLARE $data AS Utf8; DECLARE $upd AS Timestamp;
      UPSERT INTO user_progress (email, data, updated_at) VALUES ($email, $data, $upd);`;
    await session.executeQuery(q, {
      '$email': TypedValues.utf8(email),
      '$data': TypedValues.utf8(dataStr || '{}'),
      '$upd': TypedValues.timestamp(new Date()),
    });
  });
}
async function handleProgressGet(headers) {
  const email = authEmail(headers);
  if (!email) return json(401, { ok: false, error: 'no_session' });
  const data = await dbGetProgress(email);
  return json(200, { ok: true, data: data || '{}' });
}
async function handleProgressSave(body, headers) {
  const email = authEmail(headers);
  if (!email) return json(401, { ok: false, error: 'no_session' });
  const d = safeJson(body);
  let dataStr = '{}';
  if (typeof d.data === 'string') dataStr = d.data;
  else if (d.data) dataStr = JSON.stringify(d.data);
  else dataStr = JSON.stringify(d);
  if (dataStr.length > 20000) return json(400, { ok: false, error: 'too_big' });
  await dbSaveProgress(email, dataStr);
  return json(200, { ok: true });
}

// (Г) АДМИН-СБРОС профиля по email (оплату НЕ трогает)
async function handleAdminReset(body) {
  const d = safeJson(body);
  if (!ADMIN_KEY || d.admin_key !== ADMIN_KEY) return json(403, { ok: false, error: 'forbidden' });
  const email = normEmail(d.email);
  if (!email) return json(400, { ok: false, error: 'no_email' });
  const driver = await getDriver();
  const { TypedValues } = ydb();
  await driver.tableClient.withSession(async (session) => {
    await session.executeQuery(`DECLARE $email AS Utf8; DELETE FROM user_profiles WHERE email = $email;`,
      { '$email': TypedValues.utf8(email) });
    await session.executeQuery(`DECLARE $email AS Utf8; DELETE FROM user_progress WHERE email = $email;`,
      { '$email': TypedValues.utf8(email) });
  });
  return json(200, { ok: true, reset: email });
}
