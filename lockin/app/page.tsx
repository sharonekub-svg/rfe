"use client";

import { useState } from "react";

export default function Home() {
  const [goal, setGoal] = useState("");
  const [deadline, setDeadline] = useState("");
  const [time, setTime] = useState("");
  const [loading, setLoading] = useState(false);
  const [plan, setPlan] = useState("");
  const [error, setError] = useState("");

  async function generate() {
    setError("");
    setPlan("");
    if (!goal.trim()) {
      setError("Tell me your goal first 🙂");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal, deadline, time }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Something went wrong.");
      setPlan(data.plan);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="wrap">
      <span className="badge">⚡ LockIn — your AI study coach</span>
      <h1>
        Stop scrolling. <span className="grad">Lock in.</span>
      </h1>
      <p className="sub">
        Tell me what you&apos;re studying for. I&apos;ll build you a personal,
        day-by-day plan in seconds — so you always know exactly what to do next.
      </p>

      <div className="card">
        <label>What&apos;s your goal?</label>
        <input
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="e.g. Pass my biology final"
        />

        <label>When&apos;s the deadline?</label>
        <input
          value={deadline}
          onChange={(e) => setDeadline(e.target.value)}
          placeholder="e.g. In 3 weeks, on June 30"
        />

        <label>How much time can you study, and what&apos;s in your way?</label>
        <textarea
          rows={3}
          value={time}
          onChange={(e) => setTime(e.target.value)}
          placeholder="e.g. About 1 hour a day. I keep procrastinating and don't know where to start."
        />

        <button onClick={generate} disabled={loading}>
          {loading ? "Building your plan…" : "Build my lock-in plan →"}
        </button>

        {error && <p className="error">{error}</p>}
        {plan && <div className="plan">{plan}</div>}
      </div>

      <p className="foot">Built by a 14-year-old who got tired of procrastinating.</p>
    </main>
  );
}
