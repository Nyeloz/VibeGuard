"use client";

import {useState} from "react";

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("");
  const [response, setResponse] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    if (!repoUrl.trim()) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const res = await fetch("/api/scan/github", {
        method: "POST",
        headers: {"Content-Type": "application/json",},
        body: JSON.stringify({ repo_url: repoUrl }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || "Request failed");
        return;
      }

      setResponse(data);
    } catch {
      setError("Could not connect to backend");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>VibeGuard</h1>

      <div style={{ marginBottom: "1rem" }}>
        <input
          type="text"
          placeholder="https://github.com/owner/repo"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
          }}
          style={{
            width: "420px",
            padding: "0.5rem",
            marginRight: "0.5rem",
          }}
        />

        <button
          onClick={handleSubmit}
          disabled={loading || !repoUrl.trim()}
        >
          {loading ? "Scanning..." : "Scan"}
        </button>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {response && (
        <pre style={{ marginTop: "1rem" }}>
          {JSON.stringify(response, null, 2)}
        </pre>
      )}
    </main>
  );
}
