class MemoryStorage {
  constructor() {
    this.values = new Map()
  }

  get length() {
    return this.values.size
  }

  clear() {
    this.values.clear()
  }

  getItem(key) {
    return this.values.has(String(key)) ? this.values.get(String(key)) : null
  }

  key(index) {
    return [...this.values.keys()][index] ?? null
  }

  removeItem(key) {
    this.values.delete(String(key))
  }

  setItem(key, value) {
    this.values.set(String(key), String(value))
  }
}

const storage = new MemoryStorage()
Object.defineProperty(globalThis, 'localStorage', { value: storage, configurable: true })
Object.defineProperty(window, 'localStorage', { value: storage, configurable: true })
