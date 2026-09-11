/**
 * 로그인 (2026-09-11)
 *
 * 근거: docs/ui_design.md 4-1·1-5·1-6절, docs/api_contract.md 1.2절
 *
 * ## 실패 메시지를 하나로 통일한다
 *
 * 이메일이 없는 경우와 비밀번호가 틀린 경우를 **구분하지 않는다.** 알려
 * 주면 이메일만 바꿔가며 가입된 계정을 열거할 수 있다. 서버도 같은
 * 이유로 `401 INVALID_CREDENTIALS` 하나만 반환한다(api_contract 1.1절).
 *
 * ## `?redirect` — 오픈 리다이렉트 방어
 *
 * 세션이 만료돼 밀려온 사용자는 보던 화면으로 돌아가야 한다(1-6절).
 * 다만 값을 그대로 따라가면 `?redirect=https://evil.example`이 로그인
 * 직후 외부로 보내는 피싱 경로가 된다. **`/`로 시작하는 내부 경로만**
 * 허용하고 `//`(프로토콜 상대 URL)도 거부한다.
 *
 * ## StrictMode (CLAUDE.md 규칙 14)
 *
 * 이 화면에는 **effect가 없다.** `?redirect`와 도착 사유는 URL에서 바로
 * 파생되므로 effect로 동기화할 이유가 없다. 제출 중 판정은 ref로 하고
 * **setState 업데이터 안에서는 아무것도 읽거나 쓰지 않는다** — 개발
 * 모드에서만 재현되는 버그를 이 프로젝트에서 이미 두 번 겪었다
 * (troubleshooting 26·28).
 */

import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { login, toAuthFailure } from "@/api/auth";
import {
  AuthShell,
  Field,
  FormError,
  NETWORK_ERROR_TEXT,
  SubmitButton,
  UNKNOWN_ERROR_TEXT,
} from "@/components/auth/AuthFormParts";

/** 어느 쪽이 틀렸는지 알려주지 않는다(계정 열거 방어). */
const INVALID_CREDENTIALS_TEXT = "이메일 또는 비밀번호가 올바르지 않습니다.";

/**
 * `?redirect` 값이 앱 내부 경로인가.
 *
 * 허용: `/dashboard`, `/cleaning?property=2&task_id=42`
 * 거부: `https://evil.example`(외부), `//evil.example`(프로토콜 상대 —
 *       브라우저가 현재 스킴을 붙여 **외부로 나간다**), `dashboard`(상대 경로)
 */
export function safeRedirect(raw: string | null): string {
  if (!raw) return "/dashboard";
  if (!raw.startsWith("/")) return "/dashboard";
  if (raw.startsWith("//")) return "/dashboard";
  return raw;
}

/**
 * 이 화면에 **왜** 왔는지 알린다(ui_design 1-6·4-1절).
 *
 * 아무 설명 없이 로그인 화면이 뜨면 앱이 고장난 것으로 보인다. 다만
 * **세 경우를 뭉뚱그리면 안 된다** — 로그인한 적 없는 사용자에게
 * "만료되었습니다"라고 하면 자기가 뭘 잘못했는지 찾게 된다.
 *
 *   required — ProtectedRoute가 막았다(토큰 없음)
 *   expired  — 401 인터셉터가 보냈다(쓰던 중 만료)
 *   logout   — 계정 메뉴에서 스스로 나갔다
 *   그 외    — `/login`에 직접 왔다. 안내하지 않는다
 *
 * `logout`을 따로 둔 이유: 스스로 나간 사람에게 "만료되었습니다"라고 하면
 * 거짓말이고, 아무 말도 안 하면 버튼을 눌렀는데 화면만 바뀌어 "된 건가"
 * 싶어진다. 확인만 해 주면 된다.
 */
export function arrivalNotice(reason: string | null): string | null {
  if (reason === "expired") return "로그인이 만료되어 다시 로그인해 주세요.";
  if (reason === "required") return "로그인이 필요한 화면입니다.";
  if (reason === "logout") return "로그아웃되었습니다.";
  return null;
}

export default function Login() {
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 제출 중 판정을 state가 아니라 ref로 둔다. state는 갱신이 비동기라
  //   버튼 연타 시 같은 렌더의 stale 값을 보고 두 번 통과할 수 있다.
  //   ref는 즉시 반영되고, **업데이터 바깥에서** 읽으므로 규칙 14를 지킨다.
  const inFlight = useRef(false);

  // URL에서 바로 파생한다 — effect로 state에 복사하지 않는다.
  const redirectTo = safeRedirect(params.get("redirect"));
  const notice = arrivalNotice(params.get("reason"));

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (inFlight.current) return;

    inFlight.current = true;
    setSubmitting(true);
    setError(null);

    try {
      await login(email.trim(), password);
      // 성공 — 토큰은 api/auth.ts가 이미 저장했다.
      //   replace를 쓴다. push면 대시보드에서 뒤로가기 했을 때 이미
      //   로그인된 상태로 로그인 화면이 다시 뜬다.
      navigate(redirectTo, { replace: true });
      return;
    } catch (err) {
      const failure = toAuthFailure(err);
      if (failure.kind === "network") {
        setError(NETWORK_ERROR_TEXT);
      } else if (failure.kind === "server") {
        // 자격증명 오류든 형식 오류든 **같은 문구**다. 형식 오류만
        //   따로 알려주면 "형식은 맞는 이메일"인지가 드러나 열거에
        //   쓰인다.
        setError(INVALID_CREDENTIALS_TEXT);
      } else {
        setError(UNKNOWN_ERROR_TEXT);
      }
    } finally {
      // 성공 경로에서도 실행되지만, 그때는 이미 화면이 바뀌고 있어
      //   깜빡임이 보이지 않는다. 실패 시 버튼이 반드시 살아나야 하므로
      //   finally에 둔다.
      inFlight.current = false;
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="로그인"
      footer={
        <>
          계정이 없으신가요?{" "}
          <Link to="/signup" className="underline">
            회원가입
          </Link>
        </>
      }
    >
      {/* 왜 이 화면에 왔는지 알린다 — 설명 없이 로그인 화면이 뜨면
          사용자는 앱이 고장난 것으로 받아들인다(ui_design 1-6절). */}
      {notice && (
        <p className="mt-2 rounded bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {notice}
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <Field
          id="email"
          label="이메일"
          type="email"
          value={email}
          onChange={setEmail}
          disabled={submitting}
          autoComplete="email"
        />
        <Field
          id="password"
          label="비밀번호"
          type="password"
          value={password}
          onChange={setPassword}
          disabled={submitting}
          autoComplete="current-password"
        />

        {/* 실패해도 입력값을 지우지 않는다 — 이메일을 다시 치게 하지
            않는다(ui_design 4-1절). */}
        {error && <FormError>{error}</FormError>}

        <SubmitButton
          submitting={submitting}
          idleLabel="로그인"
          busyLabel="로그인 중..."
        />
      </form>
    </AuthShell>
  );
}
