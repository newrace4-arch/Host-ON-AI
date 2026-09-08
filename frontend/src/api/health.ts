/**
 * 웨이크업 전용 API (2026-09-09)
 *
 * Render 무료 플랜은 15분 무요청 시 슬립하고, 깨어나는 데 약 50초가
 * 걸린다. 대시보드가 숙소 3~5개를 병렬 호출하므로 서버가 자고 있으면
 * 요청이 한꺼번에 몰린다.
 *
 * ⚠️ **`/health`가 가벼워서 빠른 게 아니다.** `/health`도 콜드 스타트를
 *    똑같이 겪는다. 이 설계의 이유는 **"50초를 한 번만 기다리고, 이후
 *    호출은 깨어난 서버로 가서 빠르다"**는 것이다. 즉 대기 시간을
 *    없애는 게 아니라 **한 곳에 모으는** 전략이다.
 *
 * ⚠️ **실제 콜드 스타트는 로컬에서 재현할 수 없다.** 로컬 uvicorn은 항상
 *    깨어 있다. 타임아웃 값(60초)은 추정치이며 **배포(10/1) 후 실측해
 *    조정한다.**
 *
 * 이 요청은 `client`를 쓰지 않는다:
 *   - `client`의 타임아웃은 10초라 콜드 스타트를 기다리지 못한다
 *   - `/health`는 공통 봉투 `{data, error}`를 쓰지 않는 유일한
 *     엔드포인트다(api_contract v2.0 11절). 언래핑 인터셉터가 필요 없다
 *   - 401 리다이렉트도 무관하다(인증 불필요 엔드포인트)
 */

import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/**
 * 웨이크업 전용 타임아웃.
 *
 * 일반 API 타임아웃(10초, `client.ts`)과 **의도적으로 분리**한다. 콜드
 * 스타트 50초를 기다려야 하는 것은 이 요청뿐이고, 나머지 API가 60초를
 * 기다리면 장애 시 화면이 1분간 멈춘 것처럼 보인다.
 */
const WAKEUP_TIMEOUT_MS = 60_000;

const wakeUpClient = axios.create({
  baseURL: BASE_URL,
  timeout: WAKEUP_TIMEOUT_MS,
});

/**
 * 서버를 깨운다. 성공하면 resolve, 실패·타임아웃이면 throw.
 *
 * 응답 본문은 쓰지 않는다 — 200이 왔다는 사실만으로 충분하다.
 */
export async function wakeUpServer(): Promise<void> {
  await wakeUpClient.get("/health");
}
