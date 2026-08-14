export type SessionContextUsage = {
  usedTokens: number;
  maxTokens: number;
  messageTokens: number | null;
  segments: Array<{ key: string; label: string; tokens: number }>;
};

export function sessionContextUsage(value: unknown): SessionContextUsage | null {
  if (!value || typeof value !== "object") return null;
  const snapshot = value as Record<string, unknown>;
  const context = snapshot.session_context;
  if (!context || typeof context !== "object") return null;
  const details = context as Record<string, unknown>;
  const usedTokens = details.used_tokens;
  const maxTokens = details.model_window_tokens;
  if (typeof usedTokens !== "number" || typeof maxTokens !== "number" || maxTokens <= 0) return null;
  const breakdown = details.breakdown;
  const messageUsage = breakdown && typeof breakdown === "object" ? (breakdown as Record<string, unknown>).messages : null;
  const messageTokens = messageUsage && typeof messageUsage === "object" ? (messageUsage as Record<string, unknown>).tokens : null;
  const segments = Array.isArray(details.context_segments)
    ? details.context_segments.flatMap((item) => {
        if (!item || typeof item !== "object") return [];
        const segment = item as Record<string, unknown>;
        return typeof segment.key === "string" && typeof segment.label === "string" && typeof segment.tokens === "number"
          ? [{ key: segment.key, label: segment.label, tokens: segment.tokens }]
          : [];
      })
    : [];
  return { usedTokens, maxTokens, messageTokens: typeof messageTokens === "number" ? messageTokens : null, segments };
}
