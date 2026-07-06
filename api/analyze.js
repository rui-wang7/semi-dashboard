// On-demand AI spike analysis — Vercel serverless function.
//
// Called from the Analytics tab when the user clicks "AI 解读" on a live spike.
// 1. Fetches the latest news headlines for the ticker (Yahoo search, no key).
// 2. If ANTHROPIC_API_KEY is set (Vercel → Project → Settings → Environment
//    Variables), asks Claude for a 2–3 sentence explanation of the move.
//    Without the key it still returns headlines, with a setup hint.
//
// GET /api/analyze?ticker=NVDA&name=Nvidia&move=-5.2
// → { ticker, headlines: [{title, publisher, age_hours}], analysis?, error? }

const ANTHROPIC_MODEL = 'claude-haiku-4-5-20251001';

async function fetchHeadlines(ticker, name) {
  const q = encodeURIComponent(ticker.replace(/\.[A-Z]+$/, ''));
  const url = `https://query1.finance.yahoo.com/v1/finance/search?q=${q}&newsCount=6&quotesCount=0`;
  const r = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' },
  });
  if (!r.ok) throw new Error(`Yahoo news ${r.status}`);
  const j = await r.json();
  const now = Date.now() / 1000;
  return (j.news || []).map(n => ({
    title: n.title,
    publisher: n.publisher,
    age_hours: n.providerPublishTime ? Math.round((now - n.providerPublishTime) / 3600) : null,
    link: n.link,
  }));
}

async function askClaude(ticker, name, move, headlines) {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) return { error: 'ANTHROPIC_API_KEY not set — add it in Vercel project settings to enable AI analysis. Headlines below are still live.' };

  const headlineText = headlines.length
    ? headlines.map(h => `- [${h.publisher}${h.age_hours != null ? `, ${h.age_hours}h ago` : ''}] ${h.title}`).join('\n')
    : '(no recent headlines found)';

  const r = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': key,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model: ANTHROPIC_MODEL,
      max_tokens: 400,
      messages: [{
        role: 'user',
        content: `You are a semiconductor equity analyst. ${name} (${ticker}) moved ${move > 0 ? '+' : ''}${move}% today.

Recent headlines:
${headlineText}

In 2-3 concise sentences, explain the most likely driver of today's move. If headlines don't explain it, say what sector/macro factor most plausibly does. Reply in the same style as a dashboard tooltip — no preamble.`,
      }],
    }),
    signal: AbortSignal.timeout(25000),
  });
  if (!r.ok) {
    const body = await r.text();
    throw new Error(`Anthropic API ${r.status}: ${body.slice(0, 200)}`);
  }
  const j = await r.json();
  return { analysis: (j.content || []).map(c => c.text || '').join('').trim() };
}

export default async function handler(req, res) {
  const { ticker, name = '', move = '0' } = req.query;
  if (!ticker) {
    res.status(400).json({ error: 'ticker query param required' });
    return;
  }

  let headlines = [];
  try {
    headlines = await fetchHeadlines(ticker, name);
  } catch (e) {
    // headlines are best-effort; continue so Claude can still reason from the move
  }

  let out = {};
  try {
    out = await askClaude(ticker, name, parseFloat(move) || 0, headlines);
  } catch (e) {
    out = { error: `AI analysis failed: ${e.message}` };
  }

  res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
  res.status(200).json({ ticker, headlines, ...out });
}
