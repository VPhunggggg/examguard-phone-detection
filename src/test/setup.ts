import '@testing-library/jest-dom/vitest'

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
})

if (!URL.createObjectURL) {
  URL.createObjectURL = () => 'blob:test-preview'
}

if (!URL.revokeObjectURL) {
  URL.revokeObjectURL = () => undefined
}
