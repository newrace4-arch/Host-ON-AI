#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DB 제약 전수 대조 — db_spec 마이그레이션 전후 비교 자동화.

    python tools/dump_constraints.py --out <파일>
    python tools/dump_constraints.py --baseline <파일> [--expect-added N]
    python tools/dump_constraints.py --selftest

`pg_constraint`에서 FK·UNIQUE·EXCLUDE·CHECK를 전수로 뽑아 기준선과 대조한다.
11-20·12-5에서 손으로 돌린 SQL을 그대로 담았다 — **같은 결과가 나와야 한다.**

왜 파일로 만드는가(12-5 4번): 내일 revision ①~⑤ 전후로 같은 SQL을 최소
세 번 돌린다. `-A -F'|' -t` 같은 출력 플래그를 한 번이라도 빠뜨리면 앞뒤
출력 형식이 달라져 `diff`가 통째로 무의미해진다. **9/12 사고가 정확히
"숫자를 손으로 옮기다 틀린" 사고다**(9/11 보고가 40건을 39건으로 적었다).

**이름이 같은데 정의만 바뀌는 경우**를 따로 잡는다. 건수만 세면 못 잡는데,
v1.4에서 정확히 둘이 이 형태다.

    uq_property_channel                     (property_id, channel)
      → NULLS NOT DISTINCT (property_id, channel, room_id)
    inquiry_responses_inquiry_id_fkey       (inquiry_id) → inquiries
      → (inquiry_id, property_id) → inquiries   [이름은 재생성 시 달라질 수 있다]

**DB를 읽기만 한다.** 이 파일에 쓰기 SQL(INSERT/UPDATE/DELETE/ALTER/DROP)을
넣지 않는다. psql은 `-c`로 아래 SELECT 하나만 실행한다.

종료코드: 0 = 통과, 1 = 불일치·삭제 경보, 2 = 환경 문제(컨테이너 등)
"""

import sys
import os
import argparse
import subprocess
from collections import Counter


# ==============================================================
# 상수 — 접속 대상과 집계 범위의 SSOT
#
# 컨테이너·DB·사용자는 docker-compose.yml과 일치한다.
# 인자(--container / --db / --user)로 덮어쓸 수 있다.
# ==============================================================
CONTAINER = "host_on_ai_db"
DB_NAME = "host_on_ai"
DB_USER = "hoston"

EXCLUDE_TABLE = "alembic_version"   # 마이그레이션 관리 테이블 — 스키마가 아니다
CONTYPES = ("f", "u", "x", "c")     # p(PK)는 제외한다 — 11-20·12-5와 동일 범위

KIND = {"f": "FK", "u": "UNIQUE", "x": "EXCLUDE", "c": "CHECK"}

SEP = "|"
FIELDS = 4          # 테이블|제약명|contype|정의

# 11-20·12-5에서 쓴 SQL. 정렬은 테이블 → contype → 제약명 순이며,
# **매번 같은 순서여야 diff가 의미를 갖는다.**
#   pg_get_constraintdef의 개행을 공백으로 바꾸는 것만 다르다. psql -A는
#   개행을 그대로 내보내 한 제약이 두 줄로 쪼개질 수 있고, 그러면 줄 단위
#   파싱이 깨진다. 현재 40건에는 개행이 없어 결과는 동일하다.
SQL = """
SELECT c.relname,
       con.conname,
       con.contype,
       replace(pg_get_constraintdef(con.oid), chr(10), ' ')
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND con.contype IN ('f','u','x','c')
  AND c.relname <> '%s'
ORDER BY c.relname, con.contype, con.conname;
""" % EXCLUDE_TABLE

SELFTEST_BASELINE = os.path.join(".backup", "constraints_baseline_20260912.txt")
EXPECT_SELFTEST_ROWS = 40
EXPECT_SELFTEST_CONTYPE = {"f": 21, "u": 13, "c": 3, "x": 3}


# ==============================================================
# 보고 — verify_checklist.py와 같은 형식
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
# DB 읽기
# ==============================================================
def _docker_running(container):
    """컨테이너가 떠 있는가. 꺼져 있으면 멈추고 보고한다(임의 기동 금지)."""
    try:
        out = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        return None, "docker를 실행할 수 없다: %s" % exc
    if out.returncode != 0:
        return False, out.stderr.decode("utf-8", "replace").strip()
    return out.stdout.decode("utf-8", "replace").strip() == "true", ""


def fetch_current(container, db, user):
    """현재 DB의 제약을 읽어 rows로 돌려준다. 읽기 전용 SELECT 하나뿐이다."""
    running, why = _docker_running(container)
    if running is None:
        sys.exit("[중단] %s" % why)
    if not running:
        sys.exit(
            "[중단] 컨테이너 '%s'가 떠 있지 않다.\n"
            "       이 스크립트는 컨테이너를 기동하지 않는다. 먼저 띄운 뒤\n"
            "       다시 실행하라." % container)

    cmd = ["docker", "exec", container, "psql",
           "-U", user, "-d", db, "-A", "-F", SEP, "-t", "-c", SQL]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        sys.exit("[중단] psql 실패 (exit %d)\n%s"
                 % (proc.returncode,
                    proc.stderr.decode("utf-8", "replace").strip()))

    rows, bad = _parse_lines(proc.stdout.decode("utf-8", "replace"))
    if bad:
        sys.exit("[중단] psql 출력에서 필드 수가 맞지 않는 줄 %d개.\n"
                 "       첫 줄: %s" % (len(bad), bad[0]))
    return rows


# ==============================================================
# 파싱 / 직렬화
# ==============================================================
def _parse_lines(text):
    """`테이블|제약명|contype|정의` 줄들을 rows로. 정의에 든 SEP는 보존한다."""
    rows, bad = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(SEP, FIELDS - 1)   # 정의는 쪼개지 않는다
        if len(parts) == FIELDS:
            table, name, contype, definition = parts
        elif len(parts) == 3:
            # 9/12 최초 기준선이 이 형태다(정의 없이 종류 라벨만).
            table, name, contype = parts
            definition = ""
        else:
            bad.append(line)
            continue
        if contype not in CONTYPES:
            bad.append(line)
            continue
        rows.append((table, name, contype, definition.strip()))
    return rows, bad


def parse_dump(path):
    """파일을 읽어 (rows, has_definition)."""
    with open(path, encoding="utf-8") as fh:
        rows, bad = _parse_lines(fh.read())
    if bad:
        sys.exit("[중단] %s 에서 해석할 수 없는 줄 %d개.\n       첫 줄: %s"
                 % (path, len(bad), bad[0]))
    # 9/12 최초 기준선은 4번째 칸이 정의가 아니라 **종류 라벨**("FK"/"UNIQUE"…)
    # 이었다. 칸 수만 세면 정의가 있는 것으로 오인하므로 값으로 가려낸다.
    labels = set(KIND.values())
    legacy_label = bool(rows) and all(r[3] in labels for r in rows)
    has_def = bool(rows) and all(r[3] for r in rows) and not legacy_label
    return rows, has_def


def render(rows):
    return "".join(SEP.join(r) + "\n" for r in rows)


def contype_counts(rows):
    c = Counter(r[2] for r in rows)
    return {k: c.get(k, 0) for k in CONTYPES}


def _counts_line(rows):
    cc = contype_counts(rows)
    return "FK %d / UNIQUE %d / CHECK %d / EXCLUDE %d = %d" % (
        cc["f"], cc["u"], cc["c"], cc["x"], len(rows))


# ==============================================================
# 대조 — 순수 함수. DB 없이 파일끼리도 돌아간다(--selftest가 쓴다).
# ==============================================================
def compare(base_rows, cur_rows):
    """(추가, 삭제, 정의변경) 을 돌려준다. 키는 (테이블, 제약명)."""
    base = {(r[0], r[1]): r for r in base_rows}
    cur = {(r[0], r[1]): r for r in cur_rows}

    added = [cur[k] for k in sorted(set(cur) - set(base))]
    removed = [base[k] for k in sorted(set(base) - set(cur))]

    changed = []
    for k in sorted(set(base) & set(cur)):
        b, c = base[k], cur[k]
        if b[2] != c[2] or b[3] != c[3]:
            changed.append((c[0], c[1], b[2], c[2], b[3], c[3]))
    return added, removed, changed


def _fmt(row):
    return "%s.%s  [%s %s]" % (row[0], row[1], row[2], KIND[row[2]])


# ==============================================================
# --baseline 보고
# ==============================================================
def run_compare(base_rows, cur_rows, base_has_def, expect_added, rep,
                base_label, cur_label):
    print("=" * 70)
    print(" DB 제약 전수 대조 — pg_constraint (contype f,u,x,c / %s 제외)"
          % EXCLUDE_TABLE)
    print("=" * 70)
    print(" 기준선 : %s" % base_label)
    print(" 현재   : %s" % cur_label)

    added, removed, changed = compare(base_rows, cur_rows)

    _stage(1, "건수")
    print("         %s" % _delta(len(base_rows), len(cur_rows)))
    print("         기준선  %s" % _counts_line(base_rows))
    print("         현재    %s" % _counts_line(cur_rows))
    bc, cc = contype_counts(base_rows), contype_counts(cur_rows)
    print("         contype별 증분  " + " / ".join(
        "%s %+d" % (KIND[k], cc[k] - bc[k]) for k in ("f", "u", "c", "x")))

    _stage(2, "추가된 것")
    if not added:
        print("         없음")
    for r in added:
        print("         + %s" % _fmt(r))
        if r[3]:
            print("             %s" % r[3])

    _stage(3, "삭제된 것  [건수와 무관하게 경보한다]")
    if not removed:
        print("         없음")
    else:
        for r in removed:
            print("         - %s" % _fmt(r))
            if r[3]:
                print("             %s" % r[3])
        rep.red_("제약이 %d건 사라졌다 — 선언한 교체인지 확인하라. "
                 "삭제는 --expect-added와 무관하게 경보다." % len(removed))

    _stage(4, "이름은 같은데 정의가 바뀐 것  [건수만 세면 못 잡는다]")
    if not base_has_def:
        rep.warn_("기준선에 정의(pg_get_constraintdef)가 없어 이 단계를 "
                  "건너뛴다. --out으로 기준선을 다시 뽑아라.")
    elif not changed:
        print("         없음")
    else:
        for table, name, bt, ct, bd, cd in changed:
            print("         ~ %s.%s" % (table, name))
            if bt != ct:
                print("             contype %s -> %s" % (bt, ct))
            print("             기준선: %s" % bd)
            print("             현재  : %s" % cd)
        rep.warn_("정의가 바뀐 제약 %d건 — 건수는 불변이라 증분 판정에 "
                  "걸리지 않는다. 선언과 대조하라." % len(changed))

    _stage(5, "증분 판정")
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
        print(" 선언과 일치. 추가 %d / 삭제 %d / 정의변경 %d."
              % (len(added), len(removed), len(changed)))
    elif not rep.red:
        print(" RED 없음. 위 [!!] 항목이 선언한 변경과 일치하면 진행 가능.")
    return 1 if rep.red else 0


# ==============================================================
# 회귀 테스트 — 답을 아는 문제로 검증기 자신을 검증한다.
#
# 고정 케이스는 9/12에 실측해 저장한 기준선 40건이다(12-5).
# DB 없이 파일끼리 돌므로 컨테이너가 꺼져 있어도 검증기 점검은 된다.
#
# 네 번째가 핵심이다 — **건수만 세면 못 잡는 경우**이고,
# 내일 uq_property_channel과 inquiry_responses의 FK가 정확히 이 형태다.
# ==============================================================
def _selftest():
    print("=" * 70)
    print(" 회귀 테스트 — 답을 아는 문제(9/12 기준선 40건)로 검증기를 시험한다")
    print("=" * 70)

    if not os.path.isfile(SELFTEST_BASELINE):
        print(" [SKIP] 기준선이 없다: %s" % SELFTEST_BASELINE)
        return 2

    rows, has_def = parse_dump(SELFTEST_BASELINE)
    checks = []

    # ① 건수와 contype 집계
    cc = contype_counts(rows)
    checks.append(("기준선 건수", len(rows), EXPECT_SELFTEST_ROWS))
    for k in ("f", "u", "c", "x"):
        checks.append(("contype %s (%s)" % (k, KIND[k]),
                       cc[k], EXPECT_SELFTEST_CONTYPE[k]))

    # ② 같은 파일끼리 — 증분 0
    a, r, ch = compare(rows, rows)
    checks.append(("자기 자신과 대조 — 추가", len(a), 0))
    checks.append(("자기 자신과 대조 — 삭제", len(r), 0))
    checks.append(("자기 자신과 대조 — 정의변경", len(ch), 0))

    # ③ 한 줄을 뺀 사본 — 삭제 1건
    dropped = rows[:5] + rows[6:]
    a3, r3, c3 = compare(rows, dropped)
    checks.append(("한 줄 제거 — 삭제 탐지", len(r3), 1))
    checks.append(("한 줄 제거 — 추가 0", len(a3), 0))
    checks.append(("한 줄 제거 — 건수 감소", len(rows) - len(dropped), 1))

    # ④ 정의만 바꾼 사본 — 건수는 불변인데 정의변경 1건 (핵심)
    if not has_def:
        print(" [SKIP] 기준선에 정의가 없어 4번을 시험할 수 없다.")
        print("        --out으로 기준선을 다시 뽑아라.")
        return 2
    idx = next((i for i, x in enumerate(rows)
                if x[1] == "uq_property_channel"), 0)
    tweaked = list(rows)
    t = tweaked[idx]
    tweaked[idx] = (t[0], t[1], t[2],
                    "UNIQUE NULLS NOT DISTINCT (property_id, channel, room_id)")
    a4, r4, c4 = compare(rows, tweaked)
    checks.append(("정의만 변경 — 정의변경 탐지", len(c4), 1))
    checks.append(("정의만 변경 — 추가 0", len(a4), 0))
    checks.append(("정의만 변경 — 삭제 0", len(r4), 0))
    checks.append(("정의만 변경 — 건수 불변", len(tweaked) - len(rows), 0))

    failed = 0
    for label, got, exp in checks:
        mark = "OK " if got == exp else "FAIL"
        if got != exp:
            failed += 1
        print(" [%s] %-34s 기대 %2d, 실제 %2d" % (mark, label, exp, got))

    print("-" * 70)
    if failed:
        print(" 회귀 테스트 실패 %d건 — 검증기가 틀렸다. 대조에 쓰지 마라." % failed)
        return 1
    print(" 회귀 테스트 통과. 기준선 40건(f21/u13/c3/x3)을 확인했고,")
    print(" 삭제 1건과 **정의만 바뀐 1건**을 둘 다 잡았다(후자는 건수 불변).")
    return 0


# ==============================================================
def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if "--selftest" in argv:
        return _selftest()

    ap = argparse.ArgumentParser(
        description="DB 제약 전수 대조 (pg_constraint, 읽기 전용)")
    ap.add_argument("--out", metavar="파일",
                    help="현재 DB의 제약을 이 파일로 저장한다")
    ap.add_argument("--baseline", metavar="파일",
                    help="이 기준선과 현재 DB를 대조한다")
    ap.add_argument("--expect-added", type=int, metavar="N",
                    help="선언한 증분. 다르면 종료코드 1")
    ap.add_argument("--selftest", action="store_true",
                    help="9/12 기준선을 고정 케이스로 검증기 자신을 시험한다")
    ap.add_argument("--container", default=CONTAINER)
    ap.add_argument("--db", default=DB_NAME)
    ap.add_argument("--user", default=DB_USER)
    args = ap.parse_args(argv)

    if not args.out and not args.baseline:
        ap.error("--out 또는 --baseline 중 하나는 있어야 한다 (--selftest도 가능)")

    cur_rows = fetch_current(args.container, args.db, args.user)

    if args.out:
        d = os.path.dirname(args.out)
        if d and not os.path.isdir(d):
            sys.exit("디렉토리가 없다: %s" % d)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render(cur_rows))
        print("저장: %s" % args.out)
        print("      %d건 — %s" % (len(cur_rows), _counts_line(cur_rows)))
        print("      형식: 테이블|제약명|contype|정의")
        print("      정렬: 테이블 -> contype -> 제약명 (매번 동일)")

    if not args.baseline:
        return 0

    if not os.path.isfile(args.baseline):
        sys.exit("파일이 없다: %s" % args.baseline)
    base_rows, base_has_def = parse_dump(args.baseline)
    rep = Report()
    return run_compare(base_rows, cur_rows, base_has_def, args.expect_added,
                       rep, args.baseline, "DB %s@%s" % (args.db, args.container))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
