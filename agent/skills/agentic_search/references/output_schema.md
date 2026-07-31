# Output Schema

Use a machine-friendly object in this shape:

```json
{
  "objective": "string",
  "findings": [
    {
      "claim": "string",
      "support_assessment": "direct|indirect|conflicting",
      "limitations": "string",
      "evidence": [
        {
          "source_type": "document|scholarly|web",
          "source_id": "string",
          "locator": "string",
          "citation_tag": "<evidence>chunk_id|p页码|o起止偏移</evidence>",
          "retrieval_score": null
        }
      ]
    }
  ],
  "conflicts": [
    {
      "topic": "string",
      "claim_a": "string",
      "claim_b": "string",
      "note": "string"
    }
  ],
  "open_questions": ["string"],
  "next_actions": ["string"]
}
```

For `source_type = "document"`, `locator` should be derived from `page_no` and `offset_start-offset_end`, and `citation_tag` should use the exact canonical evidence format.
`retrieval_score` is optional transport metadata. Preserve a score only when the retrieval tool returned one; never estimate or invent it.

If strict JSON is not requested, keep the same sections in markdown, and preserve the same canonical `<evidence>chunk_id|p页码|o起止偏移</evidence>` tags for document citations.
