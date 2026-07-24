import { useEffect, useRef, useState } from "react";

const S = { CREDS: "punch_creds" };
const load = () => { try { return JSON.parse(localStorage.getItem(S.CREDS)) || {}; } catch { return {}; } };
const save = (o) => localStorage.setItem(S.CREDS, JSON.stringify(o));

const TYPE_LABEL = { decision: "Decision", milestone: "Milestone", blocker: "Blocker", resolution: "Resolution" };

function useJSON(path, deps) {
  const [data, setData] = useState(null);
  useEffect(() => { fetch(path).then(r => r.ok ? r.json() : null).then(setData).catch(() => {}); }, [path, ...(deps || [])]);
  return data;
}

/* ---------- Onboarding ---------- */
function Onboarding({ onDone }) {
  const saved = load();
  const [token, setToken] = useState(saved.discord_token || "");
  const [guild, setGuild] = useState(saved.guild_id || "");
  const [groq, setGroq] = useState(saved.groq_key || "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [open, setOpen] = useState(0);

  const steps = [
    { t: "Create a Discord application", b: "Open the Developer Portal and create a new application — the container for your bot.", link: "https://discord.com/developers/applications", cta: "Developer Portal" },
    { t: "Add a bot, copy its token", b: "In the Bot tab, Reset Token and copy it. Turn on Message Content Intent under Privileged Gateway Intents, or the bot reads empty messages." },
    { t: "Invite the bot", b: "OAuth2 → URL Generator: tick bot, then Read Messages / View Channels and Read Message History. Open the URL, pick your server." },
    { t: "Get a Groq key", b: "Groq runs the language model. Create a free account and copy an API key.", link: "https://console.groq.com/keys", cta: "Groq Console" },
  ];

  async function submit(e) {
    e.preventDefault();
    if (!token.trim() || !groq.trim()) { setErr("Discord token and Groq key are both required."); return; }
    setBusy(true); setErr(null);
    try {
      const r = await fetch("/api/onboard", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ discord_token: token.trim(), guild_id: guild.trim(), groq_key: groq.trim() }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || `Error ${r.status}`);
      save({ discord_token: token.trim(), guild_id: guild.trim(), groq_key: groq.trim() });
      onDone(data);
    } catch (e2) { setErr(e2.message); } finally { setBusy(false); }
  }

  return (
    <div className="onboard">
      <div className="onboard-inner">
        <header className="onboard-head">
          <div className="wordmark">Punch<span>.io</span></div>
          <p>Connect a Discord bot. Punch.io reads your team's channels and turns the scatter into a searchable project record.</p>
        </header>

        <ol className="steps">
          {steps.map((s, i) => (
            <li key={i} className={`step ${open === i ? "open" : ""}`}>
              <button type="button" className="step-head" onClick={() => setOpen(open === i ? -1 : i)}>
                <span className="step-n">{String(i + 1).padStart(2, "0")}</span>
                <span className="step-t">{s.t}</span>
                <span className="step-chev" aria-hidden>{open === i ? "−" : "+"}</span>
              </button>
              {open === i && (
                <div className="step-body">
                  <p>{s.b}</p>
                  {s.link && <a href={s.link} target="_blank" rel="noreferrer" className="step-link">{s.cta} →</a>}
                </div>
              )}
            </li>
          ))}
        </ol>

        <form onSubmit={submit} className="creds">
          <label>Discord bot token <span className="req">required</span>
            <input value={token} onChange={e => setToken(e.target.value)} type="password" placeholder="Paste the bot token" autoComplete="off" />
          </label>
          <label>Server ID <span className="opt">optional — blank auto-discovers every server the bot can see</span>
            <input value={guild} onChange={e => setGuild(e.target.value)} placeholder="Right-click the server icon → Copy Server ID" autoComplete="off" />
          </label>
          <label>Groq API key <span className="req">required</span>
            <input value={groq} onChange={e => setGroq(e.target.value)} type="password" placeholder="gsk_…" autoComplete="off" />
          </label>
          {err && <p className="err">{err}</p>}
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Syncing Discord…" : "Connect & sync"}
          </button>
          <p className="stored-note">Credentials stay in this browser (localStorage). Nothing is sent anywhere but Discord and Groq.</p>
        </form>
      </div>
    </div>
  );
}

/* ---------- Chat (Ask) ---------- */
function Chat({ groqKey, messages, turns, setTurns }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns, busy]);

  async function ask(question) {
    const updated = [...turns, { role: "user", text: question }];
    setTurns(updated);
    setBusy(true);
    try {
      let r = await fetch("/api/ask", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history: updated }),
      });
      if (r.ok) {
        const d = await r.json();
        setTurns(t => [...t, { role: "assistant", text: d.answer, sources: d.sources }]);
        return;
      }
      // Direct Groq fallback (static deploy)
      const qw = new Set((question.toLowerCase().match(/\w+/g) || []));
      const top = (messages || [])
        .map(m => ({ m, s: (m.content || "").toLowerCase().match(/\w+/g)?.filter(w => qw.has(w)).length || 0 }))
        .sort((a, b) => b.s - a.s).slice(0, 20).map(x => x.m);
      const ctx = top.map(m => `[${(m.timestamp || "").slice(0, 10)}] ${m.author} in #${m.channel}: ${m.content}`).join("\n");
      const msgs = [
        { role: "system", content: "You are the project-intelligence analyst for a software team. Answer the manager's question ONLY from the message log below. Be specific — name people, dates, numbers, decisions, blockers. If the log doesn't cover it, say so plainly. Lead with the answer.\n\nMessage log:\n" + ctx },
        ...updated.slice(0, -1).map(t => ({ role: t.role, content: t.text })),
        { role: "user", content: question },
      ];
      r = await fetch("https://api.groq.com/openai/v1/chat/completions", {
        method: "POST",
        headers: { Authorization: `Bearer ${groqKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "llama-3.3-70b-versatile", temperature: 0.2,
          messages: msgs,
        }),
      });
      if (!r.ok) throw new Error(`Groq error ${r.status}`);
      const d = await r.json();
      setTurns(t => [...t, { role: "assistant", text: d.choices?.[0]?.message?.content || "(no answer)", sources: top }]);
    } catch (e) {
      setTurns(t => [...t, { role: "assistant", text: `Couldn't answer: ${e.message}`, error: true }]);
    } finally { setBusy(false); }
  }

  function submit(e) { e.preventDefault(); if (!q.trim() || busy) return; const v = q.trim(); setQ(""); ask(v); }

  const suggestions = ["What's currently blocking the project?", "What major decisions were made?", "Summarize the last week of activity."];

  return (
    <div className="chat">
      <div className="chat-log">
        {turns.length === 0 && (
          <div className="chat-empty">
            <h2>Ask about your project</h2>
            <p>Answers are drawn only from your synced communications.</p>
            <div className="suggest">
              {suggestions.map(s => (
                <button key={s} className="chip" onClick={() => !busy && ask(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`turn turn-${t.role}`}>
            <div className={`bubble ${t.error ? "bubble-err" : ""}`}>
              {t.text}
              {t.sources?.length > 0 && (
                <details className="sources">
                  <summary>{t.sources.length} source messages</summary>
                  {t.sources.map((s, j) => (
                    <div className="src" key={j}>
                      <span className="src-who">{s.author} · #{s.channel} · {(s.timestamp || "").slice(0, 10)}</span>
                      {s.content}
                    </div>
                  ))}
                </details>
              )}
            </div>
          </div>
        ))}
        {busy && <div className="turn turn-assistant"><div className="bubble thinking"><span></span><span></span><span></span></div></div>}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={submit}>
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="Ask anything about the project…" aria-label="Message" disabled={busy} />
        <button type="submit" className="btn-primary" disabled={busy || !q.trim()}>Send</button>
      </form>
    </div>
  );
}

/* ---------- Timeline ---------- */
function Timeline({ events }) {
  const [type, setType] = useState("all");
  if (!events) return <div className="loading">Loading…</div>;
  if (!events.length) return <div className="view-empty"><h2>No timeline yet</h2><p>Sync messages, then the timeline is extracted automatically.</p></div>;
  const shown = type === "all" ? events : events.filter(e => e.type === type);
  const counts = events.reduce((a, e) => (a[e.type] = (a[e.type] || 0) + 1, a), {});

  return (
    <div className="view">
      <div className="view-head">
        <h2>Timeline</h2>
        <p>{events.length} events · what actually happened, in order.</p>
      </div>
      <div className="segbar">
        {["all", "decision", "milestone", "blocker", "resolution"].map(t => (
          <button key={t} className={`seg ${type === t ? "on" : ""}`} onClick={() => setType(t)}>
            {t === "all" ? "All" : TYPE_LABEL[t]}{t !== "all" && counts[t] ? ` ${counts[t]}` : ""}
          </button>
        ))}
      </div>
      <ol className="tl">
        {shown.map((e, i) => (
          <li className="tl-row" key={i} style={{ "--i": i }}>
            <span className={`tl-dot d-${e.type}`} />
            <div className="tl-body">
              <div className="tl-meta">
                <span className={`tag t-${e.type}`}>{TYPE_LABEL[e.type]}</span>
                <time>{e.date}</time>
                {e.channel && <span className="tl-ch">#{e.channel}</span>}
              </div>
              <p className="tl-sum">{e.summary}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ---------- Messages ---------- */
function Messages({ messages }) {
  const [ch, setCh] = useState("all");
  if (!messages) return <div className="loading">Loading…</div>;
  if (!messages.length) return <div className="view-empty"><h2>No messages</h2><p>Nothing synced yet.</p></div>;
  const channels = [...new Set(messages.map(m => m.channel).filter(Boolean))].sort();
  const shown = [...messages]
    .filter(m => ch === "all" || m.channel === ch)
    .sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""));

  return (
    <div className="view">
      <div className="view-head">
        <h2>Messages</h2>
        <p>{shown.length} of {messages.length} messages · newest first.</p>
      </div>
      <div className="segbar wrap">
        <button className={`seg ${ch === "all" ? "on" : ""}`} onClick={() => setCh("all")}>All</button>
        {channels.map(c => <button key={c} className={`seg ${ch === c ? "on" : ""}`} onClick={() => setCh(c)}>#{c}</button>)}
      </div>
      <div className="msgs">
        {shown.map((m, i) => (
          <div className="msg" key={i}>
            <div className="msg-meta"><strong>{m.author}</strong><span className="msg-ch">#{m.channel}</span><time>{(m.timestamp || "").slice(0, 16).replace("T", " ")}</time></div>
            <p className="msg-text">{m.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------- App shell ---------- */
export default function App() {
  const [creds, setCreds] = useState(load);
  const [synced, setSynced] = useState(false);
  const [tab, setTab] = useState("ask");
  const [turns, setTurns] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const messages = useJSON("/data/messages.json", [refreshKey]);
  const timeline = useJSON("/data/timeline.json", [refreshKey]);
  const meta = useJSON("/data/meta.json", [refreshKey]);

  const ready = creds.discord_token && creds.groq_key && (messages || synced);
  if (!ready) return <Onboarding onDone={() => { setCreds(load()); setSynced(true); setRefreshKey(k => k + 1); }} />;

  const nav = [["ask", "Ask"], ["timeline", "Timeline"], ["messages", "Messages"]];

  return (
    <div className="app">
      <aside className="side">
        <div className="wordmark">Punch<span>.io</span></div>
        <nav>
          {nav.map(([id, label]) => (
            <button key={id} className={`nav-item ${tab === id ? "on" : ""}`} onClick={() => setTab(id)}>{label}</button>
          ))}
        </nav>
        <div className="side-foot">
          {meta && (
            <dl className="side-stats">
              <div><dt>Messages</dt><dd>{meta.message_count}</dd></div>
              <div><dt>Channels</dt><dd>{meta.channels?.length}</dd></div>
              {timeline && <div><dt>Events</dt><dd>{timeline.length}</dd></div>}
            </dl>
          )}
          <button className="reconnect" onClick={() => { localStorage.removeItem(S.CREDS); setCreds({}); setSynced(false); }}>Reconnect bot</button>
        </div>
      </aside>
      <main className="content">
        {tab === "ask" && <Chat groqKey={creds.groq_key} messages={messages} turns={turns} setTurns={setTurns} />}
        {tab === "timeline" && <Timeline events={timeline} />}
        {tab === "messages" && <Messages messages={messages} />}
      </main>
    </div>
  );
}
