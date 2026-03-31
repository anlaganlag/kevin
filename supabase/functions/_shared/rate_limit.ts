// supabase/functions/_shared/rate_limit.ts
// In-memory sliding window rate limiter per API key.
// Resets when the edge function cold-starts (acceptable for MVP).

const WINDOW_MS = 60_000; // 1 minute
const MAX_REQUESTS = 10;  // per window per key

interface Window {
  timestamps: number[];
}

const windows = new Map<string, Window>();

/** Check rate limit for an API key. Returns null if allowed, or a Response if blocked. */
export function checkRateLimit(req: Request): { limited: boolean; remaining: number } {
  const header = req.headers.get("authorization") ?? "";
  const key = header.startsWith("Bearer ") ? header.slice(7, 15) : "anon"; // first 8 chars as bucket

  const now = Date.now();
  let win = windows.get(key);
  if (!win) {
    win = { timestamps: [] };
    windows.set(key, win);
  }

  // Evict expired entries
  win.timestamps = win.timestamps.filter((t) => now - t < WINDOW_MS);

  if (win.timestamps.length >= MAX_REQUESTS) {
    return { limited: true, remaining: 0 };
  }

  win.timestamps.push(now);
  return { limited: false, remaining: MAX_REQUESTS - win.timestamps.length };
}
