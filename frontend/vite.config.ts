import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Tailwind는 v4(4.3.3)이므로 공식 Vite 플러그인 방식을 쓴다.
// v3의 postcss.config / tailwind.config 파일은 만들지 않는다.
// CSS 진입점(src/index.css)에서 `@import "tailwindcss";` 한 줄로 로드된다.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // 절대 경로 @/ → src/ (tsconfig.app.json의 paths와 쌍으로 유지할 것)
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
