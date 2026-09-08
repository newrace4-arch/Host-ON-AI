/**
 * 통합 대시보드 (2026-09-08)
 *
 * 근거: docs/ui_design.md 4-4절, docs/ui_wireframe.md 1절
 *
 * 전체 숙소 통합 뷰다. PropertySwitcher의 선택에 영향받지 않는다.
 * 구조 3단: 상단 합산 KPI / 중단 숙소별 신호등 카드 / 하단 액션 프리뷰.
 *
 * ⚠️ 카드 디자인은 다듬지 않았다. 배치와 데이터 연결까지가 오늘 범위이며,
 *    색·여백·타이포는 나중에 정한다(ui_design.md 원칙 5 — 저해상도).
 */

import { Link } from "react-router-dom";

import { useDashboardSummary } from "@/hooks/useDashboardSummary";
import type { DashboardSummary, PropertyFetchState } from "@/types/ui";

/* ── 작은 표시 조각들 ───────────────────────────────────────────── */

function KpiCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-gray-300 p-4">
      <div className="text-sm text-gray-600">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}

/**
 * conflict_count 표시.
 *
 * **0과 null을 구분한다** — 0은 "충돌 없음", null은 "확인 불가"다.
 * null은 숙소 API 실패(PARTIAL)와 다른 종류이므로 카드를 에러로 만들지
 * 않는다. 서버가 파생 필드 계산에만 실패한 것이고 나머지 11개 값은
 * 정상이다(api_contract v2.0 4.1절).
 */
function ConflictLine({ value }: { value: number | null }) {
  if (value === null) {
    return <div className="text-sm text-gray-500">더블부킹 확인 불가</div>;
  }
  if (value === 0) {
    return <div className="text-sm text-gray-600">더블부킹 없음</div>;
  }
  return (
    <div className="text-sm font-semibold text-red-700">
      더블부킹 {value}건
    </div>
  );
}

/**
 * 숙소별 신호등.
 *
 * UI 문구는 **"위험도"가 아니라 "우선순위"**다.
 * ACTION_ITEMS.risk_level은 AI의 법적·안전 판단이 아니라 규칙기반 운영
 * 우선순위이기 때문이다(CLAUDE.md 핵심 데이터 모델 원칙).
 */
function SignalRow({ summary }: { summary: DashboardSummary }) {
  return (
    <div className="mt-2 flex gap-3 text-sm">
      <span>🔴 지금 {summary.red_now_count}</span>
      <span>🟡 오늘 {summary.yellow_today_count}</span>
      <span>🟢 자동 {summary.green_auto_count}</span>
    </div>
  );
}

/**
 * 재시도 버튼 — 실패한 숙소 카드에만 나타난다.
 *
 * **전체 재시도 버튼은 만들지 않는다.** 성공한 숙소를 다시 부를 이유가
 * 없고, 훅의 `refetchProperty(id)`도 지정한 숙소만 재호출한다.
 */
function RetryButton({
  onRetry,
  disabled,
}: {
  onRetry: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onRetry}
      disabled={disabled}
      className="mt-2 rounded border border-gray-400 px-3 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-50"
    >
      {disabled ? "다시 시도 중…" : "다시 시도"}
    </button>
  );
}

function PropertyCard({
  name,
  state,
  onRetry,
}: {
  name: string;
  state: PropertyFetchState;
  onRetry: () => void;
}) {
  if (state.status === "error") {
    return (
      <div className="rounded border border-gray-300 p-4">
        <div className="font-semibold">{name}</div>
        <div className="mt-2 text-sm text-gray-700">불러오지 못했습니다</div>
        <RetryButton onRetry={onRetry} disabled={false} />
      </div>
    );
  }

  if (!state.data) {
    // `lastError`가 있으면 최초 로딩이 아니라 **재시도 중**이다.
    // 이때 버튼을 비활성으로 남겨 중복 클릭을 막는다(훅에도 가드가 있다).
    const isRetrying = state.lastError !== undefined;
    return (
      <div className="rounded border border-gray-300 p-4">
        <div className="font-semibold">{name}</div>
        <div className="mt-2 text-sm text-gray-500">
          {isRetrying ? "다시 불러오는 중…" : "불러오는 중…"}
        </div>
        {isRetrying && <RetryButton onRetry={onRetry} disabled />}
      </div>
    );
  }

  const s = state.data;
  return (
    <div className="rounded border border-gray-300 p-4">
      <div className="flex items-center justify-between">
        <span className="font-semibold">{s.property_name}</span>
        {state.status === "refetching" && (
          <span className="text-xs text-gray-500">갱신 중</span>
        )}
      </div>
      <SignalRow summary={s} />
      <div className="mt-2 text-sm text-gray-700">
        미처리 {s.open_action_count} · 청소대기 {s.cleaning_pending_count} ·
        청소이슈 {s.cleaning_issue_count}
      </div>
      <ConflictLine value={s.conflict_count} />
    </div>
  );
}

/* ── 화면 ───────────────────────────────────────────────────────── */

export default function Dashboard() {
  const vm = useDashboardSummary();

  if (vm.status === "loading") {
    return <div className="p-6 text-gray-600">불러오는 중…</div>;
  }

  if (vm.status === "error") {
    return (
      <div className="p-6">
        <div className="font-semibold">숙소 목록을 불러오지 못했습니다</div>
        <p className="mt-2 text-sm text-gray-700">
          목록을 받지 못하면 숙소별 현황을 조회할 수 없습니다. 잠시 후 다시
          시도해 주세요.
        </p>
      </div>
    );
  }

  if (vm.status === "empty") {
    return (
      <div className="p-6">
        <div className="font-semibold">첫 숙소를 등록해 주세요</div>
        <p className="mt-2 text-sm text-gray-700">
          숙소를 등록하면 오늘 처리할 일이 여기에 모입니다.
        </p>
        <Link
          to="/onboarding"
          className="mt-4 inline-block rounded border border-gray-400 px-4 py-2 text-sm"
        >
          숙소 등록하러 가기 →
        </Link>
      </div>
    );
  }

  const t = vm.totals;

  return (
    <div className="p-6">
      {/* PARTIAL — 합산 기준을 밝힌다. 전체를 에러로 처리하지 않는다. */}
      {vm.status === "partial" && (
        <div className="mb-4 rounded border border-gray-400 bg-gray-50 p-3 text-sm">
          전체 {vm.totalCount}개 숙소 중 <strong>{vm.succeededCount}개
          기준</strong>으로 집계했습니다. 일부 숙소를 불러오지 못했습니다.
        </div>
      )}

      {/* 상단 — 합산 KPI */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">오늘 요약</h2>
        <div className="grid grid-cols-4 gap-3">
          <KpiCard label="체크인" value={t.today_checkin_count} />
          <KpiCard label="체크아웃" value={t.today_checkout_count} />
          <KpiCard label="턴오버" value={t.today_turnover_count} />
          <KpiCard label="미처리 액션" value={t.open_action_count} />
        </div>
      </section>

      {/* 중단 — 숙소별 신호등 카드 */}
      <section className="mt-8">
        <h2 className="mb-2 text-lg font-semibold">숙소별 현황</h2>
        <div className="grid grid-cols-3 gap-3">
          {vm.properties.map((p) => (
            <PropertyCard
              key={p.property_id}
              name={p.name}
              state={vm.fetchMap[p.property_id] ?? { status: "loading" }}
              onRetry={() => vm.refetchProperty(p.property_id)}
            />
          ))}
        </div>
      </section>

      {/* 하단 — 액션 프리뷰.
          조회·이동만 제공한다. 카드 내 승인·완료·거절 버튼을 두지 않는다
          (ui_design.md 원칙 2 — 조회와 처리를 분리).
          "전체 N건"의 N은 meta.total이 아니라 summary의 open_action_count
          합산이다(api_contract v2.0 9.1절). 대시보드는 이미 summary를
          호출하므로 같은 숫자를 두 경로로 얻지 않는다. */}
      <section className="mt-8">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-semibold">긴급 액션</h2>
          <Link to="/actions" className="text-sm underline">
            전체 {t.open_action_count}건 처리하러 가기 →
          </Link>
        </div>
        <div className="rounded border border-gray-300 p-4 text-sm text-gray-600">
          {t.open_action_count === 0
            ? "처리할 작업이 없습니다 — 모든 숙소가 정상 운영 중"
            : "액션 목록은 9/9에 연결합니다."}
          {/* TODO(9/9): fetchActionItems(id, { status: 'OPEN', size: 5 })로
              숙소별 프리뷰를 붙인다. API 함수는 src/api/actionItems.ts에 있다. */}
        </div>
      </section>

      {/* TODO(9/9 이후): 지식베이스 등록 유도 배너가 들어갈 자리.
          knowledge_chunks가 0건일 때만 노출한다. 조건 없이 항상 뜨는
          하드코딩 배너를 넣지 않기로 했다(9/8 결정) — 지식베이스가 채워져도
          "등록해보세요"가 남아 시연 화면에 그대로 나갈 위험이 있다. */}
    </div>
  );
}
