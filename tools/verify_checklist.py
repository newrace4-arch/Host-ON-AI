#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""체크리스트 엑셀 무결성 검증 — CLAUDE.md 8-2 절차 4번 자동화.

    python tools/verify_checklist.py <기준선.xlsx> <대상.xlsx>

기준선은 8-2 절차 0번의 **작업 전 백업본**(`.backup/`)이다.
"저장 직전 메모리 상태"가 아니다 — 유실이 저장 전에 일어나면
저장 전후는 둘 다 유실된 채 일치해서 통과한다(troubleshooting 31번).

검증은 6단계이고 앞 단계가 실패하면 뒤를 진행하지 않는다.
성격이 둘로 갈린다.

    1)~4)  파일이 깨졌나   (구조 지표)
    5)~6)  내용이 남았나   (셀 텍스트 지표)

9/9 사고는 1)~4)를 전부 통과하면서 ☑ 26개와 8/31 타이틀을 잃었다.
5)~6)이 그래서 있다.

종료코드: 0 = 통과, 1 = RED 발생
"""

import sys
import os
import re
import zipfile
import argparse
from collections import Counter

try:
    import openpyxl
except ImportError:  # 8-2 절차 0번 — 9/9에 실제로 사라져 있었다
    sys.exit("openpyxl이 없다. `pip install openpyxl` 후 다시 실행하라.")


# ==============================================================
# 기준값 상수 — 이 블록이 기대값의 SSOT다 (CLAUDE.md 8-2, 9/10 확정)
#
# 정당한 변경이 생기면 **상수와 사유를 같은 커밋에** 담고,
# CLAUDE.md 8-2 4번의 해당 줄도 함께 고친다.
# 값의 근거는 CLAUDE.md 8-2와 troubleshooting 29·31번 참고.
# ==============================================================
EXPECT_SHEETS = [
    "최종 스펙 요약",
    "진행현황 요약",
    "체크리스트",
    "9단계 검증 체크리스트",
    "일자별 실행리스트(파일위치)",
    "일일 크로스체크",
]
EXPECT_CHARTS = 0          # openpyxl은 저장 시 차트를 잃는다 — 0이어야 안전
EXPECT_IMAGES = 0
EXPECT_PIVOTS = 0
EXPECT_COND_FORMAT = 2     # 9/9 사고(29번)의 대상
EXPECT_DATA_VALID = 4
EXPECT_FORMULA = 61

CARD_SHEET = "일일 크로스체크"   # 5)~6) 카드 검증 대상 시트
TASK_SHEET = "체크리스트"        # (8) 태스크 총건수·완료건수 원천
TASK_STATUS_COL = 5              # E열 = 상태
TASK_NAME_COL = 2                # B열 = 카테고리(행 존재 판정용)
TASK_FIRST_ROW = 4               # 1~3행은 제목·공백·헤더
TASK_DONE = "완료"

CHECKED = "☑"      # 체크된 상자
UNCHECKED = "☐"    # 빈 상자
MARK_DATE = "\U0001F4C5"     # 카드 시작
MARK_TITLE = "\U0001F3AF"    # 오늘의 타이틀
MARK_MORNING = "\U0001F305"  # 아침 크로스체크
MORNING_COL = 3              # C열 (C:F 병합, 한 셀에 상자들이 이어붙어 있다)
CARD_TASK_NAME_COL = 2       # B열
CARD_TASK_DONE_COL = 7       # G열

LIST_LIMIT = 12              # 목록형 보고의 기본 출력 상한 (--full로 해제)
                             # 유실(RED)은 상한 없이 전부 출력한다


# ==============================================================
# 스냅샷
# ==============================================================
def _zip_counts(path):
    """차트·이미지·피벗은 openpyxl이 아니라 zip 내부 경로로 센다."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    return (
        sum("charts/" in n for n in names),
        sum("media/" in n for n in names),
        sum("pivotTable" in n for n in names),
    )


def _read_cards(ws):
    """'일일 크로스체크' 시트를 카드 단위로 읽는다.

    카드 구조(9/10 실측):
        A열 날짜 마커      -> 카드 시작
        A열 타이틀 마커    -> 오늘의 타이틀
        A열 아침 마커, C열 -> 한 셀 안에 상자 기호가 이어붙은 문자열
        A열 정수, B열 태스크명, G열 체크 -> 태스크 행

    태스크는 **집합**으로 담는다. 순서에 의존하면 8/31 타이틀 변경을
    "태스크가 바뀐 것"으로 오분류해서 놓친다(troubleshooting 31번).
    """
    cards = {}
    cur = None
    for r in range(1, ws.max_row + 1):
        a = ws.cell(r, 1).value
        if isinstance(a, str):
            if a.startswith(MARK_DATE):
                m = re.match(re.escape(MARK_DATE) + r"\s*(\S+)", a)
                cur = m.group(1) if m else a.strip()
                cards[cur] = {"title": None, "tasks": set(),
                              "morning": 0, "done": 0}
                continue
            if cur and a.startswith(MARK_TITLE):
                cards[cur]["title"] = a.split(":", 1)[-1].strip()
                continue
            if cur and a.startswith(MARK_MORNING):
                cell = ws.cell(r, MORNING_COL).value
                cards[cur]["morning"] = str(cell or "").count(CHECKED)
                continue
        if cur and isinstance(a, int):
            name = ws.cell(r, CARD_TASK_NAME_COL).value
            if name:
                cards[cur]["tasks"].add(str(name).strip())
                if str(ws.cell(r, CARD_TASK_DONE_COL).value or "") == CHECKED:
                    cards[cur]["done"] += 1
    return cards


def snapshot(path):
    """검증에 필요한 모든 지표를 한 번의 순회로 수집한다."""
    wb = openpyxl.load_workbook(path)
    charts, images, pivots = _zip_counts(path)

    snap = {
        "path": path,
        "size": os.path.getsize(path),
        "sheets": wb.sheetnames,
        "charts": charts, "images": images, "pivots": pivots,
        "cond_format": 0, "data_valid": 0, "formula": 0,
        "merged": {}, "freeze": {}, "dims": {},
        "cells": {}, "textlen": {}, "checked": {}, "unchecked": {},
        "cards": {}, "task_total": 0, "task_done": 0,
        "morning_total": 0, "taskmark_total": 0,
    }

    for ws in wb.worksheets:
        snap["cond_format"] += len(list(ws.conditional_formatting))
        snap["data_valid"] += len(ws.data_validations.dataValidation)
        snap["merged"][ws.title] = len(ws.merged_cells.ranges)
        snap["freeze"][ws.title] = ws.freeze_panes
        snap["dims"][ws.title] = (ws.max_row, ws.max_column)

        cells = length = chk = box = 0
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if v is None:
                    continue
                cells += 1
                if isinstance(v, str):
                    length += len(v)
                    chk += v.count(CHECKED)
                    box += v.count(UNCHECKED)
                    if v.startswith("="):
                        snap["formula"] += 1
        snap["cells"][ws.title] = cells
        snap["textlen"][ws.title] = length
        snap["checked"][ws.title] = chk
        snap["unchecked"][ws.title] = box

    if CARD_SHEET in wb.sheetnames:
        snap["cards"] = _read_cards(wb[CARD_SHEET])
        snap["morning_total"] = sum(c["morning"] for c in snap["cards"].values())
        snap["taskmark_total"] = sum(c["done"] for c in snap["cards"].values())

    if TASK_SHEET in wb.sheetnames:
        ws = wb[TASK_SHEET]
        stat = Counter(
            str(ws.cell(r, TASK_STATUS_COL).value)
            for r in range(TASK_FIRST_ROW, ws.max_row + 1)
            if ws.cell(r, TASK_NAME_COL).value
        )
        snap["task_total"] = sum(stat.values())
        snap["task_done"] = stat.get(TASK_DONE, 0)

    return snap


# ==============================================================
# 보고
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
# 1)~4)  파일이 깨졌나
# ==============================================================
def stage1_size(base, targ, rep):
    _stage(1, "파일 크기  [파일이 깨졌나]")
    rep.info("크기 %s" % _delta(base["size"], targ["size"]))
    rep.info("증가했다고 정상이 아니다 — 29번은 감소(92,009->9,332),")
    rep.info("31번은 증가(92,009->92,708)했다. 크기 하나로 판정하지 않는다.")
    if targ["size"] < base["size"] * 0.5:
        rep.red_("크기가 절반 미만으로 급감 — 29번과 같은 저장 중단이 의심된다")
    elif targ["size"] < base["size"]:
        rep.warn_("크기가 줄었다. 의도한 삭제인지 확인하라")
    else:
        rep.ok("크기 이상징후 없음 (단독 판정 근거 아님)")


def stage2_reopen(targ, rep):
    _stage(2, "재오픈  [파일이 깨졌나]")
    try:
        openpyxl.load_workbook(targ["path"])
        rep.ok("예외 없이 재로드됨")
    except Exception as exc:
        rep.red_("재오픈 실패: %s" % exc)


def stage3_sheets(targ, rep):
    _stage(3, "시트  [파일이 깨졌나]")
    if targ["sheets"] == EXPECT_SHEETS:
        rep.ok("시트 %d개, 이름·순서 모두 일치" % len(EXPECT_SHEETS))
    else:
        rep.red_("시트 불일치")
        rep.info("기대: %s" % EXPECT_SHEETS)
        rep.info("실제: %s" % targ["sheets"])


def stage4_structure(base, targ, rep):
    _stage(4, "구조  [파일이 깨졌나]")
    for label, key, exp in [
        ("차트", "charts", EXPECT_CHARTS),
        ("이미지", "images", EXPECT_IMAGES),
        ("피벗", "pivots", EXPECT_PIVOTS),
        ("조건부서식", "cond_format", EXPECT_COND_FORMAT),
        ("데이터유효성", "data_valid", EXPECT_DATA_VALID),
        ("수식", "formula", EXPECT_FORMULA),
    ]:
        got = targ[key]
        if got == exp:
            rep.ok("%s %d" % (label, got))
        else:
            rep.red_("%s 기대 %d, 실제 %d — 상수 변경이 정당하면 "
                     "사유와 함께 같은 커밋에 담아라" % (label, exp, got))

    for sh in targ["sheets"]:
        bm, tm = base["merged"].get(sh), targ["merged"][sh]
        if bm is not None and bm != tm:
            rep.warn_("병합 [%s] %s" % (sh, _delta(bm, tm)))
        bf, tf = base["freeze"].get(sh), targ["freeze"][sh]
        if bf is not None and bf != tf:
            rep.red_("freeze_panes [%s] %s -> %s" % (sh, bf, tf))
        bd, td = base["dims"].get(sh), targ["dims"][sh]
        if bd and (td[0] < bd[0] or td[1] < bd[1]):
            rep.red_("치수 감소 [%s] max_row %d->%d, max_col %d->%d"
                     % (sh, bd[0], td[0], bd[1], td[1]))
    rep.info("max_row·max_column은 감소하면 전부 보고한다('급감' 기준 없음)")


# ==============================================================
# 5)~6)  내용이 남았나
# ==============================================================
def stage5_marks(base, targ, rep):
    _stage(5, "표시 보존 — 기준선 대비  [내용이 남았나]")

    print("   [주력] (1) 아침 크로스체크 체크 — 카드별")
    lost = []
    for d in sorted(set(base["cards"]) & set(targ["cards"])):
        b = base["cards"][d]["morning"]
        t = targ["cards"][d]["morning"]
        if t < b:
            lost.append((d, b, t))
    if lost:
        total = sum(b - t for _, b, t in lost)
        rep.red_("아침 크로스체크 표시 %d개 유실 (카드 %d개)" % (total, len(lost)))
        for d, b, t in lost:
            rep.info("  %-20s %d -> %d  (-%d)" % (d, b, t, b - t))
    else:
        rep.ok("아침 크로스체크 유실 없음 (총 %s)"
               % _delta(base["morning_total"], targ["morning_total"]))

    print("   [주력] (2) 태스크 완료 체크 — 카드 내")
    if targ["taskmark_total"] < base["taskmark_total"]:
        rep.red_("태스크 완료 체크 감소 %s"
                 % _delta(base["taskmark_total"], targ["taskmark_total"]))
    else:
        rep.ok("태스크 완료 체크 %s"
               % _delta(base["taskmark_total"], targ["taskmark_total"]))
    rep.info("(1)과 (2)를 따로 세는 이유: 총합 하나로 세면 한쪽이 줄고")
    rep.info("다른 쪽이 늘 때 상쇄된다.")

    print("   [보조] (3) 체크+빈상자 합계 / (4) 시트별 텍스트 길이")
    bs = sum(base["checked"].values()) + sum(base["unchecked"].values())
    ts = sum(targ["checked"].values()) + sum(targ["unchecked"].values())
    rep.info("(3) 합계 %s" % _delta(bs, ts))
    for sh in targ["sheets"]:
        bl, tl = base["textlen"].get(sh), targ["textlen"][sh]
        if bl is not None and bl != tl:
            rep.info("(4) 텍스트 길이 [%s] %s" % (sh, _delta(bl, tl)))
    rep.info("(3)(4)는 31번을 못 잡았다 — (3)은 치환이라 합계가 불변이고,")
    rep.info("(4)는 두 기호가 둘 다 1글자라 길이 중립이다. 실측으로 둘 다")
    rep.info("오히려 늘었다. 특히 (4)는 거짓 안심을 준다. 보조로만 쓰고")
    rep.info("단독 판정 근거로 삼지 않는다.")


def stage6_content(base, targ, rep):
    _stage(6, "내용 보존 — 기준선 대비  [내용이 남았나]")

    gone = sorted(set(base["cards"]) - set(targ["cards"]))
    added = sorted(set(targ["cards"]) - set(base["cards"]))
    print("   (7) 카드 수 %s" % _delta(len(base["cards"]), len(targ["cards"])))
    if gone:
        rep.red_("카드 소멸 %d개: %s" % (len(gone), ", ".join(gone)))
    if added:
        rep.warn_("카드 신설 %d개: %s — 선언한 변경인지 확인하라"
                  % (len(added), ", ".join(added)))
    if not gone and not added:
        rep.ok("카드 증감 없음")

    print("   [주력] (5) 카드별 타이틀 — 태스크 집합(순서 무시) 동일 시 변경=경보")
    alarm = []
    legit = []
    for d in sorted(set(base["cards"]) & set(targ["cards"])):
        b, t = base["cards"][d], targ["cards"][d]
        if b["title"] == t["title"]:
            continue
        if b["tasks"] == t["tasks"]:
            alarm.append((d, b, t))
        else:
            legit.append(d)
    if alarm:
        rep.red_("태스크 집합은 같은데 타이틀만 바뀐 카드 %d개" % len(alarm))
        for d, b, t in alarm:
            rep.info("  [%s]" % d)
            rep.info("    before: %s" % (b["title"] or "")[:72])
            rep.info("    after : %s" % (t["title"] or "")[:72])
    else:
        rep.ok("지시 없는 타이틀 변경 없음")
    if legit:
        rep.info("참고: 태스크가 이동해 타이틀이 따라간 정당한 변경 %d건 "
                 "— 경보 아님" % len(legit))
        rep.info("  %s" % ", ".join(legit))

    print("   (6) 카드별 태스크 집합")
    dropped = []
    for d in sorted(set(base["cards"]) & set(targ["cards"])):
        miss = base["cards"][d]["tasks"] - targ["cards"][d]["tasks"]
        if miss:
            dropped.append((d, miss))
    if dropped:
        n_items = sum(len(m) for _, m in dropped)
        rep.warn_("태스크가 빠진 카드 %d개 / 항목 %d건 — 일정 재배치면 정상, "
                  "선언 여부를 확인하라" % (len(dropped), n_items))
        shown = 0
        for d, miss in dropped:
            for m in sorted(miss):
                if shown >= LIST_LIMIT:
                    break
                rep.info("  [%s] -%s" % (d, m[:58]))
                shown += 1
            if shown >= LIST_LIMIT:
                break
        if n_items > shown:
            rep.info("  ... 외 %d건 (전수는 --full)" % (n_items - shown))
    else:
        rep.ok("카드에서 빠진 태스크 없음")

    print("   (8) 태스크 총건수·완료건수 ('%s' 시트)" % TASK_SHEET)
    if targ["task_total"] != base["task_total"]:
        rep.warn_("총건수(분모) %s — 8-3 분모 규칙을 확인하라"
                  % _delta(base["task_total"], targ["task_total"]))
    if targ["task_done"] < base["task_done"]:
        rep.red_("완료건수 감소 %s"
                 % _delta(base["task_done"], targ["task_done"]))
    else:
        rep.ok("완료 %s" % _delta(base["task_done"], targ["task_done"]))


# ==============================================================
def _finish(rep, reached):
    print("")
    print("=" * 70)
    print(" 결과 — %d단계까지 진행" % reached)
    print("=" * 70)
    if rep.red:
        print(" [RED] %d건 — 즉시 중단하라. 커밋하지 않는다(8-2 6번)."
              % len(rep.red))
        for m in rep.red:
            print("   - %s" % m.splitlines()[0])
    if rep.warn:
        print(" [!! ] %d건 — 선언한 변경인지 확인하라." % len(rep.warn))
        for m in rep.warn:
            print("   - %s" % m.splitlines()[0])
    if not rep.red and not rep.warn:
        print(" 무손실. 6단계 전부 통과.")
    elif not rep.red:
        print(" RED 없음. 위 [!!] 항목이 선언한 변경과 일치하면 진행 가능.")
    return 1 if rep.red else 0


# ==============================================================
# 회귀 테스트 — 답을 아는 문제로 검증기 자신을 검증한다.
#
# 9/9 사고(troubleshooting 31번)를 고정 케이스로 쓴다.
#     78e063a  재생성 직전 — 아침 크로스체크 26개 살아있음
#     0f1f119  재생성 직후 — 26개 소멸 + 8/31 타이틀 변경
#
# 이 테스트를 통과하기 전에는 실제 복구 작업에 쓰지 않는다.
# ==============================================================
SELFTEST_BASE = "78e063a"
SELFTEST_TARG = "0f1f119"
SELFTEST_XLSX = "3rd_host_ai_체크리스트.xlsx"
EXPECT_MORNING_LOST = 26   # 4+4+4+4+6+4 (troubleshooting 31번 표와 일치)
EXPECT_LOST_CARDS = 6
EXPECT_TITLE_ALARM = 1     # 8/31만. 나머지 12건은 태스크 이동에 따른 정당한 변경
EXPECT_TITLE_LEGIT = 12


def _selftest():
    import subprocess
    import tempfile

    print("=" * 70)
    print(" 회귀 테스트 — 9/9 사고(31번)를 잡아내는지 확인한다")
    print("=" * 70)

    tmp = tempfile.mkdtemp(prefix="verify_checklist_")
    paths = {}
    for rev in (SELFTEST_BASE, SELFTEST_TARG):
        dst = os.path.join(tmp, rev + ".xlsx")
        try:
            blob = subprocess.check_output(
                ["git", "show", "%s:%s" % (rev, SELFTEST_XLSX)])
        except (subprocess.CalledProcessError, OSError) as exc:
            print(" [SKIP] git에서 %s를 꺼내지 못했다: %s" % (rev, exc))
            return 2
        with open(dst, "wb") as fh:
            fh.write(blob)
        paths[rev] = dst

    base = snapshot(paths[SELFTEST_BASE])
    targ = snapshot(paths[SELFTEST_TARG])

    lost = [(d, base["cards"][d]["morning"], targ["cards"][d]["morning"])
            for d in set(base["cards"]) & set(targ["cards"])
            if targ["cards"][d]["morning"] < base["cards"][d]["morning"]]
    n_lost = sum(b - t for _, b, t in lost)

    alarm = legit = 0
    for d in set(base["cards"]) & set(targ["cards"]):
        b, t = base["cards"][d], targ["cards"][d]
        if b["title"] == t["title"]:
            continue
        if b["tasks"] == t["tasks"]:
            alarm += 1
        else:
            legit += 1

    checks = [
        ("아침 크로스체크 유실 개수", n_lost, EXPECT_MORNING_LOST),
        ("유실 카드 수", len(lost), EXPECT_LOST_CARDS),
        ("타이틀 경보(태스크 집합 동일)", alarm, EXPECT_TITLE_ALARM),
        ("타이틀 정당 변경(오탐이면 안 됨)", legit, EXPECT_TITLE_LEGIT),
    ]
    failed = 0
    for label, got, exp in checks:
        mark = "OK " if got == exp else "FAIL"
        if got != exp:
            failed += 1
        print(" [%s] %-34s 기대 %2d, 실제 %2d" % (mark, label, exp, got))

    print("-" * 70)
    if failed:
        print(" 회귀 테스트 실패 %d건 — 검증기가 틀렸다. 복구에 쓰지 마라." % failed)
        return 1
    print(" 회귀 테스트 통과. 26개 유실과 8/31 타이틀 변경을 잡았고,")
    print(" 타이틀 13건 중 1건만 경보했다(오탐 0).")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="체크리스트 엑셀 무결성 검증 (CLAUDE.md 8-2 절차 4번)")
    if argv is None:
        argv = sys.argv[1:]
    if "--selftest" in argv:
        return _selftest()
    ap.add_argument("baseline", help="기준선 xlsx (8-2 0번의 작업 전 백업본)")
    ap.add_argument("target", help="검증할 xlsx")
    ap.add_argument("--full", action="store_true",
                    help="목록형 보고를 상한 없이 전부 출력한다")
    ap.add_argument("--selftest", action="store_true",
                    help="9/9 사고를 고정 케이스로 검증기 자신을 시험한다")
    args = ap.parse_args(argv)

    if args.full:
        global LIST_LIMIT
        LIST_LIMIT = 10 ** 9

    for p in (args.baseline, args.target):
        if not os.path.isfile(p):
            sys.exit("파일이 없다: %s" % p)

    print("=" * 70)
    print(" 체크리스트 엑셀 무결성 검증 — 8-2 절차 4번 (6단계)")
    print("=" * 70)
    print(" 기준선 : %s" % args.baseline)
    print(" 대상   : %s" % args.target)
    print(" 앞 단계가 실패하면 뒤를 진행하지 않는다.")

    rep = Report()
    base = snapshot(args.baseline)
    targ = snapshot(args.target)

    stage1_size(base, targ, rep)
    if rep.red:
        return _finish(rep, 1)
    stage2_reopen(targ, rep)
    if rep.red:
        return _finish(rep, 2)
    stage3_sheets(targ, rep)
    if rep.red:
        return _finish(rep, 3)
    stage4_structure(base, targ, rep)
    if rep.red:
        return _finish(rep, 4)
    stage5_marks(base, targ, rep)
    stage6_content(base, targ, rep)
    return _finish(rep, 6)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
