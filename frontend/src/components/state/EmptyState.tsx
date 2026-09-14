/**
 * 빈 상태 · 실패 상태 안내 (r58, 2026-09-14)
 *
 * `docs/ui_design.md` 5절 9번 + 5-9절. 4상태 중 **EMPTY와 ERROR 둘 다**를
 * 맡는다 — 5-9절 표가 그렇게 정했다:
 *
 *     EMPTY   요청 성공 + 데이터 0건   `EmptyState`
 *     ERROR   요청 실패               `EmptyState`(전체 실패) 또는 `Toast`(부분 실패)
 *
 * **`Toast`(부분 실패)는 이번에 만들지 않는다.** 쓰는 곳이 0곳이고, 유일한
 * 부분 실패인 대시보드 PARTIAL은 **실서버에서 재현할 수단이 없어** 눈으로
 * 확인할 수 없다. 확인할 수 없는 것을 공통화하지 않는다.
 *
 * ## 세 요소를 구조로 강제한다
 *
 * 5-9절: *"**`EmptyState`는 반드시 세 가지를 담는다** — 1. 왜 비어 있는지
 * 2. 지금 무엇을 하면 되는지 3. 그 행동으로 가는 버튼·링크"*.
 * `title` / `description` / `action`이 그 셋이다.
 *
 * ## 🔴 `action`이 판별 유니온인 이유
 *
 * `onRetry`와 `to`를 **나란한 선택 필드**로 두면 둘 다 넘기거나 둘 다
 * 빠뜨려도 **컴파일이 통과한다.** 유니온이면 `tsc`가 그 자리에서 막는다.
 *
 * 코딩규칙 15번이 `client.get` 대신 `api` 래퍼를 둔 것과 같은 판단이다 —
 * *"래퍼는 두 번째 제네릭을 내부에서 고정하므로 **호출부가 빠뜨릴 수
 * 없다**"*. 프론트에 테스트 러너가 없어 **`tsc`가 유일한 자동 검증**이므로,
 * 잡을 수 있는 것은 타입으로 잡아 둔다.
 *
 * 재조회(`button`)와 화면 이동(`Link`)은 **바꿔 쓸 수 없다** — 재조회를
 * `<a>`로 만들면 페이지가 새로 뜨고, 이동을 `button`으로 만들면 새 탭
 * 열기·주소 복사가 죽는다.
 *
 * ## EMPTY와 ERROR를 시각적으로 구분한다
 *
 * 5-9절: *"**EMPTY와 ERROR를 시각적으로 구분한다.** "처리할 일이
 * 없습니다"는 정상 상태이므로 경고색을 쓰지 않는다."*
 *
 * 지금은 **제목 색만** 다르다(`gray-700` / `red-800`). 배경·테두리까지
 * 칠하지 않는 것은 ui_design 원칙 5(저해상도)를 따른 것이며, 색·여백·
 * 타이포는 나중에 정한다.
 */

import { Link } from "react-router-dom";

export type EmptyStateAction =
  | { kind: "retry"; onRetry: () => void; disabled?: boolean }
  | { kind: "link"; to: string; label: string };

export interface EmptyStateProps {
  /** 정상적으로 비어 있는가(`empty`), 조회에 실패했는가(`error`) */
  tone: "empty" | "error";
  /** ① 왜 비어 있는지 — 원인 */
  title: string;
  /** ② 지금 무엇을 하면 되는지 — 다음 행동 */
  description?: string;
  /** ③ 그 행동으로 가는 버튼·링크 */
  action?: EmptyStateAction;
}

/** 재시도 버튼과 이동 링크가 **같은 모양**이어야 하므로 한 곳에 둔다. */
const ACTION_CLASS =
  "mt-2 inline-block rounded border border-gray-400 px-3 py-1 text-sm " +
  "disabled:cursor-not-allowed disabled:opacity-50";

export default function EmptyState({
  tone,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div>
      <p
        className={
          tone === "error"
            ? "text-sm font-medium text-red-800"
            : "text-sm font-medium text-gray-700"
        }
      >
        {title}
      </p>

      {description !== undefined && (
        <p className="mt-1 text-sm text-gray-600">{description}</p>
      )}

      {action?.kind === "retry" && (
        <button
          type="button"
          onClick={action.onRetry}
          disabled={action.disabled ?? false}
          className={ACTION_CLASS}
        >
          {action.disabled === true ? "다시 시도 중…" : "다시 시도"}
        </button>
      )}

      {action?.kind === "link" && (
        <Link to={action.to} className={ACTION_CLASS}>
          {action.label}
        </Link>
      )}
    </div>
  );
}
