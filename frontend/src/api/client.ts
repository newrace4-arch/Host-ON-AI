/**
 * axios 클라이언트 (2026-09-08)
 *
 * 근거: CLAUDE.md 코딩규칙 9번(프론트 재시도 패턴, 9/8 보강),
 *       docs/api_contract.md v2.0 0절(공통 응답 봉투)
 *
 * ⚠️ 【반환 타입 — 호출 전에 반드시 읽을 것】
 * 응답 인터셉터가 `response.data`를 반환해 **axios 껍데기를 벗긴다.**
 * 따라서 이 클라이언트의 반환값은 `AxiosResponse`가 아니라 **언래핑된
 * `Envelope<T>`**(`{ data, meta?, error }`)다. `res.status`·`res.headers`는
 * 존재하지 않으며, `res.data.data` 같은 이중 접근도 없다.
 *
 * **호출 시 두 번째 제네릭(R)을 지정해야 한다.** 지정하지 않으면 타입은
 * `AxiosResponse<T>`로 추론되어 런타임 값과 어긋난다.
 *
 *   client.get<unknown, Envelope<Property[]>>("/properties")
 *   // 두 번째 제네릭(R)을 지정해야 AxiosResponse 래핑이 대체된다
 *
 * 【두 인스턴스의 차이】
 *   client     — 언래핑 + 401 리다이렉트 + GET 재시도
 *   authClient — 언래핑만 (401·재시도 없음)
 *
 * 여기서 결정한 것 세 가지:
 *   1. 자동 재시도는 GET만. POST·PATCH·DELETE는 하지 않는다.
 *   2. axios 껍데기만 벗기고 백엔드 봉투 { data, meta?, error }는 유지한다.
 *   3. 인증 API는 별도 인스턴스를 쓴다(401 리다이렉트·재시도 미적용).
 */

import axios, { AxiosError, type AxiosInstance } from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/**
 * 토큰 저장 위치는 **이 두 함수에서만** 다룬다.
 * 내일 로그인 구현 시 저장 방식을 바꾸더라도 여기만 고치면 된다.
 * (오늘은 저장하는 쪽이 없어 항상 null이다 — 인터셉터 구조만 준비)
 */
const TOKEN_KEY = "hoston_access_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/* ── 재시도 정책 ────────────────────────────────────────────────── */

const RETRYABLE_STATUS = [502, 503, 504];
const MAX_RETRY = 1;
const RETRY_BASE_MS = 800;
const RETRY_JITTER_MS = 400;

/**
 * 재시도해도 되는 요청인가.
 *
 * - **GET만** 재시도한다. PATCH가 서버에서 성공했는데 응답만 타임아웃된
 *   경우 재시도가 같은 작업을 두 번 실행하기 때문이다(정산 확정,
 *   액션 처리에서 발생하면 데이터가 어긋난다).
 *   9/8 확인: api_contract v2.0의 GET 20개 중 부수효과가 있는 것은 없다.
 * - 502·503·504는 Render 콜드 스타트·인스턴스 재시작에서 흔하다.
 * - **500은 제외한다.** 서버 내부 코드 오류라 즉시 재시도해도 실패한다.
 * - **4xx(401 포함)도 제외한다.** 재시도로 해결되지 않는다.
 * - 네트워크 오류(응답 자체가 없음)는 `!error.response`로 판정한다.
 */
function isRetryable(error: AxiosError): boolean {
  const method = error.config?.method?.toUpperCase();
  if (method !== "GET") return false;

  if (!error.response) return true; // 네트워크 오류 · 타임아웃
  return RETRYABLE_STATUS.includes(error.response.status);
}

/**
 * 고정 지연이 아니라 jitter를 섞는다.
 * 숙소 3~5개의 summary를 병렬 호출하므로, 동시에 실패하면 재시도가 한
 * 덩어리로 몰려 서버를 다시 밀어버린다.
 */
function retryDelayMs(): number {
  return RETRY_BASE_MS + Math.random() * RETRY_JITTER_MS;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/* ── 인스턴스 ───────────────────────────────────────────────────── */

function createInstance(): AxiosInstance {
  return axios.create({
    baseURL: BASE_URL,
    timeout: 10_000,
    headers: { "Content-Type": "application/json" },
  });
}

/** 일반 API용 — 재시도 + 401 처리가 붙는다. */
export const client = createInstance();

/**
 * 인증 API 전용 — **401 리다이렉트와 재시도를 붙이지 않는다.**
 *
 * 로그인 실패(자격증명 오류)의 401과 세션 만료의 401은 성격이 다르다.
 * 전자는 "로그인 실패" 메시지만 보여줘야 하는데, 공용 인스턴스를 쓰면
 * 401 인터셉터가 토큰을 지우고 /login으로 보내버린다.
 * 재시도도 붙이지 않는다 — 로그인은 POST라 애초에 재시도 대상이 아니다.
 *
 * **단, 응답 언래핑은 client와 동일하게 적용한다(아래).** 같은 백엔드가
 * 같은 봉투로 응답하는데 인스턴스마다 접근 방식이 다르면
 * (`res.data` vs `res.data.data`) 호출부에서 혼동이 생긴다.
 */
export const authClient = createInstance();

/**
 * authClient의 유일한 인터셉터 — 언래핑.
 *
 * `createInstance()`에 넣지 않는 이유: 거기에 넣으면 401·재시도까지 두
 * 인스턴스에 공통으로 붙일 수밖에 없는 구조가 되어 분리한 의미가 없어진다.
 * 인스턴스별로 필요한 것만 바깥에서 붙인다.
 */
authClient.interceptors.response.use((response) => response.data);

/* ── 요청 인터셉터: Authorization 헤더 ──────────────────────────── */

/**
 * 오늘은 토큰을 저장하는 쪽이 없어 항상 통과한다.
 * 내일 로그인이 토큰을 저장하는 순간 **이 코드를 고치지 않고** 연동된다.
 */
client.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/* ── 응답 인터셉터: 언래핑 + 재시도 + 401 ───────────────────────── */

/**
 * axios 껍데기(status/headers/config)만 벗기고 **백엔드 봉투는 유지**한다.
 * 호출부가 받는 값은 `{ data, meta?, error }`다.
 *
 * payload까지 벗기지 않는 이유: 목록 API에는 meta가 필요하고 error 봉투도
 * 있다. 여기까지만 벗기면 `response.data.data` 같은 중첩 접근도 사라진다.
 */
client.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError) => {
    const config = error.config as
      | (AxiosError["config"] & { _retryCount?: number })
      | undefined;

    /* 401 — 세션 만료 */
    if (error.response?.status === 401) {
      // 이미 /login에 있으면 리다이렉트하지 않는다. 이 가드가 없으면
      // 로그인 화면에서 401이 날 때마다 무한 루프가 생긴다.
      if (window.location.pathname !== "/login") {
        clearAccessToken();
        // replace를 쓴다 — href는 하드 리로드라 상태가 초기화되고
        // 히스토리에 만료된 경로가 남는다.
        // TODO(9/9): 라우터가 붙으면 navigate 기반으로 교체
        window.location.replace("/login");
      }
      return Promise.reject(error);
    }

    /* 재시도 — GET + 502/503/504 + 네트워크 오류만 */
    if (config && isRetryable(error)) {
      const attempted = config._retryCount ?? 0;
      if (attempted < MAX_RETRY) {
        config._retryCount = attempted + 1;
        await sleep(retryDelayMs());
        return client.request(config);
      }
    }

    return Promise.reject(error);
  },
);
