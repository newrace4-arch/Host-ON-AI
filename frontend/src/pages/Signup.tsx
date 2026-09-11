/**
 * 회원가입 (2026-09-11)
 *
 * 근거: docs/ui_design.md 4-2·1-5절, docs/api_contract.md 1.3절
 *
 * ## 로그인과 반대로 — 실패를 **필드별로** 알려준다
 *
 * 로그인은 계정 열거를 막으려고 문구를 하나로 통일하지만, 가입 화면은
 * 애초에 **"이 이메일을 쓸 수 있는가"를 묻는 곳**이라 숨길 수 없다.
 * 숨기면 사용자가 왜 가입이 안 되는지 알 수 없다(ui_design 4-2절).
 *
 * ## 비밀번호 안내는 "8자 이상 64자 이하"다
 *
 * 72는 bcrypt의 **바이트** 한계이지 글자 수가 아니다. 화면에 72를 적으면
 * 한글 사용자는 72자까지 되는 줄 알지만 **25자에서 거부된다**
 * (한글 1자 = UTF-8 3바이트, 25×3 = 75 > 72). 바이트 초과는 서버가
 * `PASSWORD_TOO_LONG`으로 따로 알려주며 그때 한글 기준으로 설명한다.
 *
 * ## 가입 성공 시 `/login`을 거치지 않는다
 *
 * 서버가 201과 함께 토큰을 주므로 곧바로 로그인 상태가 된다
 * (api_contract 1.3절). 다시 로그인하게 하면 같은 정보를 두 번 입력하게
 * 된다. 목적지는 `/onboarding`이다(ui_design 4-2절) — 첫 숙소가 없으면
 * 나머지 화면이 동작할 데이터가 없다.
 *
 * ## StrictMode (CLAUDE.md 규칙 14)
 *
 * `Login.tsx`와 같다 — effect 없음, 제출 중 판정은 ref, setState
 * 업데이터 안에서는 아무것도 읽거나 쓰지 않는다.
 */

import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { signup, toAuthFailure } from "@/api/auth";
import {
  AuthShell,
  Field,
  FormError,
  NETWORK_ERROR_TEXT,
  SubmitButton,
  UNKNOWN_ERROR_TEXT,
} from "@/components/auth/AuthFormParts";

/** 서버가 검증하는 값과 같아야 한다(api_contract 1.1절). */
const PASSWORD_MIN = 8;
const PASSWORD_MAX = 64;

const PASSWORD_HINT = `${PASSWORD_MIN}자 이상 ${PASSWORD_MAX}자 이하`;

type FieldErrors = {
  email?: "taken" | string;
  password?: string;
  confirm?: string;
  form?: string;
};

/**
 * 서버 에러 코드 → 어느 필드에 붙일 것인가(ui_design 4-2절 표).
 *
 * `EMAIL_ALREADY_EXISTS`는 `"taken"` 표식으로 돌려준다. 이 경우에만
 * "로그인하러 가기" 링크를 함께 보여야 하는데, 문구에 링크를 섞으면
 * 문자열로 표현할 수 없기 때문이다.
 */
function mapServerError(code: string, message: string): FieldErrors {
  switch (code) {
    case "EMAIL_ALREADY_EXISTS":
      return { email: "taken" };
    case "INVALID_EMAIL_FORMAT":
      return { email: "이메일 형식이 올바르지 않습니다." };
    case "INVALID_PASSWORD_FORMAT":
      return { password: `비밀번호는 ${PASSWORD_HINT}여야 합니다.` };
    case "PASSWORD_TOO_LONG":
      // 서버 문구를 그대로 쓴다 — 한글 몇 자까지인지를 서버가 알려준다.
      //   ("한글은 한 글자가 3바이트라 24자를 넘으면 사용할 수 없습니다")
      return { password: message || "비밀번호가 너무 깁니다." };
    default:
      // VALIDATION_ERROR 등. name 위반이 여기로 온다(전용 코드가 없다).
      return { form: message || UNKNOWN_ERROR_TEXT };
  }
}

export default function Signup() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});

  const inFlight = useRef(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (inFlight.current) return;

    // 비밀번호 확인은 **서버에 보내지 않고 여기서 막는다**(ui_design 4-2절).
    //   서버가 알 수 없는 값이라 보낼 이유가 없고, 왕복 없이 즉시 알려주는
    //   편이 낫다.
    if (password !== confirm) {
      setErrors({ confirm: "비밀번호가 일치하지 않습니다." });
      return;
    }

    inFlight.current = true;
    setSubmitting(true);
    setErrors({});

    try {
      await signup(email.trim(), password, name.trim());
      // 토큰은 api/auth.ts가 저장했다. /login을 거치지 않는다.
      navigate("/onboarding", { replace: true });
      return;
    } catch (err) {
      const failure = toAuthFailure(err);
      if (failure.kind === "network") {
        setErrors({ form: NETWORK_ERROR_TEXT });
      } else if (failure.kind === "server") {
        setErrors(mapServerError(failure.code, failure.message));
      } else {
        setErrors({ form: UNKNOWN_ERROR_TEXT });
      }
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="회원가입"
      footer={
        <>
          이미 계정이 있으신가요?{" "}
          <Link to="/login" className="underline">
            로그인
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} noValidate>
        <Field
          id="email"
          label="이메일"
          type="email"
          value={email}
          onChange={setEmail}
          disabled={submitting}
          autoComplete="email"
          error={
            errors.email === "taken" ? (
              <>
                이미 가입된 이메일입니다.{" "}
                <Link to="/login" className="underline">
                  로그인하러 가기
                </Link>
              </>
            ) : (
              errors.email
            )
          }
        />

        {/* HOSTS.name이 NOT NULL이라 선택이 될 수 없다(ui_design 4-2절). */}
        <Field
          id="name"
          label="이름"
          type="text"
          value={name}
          onChange={setName}
          disabled={submitting}
          autoComplete="name"
        />

        <Field
          id="password"
          label="비밀번호"
          type="password"
          value={password}
          onChange={setPassword}
          disabled={submitting}
          autoComplete="new-password"
          hint={PASSWORD_HINT}
          error={errors.password}
        />

        <Field
          id="confirm"
          label="비밀번호 확인"
          type="password"
          value={confirm}
          onChange={setConfirm}
          disabled={submitting}
          autoComplete="new-password"
          error={errors.confirm}
        />

        {errors.form && <FormError>{errors.form}</FormError>}

        <SubmitButton
          submitting={submitting}
          idleLabel="가입하기"
          busyLabel="가입 중..."
        />
      </form>
    </AuthShell>
  );
}
