/**
 * 일일방문증 발급 기록 받기
 * 방문증 페이지가 방문증을 만들 때마다 학년·반·이름을 보내오면,
 * 명단과 대조해서 맞는 학생만 '발급기록' 탭에 한 줄씩 적는다.
 */
const ROSTER_ID = '1Slqpkx79aLFXbGJQMQiSAHwnAajloXbzImjrHymcIkc'; // 명단 시트 주소에서 /d/ 와 /edit 사이의 값
const ROSTER_TAB = '전체';   // 명단이 들어 있는 탭 이름
const LOG_TAB = '발급기록';  // 기록이 쌓이는 탭 (없으면 자동으로 만든다)

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    const hit = findStudent_(d.grade, d.cls, d.name);
    if (!hit) return reply_({ ok: false, error: 'not_in_roster' });
    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      logSheet_().appendRow([
        Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd HH:mm:ss'),
        Number(d.grade), Number(d.cls), hit.num, hit.name
      ]);
    } finally {
      lock.releaseLock();
    }
    return reply_({ ok: true });
  } catch (err) {
    return reply_({ ok: false, error: String(err) });
  }
}

// 배포한 주소를 브라우저로 열었을 때 켜져 있는지 확인하는 용도
function doGet() {
  return reply_({ ok: true, message: '일일방문증 기록 창구가 켜져 있습니다.' });
}

// 명단에서 학생을 찾는다. 띄어쓰기와 영문 대소문자는 구분하지 않고, 비고의 한글 이름으로도 찾는다.
function findStudent_(grade, cls, name) {
  const cache = CacheService.getScriptCache();
  let json = cache.get('roster');
  if (!json) {
    const rows = SpreadsheetApp.openById(ROSTER_ID).getSheetByName(ROSTER_TAB).getDataRange().getValues();
    const map = {};
    rows.slice(1).forEach(function (r) {
      if (r[0] === '' || r[3] === '') return;
      const v = { num: r[2], name: String(r[3]).trim() };
      map[key_(r[0], r[1], r[3])] = v;
      if (r[4]) map[key_(r[0], r[1], r[4])] = v;
    });
    json = JSON.stringify(map);
    cache.put('roster', json, 300); // 명단을 고치면 5분 안에 반영된다
  }
  return JSON.parse(json)[key_(grade, cls, name)] || null;
}

function key_(grade, cls, name) {
  return [String(grade).trim(), String(cls).trim(),
          String(name).normalize('NFC').replace(/\s+/g, '').toUpperCase()].join('|');
}

function logSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(LOG_TAB);
  if (!sh) {
    sh = ss.insertSheet(LOG_TAB);
    sh.appendRow(['발급 시각', '학년', '반', '번호', '이름']);
    sh.setFrozenRows(1);
  }
  return sh;
}

function reply_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
