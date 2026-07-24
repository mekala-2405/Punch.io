// Pure data-shaping helpers for the charts. No React, no deps — so they get a
// runnable self-check (node aggregate.js) since this is the only real logic here.

/** Group events into {open, resolved} blocker counts over time (cumulative).
 * Walks events by date: each blocker opens one, each resolution closes one.
 * Returns [{date, open, resolvedTotal}] — one row per date that has activity. */
export function blockerTrend(events) {
  const byDate = new Map();
  for (const e of events) {
    if (e.type !== "blocker" && e.type !== "resolution") continue;
    const row = byDate.get(e.date) || { date: e.date, opened: 0, resolved: 0 };
    if (e.type === "blocker") row.opened += 1;
    else row.resolved += 1;
    byDate.set(e.date, row);
  }
  const dates = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  let openRunning = 0;
  let resolvedRunning = 0;
  return dates.map((r) => {
    openRunning += r.opened - r.resolved;
    resolvedRunning += r.resolved;
    return { date: r.date, open: Math.max(0, openRunning), resolvedTotal: resolvedRunning };
  });
}

/** Messages per channel per day -> rows for a stacked area chart.
 * Returns { rows: [{date, [channel]: count, ...}], channels: [...] }. */
export function activityByChannel(messages) {
  const channels = [...new Set(messages.map((m) => m.channel))].sort();
  const byDate = new Map();
  for (const m of messages) {
    const date = (m.timestamp || "").slice(0, 10);
    if (!date) continue;
    const row = byDate.get(date) || { date };
    row[m.channel] = (row[m.channel] || 0) + 1;
    byDate.set(date, row);
  }
  const rows = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  // fill missing channel keys with 0 so the stack renders cleanly
  for (const row of rows) for (const c of channels) if (!(c in row)) row[c] = 0;
  return { rows, channels };
}

// --- self-check: run `node src/aggregate.js` ---
if (import.meta.url === `file://${process.argv[1]}`) {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL:", msg); process.exit(1); } };

  const trend = blockerTrend([
    { date: "2024-01-01", type: "blocker" },
    { date: "2024-01-01", type: "blocker" },
    { date: "2024-01-02", type: "resolution" },
  ]);
  assert(trend[0].open === 2, "two blockers open on day 1");
  assert(trend[1].open === 1 && trend[1].resolvedTotal === 1, "one resolved on day 2");

  const { rows, channels } = activityByChannel([
    { timestamp: "2024-01-01T09:00:00Z", channel: "general" },
    { timestamp: "2024-01-01T10:00:00Z", channel: "general" },
    { timestamp: "2024-01-01T11:00:00Z", channel: "backend" },
  ]);
  assert(channels.length === 2, "two channels");
  assert(rows[0].general === 2 && rows[0].backend === 1, "day 1 counts per channel");
  console.log("aggregate self-check ok");
}
