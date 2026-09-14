#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenAPI 계약 전수 대조 — 엔드포인트·스키마 변경 자동 감지.

    python tools/dump_openapi.py --out backend/tests/snapshots/openapi_baseline_YYYYMMDD.txt
    python tools/dump_openapi.py --baseline backend/tests/snapshots/openapi_baseline_YYYYMMDD.txt [--expect-added N]
    python tools/dump_openapi.py --selftest

FastAPI가 만드는 `/openapi.json`을 두 평면(엔드포인트 / 스키마)으로 펼쳐
기준선과 대조한다. `tools/dump_constraints.py`와 **같은 형태**다 — 인자,
종료코드, 단계 구분, [OK]/[!!]/[RED] 마커, 기준선 파일 규약이 모두 같다.

왜 만드는가(9/13 devlog 6-3절): **계약 불일치는 런타임에 터진다.** 9/13에
`/openapi.json`의 `components.schemas` 12개가 **전부 요청·검증용**이고 응답
스키마가 **0개**라는 사실이 있었는데, 그날의 검증 중 이것을 볼 수 있는
도구가 하나도 없었다 — `npm run build`도 pytest도 제약 대조도 OpenAPI를
보지 않는다. 그래서 9/14 조사에서야 드러났다.

## 두 평면으로 나눈다

`dump_constraints`는 제약이라는 **평면 하나**였다. OpenAPI는 둘이다.

    OP      키 = "METHOD path"     정의 = 정규화된 operation
    SCHEMA  키 = 스키마명           정의 = 정규화된 스키마 본문

🔴 **`$ref`를 전개(inline)하지 않는다.** 전개하면 `HTTPValidationError` 한
글자가 바뀔 때 그것을 참조하는 **엔드포인트가 전부 동시에 빨개진다.**
9/9에 오탐 12건으로 검증 항목 하나가 통째로 무력화된 선례가 있어, 신호가
뭉개지는 쪽이 더 위험하다.

**그 대신 생기는 구멍은 역참조로 막는다** — 스키마가 바뀌면 **그것을
참조하는 엔드포인트 목록을 반드시 함께 출력**한다. 이것은 선택이 아니라
비전개 결정의 성립 조건이며, `--selftest` 케이스 ⑦이 그것을 시험한다.

## 비교에서 빼는 것

`title` · `description` · `summary`를 **재귀로 제거**한다. 셋 다 계약이
아니다 —

    description  라우터·DTO 도크스트링 **원문**이 통째로 들어간다.
                 주석 한 줄만 고쳐도 매번 빨개져서 도구가 곧 무시된다.
    summary      라우터 summary= 문자열. 같은 이유.
    title        전부 파생값이다. 응답 "Response Create Room ..."은
                 함수명에서, 필드 "Room Name"은 필드명에서, 스키마
                 "RoomCreateRequest"는 스키마명에서 나온다 —
                 셋 다 이미 다른 곳이 잡는다.

반대로 **`security`와 `operationId`는 반드시 본다.** 전자가 사라지면
엔드포인트가 공개되고(그래서 [RED]다), 후자는 openapi-typescript가
`operations["..."]` 키를 만드는 근거라 바뀌면 프론트 타입 이름이 바뀐다.

## 기준선은 `backend/tests/snapshots/` 에 둔다 — **커밋한다**

`dump_constraints`의 제약 기준선은 `.backup/`(=`.gitignore` 대상)에
있지만 **이 도구는 다르게 간다.** 둘은 성격이 다르다 —

    .backup/                 복구용 백업. 커밋되지 않는 것이 맞다
    backend/tests/snapshots/ 검증 자산. 코드와 함께 움직여야 한다

기준선이 커밋되지 않으면 **브랜치를 전환하거나 롤백했을 때 코드와
어긋난다.** 10/8 Feature Freeze 이후 `hotfix/*` 브랜치로 가면
브랜치마다 다른 기준선을 보게 되는데, 그러면 *"이 브랜치에서 계약이
바뀌었나"*를 판정할 수 없다. 계약은 코드의 일부이므로 기준선도
코드와 같은 이력을 따라야 한다.

파일명은 `openapi_baseline_<YYYYMMDD>[_<태그>].txt`다.

## 읽기만 한다

**서버를 띄우지 않고 DB에 붙지 않는다.** `app.main`을 import해
`app.openapi()`를 부를 뿐이며, lifespan이 돌지 않아 커넥션이 열리지 않는다.
`dump_constraints`가 *"컨테이너를 임의로 기동하지 않는다"*로 둔 자리에
대응한다 — import가 실패하면 멈추고 보고한다(종료코드 2).

종료코드: 0 = 통과, 1 = 불일치·삭제 경보, 2 = 환경 문제(import 실패 등)
"""

import sys
import os
import json
import argparse
from collections import Counter


# ==============================================================
# 상수 — 집계 범위와 파일 형식의 SSOT
# ==============================================================
APP_IMPORT = "app.main"          # FastAPI 인스턴스가 있는 모듈
APP_ATTR = "app"

PLANES = ("OP", "SCHEMA")
PLANE_LABEL = {"OP": "엔드포인트", "SCHEMA": "스키마"}

# 계약이 아닌 키. 재귀로 제거한다(위 도크스트링 참고).
DROP_KEYS = ("title", "description", "summary")

SEP = "|"
FIELDS = 4          # 평면|키|보조|정의

REF_PREFIX = "#/components/schemas/"


# ==============================================================
# 보고 — dump_constraints.py와 같은 형식
# ==============================================================
class Report(object):
    def __init__(self):
        self.red = []
        self.warn = []

    def ok(self, msg):
        print("   [OK ] " + msg)

    def info(self, msg):
        print("         " + msg)

    def warn_(self, msg):
        self.warn.append(msg)
        print("   [!! ] " + msg)

    def red_(self, msg):
        self.red.append(msg)
        print("   [RED] " + msg)


def _stage(n, title):
    print("")
    print("-" * 70)
    print(" %d) %s" % (n, title))
    print("-" * 70)


def _delta(a, b):
    return "%s -> %s (%+d)" % (format(a, ","), format(b, ","), b - a)


# ==============================================================
# 정규화 — 순서가 흔들리면 diff가 의미를 잃는다
# ==============================================================
def strip_prose(node):
    """`title`·`description`·`summary`를 **재귀로** 제거한 사본을 돌려준다.

    원본을 바꾸지 않는다 — 이 도구는 스펙을 읽기만 한다.
    """
    if isinstance(node, dict):
        return {k: strip_prose(v) for k, v in node.items() if k not in DROP_KEYS}
    if isinstance(node, list):
        return [strip_prose(v) for v in node]
    return node


def canon(node):
    """정규화 JSON 문자열. **매번 같은 바이트가 나와야 한다.**

    `sort_keys`로 키 순서를 고정하고, 개행을 공백으로 바꾼다 — 줄 단위
    파싱이 깨지지 않게 하려는 것이며 `dump_constraints`가
    `pg_get_constraintdef`의 개행을 바꾼 것과 같은 이유다.
    """
    s = json.dumps(strip_prose(node), sort_keys=True, ensure_ascii=False,
                   separators=(",", ":"))
    return s.replace("\n", " ").replace("\r", " ")


def _response_codes(op):
    """응답 코드 집합을 보조 칸 문자열로. 정렬해 순서를 고정한다."""
    codes = sorted(str(c) for c in op.get("responses", {}))
    return ",".join(codes)


# ==============================================================
# 스펙 → rows
# ==============================================================
def spec_to_rows(spec):
    """OpenAPI 스펙 dict → `(평면, 키, 보조, 정의)` 리스트.

    정렬: **OP(경로 → 메서드) 먼저, 그다음 SCHEMA(이름)**. 매번 동일하다.
    """
    ops = []
    for path, methods in (spec.get("paths") or {}).items():
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue            # 'parameters' 같은 path 레벨 키는 건너뛴다
            key = "%s %s" % (method.upper(), path)
            ops.append((path, method.lower(), key,
                        _response_codes(op), canon(op)))
    ops.sort(key=lambda r: (r[0], r[1]))

    rows = [("OP", key, aux, defn) for _, _, key, aux, defn in ops]

    schemas = (spec.get("components") or {}).get("schemas") or {}
    for name in sorted(schemas):
        rows.append(("SCHEMA", name, "", canon(schemas[name])))

    return rows


def load_spec_from_app():
    """`app.main`을 import해 스펙을 만든다. **서버를 띄우지 않는다.**

    :raises SystemExit: import 실패 시 종료코드 2(환경 문제).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    backend = os.path.join(os.path.dirname(here), "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    try:
        mod = __import__(APP_IMPORT, fromlist=[APP_ATTR])
        app = getattr(mod, APP_ATTR)
        return app.openapi()
    except Exception as exc:                      # noqa: BLE001
        print("=" * 70)
        print(" [환경] FastAPI 앱을 불러오지 못했다 — 스펙을 만들 수 없다.")
        print("=" * 70)
        print("   %s: %s" % (type(exc).__name__, exc))
        print("   확인: backend/.venv 의존성, %s 의 import 오류" % APP_IMPORT)
        sys.exit(2)


# ==============================================================
# 파일 입출력 — dump_constraints와 같은 규약
# ==============================================================
def render(rows):
    return "".join(SEP.join(r) + "\n" for r in rows)


def parse_dump(path):
    """`평면|키|보조|정의` 줄들을 rows로. **정의에 든 SEP는 보존한다.**"""
    rows = []
    has_def = True
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split(SEP, FIELDS - 1)
            if len(parts) == FIELDS:
                plane, key, aux, defn = parts
            elif len(parts) == 3:
                plane, key, aux = parts
                defn = ""
                has_def = False
            else:
                continue
            if plane not in PLANES:
                continue
            rows.append((plane, key, aux, defn.strip()))
    return rows, has_def


# ==============================================================
# 대조 — 순수 함수. 앱 없이 파일끼리도 돌아간다(--selftest가 쓴다).
# ==============================================================
def compare(base_rows, cur_rows):
    """(추가, 삭제, 정의변경, 코드변경). 키는 `(평면, 키)`."""
    b = {(r[0], r[1]): r for r in base_rows}
    c = {(r[0], r[1]): r for r in cur_rows}

    added = [c[k] for k in c if k not in b]
    removed = [b[k] for k in b if k not in c]

    changed, code_changed = [], []
    for k in b:
        if k not in c:
            continue
        br, cr = b[k], c[k]
        if br[3] != cr[3]:
            changed.append((br[0], br[1], br[3], cr[3]))
        if br[0] == "OP" and br[2] != cr[2]:
            code_changed.append((br[1], br[2], cr[2]))

    added.sort(key=lambda r: (r[0], r[1]))
    removed.sort(key=lambda r: (r[0], r[1]))
    changed.sort(key=lambda r: (r[0], r[1]))
    code_changed.sort()
    return added, removed, changed, code_changed


def referencing_ops(rows, schema_name):
    """`schema_name`을 참조하는 OP 키 목록.

    🔴 **$ref 비전개 결정의 성립 조건이다.** 스키마 변경이 어느 엔드포인트에
    닿는지 사람이 연결하지 못하면 비전개는 그냥 구멍이다.
    """
    needle = REF_PREFIX + schema_name + '"'
    return sorted(r[1] for r in rows if r[0] == "OP" and needle in r[3])


def _security_of(defn):
    """정의 JSON에서 security를 꺼낸다. 못 읽으면 None(판정 보류)."""
    try:
        return json.loads(defn).get("security")
    except Exception:                             # noqa: BLE001
        return None


def plane_counts(rows):
    c = Counter(r[0] for r in rows)
    return {k: c.get(k, 0) for k in PLANES}


def _counts_line(rows):
    pc = plane_counts(rows)
    return "OP %d / SCHEMA %d = %d" % (pc["OP"], pc["SCHEMA"], len(rows))


def _fmt(r):
    return "%s %s" % (r[0], r[1])


# ==============================================================
# 판정
# ==============================================================
def run_compare(base_rows, cur_rows, base_has_def, expect_added, rep,
                base_label, cur_label):
    print("=" * 70)
    print(" OpenAPI 계약 전수 대조 — 두 평면(OP / SCHEMA), 산문 제외")
    print("=" * 70)
    print(" 기준선 : %s" % base_label)
    print(" 현재   : %s" % cur_label)
    print(" 제외   : %s (계약이 아니다 — 도크스트링·파생 title)"
          % ", ".join(DROP_KEYS))

    added, removed, changed, code_changed = compare(base_rows, cur_rows)

    _stage(1, "건수")
    print("         %s" % _delta(len(base_rows), len(cur_rows)))
    print("         기준선  %s" % _counts_line(base_rows))
    print("         현재    %s" % _counts_line(cur_rows))
    bc, cc = plane_counts(base_rows), plane_counts(cur_rows)
    print("         평면별 증분  " + " / ".join(
        "%s %+d" % (p, cc[p] - bc[p]) for p in PLANES))

    _stage(2, "추가된 것")
    if not added:
        print("         없음")
    for r in added:
        print("         + %s" % _fmt(r))
        if r[0] == "OP" and r[2]:
            print("             응답 %s" % r[2])

    _stage(3, "삭제된 것  [건수와 무관하게 경보한다]")
    if not removed:
        print("         없음")
    else:
        for r in removed:
            print("         - %s" % _fmt(r))
            if r[0] == "SCHEMA":
                refs = referencing_ops(base_rows, r[1])
                print("             기준선에서 참조하던 엔드포인트: %s"
                      % (", ".join(refs) if refs else "(없음)"))
        rep.red_("계약이 %d건 사라졌다 — 선언한 교체인지 확인하라. "
                 "삭제는 --expect-added와 무관하게 경보다." % len(removed))

    _stage(4, "정의가 바뀐 것  [건수만 세면 못 잡는다]")
    if not base_has_def:
        rep.warn_("기준선에 정의가 없어 이 단계를 건너뛴다. "
                  "--out으로 기준선을 다시 뽑아라.")
    elif not changed:
        print("         없음")
    else:
        sec_lost = []
        for plane, key, bd, cd in changed:
            print("         ~ %s %s" % (plane, key))
            print("             기준선: %s" % _clip(bd))
            print("             현재  : %s" % _clip(cd))
            if plane == "SCHEMA":
                # 🔴 비전개 결정의 성립 조건 — 어디에 닿는지 반드시 보여준다.
                refs = referencing_ops(cur_rows, key)
                print("             ↳ 이 스키마를 참조하는 엔드포인트: %s"
                      % (", ".join(refs) if refs else "(없음)"))
            if plane == "OP":
                bs, cs = _security_of(bd), _security_of(cd)
                if bs and not cs:
                    sec_lost.append(key)
        if sec_lost:
            rep.red_("security가 사라진 엔드포인트 %d건 — 인증 없이 열린다: %s"
                     % (len(sec_lost), ", ".join(sec_lost)))
        rep.warn_("정의가 바뀐 것 %d건 — 건수는 불변이라 증분 판정에 "
                  "걸리지 않는다. 선언과 대조하라." % len(changed))

    _stage(5, "응답 코드 집합 변화  [코드가 사라지면 경보한다]")
    if not code_changed:
        print("         없음")
    else:
        lost = []
        for key, ba, ca in code_changed:
            bset = set(x for x in ba.split(",") if x)
            cset = set(x for x in ca.split(",") if x)
            gone, new = sorted(bset - cset), sorted(cset - bset)
            print("         ~ %s" % key)
            print("             기준선: %s" % (ba or "(없음)"))
            print("             현재  : %s" % (ca or "(없음)"))
            if gone:
                print("             사라짐: %s" % ", ".join(gone))
                lost.append("%s(%s)" % (key, ",".join(gone)))
            if new:
                print("             추가  : %s" % ", ".join(new))
        if lost:
            rep.red_("응답 코드가 사라진 엔드포인트 %d건 — 프론트의 그 분기는 "
                     "죽은 코드가 되고 해당 상황은 500으로 나간다: %s"
                     % (len(lost), "; ".join(lost)))
        else:
            rep.warn_("응답 코드가 늘어난 엔드포인트 %d건 — 선언한 변경인지 "
                      "확인하라." % len(code_changed))

    _stage(6, "증분 판정")
    delta = len(cur_rows) - len(base_rows)
    if expect_added is None:
        print("         --expect-added 없음 — 증분 %+d 보고만 한다." % delta)
    elif delta == expect_added:
        rep.ok("증분 %+d — 선언(%+d)과 일치" % (delta, expect_added))
    else:
        rep.red_("증분 %+d — 선언은 %+d다. 일치하지 않는다."
                 % (delta, expect_added))

    print("")
    print("=" * 70)
    if rep.red:
        print(" [RED] %d건 — 선언과 어긋난다. 진행하지 마라." % len(rep.red))
        for m in rep.red:
            print("   - %s" % m.splitlines()[0])
    if rep.warn:
        print(" [!! ] %d건 — 선언한 변경인지 확인하라." % len(rep.warn))
        for m in rep.warn:
            print("   - %s" % m.splitlines()[0])
    if not rep.red and not rep.warn:
        print(" 선언과 일치. 추가 %d / 삭제 %d / 정의변경 %d / 코드변경 %d."
              % (len(added), len(removed), len(changed), len(code_changed)))
    elif not rep.red:
        print(" RED 없음. 위 [!!] 항목이 선언한 변경과 일치하면 진행 가능.")
    return 1 if rep.red else 0


def _clip(s, n=110):
    return s if len(s) <= n else s[:n] + " …(%d자)" % len(s)


# ==============================================================
# --selftest — 답을 아는 고정 케이스. **파일에 의존하지 않는다.**
#
# dump_constraints는 기준선 파일(.backup/)을 읽지만, 이 도구는 기준선이
# 아직 존재하지 않는 날에 만들어진다. 파일에 의존시키면 첫 실행부터
# SKIP이 되어 "자기 검증이 된다"는 등급 3 판정의 근거가 성립하지 않는다.
# ==============================================================
def _ok_resp(code, ref=None):
    schema = {"$ref": REF_PREFIX + ref} if ref else {
        "type": "object", "title": "Response Something"}
    return {code: {"description": "Successful Response",
                   "content": {"application/json": {"schema": schema}}}}


def _selftest_spec():
    post_resp = {}
    post_resp.update(_ok_resp("201"))
    post_resp.update(_ok_resp("409"))
    return {
        "openapi": "3.1.0",
        "info": {"title": "셀프테스트", "version": "0.1.0"},
        "paths": {
            "/things": {
                "get": {
                    "tags": ["things"],
                    "summary": "목록",
                    "description": "목록을 돌려준다.",
                    "operationId": "list_things_things_get",
                    "security": [{"OAuth2PasswordBearer": []}],
                    "responses": _ok_resp("200"),
                },
                "post": {
                    "tags": ["things"],
                    "summary": "생성",
                    "description": "새로 만든다.",
                    "operationId": "create_thing_things_post",
                    "security": [{"OAuth2PasswordBearer": []}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": REF_PREFIX + "ThingCreate"}}},
                    },
                    "responses": post_resp,
                },
            },
        },
        "components": {"schemas": {
            "ThingCreate": {
                "type": "object",
                "title": "ThingCreate",
                "description": "생성 요청.",
                "required": ["name"],
                "properties": {"name": {"type": "string", "title": "Name"}},
            },
        }},
    }


def _deep(obj):
    return json.loads(json.dumps(obj))


def _selftest():
    print("=" * 70)
    print(" 회귀 테스트 — 답을 아는 고정 케이스로 검증기를 시험한다")
    print("=" * 70)
    print(" 픽스처: 내장(파일 비의존) — 엔드포인트 2 + 스키마 1")

    spec = _selftest_spec()
    rows = spec_to_rows(spec)
    checks = []

    # ⓪ 픽스처 자체
    pc = plane_counts(rows)
    checks.append(("픽스처 OP 수", pc["OP"], 2))
    checks.append(("픽스처 SCHEMA 수", pc["SCHEMA"], 1))

    # ① 자기 자신과 대조 — 전부 0
    a, r, ch, cc = compare(rows, rows)
    checks.append(("자기 자신 — 추가", len(a), 0))
    checks.append(("자기 자신 — 삭제", len(r), 0))
    checks.append(("자기 자신 — 정의변경", len(ch), 0))
    checks.append(("자기 자신 — 코드변경", len(cc), 0))

    # ② 한 줄(OP) 제거 — 삭제 1
    dropped = [x for x in rows if x[1] != "GET /things"]
    a2, r2, ch2, _ = compare(rows, dropped)
    checks.append(("OP 제거 — 삭제 탐지", len(r2), 1))
    checks.append(("OP 제거 — 추가 0", len(a2), 0))
    checks.append(("OP 제거 — 건수 감소", len(rows) - len(dropped), 1))

    # ③ 경로는 그대로 두고 스키마만 변경 — 건수 불변인데 변경 1  [핵심]
    s3 = _deep(spec)
    s3["components"]["schemas"]["ThingCreate"]["properties"]["age"] = {
        "type": "integer", "title": "Age"}
    rows3 = spec_to_rows(s3)
    a3, r3, ch3, _ = compare(rows, rows3)
    checks.append(("스키마만 변경 — 건수 불변", len(rows3) - len(rows), 0))
    checks.append(("스키마만 변경 — 변경 탐지", len(ch3), 1))
    checks.append(("스키마만 변경 — 추가·삭제 0", len(a3) + len(r3), 0))

    # ④ 응답 코드 하나(409) 제거 — 건수 불변인데 코드 소실 탐지
    s4 = _deep(spec)
    del s4["paths"]["/things"]["post"]["responses"]["409"]
    rows4 = spec_to_rows(s4)
    a4, r4, ch4, cc4 = compare(rows, rows4)
    checks.append(("409 제거 — 건수 불변", len(rows4) - len(rows), 0))
    checks.append(("409 제거 — 코드변경 탐지", len(cc4), 1))
    lost4 = 0
    if cc4:
        b, c = set(cc4[0][1].split(",")), set(cc4[0][2].split(","))
        lost4 = len(b - c)
    checks.append(("409 제거 — 사라진 코드 1", lost4, 1))

    # ⑤ security 제거 — RED 판정
    s5 = _deep(spec)
    del s5["paths"]["/things"]["get"]["security"]
    rows5 = spec_to_rows(s5)
    _, _, ch5, _ = compare(rows, rows5)
    sec_lost = 0
    for plane, key, bd, cd in ch5:
        if plane == "OP" and _security_of(bd) and not _security_of(cd):
            sec_lost += 1
    checks.append(("security 제거 — 소실 탐지", sec_lost, 1))

    # ⑥ 산문만 다른 스펙 — 변경 0이어야 한다  [제외 규칙 검증]
    s6 = _deep(spec)
    s6["paths"]["/things"]["get"]["description"] = "완전히 다른 설명이다." * 5
    s6["paths"]["/things"]["get"]["summary"] = "딴 요약"
    s6["components"]["schemas"]["ThingCreate"]["description"] = "다른 설명"
    s6["components"]["schemas"]["ThingCreate"]["properties"]["name"][
        "title"] = "Totally Different"
    rows6 = spec_to_rows(s6)
    a6, r6, ch6, cc6 = compare(rows, rows6)
    checks.append(("산문만 변경 — 정의변경 0", len(ch6), 0))
    checks.append(("산문만 변경 — 추가·삭제·코드 0",
                   len(a6) + len(r6) + len(cc6), 0))

    # ⑦ 스키마 변경 시 역참조가 실제로 나오는가  [비전개 결정의 성립 조건]
    refs = referencing_ops(rows3, "ThingCreate")
    checks.append(("역참조 — 참조 엔드포인트 수", len(refs), 1))
    checks.append(("역참조 — 대상이 POST /things",
                   1 if refs == ["POST /things"] else 0, 1))
    refs_none = referencing_ops(rows3, "존재하지않는스키마")
    checks.append(("역참조 — 무관한 이름은 0건", len(refs_none), 0))

    # 결과
    print("")
    print("-" * 70)
    print(" 케이스별 결과")
    print("-" * 70)
    failed = 0
    for name, got, want in checks:
        mark = "[OK ]" if got == want else "[RED]"
        if got != want:
            failed += 1
        print("   %s %-34s 기대 %-4s 실제 %s" % (mark, name, want, got))

    print("")
    print("=" * 70)
    if failed:
        print(" [RED] %d건 실패 — 검증기 자신이 망가졌다. 이 도구를 믿지 마라."
              % failed)
        return 1
    print(" 전부 통과(%d건). 검증기가 정상 동작한다." % len(checks))
    return 0


# ==============================================================
def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if "--selftest" in argv:
        return _selftest()

    ap = argparse.ArgumentParser(
        description="OpenAPI 계약 전수 대조 (app.openapi(), 읽기 전용)")
    ap.add_argument("--out", metavar="파일",
                    help="현재 스펙을 이 파일로 저장한다")
    ap.add_argument("--baseline", metavar="파일",
                    help="이 기준선과 현재 스펙을 대조한다")
    ap.add_argument("--expect-added", type=int, metavar="N",
                    help="선언한 증분. 다르면 종료코드 1")
    ap.add_argument("--selftest", action="store_true",
                    help="내장 고정 케이스로 검증기 자신을 시험한다")
    args = ap.parse_args(argv)

    if not args.out and not args.baseline:
        ap.error("--out 또는 --baseline 중 하나는 있어야 한다 (--selftest도 가능)")

    spec = load_spec_from_app()
    cur_rows = spec_to_rows(spec)

    if args.out:
        d = os.path.dirname(args.out)
        if d and not os.path.isdir(d):
            sys.exit("디렉토리가 없다: %s" % d)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(cur_rows))
        print("저장: %s" % args.out)
        print("      %d건 — %s" % (len(cur_rows), _counts_line(cur_rows)))
        print("      형식: 평면|키|보조|정의  (보조 = OP의 응답 코드 집합)")
        print("      정렬: OP(경로 -> 메서드) 먼저, 그다음 SCHEMA(이름)")
        print("      제외: %s" % ", ".join(DROP_KEYS))

    if not args.baseline:
        return 0

    if not os.path.isfile(args.baseline):
        sys.exit("파일이 없다: %s" % args.baseline)
    base_rows, base_has_def = parse_dump(args.baseline)
    rep = Report()
    return run_compare(base_rows, cur_rows, base_has_def, args.expect_added,
                       rep, args.baseline, "app.openapi() (in-process)")


if __name__ == "__main__":
    sys.exit(main())
