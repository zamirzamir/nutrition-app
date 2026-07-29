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
const ACCESS_DAYS    = 95;   // срок доступа после оплаты (~90 дней плана + буфер, P2a)
// P0: подпись приватного recipes.json. Статический S3-ключ сервисного аккаунта с ролью storage.viewer.
const S3_KEY_ID      = process.env.S3_KEY_ID || '';
const S3_SECRET      = process.env.S3_SECRET || '';
const RECIPES_BUCKET = process.env.RECIPES_BUCKET || 'roman-app-v2';
const RECIPES_KEY    = process.env.RECIPES_KEY || 'recipes.json';

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
      // C1: дебаг-выдача последнего webhook содержит PII+код входа — только по admin_key.
      if (q.debug === 'webhook') {
        if (!ADMIN_KEY || q.admin_key !== ADMIN_KEY) return json(403, { ok: false, error: 'forbidden' });
        return json(200, { last: _lastWebhook });
      }
      return await handleCheck(headers);
    }
    if (path.endsWith('/debug-last')) {
      const q = event.queryStringParameters || {};
      if (!ADMIN_KEY || q.admin_key !== ADMIN_KEY) return json(403, { ok: false, error: 'forbidden' });
      return json(200, { last: _lastWebhook });
    }
    if (path.endsWith('/profile-get'))    return await handleProfileGet(headers);
    if (path.endsWith('/profile-save'))   return await handleProfileSave(body, headers);
    if (path.endsWith('/progress-get'))   return await handleProgressGet(headers);
    if (path.endsWith('/progress-save'))  return await handleProgressSave(body, headers);
    if (path.endsWith('/admin-reset'))    return await handleAdminReset(body);
    if (path.endsWith('/feedback-done'))  return await handleFeedbackDone(body);
    if (path.endsWith('/feedback-list'))  return await handleFeedbackList(body, event.queryStringParameters || {});
    if (path.endsWith('/feedback'))       return await handleFeedbackSave(body, headers);
    if (path.endsWith('/recipes-url'))    return await handleRecipesUrl(headers);
    if (path.endsWith('/admin-extend-subs')) return await handleAdminExtendSubs(body);

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

  // читаем текущий срок И число оплаченных периодов — чтобы продлить (не обнулить) и нарастить план
  let base = now, periods = 1;
  await driver.tableClient.withSession(async (session) => {
    const sel = `DECLARE $email AS Utf8;
      SELECT expires_at, periods FROM subscriptions WHERE email = $email;`;
    const { resultSets } = await session.executeQuery(sel, { '$email': TypedValues.utf8(email) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (rows.length) {
      const cur = new Date(rows[0].expires_at).getTime();
      if (cur > now) base = cur; // ещё активна → продлеваем от старой даты
      periods = (Number(rows[0].periods) || 1) + 1; // повторная оплата → +1 период (дни 91–180, 181–270…)
    }
  });
  const expires = base + ACCESS_DAYS * 24 * 60 * 60 * 1000;

  await driver.tableClient.withSession(async (session) => {
    const q = `
      DECLARE $email AS Utf8; DECLARE $phone AS Utf8; DECLARE $order AS Utf8;
      DECLARE $paid AS Timestamp; DECLARE $expires AS Timestamp; DECLARE $upd AS Timestamp; DECLARE $periods AS Uint32;
      UPSERT INTO subscriptions (email, phone, prodamus_order_id, paid_at, expires_at, updated_at, periods)
      VALUES ($email, $phone, $order, $paid, $expires, $upd, $periods);`;
    await session.executeQuery(q, {
      '$email': TypedValues.utf8(email),
      '$phone': TypedValues.utf8(phone || ''),
      '$order': TypedValues.utf8(orderId || ''),
      '$paid': TypedValues.timestamp(new Date(now)),
      '$expires': TypedValues.timestamp(new Date(expires)),
      '$upd': TypedValues.timestamp(new Date(now)),
      '$periods': TypedValues.uint32(periods),
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
      SELECT email, prodamus_order_id, expires_at, periods FROM subscriptions WHERE email = $email;`;
    const { resultSets } = await session.executeQuery(q, { '$email': TypedValues.utf8(email) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (rows.length) {
      const exp = new Date(rows[0].expires_at).getTime();
      const per = Number(rows[0].periods) || 1;                 // NULL у старых подписчиков → 1
      result = { email, orderId: String(rows[0].prodamus_order_id || ''), expires: exp, active: Date.now() < exp, plan_days: per * 90 };
    }
  });
  return result;
}

// P0: presigned GET URL для приватного объекта в Yandex Object Storage (S3 SigV4, без доп. зависимостей).
function presignGetUrl(bucket, key, expiresSec) {
  const host = `${bucket}.storage.yandexcloud.net`;
  const region = 'ru-central1';
  const amzDate = new Date().toISOString().replace(/[:\-]|\.\d{3}/g, ''); // YYYYMMDDTHHMMSSZ
  const dateStamp = amzDate.slice(0, 8);
  const scope = `${dateStamp}/${region}/s3/aws4_request`;
  const canonicalUri = '/' + key.split('/').map(encodeURIComponent).join('/');
  const params = {
    'X-Amz-Algorithm': 'AWS4-HMAC-SHA256',
    'X-Amz-Credential': `${S3_KEY_ID}/${scope}`,
    'X-Amz-Date': amzDate,
    'X-Amz-Expires': String(expiresSec),
    'X-Amz-SignedHeaders': 'host',
  };
  const canonicalQuery = Object.keys(params).sort()
    .map(k => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`).join('&');
  const canonicalRequest = ['GET', canonicalUri, canonicalQuery, `host:${host}\n`, 'host', 'UNSIGNED-PAYLOAD'].join('\n');
  const sha = s => crypto.createHash('sha256').update(s, 'utf8').digest('hex');
  const stringToSign = ['AWS4-HMAC-SHA256', amzDate, scope, sha(canonicalRequest)].join('\n');
  const hmac = (k, d) => crypto.createHmac('sha256', k).update(d, 'utf8').digest();
  let kSign = hmac('AWS4' + S3_SECRET, dateStamp);
  kSign = hmac(kSign, region); kSign = hmac(kSign, 's3'); kSign = hmac(kSign, 'aws4_request');
  const signature = crypto.createHmac('sha256', kSign).update(stringToSign, 'utf8').digest('hex');
  return `https://${host}${canonicalUri}?${canonicalQuery}&X-Amz-Signature=${signature}`;
}

// P0: отдаёт подписанную ссылку на ПРИВАТНЫЙ recipes.json ТОЛЬКО оплатившему (активная подписка).
async function handleRecipesUrl(headers) {
  const email = authEmail(headers);
  if (!email) return json(401, { ok: false, error: 'no_session' });
  const sub = await dbGetSubByEmail(email);
  if (!sub || !sub.active) return json(403, { ok: false, error: 'expired' });
  if (!S3_KEY_ID || !S3_SECRET) return json(500, { ok: false, error: 's3_not_configured' });
  const url = presignGetUrl(RECIPES_BUCKET, RECIPES_KEY, 3600); // ссылка живёт 1 час
  return json(200, { ok: true, url });
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
  // C2: FAIL-CLOSED. Раньше при пустом PRODAMUS_SECRET проверка ПРОПУСКАЛАСЬ → любой POST давал
  // бесплатную подписку на 95 дней. Теперь без секрета — отказ (кроме намеренного режима калибровки).
  if (!calibrate) {
    if (!PRODAMUS_SECRET) return json(503, { ok: false, error: 'signature not configured' });
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
  return json(200, { ok: true, token: cookieVal, expires: sub.expires, plan_days: sub.plan_days }, { 'Set-Cookie': cookie });
}

// (В) ГЕЙТ: проверка сессии + активной подписки
async function handleCheck(headers) {
  const v = verifyCookie(readSession(headers));
  if (!v) return json(401, { ok: false, error: 'no_session' });
  const sub = await dbGetSubByEmail(v.email);
  if (!sub || !sub.active) return json(403, { ok: false, error: 'expired' });
  return json(200, { ok: true, email: v.email, expires: sub.expires, plan_days: sub.plan_days });
}

// ===================== ПРОФИЛЬ + ПРОГРЕСС (ключ — email) =====================

// P3a: вес и желаемый вес МОЖНО менять на залоченном профиле (раз в 30 дней — гейт держит фронт).
// Неизменяемы навсегда только пол/рост/возраст.
const FIXED_FIELDS = ['gender', 'height', 'age'];
const EDITABLE_FIELDS = ['activity', 'goal', 'exclusions', 'current_weight', 'desired_weight'];

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
  // 16.07 ЗАЩИТА: НЕ лочим профиль, пока ключевые фиксируемые поля (рост/возраст/пол) не заполнены.
  // Раньше ЛЮБОЙ сейв ставил locked=true → случайный ранний сейв (напр. выбор стажа до ввода данных)
  // залочивал профиль с нулями, и настоящая фиксация FIXED_FIELDS их уже не переписывала. Раз залочен —
  // остаётся залочен (wasLocked). Это бэкенд-страховка поверх клиентского фикса.
  const fixedFilled = Number(out.height) > 0 && Number(out.age) > 0 && !!out.gender;
  const lock = wasLocked || fixedFilled;
  await dbSaveProfileRow(email, out, lock, createdAt);
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
  // 16.07 (Замир): МАРКЕР СБРОСА должен переживать ре-заливку от уже открытой сессии клиента.
  // Если на сервере стоит reset_at (админ сбросил аккаунт), сохраняем его в новом блобе — ПОКА клиент
  // явно не подтвердит применение сброса (reset_ack >= reset_at). Иначе открытая вкладка со старой
  // неделей затирает маркер, и сброс «не держится». Как только клиент при следующем открытии увидит
  // reset_at, сотрёт локальное и подтвердит — маркер снимается.
  try {
    let incoming = {}; try { incoming = JSON.parse(dataStr) || {}; } catch (e) { incoming = {}; }
    const prevStr = await dbGetProgress(email);
    let prev = {}; try { prev = JSON.parse(prevStr || '{}') || {}; } catch (e) { prev = {}; }
    const prevReset = Number(prev.reset_at || 0);
    if (prevReset > 0) {
      const ack = Number(incoming.reset_ack || 0);
      if (ack >= prevReset) { if (incoming.reset_at) delete incoming.reset_at; }  // подтверждён → снять маркер
      else { incoming.reset_at = prevReset; }                                     // не подтверждён → сохранить маркер
      delete incoming.reset_ack;
      dataStr = JSON.stringify(incoming);
      if (dataStr.length > 20000) return json(400, { ok: false, error: 'too_big' });
    } else if (incoming.reset_ack != null) {
      delete incoming.reset_ack; dataStr = JSON.stringify(incoming);            // маркера нет — убрать служебное поле
    }
  } catch (e) { /* при сбое — сохраняем как пришло */ }
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
  });
  // 16.07 (Замир): прогресс НЕ просто удаляем, а пишем МАРКЕР сброса (reset_at). Иначе уже открытая
  // сессия клиента (с неделей 11 и т.п. в localStorage) заливает старое состояние обратно на сервер —
  // сброс «не держится». По маркеру клиент при следующем открытии понимает, что был сброшен, стирает
  // всё локальное (тренировки/дни/съел/замки) и запоминает эпоху, поэтому старое больше не всплывает.
  // dbSaveProgress перезаписывает любой прежний прогресс этой строкой-маркером.
  const resetAt = Date.now();
  await dbSaveProgress(email, JSON.stringify({ reset_at: resetAt }));
  return json(200, { ok: true, reset: email, reset_at: resetAt });
}

// (Г) РАЗОВОЕ ПРОДЛЕНИЕ существующих подписок под честные 90 дней (P2a).
// Тело: { admin_key, apply?:true }. Без apply → DRY-RUN (только отчёт «было→стало», база НЕ меняется).
// Правило: expires_at → paid_at + ACCESS_DAYS*periods дней, НО только если это БОЛЬШЕ текущего
// (никого не укорачивает). Идемпотентно: повторный запуск ничего лишнего не делает.
async function handleAdminExtendSubs(body) {
  const d = safeJson(body);
  if (!ADMIN_KEY || d.admin_key !== ADMIN_KEY) return json(403, { ok: false, error: 'forbidden' });
  const apply = d.apply === true;
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  const DAY = 24 * 60 * 60 * 1000;

  let rows = [];
  await driver.tableClient.withSession(async (session) => {
    const { resultSets } = await session.executeQuery(
      `SELECT email, paid_at, expires_at, periods FROM subscriptions;`);
    rows = TypedData.createNativeObjects(resultSets[0]);
  });

  const report = [];
  let applied = 0;
  for (const r of rows) {
    const email = String(r.email || '');
    const per   = Number(r.periods) || 1;
    const curExp = r.expires_at ? new Date(r.expires_at).getTime() : 0;
    const paid   = r.paid_at ? new Date(r.paid_at).getTime() : 0;
    if (!paid) { report.push({ email, skip: 'no paid_at' }); continue; }
    const target = paid + ACCESS_DAYS * per * DAY;
    const willChange = target > curExp;
    report.push({
      email, periods: per,
      before: new Date(curExp).toISOString().slice(0, 10),
      after:  new Date(Math.max(curExp, target)).toISOString().slice(0, 10),
      changed: willChange,
    });
    if (apply && willChange) {
      await driver.tableClient.withSession(async (session) => {
        await session.executeQuery(
          `DECLARE $email AS Utf8; DECLARE $exp AS Timestamp;
           UPDATE subscriptions SET expires_at = $exp WHERE email = $email;`,
          { '$email': TypedValues.utf8(email), '$exp': TypedValues.timestamp(new Date(target)) });
      });
      applied++;
    }
  }
  return json(200, {
    ok: true, mode: apply ? 'APPLIED' : 'DRY-RUN',
    total: rows.length, willChange: report.filter(x => x.changed).length, applied, report,
  });
}

// ===================== ОБРАТНАЯ СВЯЗЬ («Нашли ошибку?») =====================
// POST /feedback — приём отзыва от клиента. БЕЗ авторизации (любой может отправить).
// Тело: { text, diag }. Если есть валидная кука — подставим email отправителя.
async function handleFeedbackSave(body, headers) {
  const d = safeJson(body);
  var text = String(d.text || '').slice(0, 5000);
  var diag = String(d.diag || '').slice(0, 4000);
  if (!text.trim() && !diag.trim()) return json(400, { ok: false, error: 'empty' });
  var email = '';
  try { email = authEmail(headers) || ''; } catch (e) {}      // необязательно
  var id = (Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8));
  await dbSaveFeedback(id, email, text, diag);
  return json(200, { ok: true });
}
// POST /feedback-list — выгрузка отзывов (защита admin_key). По умолчанию только АКТИВНЫЕ
// (неархивные). { admin_key, archived:true } — показать архив (разобранные).
async function handleFeedbackList(body, query) {
  const d = safeJson(body);
  const key = (d && d.admin_key) || (query && query.admin_key);
  if (!ADMIN_KEY || key !== ADMIN_KEY) return json(403, { ok: false, error: 'forbidden' });
  const showArchived = !!(d && d.archived) || (query && (query.archived === '1' || query.archived === 'true'));
  const items = await dbListFeedback(showArchived);
  return json(200, { ok: true, count: items.length, items });
}
// POST /feedback-done — пометить отзывы РАЗОБРАННЫМИ (переносит в архив, НЕ удаляет).
// Тело: { admin_key, ids: [...] }.
async function handleFeedbackDone(body) {
  const d = safeJson(body);
  if (!ADMIN_KEY || d.admin_key !== ADMIN_KEY) return json(403, { ok: false, error: 'forbidden' });
  const ids = Array.isArray(d.ids) ? d.ids.filter(Boolean).map(String) : [];
  if (!ids.length) return json(400, { ok: false, error: 'no_ids' });
  await dbArchiveFeedback(ids);
  return json(200, { ok: true, archived: ids.length });
}

async function dbSaveFeedback(id, email, text, diag) {
  const driver = await getDriver();
  const { TypedValues } = ydb();
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $id AS Utf8; DECLARE $email AS Utf8; DECLARE $text AS Utf8; DECLARE $diag AS Utf8; DECLARE $ts AS Timestamp;
      UPSERT INTO feedback (id, email, text, diag, created_at) VALUES ($id, $email, $text, $diag, $ts);`;
    await session.executeQuery(q, {
      '$id': TypedValues.utf8(id),
      '$email': TypedValues.utf8(email || ''),
      '$text': TypedValues.utf8(text || ''),
      '$diag': TypedValues.utf8(diag || ''),
      '$ts': TypedValues.timestamp(new Date()),
    });
  });
}
async function dbListFeedback(showArchived) {
  const driver = await getDriver();
  const { TypedData } = ydb();
  let items = [];
  // archived может быть NULL (старые строки) — считаем их активными.
  const cond = showArchived ? 'archived = true' : '(archived IS NULL OR archived = false)';
  await driver.tableClient.withSession(async (session) => {
    const q = `SELECT id, email, text, diag, created_at FROM feedback WHERE ${cond} ORDER BY created_at DESC LIMIT 1000;`;
    const { resultSets } = await session.executeQuery(q);
    items = TypedData.createNativeObjects(resultSets[0]);
  });
  return items;
}
// Пометить строки archived=true (UPSERT меняет только эту колонку, остальное не трогает).
async function dbArchiveFeedback(ids) {
  const driver = await getDriver();
  const { TypedValues } = ydb();
  await driver.tableClient.withSession(async (session) => {
    for (const id of ids) {
      await session.executeQuery(
        `DECLARE $id AS Utf8; UPSERT INTO feedback (id, archived) VALUES ($id, true);`,
        { '$id': TypedValues.utf8(String(id)) });
    }
  });
}
