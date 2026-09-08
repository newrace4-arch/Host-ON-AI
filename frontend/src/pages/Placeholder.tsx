/**
 * 미구현 화면 공용 컴포넌트 (2026-09-08)
 *
 * 라우트 12개 중 /dashboard만 실제 구현한다. 나머지 11개는 이 파일 하나를
 * 이름만 바꿔 재사용한다 — 11개 파일을 각각 만들지 않는다.
 */

export default function Placeholder({ name }: { name: string }) {
  return (
    <div className="p-6">
      <h1 className="text-lg font-semibold">{name}</h1>
      <p className="mt-2 text-sm text-gray-600">준비 중입니다.</p>
    </div>
  );
}
