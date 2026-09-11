/**
 * 로그인·회원가입 공용 폼 조각 (2026-09-11)
 *
 * 근거: docs/ui_design.md 4-1·4-2절, 5절(공통 컴포넌트)
 *
 * 두 화면이 같은 4상태(입력 대기 / 제출 중 / 실패 / 성공)를 쓰므로
 * 조각을 공유한다. 따로 쓰면 **"제출 중에 입력이 비활성되는가"** 같은
 * 규칙이 한쪽에서만 지켜지는 일이 생긴다.
 *
 * ⚠️ 카드 디자인은 다듬지 않았다. 배치와 상태 표현까지가 범위이며
 *    색·여백·타이포는 나중에 정한다(ui_design 원칙 5 — 저해상도).
 */

import type { ReactNode } from "react";

/** 인증 화면 공통 껍데기 — 가운데 정렬 카드. */
export function AuthShell({
  title,
  children,
  footer,
}: {
  title: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-sm rounded border border-gray-300 bg-white p-6">
        <h1 className="text-lg font-semibold">{title}</h1>
        {children}
        <div className="mt-4 text-sm text-gray-600">{footer}</div>
      </div>
    </div>
  );
}

/**
 * 라벨 + 입력 + 필드 인라인 에러.
 *
 * `error`가 있으면 `aria-invalid`와 `aria-describedby`를 함께 건다 —
 * 색만으로 알리면 스크린리더와 색각 이상 사용자가 알 수 없다.
 */
export function Field({
  id,
  label,
  type,
  value,
  onChange,
  disabled,
  error,
  hint,
  autoComplete,
}: {
  id: string;
  label: string;
  type: "email" | "password" | "text";
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
  error?: ReactNode;
  hint?: string;
  autoComplete?: string;
}) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  return (
    <div className="mt-4">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        autoComplete={autoComplete}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        className={`mt-1 w-full rounded border px-3 py-2 text-sm disabled:bg-gray-100 ${
          error ? "border-red-600" : "border-gray-300"
        }`}
      />
      {hint && !error && (
        <p id={hintId} className="mt-1 text-xs text-gray-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="mt-1 text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * 제출 버튼 — 제출 중에는 비활성 + 문구 교체.
 *
 * **중복 제출을 막는 것이 목적이다**(ui_design 4-1). 같은 가입 요청이 두
 * 번 나가면 두 번째는 409를 받아, 방금 자기가 만든 계정 때문에 "이미
 * 가입된 이메일"이라는 메시지를 보게 된다.
 */
export function SubmitButton({
  submitting,
  idleLabel,
  busyLabel,
}: {
  submitting: boolean;
  idleLabel: string;
  busyLabel: string;
}) {
  return (
    <button
      type="submit"
      disabled={submitting}
      className="mt-6 w-full rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white disabled:bg-gray-400"
    >
      {submitting ? busyLabel : idleLabel}
    </button>
  );
}

/** 폼 하단 인라인 에러(로그인은 필드별로 가르지 않고 하나로 표시한다). */
export function FormError({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="mt-4 text-sm text-red-700">
      {children}
    </p>
  );
}

/**
 * 네트워크 오류 문구 — 두 화면이 같은 문구를 쓴다.
 *
 * **서버 오류와 구분해서 말한다.** Render 무료 플랜은 15분 무요청 시
 * 슬립하므로 첫 진입에서 실제로 발생한다. "이메일 또는 비밀번호가
 * 올바르지 않습니다"로 뭉뚱그리면 사용자가 맞는 비밀번호를 계속 다시
 * 친다.
 */
export const NETWORK_ERROR_TEXT =
  "서버와 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.";

export const UNKNOWN_ERROR_TEXT =
  "알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";
