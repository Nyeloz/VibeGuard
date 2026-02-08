"use client";

import React, { useEffect, useRef, useState } from "react";

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("");
  const [response, setResponse] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function handleSubmit(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!repoUrl.trim()) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const res = await fetch("/api/scan/github", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl }),
      });

      const json = await res.json();

      if (!res.ok) {
        setError(json?.detail || json?.error || "Request failed");
      } else {
        setResponse(json);
        // clear input on success so users see results clearly
        setRepoUrl("");
        // return focus to input
        inputRef.current?.focus();
      }
    } catch (err: any) {
      setError(err?.message || "Could not connect to backend");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <header className="site-header">
        <img src="/VibesGuard_Logo.png" alt="VibeGuard Logo" className="site-logo" />
        <div className="site-title">VibeGuard</div>
        <div className="site-sub">Guarding your automated code against vulnerabilities</div>
      </header>

      <main className="container">
        <section className="card scan-card">
          <form id="scan-form" className="scan-form" onSubmit={handleSubmit}>
            <label htmlFor="flink" className="small-muted" style={{ textAlign: "center", display: "block", marginBottom: 6 }}>
              Enter GitHub repository URL
            </label>

            <div className="input-row">
              <input
                ref={inputRef}
                id="flink"
                type="url"
                placeholder="https://github.com/owner/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                aria-label="GitHub repository URL"
              />
            </div>

            <div style={{ display: "flex", justifyContent: "center", marginTop: 12 }}>
              <button id="scan-btn" className="button-primary" type="submit" disabled={loading || !repoUrl.trim()}>
                {loading ? "Scanning…" : "Scan"}
              </button>
            </div>

            <div className="small-muted" style={{ textAlign: "center", marginTop: 10 }}>
              Public GitHub repos only — no auth required for demo
            </div>
          </form>
        </section>

        <aside className="card results-card">
          <h2 style={{ textAlign: "center" }}>Flagged Messages</h2>
          <div style={{ textAlign: "center", marginBottom: 8, color: "var(--muted)" }}>Results are redacted and filtered for high-confidence matches.</div>

          {error && (
            <div style={{ color: "#ffb4b4", textAlign: "center", marginBottom: 8 }}>{error}</div>
          )}

          <pre id="show-errors">{response ? JSON.stringify(response, null, 2) : "No results yet — enter a repo and press Scan."}</pre>

          <div className="footer-note">Results are redacted and filtered for high-confidence matches.</div>
        </aside>
      </main>
    </div>
  );
}
