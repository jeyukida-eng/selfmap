/**
 * 단체 도시락 주문 접수 앱 (Google Apps Script)
 * - 손님: 웹앱 주소로 주문서 작성 → 구글 시트에 저장
 * - 사장님: 텔레그램(즉시 푸시) + 이메일로 새 주문 알림
 *
 * 설치 방법은 같은 폴더의 README.md 참고.
 */

// ===== 가게에 맞게 수정하는 부분 =====
const CONFIG = {
  shopName: '도시락 단체주문',
  menus: [
    '유부초밥+샌드위치 도시락',
    '유부초밥 도시락',
    '샌드위치 도시락',
  ],
  minQty: 5,          // 최소 주문 수량
  maxQty: 300,
  leadDays: 1,        // 며칠 전까지 주문 가능 (1 = 내일부터 선택 가능)
  maxDates: 10,       // 한 번에 고를 수 있는 날짜 수
  pickupAllowed: true,
  notice: '주문 확인 후 연락드려 결제·예약금을 안내해 드립니다.',
  ownerEmail: '',     // 비워두면 스크립트 소유자 Gmail로 발송
  sheetName: '주문',
  timezone: 'Asia/Seoul',
};
// =====================================

const HEADERS = [
  '접수번호', '접수시각', '단체명', '담당자', '연락처', '필요날짜', '메뉴', '수량',
  '수령방법', '수령시간', '배달장소', '요청사항', '상태', '메모',
];
const STATUSES = ['접수', '확정', '완료', '취소'];

function doGet() {
  const t = HtmlService.createTemplateFromFile('Index');
  // </script> 깨짐 방지
  t.config = JSON.stringify(publicConfig_()).replace(/</g, '\\u003c');
  return t.evaluate()
    .setTitle(CONFIG.shopName)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function publicConfig_() {
  return {
    shopName: CONFIG.shopName,
    menus: CONFIG.menus,
    minQty: CONFIG.minQty,
    maxQty: CONFIG.maxQty,
    maxDates: CONFIG.maxDates,
    pickupAllowed: CONFIG.pickupAllowed,
    notice: CONFIG.notice,
    minDate: dateAfter_(CONFIG.leadDays),
  };
}

/** 주문서 제출 (Index.html 에서 google.script.run 으로 호출) */
function submitOrder(form) {
  if (form && form.website) return { ok: true, ids: [] }; // 스팸봇 함정 필드
  const order = validate_(form || {});

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  let ids;
  try {
    const sheet = getSheet_();
    const now = new Date();
    const stamp = Utilities.formatDate(now, CONFIG.timezone, 'yyMMdd-HHmmss');
    const at = Utilities.formatDate(now, CONFIG.timezone, 'yyyy-MM-dd HH:mm');
    ids = order.dates.map((_, i) => order.dates.length > 1 ? `${stamp}-${i + 1}` : stamp);
    const rows = order.dates.map((d, i) => [
      ids[i], at, order.org, order.name, order.phone, d, order.menu, order.qty,
      order.method, order.time, order.place, order.requests, '접수', '',
    ].map(safeCell_));
    sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, HEADERS.length).setValues(rows);
  } finally {
    lock.releaseLock();
  }

  // 알림 실패가 주문 접수를 막지 않도록 분리
  try { notify_(order, ids); } catch (e) { console.error('알림 실패', e); }
  return { ok: true, ids: ids };
}

function validate_(f) {
  const s = (v, max) => String(v == null ? '' : v).trim().slice(0, max);
  const o = {
    org: s(f.org, 60),
    name: s(f.name, 30),
    phone: s(f.phone, 20).replace(/[^\d-]/g, ''),
    menu: s(f.menu, 60),
    qty: parseInt(f.qty, 10),
    method: s(f.method, 5),
    time: s(f.time, 5),
    place: s(f.place, 120),
    requests: s(f.requests, 500),
    dates: Array.isArray(f.dates) ? f.dates.map(d => s(d, 10)) : [],
  };
  const fail = msg => { throw new Error(msg); };

  if (!o.org) fail('단체명(회사명)을 입력해 주세요.');
  if (!o.name) fail('담당자 성함을 입력해 주세요.');
  if (!/^01\d-?\d{3,4}-?\d{4}$|^0\d{1,2}-?\d{3,4}-?\d{4}$/.test(o.phone)) fail('연락처 형식을 확인해 주세요.');
  if (CONFIG.menus.indexOf(o.menu) < 0) fail('메뉴를 선택해 주세요.');
  if (!(o.qty >= CONFIG.minQty && o.qty <= CONFIG.maxQty)) fail(`수량은 ${CONFIG.minQty}~${CONFIG.maxQty}개 사이로 입력해 주세요.`);
  if (o.method !== '배달' && !(o.method === '픽업' && CONFIG.pickupAllowed)) fail('수령 방법을 선택해 주세요.');
  if (!/^\d{2}:\d{2}$/.test(o.time)) fail('수령(배달) 시간을 선택해 주세요.');
  if (o.method === '배달' && !o.place) fail('배달 받을 장소를 입력해 주세요.');
  if (o.method === '픽업') o.place = '';
  if (f.consent !== true) fail('개인정보 수집·이용에 동의해 주세요.');

  const minDate = dateAfter_(CONFIG.leadDays);
  o.dates = Array.from(new Set(o.dates)).sort();
  if (!o.dates.length) fail('필요한 날짜를 선택해 주세요.');
  if (o.dates.length > CONFIG.maxDates) fail(`날짜는 최대 ${CONFIG.maxDates}개까지 선택할 수 있어요.`);
  o.dates.forEach(d => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) fail('날짜 형식이 올바르지 않아요.');
    if (d < minDate) fail(`${d}은(는) 주문 가능 날짜가 지났어요. ${minDate}부터 가능합니다.`);
  });
  return o;
}

function notify_(o, ids) {
  const dates = o.dates.map(fmtDate_).join(', ');
  const lines = [
    `🍱 새 단체주문 (${o.dates.length}건)`,
    `단체/담당: ${o.org} (${o.name})`,
    `연락처: ${o.phone}`,
    `날짜: ${dates}`,
    `메뉴: ${o.menu} × ${o.qty}개`,
    `수령: ${o.method} ${o.time}${o.place ? ' / ' + o.place : ''}`,
    o.requests ? `요청: ${o.requests}` : '',
    `접수번호: ${ids.join(', ')}`,
  ].filter(Boolean);
  const text = lines.join('\n');

  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('TELEGRAM_TOKEN');
  const chatId = props.getProperty('TELEGRAM_CHAT_ID');
  if (token && chatId) {
    const res = UrlFetchApp.fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'post',
      payload: { chat_id: chatId, text: text },
      muteHttpExceptions: true,
    });
    if (res.getResponseCode() !== 200) console.error('텔레그램 실패', res.getContentText());
  }

  const to = CONFIG.ownerEmail || Session.getEffectiveUser().getEmail();
  if (to) {
    MailApp.sendEmail({
      to: to,
      subject: `[새 주문] ${o.org} · ${dates} · ${o.qty}개`,
      body: text + '\n\n시트: ' + SpreadsheetApp.getActiveSpreadsheet().getUrl(),
    });
  }
}

function getSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(CONFIG.sheetName);
  if (!sh) sh = ss.insertSheet(CONFIG.sheetName);
  if (sh.getLastRow() === 0) {
    sh.appendRow(HEADERS);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, HEADERS.length).setFontWeight('bold').setBackground('#f1f3f4');
    const statusCol = HEADERS.indexOf('상태') + 1;
    sh.getRange(2, statusCol, sh.getMaxRows() - 1, 1).setDataValidation(
      SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).build());
  }
  return sh;
}

// 시트 수식 주입 방지 (=, +, -, @ 로 시작하는 값)
function safeCell_(v) {
  return typeof v === 'string' && /^[=+\-@]/.test(v) ? "'" + v : v;
}

function dateAfter_(days) {
  return Utilities.formatDate(new Date(Date.now() + days * 864e5), CONFIG.timezone, 'yyyy-MM-dd');
}

function fmtDate_(d) {
  const [y, m, day] = d.split('-').map(Number);
  const w = '일월화수목금토'[new Date(y, m - 1, day).getDay()];
  return `${m}.${day}.(${w})`;
}

// ===== 설치할 때 한 번씩 실행하는 함수 =====

/** 텔레그램 봇에게 아무 메시지나 보낸 뒤 실행 → 실행 로그에 chat_id 표시 */
function setupFindTelegramChatId() {
  const token = PropertiesService.getScriptProperties().getProperty('TELEGRAM_TOKEN');
  if (!token) throw new Error('먼저 스크립트 속성에 TELEGRAM_TOKEN 을 저장하세요.');
  const res = JSON.parse(UrlFetchApp.fetch(`https://api.telegram.org/bot${token}/getUpdates`).getContentText());
  const ids = (res.result || []).map(u => u.message && u.message.chat.id).filter(Boolean);
  console.log(ids.length ? 'chat_id: ' + Array.from(new Set(ids)).join(', ') : '봇에게 메시지를 먼저 보내주세요.');
}

/** 시트 생성 + 테스트 알림 발송 (권한 승인도 이때 진행됨) */
function setupTestNotify() {
  getSheet_();
  notify_({
    org: '테스트단체', name: '홍길동', phone: '010-0000-0000', menu: CONFIG.menus[0], qty: 10,
    method: '배달', time: '09:00', place: '테스트 장소', requests: '알림 테스트입니다',
    dates: [dateAfter_(CONFIG.leadDays)],
  }, ['TEST']);
}
