// Cloudflare Pages Function: POST /api/ask
// Live Q&A for the deployed demo. At this dataset size (tens of messages) we skip
// RAG entirely and inline all messages as context into one Groq call — no embeddings,
// no vector store, which is what lets this run in a Worker.
//
// Setup: bind GROQ_API_KEY as a secret in the CF Pages project settings.
// messages.json is served as a static asset from the same deployment.

export async function onRequestPost({ request, env }) {
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "application/json",
  };

  if (!env.GROQ_API_KEY) {
    return new Response(JSON.stringify({ error: "GROQ_API_KEY not configured" }),
      { status: 500, headers: cors });
  }

  let question;
  try {
    ({ question } = await request.json());
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }),
      { status: 400, headers: cors });
  }
  if (!question || typeof question !== "string") {
    return new Response(JSON.stringify({ error: "Missing 'question'" }),
      { status: 400, headers: cors });
  }

  // Load the bundled messages (same-origin static asset).
  const url = new URL(request.url);
  const msgsResp = await fetch(`${url.origin}/data/messages.json`);
  if (!msgsResp.ok) {
    return new Response(JSON.stringify({ error: "Message data unavailable" }),
      { status: 500, headers: cors });
  }
  const messages = await msgsResp.json();

  // Rank messages by naive keyword overlap and keep the top slice, so context stays
  // bounded even if the dataset grows. ponytail: keyword ranking, swap for embeddings
  // if the corpus outgrows a single prompt.
  const qWords = new Set(question.toLowerCase().match(/\w+/g) || []);
  const scored = messages
    .map((m) => {
      const words = (m.content || "").toLowerCase().match(/\w+/g) || [];
      const score = words.filter((w) => qWords.has(w)).length;
      return { m, score };
    })
    .sort((a, b) => b.score - a.score);
  const top = (scored.some((s) => s.score > 0)
    ? scored.filter((s) => s.score > 0)
    : scored
  ).slice(0, 20).map((s) => s.m);

  const context = top
    .map((m) => `[${(m.timestamp || "").slice(0, 10)}] ${m.author} in #${m.channel}: ${m.content}`)
    .join("\n");

  const body = {
    model: "llama-3.3-70b-versatile",
    temperature: 0.2,
    messages: [
      {
        role: "system",
        content:
          "You answer questions about a software/ML project using ONLY the chat log " +
          "below. Cite specifics (people, numbers, decisions). If the log doesn't cover " +
          "it, say so.\n\nChat log:\n" + context,
      },
      { role: "user", content: question },
    ],
  };

  const groq = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GROQ_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!groq.ok) {
    return new Response(JSON.stringify({ error: `Groq error ${groq.status}` }),
      { status: 502, headers: cors });
  }

  const data = await groq.json();
  const answer = data.choices?.[0]?.message?.content || "(no answer)";
  return new Response(JSON.stringify({
    answer,
    sources: top.map((m) => ({
      author: m.author, channel: m.channel, timestamp: m.timestamp, content: m.content,
    })),
  }), { headers: cors });
}
