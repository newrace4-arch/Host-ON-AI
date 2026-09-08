/**
 * 미구현 화면 공용 컴포넌트 (2026-09-08)
 *
 * /dashboard만 실제 구현하고 나머지는 이 파일 하나를 이름만 바꿔
 * 재사용한다 — 화면 수만큼 파일을 만들지 않는다.
 *
 * `scoped`는 **숙소 스코프 화면**(?property= 컨텍스트가 필요한 7개)임을
 * 뜻한다. 숙소 목록이 없거나 실패한 상태를 `PropertyScopeGate`가 대신
 * 처리하므로, 실제 화면을 구현할 때도 같은 감싸기를 그대로 쓰면 된다.
 *
 * 제목(h1)은 **항상** 보여준다. 목록 조회에 실패해도 사용자는 자기가 어느
 * 화면에 있는지 알아야 한다. 제목 문구는 ui_design.md 2절의 공식 화면명이다
 * (사이드바 축약 라벨과 다르다 — 5-2절).
 */

import PropertyScopeGate from "@/components/PropertyScopeGate";

export default function Placeholder({
  name,
  scoped = false,
}: {
  name: string;
  scoped?: boolean;
}) {
  const body = <p className="mt-2 text-sm text-gray-600">준비 중입니다.</p>;

  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold">{name}</h1>
      {scoped ? <PropertyScopeGate>{body}</PropertyScopeGate> : body}
    </div>
  );
}
