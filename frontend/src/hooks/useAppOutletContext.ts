/**
 * AppLayout이 내려준 컨텍스트를 꺼낸다 (2026-09-08)
 *
 * `useOutletContext`를 화면마다 제네릭과 함께 쓰면 타입 인자를 빠뜨리기
 * 쉽다(코딩규칙 8번의 `api` 래퍼와 같은 취지 — 호출부가 빠뜨릴 수 없게
 * 한 곳에 고정한다).
 *
 * ⚠️ **AppLayout 안의 라우트에서만 쓸 수 있다.** /login·/signup·/onboarding은
 *    레이아웃 밖이라 컨텍스트가 없다.
 */

import { useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "@/types/ui";

export function useAppOutletContext(): AppOutletContext {
  return useOutletContext<AppOutletContext>();
}
