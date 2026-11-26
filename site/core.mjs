export function normalizedQuery(value) {
  let q = value.trim().toLocaleLowerCase();
  try { q = decodeURIComponent(q); } catch { /* An incomplete search string is still searchable. */ }
  return q.replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi\s*:\s*)/i, '').replace(/[.,;]+$/, '');
}

export function matchingOccurrences(paper, {query = '', topic = '', pick = false} = {}) {
  const q = normalizedQuery(query);
  return paper.occurrences.filter(o => (!topic || o.topics.includes(topic)) && (!pick || o.editors_pick) &&
    (!q || [paper.metadata.doi || '', o.title, ...o.keywords, o.summary].join(' ').toLocaleLowerCase().includes(q)));
}

export function monthCells(year, month) {
  const offset = (new Date(Date.UTC(year, month - 1, 1)).getUTCDay() + 6) % 7;
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return [...Array(offset).fill(null), ...Array.from({length: days}, (_, i) =>
    `${year}-${String(month).padStart(2, '0')}-${String(i + 1).padStart(2, '0')}`)];
}

export function safeURL(value) {
  try { const u = new URL(value); return u.protocol === 'https:' && !u.username && !u.password ? u.href : null; }
  catch { return null; }
}

export function archivePath(value) {
  return /^(archive\/\d{4}\/\d{2}\/\d{4}-\d{2}-\d{2}\.json|history\/\d{4}-\d{2}-\d{2}\/[a-f0-9]{64}\.json)$/.test(value);
}
