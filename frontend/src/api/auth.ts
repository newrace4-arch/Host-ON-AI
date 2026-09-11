/**
 * 인증 API 클라이언트 (2026-09-11)
 *
 * 근거: docs/api_contract.md 1절, docs/ui_design.md 4-1·4-2절
 *
 * ⚠️ **`authApi`를 쓴다. `api`를 쓰면 안 된다.**
 * `api`(= `client`)에는 401 인터셉터가 붙어 있어, 로그인 실패의 401에도
 * 토큰을 지우고 `/login`으로 보낸다. **로그인 화면에서 로그인 화면으로
 * 튕기는 것처럼 보인다.** `authApi`는 언래핑만 하고 401을 그대로
 * 던지므로 호출부가 `try/catch`로 잡아 메시지만 표시할 수 있다
 * (CLAUDE.md 코딩규칙 15, ui_design 4-1절).
 *
 * 【에러 코드 추출을 여기 모은 이유】
 * `authClient`의 응답 인터셉터는 **성공 경로만** 언래핑한다. 실패는
 * `AxiosError`로 통과하므로 봉투가 `error.response.data.error.code`에
 * 있다. 이 경로를 화면마다 다시 쓰면 한 군데만 틀려도 조용히 "알 수 없는
 * 오류"가 된다.
 */

import { AxiosError } from "axios";

import { authApi, setAccessToken } from "@/api/client";
import type { TokenResponse } from "@/types/ui";

/** api_contract 1.1절 에러 코드 표. 서버가 실제로 내는 값들이다. */
export type AuthErrorCode =
  | "INVALID_CREDENTIALS"
  | "EMAIL_ALREADY_EXISTS"
  | "INVALID_EMAIL_FORMAT"
  | "INVALID_PASSWORD_FORMAT"
  | "PASSWORD_TOO_LONG"
  | "VALIDATION_ERROR"
  | "UNAUTHORIZED";

/**
 * 실패 원인을 화면이 분기할 수 있는 형태로 정규화한다.
 *
 * `kind`가 셋인 이유는 **화면의 대응이 셋이기 때문**이다.
 *   server  — 서버가 판정한 것. `code`로 필드를 가른다
 *   network — 응답 자체가 없음. **토큰을 지우지 않는다**(ui_design 1-6)
 *   unknown — 그 외
 */
export type AuthFailure =
  | { kind: "server"; code: AuthErrorCode | string; message: string }
  | { kind: "network" }
  | { kind: "unknown" };

interface ErrorEnvelope {
  error?: { code?: string; message?: string } | null;
}

/**
 * `AxiosError` → `AuthFailure`.
 *
 * **`error.response`의 유무로 네트워크 오류를 판정한다.** `client.ts`의
 * `isRetryable`과 같은 기준이다 — 두 곳이 다른 기준을 쓰면 "재시도는
 * 하는데 화면은 서버 오류라고 말하는" 상태가 생긴다.
 */
export function toAuthFailure(error: unknown): AuthFailure {
  if (!(error instanceof AxiosError)) return { kind: "unknown" };

  // 응답이 아예 없다 = 네트워크 오류·타임아웃(Render 슬립 포함).
  if (!error.response) return { kind: "network" };

  const body = error.response.data as ErrorEnvelope | undefined;
  const code = body?.error?.code;
  if (!code) return { kind: "unknown" };

  return { kind: "server", code, message: body?.error?.message ?? "" };
}

/**
 * 성공 응답에서 토큰을 꺼내 저장하고 `host`를 돌려준다.
 *
 * **저장을 여기서 한다.** 화면마다 하면 한 곳을 빠뜨렸을 때 "로그인은
 * 됐는데 다음 요청이 401"이 되고, 원인이 화면에 드러나지 않는다.
 */
function persist(payload: TokenResponse | null): TokenResponse {
  if (!payload?.access_token) {
    // 200/201인데 토큰이 없는 경우. 서버 계약 위반이라 정상 흐름이 아니다.
    throw new Error("로그인 응답에 토큰이 없습니다.");
  }
  setAccessToken(payload.access_token);
  return payload;
}

/** POST /auth/login — api_contract 1.2절 */
export async function login(
  email: string,
  password: string,
): Promise<TokenResponse> {
  const res = await authApi.post<TokenResponse>("/auth/login", {
    email,
    password,
  });
  return persist(res.data);
}

/** POST /auth/signup — api_contract 1.3절. 201 + 토큰을 함께 받는다. */
export async function signup(
  email: string,
  password: string,
  name: string,
): Promise<TokenResponse> {
  const res = await authApi.post<TokenResponse>("/auth/signup", {
    email,
    password,
    name,
  });
  return persist(res.data);
}
