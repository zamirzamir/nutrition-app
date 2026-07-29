/**
 * Главная функция-роутер для авторизации и оплаты.
 * Yandex Cloud Function (Node.js 18), подключение к YDB serverless.
 *
 * Обрабатывает запросы по полю event.path (через API Gateway):
 *   POST /prodamus-webhook   — приём оплаты от Продамуса (телефон+email → БД)
 *   POST /login-request      — клиент ввёл телефон → проверяем оплату → шлём код (Telegram/SMS)
 *   POST /login-verify       — клиент ввёл код → ставим куку (31 день)
 *   GET  /check              — гейт части 2: валидна ли кука + активна ли оплата
 *   POST /telegram-webhook   — приём апдейтов от Telegram-бота (контакт телефона)
 *
 * Переменные окружения (задаются при создании функции):
 *   SESSION_SECRET     — секрет для подписи куки
 *   PRODAMUS_SECRET    — секрет формы Продамуса (проверка подписи webhook)
 *   SMSRU_API_KEY      — ключ SMS.ru (запасной канал кода)
 *   TELEGRAM_BOT_TOKEN — токен Telegram-бота (основной канал кода)
 *   YDB_DATABASE       — путь к базе YDB
 *   YDB_ENDPOINT       — эндпоинт YDB
 */

const crypto = require('crypto');
// ydb-sdk грузим ЛЕНИВО (только когда нужна база) — чтобы быстрые маршруты
// (/start, /check) отвечали мгновенно и Telegram не отваливался по таймауту.
let _ydb = null;
function ydb() {
  if (!_ydb) _ydb = require('ydb-sdk');
  return _ydb;
}

// ---- Конфиг из переменных окружения ----
const YDB_ENDPOINT = process.env.YDB_ENDPOINT || 'grpcs://ydb.serverless.yandexcloud.net:2135';
const YDB_DATABASE = process.env.YDB_DATABASE; // /ru-central1/.../...
const SESSION_SECRET = process.env.SESSION_SECRET || 'change-me';
const PRODAMUS_SECRET = process.env.PRODAMUS_SECRET || '';
const SMSRU_API_KEY = process.env.SMSRU_API_KEY || '';
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';
const ADMIN_KEY = process.env.ADMIN_KEY || ''; // ключ для админ-сброса профиля
const ACCESS_DAYS = 31;       // срок доступа после оплаты
const OTP_TTL_MIN = 5;        // код живёт 5 минут
const OTP_MAX_ATTEMPTS = 5;   // защита от перебора

// Временное хранилище последнего webhook (для калибровки подписи). Убрать после.
let _lastWebhook = null;

// ---- Драйвер YDB (переиспользуем между вызовами) ----
let _driver = null;
async function getDriver() {
  if (_driver) return _driver;
  const { Driver, getCredentialsFromEnv } = ydb();
  _driver = new Driver({
    endpoint: YDB_ENDPOINT,
    database: YDB_DATABASE,
    authService: getCredentialsFromEnv(), // авторизация через сервисный аккаунт функции
  });
  const ready = await _driver.ready(10000);
  if (!ready) throw new Error('YDB driver not ready');
  return _driver;
}

// ===================== УТИЛИТЫ =====================

// Нормализация телефона: всё в формат 79XXXXXXXXX (11 цифр, начинается с 7)
function normPhone(raw) {
  if (!raw) return '';
  let d = String(raw).replace(/\D/g, '');
  if (d.length === 11 && d[0] === '8') d = '7' + d.slice(1);
  if (d.length === 10) d = '7' + d;
  return d;
}

// Подписанная кука: phone.expires.HMAC
function makeCookie(phone, expiresMs) {
  const payload = `${phone}.${expiresMs}`;
  const sig = crypto.createHmac('sha256', SESSION_SECRET).update(payload).digest('hex');
  return `${payload}.${sig}`;
}
function verifyCookie(cookie) {
  if (!cookie) return null;
  const parts = cookie.split('.');
  if (parts.length !== 3) return null;
  const [phone, expires, sig] = parts;
  const expect = crypto.createHmac('sha256', SESSION_SECRET).update(`${phone}.${expires}`).digest('hex');
  if (sig !== expect) return null;               // подделка
  if (Date.now() > Number(expires)) return null; // кука истекла
  return { phone, expires: Number(expires) };
}

function readCookie(headers, name) {
  const raw = headers?.cookie || headers?.Cookie || '';
  const m = raw.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]+)'));
  return m ? decodeURIComponent(m[1]) : null;
}

function genCode() {
  return String(Math.floor(1000 + Math.random() * 9000)); // 4 цифры
}

function json(status, body, extraHeaders = {}) {
  return {
    statusCode: status,
    headers: { 'Content-Type': 'application/json', ...extraHeaders },
    body: JSON.stringify(body),
    isBase64Encoded: false,
  };
}

// ===================== ОБРАБОТЧИК =====================

module.exports.handler = async function (event, context) {
  try {
    const path = (event.path || event.url || '').replace(/\/+$/, '');
    const method = (event.httpMethod || event.method || 'GET').toUpperCase();
    const headers = event.headers || {};
    let body = event.body || '';
    if (event.isBase64Encoded && body) body = Buffer.from(body, 'base64').toString('utf8');

    if (path.endsWith('/prodamus-webhook')) return await handleWebhook(body, headers);
    if (path.endsWith('/login-request'))   return await handleLoginRequest(body);
    if (path.endsWith('/login-verify'))    return await handleLoginVerify(body);
    if (path.endsWith('/check')) {
      // временно: ?debug=webhook отдаёт последний принятый webhook (для калибровки)
      const q = event.queryStringParameters || {};
      if (q.debug === 'webhook') return json(200, { last: _lastWebhook });
      return await handleCheck(headers);
    }
    if (path.endsWith('/debug-last'))      return json(200, { last: _lastWebhook });
    if (path.endsWith('/profile-get'))     return await handleProfileGet(headers);
    if (path.endsWith('/profile-save'))    return await handleProfileSave(body, headers);
    if (path.endsWith('/progress-get'))    return await handleProgressGet(headers);
    if (path.endsWith('/progress-save'))   return await handleProgressSave(body, headers);
    if (path.endsWith('/admin-reset'))     return await handleAdminReset(body);
    if (path.endsWith('/telegram-webhook')) {
      // Telegram рвёт соединение по таймауту, если ждать долго.
      // Отвечаем 200 СРАЗУ, а обработку делаем без ожидания (fire-and-forget).
      handleTelegram(body).catch(e => console.error('tg async error', e));
      return json(200, { ok: true });
    }

    return json(404, { ok: false, error: 'unknown route', path });
  } catch (e) {
    console.error('handler error', e);
    return json(500, { ok: false, error: String(e && e.message || e) });
  }
};

// ===================== ДОСТУП К БАЗЕ (YQL) =====================

// Записать/обновить оплату по телефону
async function dbUpsertSubscription(phone, email, orderId) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  const now = Date.now();
  const expires = now + ACCESS_DAYS * 24 * 60 * 60 * 1000;
  await driver.tableClient.withSession(async (session) => {
    const query = `
      DECLARE $phone AS Utf8; DECLARE $email AS Utf8;
      DECLARE $paid AS Timestamp; DECLARE $expires AS Timestamp;
      DECLARE $order AS Utf8; DECLARE $upd AS Timestamp;
      UPSERT INTO subscriptions (phone, email, paid_at, expires_at, prodamus_order_id, updated_at)
      VALUES ($phone, $email, $paid, $expires, $order, $upd);`;
    await session.executeQuery(query, {
      '$phone': TypedValues.utf8(phone),
      '$email': TypedValues.utf8(email || ''),
      '$paid': TypedValues.timestamp(new Date(now)),
      '$expires': TypedValues.timestamp(new Date(expires)),
      '$order': TypedValues.utf8(orderId || ''),
      '$upd': TypedValues.timestamp(new Date(now)),
    });
  });
  return expires;
}

// Найти активную подписку по телефону (вернёт expires_at в ms или null)
async function dbGetActiveSub(phone) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  let result = null;
  await driver.tableClient.withSession(async (session) => {
    const query = `
      DECLARE $phone AS Utf8;
      SELECT phone, email, expires_at FROM subscriptions WHERE phone = $phone;`;
    const { resultSets } = await session.executeQuery(query, { '$phone': TypedValues.utf8(phone) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (rows.length) {
      const exp = new Date(rows[0].expires_at).getTime();
      result = { phone, email: rows[0].email, expires: exp, active: Date.now() < exp };
    }
  });
  return result;
}

// Сохранить код подтверждения
async function dbSaveOtp(phone, code) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  const expires = Date.now() + OTP_TTL_MIN * 60 * 1000;
  await driver.tableClient.withSession(async (session) => {
    const query = `
      DECLARE $phone AS Utf8; DECLARE $code AS Utf8; DECLARE $exp AS Timestamp; DECLARE $att AS Uint32;
      UPSERT INTO otp_codes (phone, code, expires_at, attempts) VALUES ($phone, $code, $exp, $att);`;
    await session.executeQuery(query, {
      '$phone': TypedValues.utf8(phone),
      '$code': TypedValues.utf8(code),
      '$exp': TypedValues.timestamp(new Date(expires)),
      '$att': TypedValues.uint32(0),
    });
  });
}

// Проверить код (учёт срока и попыток)
async function dbCheckOtp(phone, code) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  let verdict = { ok: false, reason: 'not_found' };
  await driver.tableClient.withSession(async (session) => {
    const sel = `DECLARE $phone AS Utf8;
      SELECT code, expires_at, attempts FROM otp_codes WHERE phone = $phone;`;
    const { resultSets } = await session.executeQuery(sel, { '$phone': TypedValues.utf8(phone) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (!rows.length) { verdict = { ok: false, reason: 'not_found' }; return; }
    const r = rows[0];
    if (Date.now() > new Date(r.expires_at).getTime()) { verdict = { ok: false, reason: 'expired' }; return; }
    if (r.attempts >= OTP_MAX_ATTEMPTS) { verdict = { ok: false, reason: 'too_many' }; return; }
    if (String(r.code) === String(code)) {
      verdict = { ok: true };
      // удаляем использованный код
      const del = `DECLARE $phone AS Utf8; DELETE FROM otp_codes WHERE phone = $phone;`;
      await session.executeQuery(del, { '$phone': TypedValues.utf8(phone) });
    } else {
      verdict = { ok: false, reason: 'wrong' };
      const upd = `DECLARE $phone AS Utf8; DECLARE $a AS Uint32;
        UPDATE otp_codes SET attempts = $a WHERE phone = $phone;`;
      await session.executeQuery(upd, { '$phone': TypedValues.utf8(phone), '$a': TypedValues.uint32(r.attempts + 1) });
    }
  });
  return verdict;
}

// ===================== ОТПРАВКА КОДА =====================

// SMS.ru (запасной канал)
async function sendSms(phone, code) {
  if (!SMSRU_API_KEY) return { ok: false, error: 'no_smsru_key' };
  const msg = encodeURIComponent(`Код для входа: ${code}`);
  const url = `https://sms.ru/sms/send?api_id=${SMSRU_API_KEY}&to=${phone}&msg=${msg}&json=1`;
  const r = await fetch(url);
  const data = await r.json().catch(() => ({}));
  return { ok: data.status === 'OK', data };
}

// Telegram: код шлём в чат, если бот знает chat_id по телефону.
// chat_id хранится в таблице tg_links (связь устанавливается при «Поделиться контактом»).
async function dbGetTgChat(phone) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  let chatId = null;
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $phone AS Utf8; SELECT chat_id FROM tg_links WHERE phone = $phone;`;
    const { resultSets } = await session.executeQuery(q, { '$phone': TypedValues.utf8(phone) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (rows.length) chatId = String(rows[0].chat_id);
  });
  return chatId;
}
async function dbSaveTgChat(phone, chatId) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $phone AS Utf8; DECLARE $chat AS Utf8;
      UPSERT INTO tg_links (phone, chat_id) VALUES ($phone, $chat);`;
    await session.executeQuery(q, { '$phone': TypedValues.utf8(phone), '$chat': TypedValues.utf8(String(chatId)) });
  });
}
// Вызов Telegram API с увеличенным таймаутом и ретраями
// (из дата-центра Яндекса соединение к api.telegram.org бывает медленным).
async function tgApi(method, payload, tries = 3) {
  if (!TELEGRAM_BOT_TOKEN) return { ok: false, error: 'no_token' };
  const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/${method}`;
  let lastErr = null;
  for (let i = 0; i < tries; i++) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 8000); // 8 сек на попытку
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
      clearTimeout(t);
      const data = await r.json().catch(() => ({}));
      return { ok: !!data.ok, data };
    } catch (e) {
      lastErr = e;
      console.warn(`tgApi ${method} attempt ${i + 1} failed:`, String(e && e.message || e));
      await new Promise(res => setTimeout(res, 500 * (i + 1))); // пауза перед ретраем
    }
  }
  return { ok: false, error: 'fetch_failed', cause: String(lastErr && lastErr.message || lastErr) };
}

async function sendTelegram(phone, code) {
  const chatId = await dbGetTgChat(phone);
  if (!chatId) return { ok: false, error: 'no_tg_chat' };
  return await tgApi('sendMessage', { chat_id: chatId, text: `Код для входа в приложение: ${code}` });
}

// ===================== ОБРАБОТЧИКИ =====================

// (А) WEBHOOK от Продамуса — приём оплаты
async function handleWebhook(body, headers) {
  // Продамус шлёт x-www-form-urlencoded ИЛИ JSON. Парсим оба.
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

  // ЛОГ входящего webhook — для калибровки подписи Продамуса (видно в логах функции).
  console.log('PRODAMUS_WEBHOOK_RAW', JSON.stringify({ headers, data }));
  _lastWebhook = { at: new Date().toISOString(), headers, data, rawBody: body }; // для /debug-last

  // Проверка подписи (HMAC-SHA256 по данным + секрет формы).
  // PRODAMUS_CALIBRATE=1 — режим калибровки: подпись проверяется, но webhook НЕ
  // отклоняется (чтобы поймать реальный формат). После калибровки убрать флаг.
  const calibrate = process.env.PRODAMUS_CALIBRATE === '1';
  const sign = data.signature || data.sign || headers['sign'] || headers['Sign'] || '';
  if (PRODAMUS_SECRET && !calibrate) {
    if (!sign) { console.warn('webhook without sign — rejected'); return json(403, { ok: false, error: 'no sign' }); }
    const copy = { ...data }; delete copy.signature; delete copy.sign;
    const ok = verifyProdamusSign(copy, sign, PRODAMUS_SECRET);
    if (!ok) { console.warn('bad prodamus sign'); return json(403, { ok: false, error: 'bad sign' }); }
  } else if (calibrate) {
    const copy = { ...data }; delete copy.signature; delete copy.sign;
    const ok = sign ? verifyProdamusSign(copy, sign, PRODAMUS_SECRET) : false;
    console.log('CALIBRATE sign check:', ok ? 'MATCH ✅' : 'no-match', 'sign=', sign);
  }

  const phone = normPhone(data.customer_phone || data.phone || data.payer_phone);
  const email = data.customer_email || data.email || '';
  const orderId = data.order_num || data.order_id || data.id || '';
  // Считаем оплату успешной (Продамус шлёт webhook при успехе; статус можно дополнительно сверить)
  const status = (data.payment_status || data.status || 'success').toLowerCase();

  if (!phone) return json(400, { ok: false, error: 'no phone in webhook' });
  if (status && !['success', 'paid', 'ok', 'оплачен'].includes(status) && status !== '') {
    // если Продамус прислал не-успех — не открываем доступ
    return json(200, { ok: true, ignored: true, status });
  }

  const expires = await dbUpsertSubscription(phone, email, orderId);
  console.log('payment recorded', phone, 'until', new Date(expires).toISOString());
  return json(200, { ok: true });
}

// Проверка подписи Продамуса: рекурсивная сортировка ключей → HMAC-SHA256.
function verifyProdamusSign(params, sign, secret) {
  function sortDeep(obj) {
    if (Array.isArray(obj)) return obj.map(sortDeep);
    if (obj && typeof obj === 'object') {
      const out = {};
      for (const k of Object.keys(obj).sort()) out[k] = sortDeep(obj[k]);
      return out;
    }
    return obj === null || obj === undefined ? '' : String(obj);
  }
  const sorted = sortDeep(params);
  const payload = JSON.stringify(sorted);
  const hmac = crypto.createHmac('sha256', secret).update(payload, 'utf8').digest('hex');
  return hmac === String(sign).toLowerCase();
}

// (Б) ВХОД шаг 1: клиент ввёл телефон → если оплатил, шлём код
async function handleLoginRequest(body) {
  const data = safeJson(body);
  const phone = normPhone(data.phone);
  const channel = (data.channel || 'telegram').toLowerCase(); // telegram | sms
  if (!phone) return json(400, { ok: false, error: 'no phone' });

  const sub = await dbGetActiveSub(phone);
  if (!sub) return json(403, { ok: false, error: 'not_paid', message: 'Оплата по этому номеру не найдена' });
  if (!sub.active) return json(403, { ok: false, error: 'expired', message: 'Срок доступа истёк' });

  const code = genCode();
  await dbSaveOtp(phone, code);

  let sent;
  if (channel === 'sms') sent = await sendSms(phone, code);
  else sent = await sendTelegram(phone, code);

  // если основной канал не сработал — сообщаем, чтобы фронт предложил другой
  if (!sent.ok) return json(200, { ok: true, code_sent: false, channel, hint: sent.error });
  return json(200, { ok: true, code_sent: true, channel });
}

// (В) ВХОД шаг 2: клиент ввёл код → ставим куку 31 день
async function handleLoginVerify(body) {
  const data = safeJson(body);
  const phone = normPhone(data.phone);
  const code = String(data.code || '').trim();
  if (!phone || !code) return json(400, { ok: false, error: 'no phone/code' });

  const check = await dbCheckOtp(phone, code);
  if (!check.ok) return json(403, { ok: false, error: check.reason });

  const sub = await dbGetActiveSub(phone);
  if (!sub || !sub.active) return json(403, { ok: false, error: 'not_active' });

  const cookieVal = makeCookie(phone, sub.expires);
  const maxAge = Math.floor((sub.expires - Date.now()) / 1000);
  // SameSite=None обязателен: сайт (...yandexcloud.net) и API (...apigw.yandexcloud.net) —
  // разные сайты (cross-site), при Lax кука не отправляется обратно. None требует Secure.
  const cookie = `nutri_session=${encodeURIComponent(cookieVal)}; Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=None`;
  // token в теле — для браузеров, где cross-site кука блокируется (Safari ITP).
  // Фронт хранит его в localStorage и шлёт в заголовке Authorization.
  return json(200, { ok: true, token: cookieVal, expires: sub.expires }, { 'Set-Cookie': cookie });
}

// Достаёт session-значение из куки ИЛИ из заголовка Authorization: Bearer <token>.
function readSession(headers) {
  const fromCookie = readCookie(headers, 'nutri_session');
  if (fromCookie) return fromCookie;
  const auth = headers?.authorization || headers?.Authorization || '';
  const m = auth.match(/^Bearer\s+(.+)$/i);
  return m ? m[1] : null;
}

// (Г) ГЕЙТ части 2: проверка сессии (кука/токен) + активной оплаты
async function handleCheck(headers) {
  const v = verifyCookie(readSession(headers));
  if (!v) return json(401, { ok: false, error: 'no_session' });
  const sub = await dbGetActiveSub(v.phone);
  if (!sub || !sub.active) return json(403, { ok: false, error: 'expired' });
  return json(200, { ok: true, phone: v.phone, expires: sub.expires });
}

// ===================== ЛИЧНЫЙ КАБИНЕТ (профиль + прогресс) =====================

// Достаёт авторизованный телефон из куки/токена или null.
function authPhone(headers) {
  const v = verifyCookie(readSession(headers));
  return v ? v.phone : null;
}

// --- БД: профиль (хранится одной JSON-строкой в поле data) ---
// Фиксируемые поля (не меняются после locked): gender, height, age, current_weight, desired_weight.
// Редактируемые: activity, goal, exclusions.
const FIXED_FIELDS = ['gender', 'height', 'age', 'current_weight', 'desired_weight'];
const EDITABLE_FIELDS = ['activity', 'goal', 'exclusions'];

async function dbGetProfileRow(phone) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  let row = null;
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $phone AS Utf8;
      SELECT phone, data, locked, created_at FROM user_profiles WHERE phone = $phone;`;
    const { resultSets } = await session.executeQuery(q, { '$phone': TypedValues.utf8(phone) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (rows.length) row = rows[0];
  });
  return row;
}

async function dbSaveProfileRow(phone, dataObj, locked, createdAt) {
  const driver = await getDriver();
  const { TypedValues } = ydb();
  const now = Date.now();
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $phone AS Utf8; DECLARE $data AS Utf8; DECLARE $locked AS Utf8;
      DECLARE $created AS Timestamp; DECLARE $upd AS Timestamp;
      UPSERT INTO user_profiles (phone, data, locked, created_at, updated_at)
      VALUES ($phone, $data, $locked, $created, $upd);`;
    await session.executeQuery(q, {
      '$phone': TypedValues.utf8(phone),
      '$data': TypedValues.utf8(JSON.stringify(dataObj)),
      '$locked': TypedValues.utf8(locked ? '1' : '0'),
      '$created': TypedValues.timestamp(createdAt),
      '$upd': TypedValues.timestamp(new Date(now)),
    });
  });
}

function profileFromRow(row) {
  if (!row) return null;
  let d = {};
  try { d = JSON.parse(row.data || '{}'); } catch { d = {}; }
  d.locked = (row.locked === '1' || row.locked === 1 || row.locked === true);
  return d;
}

async function handleProfileGet(headers) {
  const phone = authPhone(headers);
  if (!phone) return json(401, { ok: false, error: 'no_session' });
  const row = await dbGetProfileRow(phone);
  return json(200, { ok: true, profile: profileFromRow(row) }); // null = ещё не заполнял
}

async function handleProfileSave(body, headers) {
  const phone = authPhone(headers);
  if (!phone) return json(401, { ok: false, error: 'no_session' });
  const p = safeJson(body);
  const row = await dbGetProfileRow(phone);
  const existing = row ? (() => { try { return JSON.parse(row.data || '{}'); } catch { return {}; } })() : null;
  const wasLocked = row && (row.locked === '1' || row.locked === 1 || row.locked === true);
  const createdAt = row ? new Date(row.created_at) : new Date();

  const out = {};
  // Фиксируемые: если уже locked — берём старые значения, новые игнорируем.
  for (const f of FIXED_FIELDS) {
    out[f] = wasLocked ? (existing ? existing[f] : undefined) : p[f];
  }
  // Редактируемые: всегда из запроса (или старое, если не прислали).
  for (const f of EDITABLE_FIELDS) {
    out[f] = (p[f] !== undefined && p[f] !== null) ? p[f] : (existing ? existing[f] : undefined);
  }
  await dbSaveProfileRow(phone, out, true, createdAt); // после первого сохранения — locked
  const saved = await dbGetProfileRow(phone);
  return json(200, { ok: true, profile: profileFromRow(saved) });
}

// --- БД: прогресс дней ---
async function dbGetProgress(phone) {
  const driver = await getDriver();
  const { TypedValues, TypedData } = ydb();
  let data = null;
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $phone AS Utf8; SELECT data FROM user_progress WHERE phone = $phone;`;
    const { resultSets } = await session.executeQuery(q, { '$phone': TypedValues.utf8(phone) });
    const rows = TypedData.createNativeObjects(resultSets[0]);
    if (rows.length) data = rows[0].data;
  });
  return data;
}

async function dbSaveProgress(phone, dataStr) {
  const driver = await getDriver();
  const { TypedValues } = ydb();
  await driver.tableClient.withSession(async (session) => {
    const q = `DECLARE $phone AS Utf8; DECLARE $data AS Utf8; DECLARE $upd AS Timestamp;
      UPSERT INTO user_progress (phone, data, updated_at) VALUES ($phone, $data, $upd);`;
    await session.executeQuery(q, {
      '$phone': TypedValues.utf8(phone),
      '$data': TypedValues.utf8(dataStr || '{}'),
      '$upd': TypedValues.timestamp(new Date()),
    });
  });
}

async function handleProgressGet(headers) {
  const phone = authPhone(headers);
  if (!phone) return json(401, { ok: false, error: 'no_session' });
  const data = await dbGetProgress(phone);
  return json(200, { ok: true, data: data || '{}' });
}

async function handleProgressSave(body, headers) {
  const phone = authPhone(headers);
  if (!phone) return json(401, { ok: false, error: 'no_session' });
  const d = safeJson(body);
  // ожидаем { data: "<json-строка>" } или сам объект
  let dataStr = '{}';
  if (typeof d.data === 'string') dataStr = d.data;
  else if (d.data) dataStr = JSON.stringify(d.data);
  else dataStr = JSON.stringify(d);
  if (dataStr.length > 20000) return json(400, { ok: false, error: 'too_big' });
  await dbSaveProgress(phone, dataStr);
  return json(200, { ok: true });
}

// (Е) АДМИН-СБРОС профиля клиента (для поддержки).
// Удаляет профиль и прогресс по телефону. Оплату (subscriptions) НЕ трогает.
// Защита: в теле должен прийти правильный admin_key.
async function handleAdminReset(body) {
  const d = safeJson(body);
  if (!ADMIN_KEY || d.admin_key !== ADMIN_KEY) {
    return json(403, { ok: false, error: 'forbidden' });
  }
  const phone = normPhone(d.phone);
  if (!phone) return json(400, { ok: false, error: 'no_phone' });
  const driver = await getDriver();
  const { TypedValues } = ydb();
  await driver.tableClient.withSession(async (session) => {
    await session.executeQuery(
      `DECLARE $phone AS Utf8; DELETE FROM user_profiles WHERE phone = $phone;`,
      { '$phone': TypedValues.utf8(phone) });
    await session.executeQuery(
      `DECLARE $phone AS Utf8; DELETE FROM user_progress WHERE phone = $phone;`,
      { '$phone': TypedValues.utf8(phone) });
  });
  return json(200, { ok: true, reset: phone, note: 'профиль и прогресс удалены, оплата сохранена' });
}

// (Д) TELEGRAM webhook: ловим «Поделиться контактом» → связываем телефон с chat_id
async function handleTelegram(body) {
  const upd = safeJson(body);
  const msg = upd.message || {};
  const chatId = msg.chat && msg.chat.id;
  if (msg.contact && msg.contact.phone_number && chatId) {
    const phone = normPhone(msg.contact.phone_number);
    await dbSaveTgChat(phone, chatId); // связь телефон↔chat_id в БД
    await tgApi('sendMessage', { chat_id: chatId, text: 'Номер привязан ✅ Теперь коды для входа будут приходить сюда.' });
  } else if (msg.text === '/start' && chatId) {
    await tgApi('sendMessage', {
      chat_id: chatId,
      text: 'Нажмите кнопку, чтобы привязать номер для входа:',
      reply_markup: { keyboard: [[{ text: '📱 Поделиться номером', request_contact: true }]], resize_keyboard: true, one_time_keyboard: true },
    });
  }
  return json(200, { ok: true });
}

function safeJson(s) { try { return JSON.parse(s || '{}'); } catch { return {}; } }
