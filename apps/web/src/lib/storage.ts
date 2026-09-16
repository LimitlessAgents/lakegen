const memory = new Map<string, string>();

export function readLocal(key: string): string | null {
  try {
    return localStorage.getItem(key) ?? memory.get(key) ?? null;
  } catch {
    return memory.get(key) ?? null;
  }
}

export function writeLocal(key: string, value: string): void {
  memory.set(key, value);
  try {
    localStorage.setItem(key, value);
  } catch {
    // Storage can be disabled or unavailable (for example, private browsing).
  }
}

export function removeLocal(key: string): void {
  memory.delete(key);
  try {
    localStorage.removeItem(key);
  } catch {
    // Keep the in-memory fallback consistent even if persistent storage fails.
  }
}
