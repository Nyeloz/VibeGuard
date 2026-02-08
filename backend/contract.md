## Finding
- rule_id: string (required)
- severity: "low" | "medium" | "high"
- message: string (required)
- line: number (optional)
- snippet: string (optional)

## GitHubScanRequest
{
  "findings": [Finding]
}

## Notes
- Fields are frozen for MVP
- New optional fields may be added
- Fields may not be renamed or removed

