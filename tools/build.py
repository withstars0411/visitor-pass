#!/usr/bin/env python3
"""명단 CSV로 독립 실행형 index.html을 만든다. 방문증 이미지까지 한 파일에 들어간다.

사용법:  python3 tools/build.py [명단.csv] [출력.html]
  명단.csv   기본값 tools/roster.csv  (열: 학년,반,번호,성명,비고)
  출력.html  기본값 저장소 맨 위의 index.html
필요한 것: Python 3, cryptography  (pip install cryptography)

명단은 이름 대신 해시와 암호문만 페이지에 넣는다.
- 한글 이름 학생: sha256("h|학년|반|정규화한이름") 앞 32자리만 저장
- 영문 이름 학생: 영문 이름과 비고(한글 이름)를 AES-GCM으로 암호화해 저장.
  영문 이름과 한글 이름 어느 쪽으로 입력해도 같은 방문증을 찾는다.
정규화: NFC, 공백 모두 제거, 대문자.
"""
import base64, csv, hashlib, json, os, re, sys, unicodedata
from collections import defaultdict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'roster.csv')
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '..', 'index.html')
if not os.path.exists(src):
    sys.exit(f'명단 파일이 없습니다: {src}\ntools/roster.example.csv 형식을 참고해 tools/roster.csv를 만들어 주세요.')


# 발급 기록 웹앱 주소(선택): tools/config.json 의 "log_url". 없으면 기록 기능이 꺼진다.
log_url = ''
CONFIG = os.path.join(HERE, 'config.json')
if os.path.exists(CONFIG):
    log_url = json.load(open(CONFIG, encoding='utf-8')).get('log_url', '').strip()
    if log_url and not log_url.startswith('https://script.google.com/macros/s/'):
        sys.exit('config.json의 log_url은 https://script.google.com/macros/s/.../exec 형식이어야 합니다.')


def norm(s):
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', s)).upper()


def sha(s):
    return hashlib.sha256(s.encode('utf-8')).digest()


idx, classes, owners = {}, defaultdict(int), {}
n_rows = n_foreign = n_ko = 0

with open(src, encoding='utf-8-sig', newline='') as f:
    rows = list(csv.reader(f))
head, body = rows[0], rows[1:]
if head[:4] != ['학년', '반', '번호', '성명']:
    sys.exit(f'첫 줄이 "학년,반,번호,성명,비고" 형식이 아닙니다: {head}')

for r in body:
    if not r or not r[0].strip():
        continue
    g, c, num, name = [x.strip() for x in r[:4]]
    note = r[4].strip() if len(r) > 4 else ''
    n_rows += 1
    classes[g] = max(classes[g], int(c))
    foreign = bool(re.search(r'[A-Za-z]', name))
    names = [name] + ([note] if (foreign and note) else [])
    if foreign:
        n_foreign += 1
        n_ko += bool(note)
        if not note:
            print(f'참고: {g}학년 {c}반 {num}번의 영문 이름에 비고(한글 이름)가 비어 있습니다.')
    for nm in names:
        look = f'{g}|{c}|{norm(nm)}'
        h = hashlib.sha256(('h|' + look).encode()).hexdigest()[:32]
        if h in idx:
            sys.exit(f'같은 학급에 같은 이름이 있습니다: {g}학년 {c}반 {nm} (앞서 나온 {owners[h]})')
        owners[h] = (g, c, num)
        if foreign:
            payload = json.dumps({'en': re.sub(r'\s+', ' ', unicodedata.normalize('NFC', name)),
                                  'ko': unicodedata.normalize('NFC', note)}, ensure_ascii=False).encode()
            iv = os.urandom(12)
            idx[h] = base64.b64encode(iv + AESGCM(sha('k|' + look)).encrypt(iv, payload, None)).decode()
        else:
            idx[h] = ''

data = {'idx': idx, 'classes': {k: classes[k] for k in sorted(classes)}}
tpl = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
bg = base64.b64encode(open(os.path.join(HERE, 'pass-bg.jpg'), 'rb').read()).decode()
assert "/*__BG__*/''" in tpl and '/*__DATA__*/null' in tpl and "/*__LOG__*/''" in tpl
tpl = tpl.replace("/*__LOG__*/''", json.dumps(log_url))
tpl = tpl.replace("/*__BG__*/''", "'data:image/jpeg;base64," + bg + "'")
tpl = tpl.replace('/*__DATA__*/null', json.dumps(data, ensure_ascii=False, separators=(',', ':')))

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Crect width='32' height='32' rx='7' fill='%232f55b5'/%3E%3Crect x='7' y='9' width='18' height='14' rx='2' fill='%23fff'/%3E"
           "%3Crect x='10' y='13' width='12' height='2' fill='%232f55b5'/%3E%3Crect x='10' y='17' width='8' height='2' fill='%232f55b5'/%3E%3C/svg%3E")
HEAD = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex">\n'
        f'<link rel="icon" href="{FAVICON}">\n')
cut = tpl.index('</style>') + len('</style>')
html = (HEAD + tpl[:cut] + '\n</head>\n<body>\n<noscript>이 페이지는 JavaScript를 켜야 사용할 수 있습니다.</noscript>' +
        tpl[cut:] + '\n</body>\n</html>\n')
open(out, 'w', encoding='utf-8').write(html)

print(f'학생 {n_rows}명, 영문 이름 {n_foreign}명(비고 입력 {n_ko}명), 해시 {len(idx)}개')
print('학년별 학급 수:', data['classes'])
print('발급 기록:', log_url or '꺼짐 (tools/config.json에 log_url이 없습니다)')
print('저장:', os.path.abspath(out), f'({os.path.getsize(out) // 1024}KB)')
