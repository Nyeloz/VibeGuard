## Finding
- rule_id: string (required)
- severity: "low" | "medium" | "high"
- message: string (required)
- path: string (optional)
- line: number (optional)
- snippet: string (optional)
- location: number (optional)

## GitHubScanRequest
{
  "findings": [Finding]
}

## Notes
- Fields are frozen for MVP
- New optional fields may be added
- Fields may not be renamed or removed
