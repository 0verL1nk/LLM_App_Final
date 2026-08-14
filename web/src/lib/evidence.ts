const EVIDENCE_TAG = /<evidence>([^<]+)<\/evidence>/gi

export function formatEvidenceCitations(
  content: string,
  evidence: Array<Record<string, unknown>> = [],
): string {
  return content.replace(EVIDENCE_TAG, (_tag, rawReference: string) => {
    const reference = rawReference.trim()
    const chunkId = reference.split("|", 1)[0]?.trim() ?? ""
    const evidenceIndex = evidence.findIndex((item) => String(item.chunk_id ?? "") === chunkId)
    const label = evidenceIndex >= 0 ? String(evidenceIndex + 1) : "引用"
    return ` [${label}](#evidence-${encodeURIComponent(reference)})`
  })
}
