import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.js'],
    setupFiles: ['src/test/setup.js'],
    clearMocks: true,
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      all: true,
      include: [
        'src/composables/useApiFetch.js',
        'src/stores/user.js',
        'src/utils/Utils.js',
        'src/utils/authFetch.js',
        'src/utils/useToast.js',
      ],
      exclude: ['src/**/*.test.js'],
      reporter: ['text', 'html', 'json-summary', 'lcov'],
      reportsDirectory: 'output/evidence/web-coverage',
      thresholds: {
        lines: 60,
        functions: 60,
        branches: 60,
        statements: 60,
      },
    },
  },
})
