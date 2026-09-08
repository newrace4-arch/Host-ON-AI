/**
 * 웨이크업 게이트 (2026-09-08)
 *
 * **라우터보다 앞에 둔다.** `CONNECTED`가 된 뒤에만 children(라우터)이
 * 렌더링된다. 게이트 없이 라우터가 먼저 뜨면 대시보드가 슬립 중인 서버로
 * 숙소 3~5개분 요청을 한꺼번에 쏴서 웨이크업 전략 자체가 무력화된다.
 *
 * 웨이크업 상태를 **전역 Context로 노출하지 않는다.** 여기서 게이트로만
 * 쓰고, 하위 화면은 이 상태를 알 필요가 없다.
 *
 * 근거: CLAUDE.md 코딩규칙 9번(Render 콜드스타트), api_contract v2.0 11절
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { wakeUpServer } from "@/api/health";
import type { WakeUpStatus } from "@/types/ui";

/**
 * 게이트를 건너뛸지 판정한다.
 *
 * - **개발 환경**: 로컬 uvicorn은 슬립하지 않는다. 매번 60초 타임아웃
 *   가능성을 안고 개발할 이유가 없다.
 * - **Mock 모드**: 서버를 아예 부르지 않으므로 깨울 대상이 없다.
 *
 * 두 경우 모두 즉시 통과시킨다.
 */
const SKIP_WAKEUP =
  import.meta.env.DEV || import.meta.env.VITE_USE_MOCK === "true";

export default function WakeUpGate({
  children,
}: {
  children: React.ReactNode;
}) {
  const [status, setStatus] = useState<WakeUpStatus>(
    SKIP_WAKEUP ? "connected" : "connecting",
  );

  /**
   * StrictMode의 effect 이중 실행에서 웨이크업을 두 번 보내지 않게 한다.
   *
   * ⚠️ CLAUDE.md 규칙 14번: **중복 방지와 취소 처리를 동시에 넣지
   * 않는다.** 여기서는 ref 가드만 쓴다. cleanup에 `cancelled` 플래그를
   * 더하면 첫 실행의 응답이 통째로 버려져 화면이 연결 중에서 멈춘다
   * (troubleshooting 26번에서 실제로 겪은 문제다).
   */
  const startedRef = useRef(false);

  const attempt = useCallback(() => {
    setStatus("connecting");
    void wakeUpServer()
      .then(() => setStatus("connected"))
      .catch(() => setStatus("connection_failed"));
  }, []);

  useEffect(() => {
    if (SKIP_WAKEUP) return;
    if (startedRef.current) return;
    startedRef.current = true;
    attempt();
  }, [attempt]);

  if (status === "connected") return <>{children}</>;

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        {status === "connecting" ? (
          <>
            {/* 스피너 — 경과 시간 카운터·진행률은 만들지 않는다.
                예상 시간을 보여주면 그 숫자가 틀렸을 때 더 불안해진다. */}
            <div
              className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-gray-700"
              role="status"
              aria-label="서버와 연결 중"
            />
            <p className="mt-4 text-sm text-gray-600">서버와 연결 중입니다</p>
          </>
        ) : (
          <>
            <p className="text-sm text-gray-700">서버에 연결하지 못했습니다</p>
            {/* 자동 재시도하지 않는다 — 이미 60초를 기다린 사용자를 또
                기다리게 하면 안 된다. 다시 시도할지는 사용자가 정한다. */}
            <button
              type="button"
              onClick={attempt}
              className="mt-4 rounded border border-gray-400 px-4 py-2 text-sm"
            >
              다시 시도
            </button>
          </>
        )}
      </div>
    </div>
  );
}
