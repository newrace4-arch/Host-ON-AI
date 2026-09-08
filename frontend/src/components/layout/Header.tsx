/**
 * 헤더 (2026-09-08)
 *
 * ⚠️ PropertySwitcher는 **오늘 API를 호출하지 않는다.** 자리와 마크업만
 *    만들고 실제 목록 연결은 9/9로 미룬다.
 *
 * 이유(9/8 결정): GET /properties가 필요한 곳이 셋이다 — 이 드롭다운,
 * 쿼리 폴백, 대시보드 병렬 호출. 각자 부르면 같은 요청이 중복된다.
 * 상태관리 라이브러리를 쓰지 않기로 했으므로 오늘 Header와 Dashboard가
 * 목록을 공유할 깔끔한 방법이 없고, 억지로 Context를 만들면 내일 인증
 * Context와 겹쳐 구조가 꼬인다. 오늘은 훅 안에서만 호출한다.
 *
 * TODO(9/9): 목록 연결 + 폴백 정책 구현
 *   - 쿼리 없음        → 첫 번째 숙소로 치환, URL은 replace(히스토리 보존)
 *   - 존재하지 않는 ID → 안내 후 첫 번째로 폴백
 *   - 숙소 0개         → 자동 선택·폴백을 수행하지 않는다
 *   - usePropertyLink() 공통 훅으로 링크가 현재 쿼리를 자동 보존
 *     · Link 래퍼가 아니라 **경로 문자열을 만들어 반환하는 함수**로 만든다.
 *       래퍼면 navigate() 기반 이동에서 재사용할 수 없다.
 *     · property 외의 기존 쿼리(status·size 등)도 함께 보존해야 한다.
 *   useSearchParams 함정(내일 적용):
 *     · setSearchParams(params, { replace: true }) — 두 번째 인자 필수
 *     · useEffect 의존성에 searchParams 객체를 넣지 말 것(매번 새 객체 →
 *       무한 루프). .get('property')로 꺼낸 문자열만 넣는다
 *     · ?property=abc 에 Number()를 쓰면 NaN — 숫자인지 → 실제 존재하는
 *       숙소인지 순서로 검증한다
 */

export default function Header() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-300 px-4">
      <span className="font-semibold">Host ON</span>

      {/* PropertySwitcher 자리 — 오늘은 비활성 마크업만 */}
      <div className="flex items-center gap-4">
        <div className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-500">
          숙소 선택 (9/9 연결 예정)
        </div>
        <span className="text-sm text-gray-500">계정</span>
      </div>
    </header>
  );
}
