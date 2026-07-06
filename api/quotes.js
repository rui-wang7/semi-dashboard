// Live quote proxy for the Analytics tab — runs as a Vercel serverless function.
//
// Provider architecture (pluggable):
//   PRIMARY  — set env var QUOTES_PROVIDER_URL to any endpoint that accepts
//              ?symbols=A,B,C and returns {quotes:{SYM:{price,prevClose,changePct}}}.
//              Reserved for a dedicated market-data source (e.g. a Claude
//              market-data skill exposed as an HTTP endpoint).
//   FALLBACK — Yahoo Finance v8 chart API. No API key, works server-side
//              (browser calls are blocked by CORS, hence this proxy).
//
// GET /api/quotes?symbols=NVDA,TSM,000660.KS
// → { provider, asof, quotes: { NVDA: { price, prevClose, changePct, currency }, … } }

const MAX_SYMBOLS = 120;
const CONCURRENCY = 12;

async function fetchYahooQuote(symbol) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=1d&interval=1d`;
  const r = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' },
  });
  if (!r.ok) throw new Error(`Yahoo ${r.status} for ${symbol}`);
  const j = await r.json();
  const meta = j?.chart?.result?.[0]?.meta;
  if (!meta || meta.regularMarketPrice == null) throw new Error(`no data for ${symbol}`);
  const price = meta.regularMarketPrice;
  const prevClose = meta.chartPreviousClose ?? meta.previousClose ?? null;
  return {
    price,
    prevClose,
    changePct: prevClose ? +(((price - prevClose) / prevClose) * 100).toFixed(2) : null,
    currency: meta.currency || 'USD',
  };
}

async function fetchYahooBatch(symbols) {
  const quotes = {};
  const errors = [];
  let i = 0;
  async function worker() {
    while (i < symbols.length) {
      const sym = symbols[i++];
      try {
        quotes[sym] = await fetchYahooQuote(sym);
      } catch (e) {
        errors.push(`${sym}: ${e.message}`);
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, symbols.length) }, worker));
  return { quotes, errors };
}

async function fetchPrimary(symbols) {
  const base = process.env.QUOTES_PROVIDER_URL;
  if (!base) return null;
  const r = await fetch(`${base}${base.includes('?') ? '&' : '?'}symbols=${encodeURIComponent(symbols.join(','))}`, {
    signal: AbortSignal.timeout(8000),
  });
  if (!r.ok) throw new Error(`primary provider ${r.status}`);
  const j = await r.json();
  if (!j || typeof j.quotes !== 'object') throw new Error('primary provider bad payload');
  return j.quotes;
}

export default async function handler(req, res) {
  const raw = (req.query.symbols || '').trim();
  if (!raw) {
    res.status(400).json({ error: 'symbols query param required, e.g. ?symbols=NVDA,TSM' });
    return;
  }
  const symbols = [...new Set(raw.split(',').map(s => s.trim()).filter(Boolean))].slice(0, MAX_SYMBOLS);

  let provider = 'yahoo';
  let quotes = null;
  let errors = [];

  try {
    quotes = await fetchPrimary(symbols);
    if (quotes) provider = 'primary';
  } catch (e) {
    errors.push(`primary failed, falling back to yahoo: ${e.message}`);
  }

  if (!quotes) {
    const out = await fetchYahooBatch(symbols);
    quotes = out.quotes;
    errors = errors.concat(out.errors);
  }

  res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=120');
  res.status(200).json({
    provider,
    asof: new Date().toISOString(),
    count: Object.keys(quotes).length,
    quotes,
    errors: errors.length ? errors : undefined,
  });
}
