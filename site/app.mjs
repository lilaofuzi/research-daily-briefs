import {matchingOccurrences, monthCells, safeURL, archivePath} from './core.mjs';

const $ = id => document.getElementById(id);
function node(tag, className = '', text = '') {
  const n = document.createElement(tag); n.className = className; n.textContent = text; return n;
}
function link(text, url) {
  const n = node('a', '', text); const safe = safeURL(url);
  if (safe) { n.href = safe; n.target = '_blank'; n.rel = 'noopener noreferrer'; }
  return n;
}
function badge(text, cls = '') { return node('span', `badge ${cls}`, text); }
async function json(path) {
  const r = await fetch(path, {cache: 'no-cache'});
  if (!r.ok) throw new Error(`归档读取失败（HTTP ${r.status}）`);
  return r.json();
}
const now = new Intl.DateTimeFormat('sv-SE', {timeZone: 'Asia/Shanghai'}).format(new Date());
let index, db, view = 'archive', selected = null, year = Number(now.slice(0, 4)), month = Number(now.slice(5, 7)), request = 0;
const filter = () => ({query: $('search').value, topic: $('topic').value, pick: view === 'picks'});
const originText = kind => kind === 'historical_import' ? '历史导入' : '网页独立生成';

function setMonth(y, m) {
  const d = new Date(Date.UTC(y, m - 1, 1)); year = d.getUTCFullYear(); month = d.getUTCMonth() + 1;
  const years = new Set([year, Number(now.slice(0, 4)), ...index.briefs.map(b => Number(b.date.slice(0, 4)))]);
  $('year').replaceChildren(...[...years].sort((a,b) => b-a).map(y => {
    const o = node('option', '', `${y} 年`); o.value = y; return o;
  }));
  $('year').value = year; $('month').value = month; renderCalendar();
}

function renderCalendar() {
  const dates = new Map(index.briefs.map(b => [b.date, b]));
  $('calendar').replaceChildren(...monthCells(year, month).map(day => {
    if (!day) return node('span');
    const b = dates.get(day), n = node('button', `${b ? 'has-brief' : ''} ${day === selected ? 'selected' : ''}`, String(Number(day.slice(-2))));
    n.type = 'button'; n.disabled = !b;
    n.setAttribute('aria-label', `${day}${b ? ` ${b.source_label} ${b.title}` : ' 无归档'}`);
    if (day === now) n.setAttribute('aria-current', 'date');
    n.addEventListener('click', () => { location.hash = new URLSearchParams({date: day}); }); return n;
  }));
}

function paperCard(item, occurrences = []) {
  const card = node('article', 'paper-card');
  const meta = node('div', 'badges');
  item.topics.forEach(t => meta.append(badge(t)));
  if (item.editors_pick) meta.append(badge("Editor's Pick", 'pick'));
  meta.append(badge(`证据：${item.evidence_level}`)); card.append(meta);
  const title = node('h3'); title.append(link(item.title, item.source_url)); card.append(title);
  card.append(node('p', 'paper-meta', [item.journal, item.publication_date ? `出版 ${item.publication_date}` : '出版日期未核实'].filter(Boolean).join(' · ')));
  if (item.doi) card.append(link(item.doi, `https://doi.org/${item.doi}`));
  card.append(node('p', 'summary', item.summary));
  if (item.significance) card.append(node('p', '', `研究意义：${item.significance}`));
  if (item.limitations) card.append(node('p', 'limitations', `证据边界：${item.limitations}`));
  if (item.editors_pick) card.append(node('p', 'pick-reason', `精选理由：${item.pick_reason}`));
  const links = node('div', 'source-links');
  links.append(link('出版方 / 官方来源', item.source_url));
  if (item.oa.status === 'verified') {
    links.append(link('合法 OA 仓储', item.oa.url), link('OA 状态依据', item.oa.evidence_url));
  } else links.append(node('span', '', 'OA 未确认'));
  card.append(links);
  const proof = node('details', 'proof'); proof.append(node('summary', '', '核验与来源'));
  proof.append(node('p', '', `日期依据：${item.publication_date_basis}`));
  proof.append(node('p', '', item.verification.status === 'automated' ? item.verification.fact_check : '历史记录，尚未重新核验。'));
  if (item.verification.metadata_url) proof.append(link('元数据依据', item.verification.metadata_url));
  if (item.verification.evidence_url) proof.append(link('摘要 / 正文证据来源', item.verification.evidence_url));
  if (item.verification.evidence_quote) proof.append(node('blockquote', '', item.verification.evidence_quote));
  card.append(proof);
  if (occurrences.length) {
    const dates = node('div', 'occurrences'); dates.append(node('span', '', '出现于：'));
    occurrences.forEach(o => { const a = node('a', '', `${o.date} · ${o.source_label}`); a.href = `#date=${o.date}`; dates.append(a); });
    card.append(dates);
  }
  return card;
}

function render() {
  const options = filter(), matches = db.papers.filter(p => matchingOccurrences(p, options).length);
  const ids = new Set(matches.map(p => p.id));
  const results = $('results'); results.replaceChildren();
  for (const name of ['archive', 'papers', 'picks']) {
    $(`${name}-tab`).classList.toggle('active', view === name);
    $(`${name}-tab`).setAttribute('aria-pressed', String(view === name));
  }
  if (view === 'archive') {
    const searching = options.query.trim() || options.topic;
    const briefs = [...index.briefs].reverse().filter(b => !searching || b.paper_ids.some(id => ids.has(id) &&
      matchingOccurrences(db.papers.find(p => p.id === id), options).some(o => o.date === b.date)));
    results.append(node('h2', 'results-heading', `日期归档 · ${briefs.length} 期`));
    for (const b of briefs) {
      const card = node('article', 'brief-card'), a = node('a', '', b.title); a.href = `#date=${b.date}`;
      const h = node('h3'); h.append(a); card.append(h);
      const meta = node('div', 'badges'); meta.append(badge(b.date), badge(b.source_label), badge(originText(b.origin)));
      card.append(meta);
      if (b.source_label === '阶段汇总') card.append(node('p', '', `覆盖区间：${b.period.start} 至 ${b.period.end}`));
      card.append(node('p', 'paper-meta', `${b.paper_ids.length} 条文献 / 政策 · ${b.topics.join(' / ') || '无合格条目'}`));
      results.append(card);
    }
    if (!briefs.length) results.append(node('p', 'empty', index.briefs.length ? '当前筛选没有匹配日期。' : '尚无归档。等待原历史包导入，或首次独立生成成功后，这里将显示真实日期。'));
  } else {
    results.append(node('h2', 'results-heading', `${view === 'picks' ? "Editor's Pick" : '文献总索引'} · ${matches.length} 篇`));
    for (const p of matches) {
      const occurrences = matchingOccurrences(p, options);
      const latest = occurrences.at(-1);
      const metadata = p.metadata_versions.find(v => v.hash === latest.metadata_hash)?.metadata || p.metadata;
      const item = {...metadata, title: latest.title, summary: latest.summary,
        editors_pick: occurrences.some(o => o.editors_pick),
        pick_reason: occurrences.filter(o => o.editors_pick).map(o => `${o.date}：${o.pick_reason}`).join('；')};
      results.append(paperCard(item, occurrences));
    }
    if (!matches.length) results.append(node('p', 'empty', '没有匹配文献，请调整搜索词或主题。'));
  }
  if (selected) showBrief(selected, false); else { request++; $('detail').hidden = true; }
}

async function showBrief(day, scroll = true, versionPath = null) {
  const b = index.briefs.find(b => b.date === day), token = ++request;
  const detail = $('detail'); detail.hidden = false; detail.replaceChildren(node('p', '', '正在读取日期详情…'));
  if (!b) { detail.replaceChildren(node('p', 'error', '该日期没有经证据确认的归档记录。')); return; }
  const path = versionPath || b.path;
  if (!archivePath(path) || (path !== b.path && !b.versions.some(v => v.path === path))) return;
  try {
    const brief = await json(path); if (token !== request) return;
    detail.replaceChildren();
    const heading = node('div', 'section-heading'); heading.append(node('h2', '', brief.title));
    const close = node('button', '', '关闭详情'); close.addEventListener('click', () => { location.hash = ''; }); heading.append(close); detail.append(heading);
    const badges = node('div', 'badges'); badges.append(badge(brief.date), badge(brief.source_label), badge(originText(brief.origin.kind))); detail.append(badges);
    if (brief.source_label === '阶段汇总') detail.append(node('p', '', `覆盖区间：${brief.period.start} 至 ${brief.period.end}`));
    detail.append(node('p', 'paper-meta', `版本时间：${brief.generated_at}${brief.origin.model ? ` · ${brief.origin.model}` : ''}`));
    if (safeURL(brief.origin.reference)) detail.append(link('原始来源 / 生成运行记录', brief.origin.reference));
    if (b.versions.length) {
      const label = node('label', 'version-label', '历史版本 '), select = node('select'); select.setAttribute('aria-label', '历史版本');
      const current = node('option', '', '当前版本'); current.value = b.path; select.append(current);
      b.versions.filter(v => v.hash !== b.hash).sort((a,b) => b.generated_at.localeCompare(a.generated_at)).forEach(v => {
        const o = node('option', '', `${v.generated_at} · ${v.hash.slice(0, 8)}`); o.value = v.path; select.append(o);
      }); select.value = path; select.addEventListener('change', () => showBrief(day, false, select.value)); label.append(select); detail.append(label);
    }
    const notes = node('ul', 'notice'); brief.notes.forEach(text => notes.append(node('li', '', text))); detail.append(notes);
    const body = node('details', 'body-detail'); body.append(node('summary', '', `${brief.source_label}内容 · 保留来源版本文字`), node('pre', '', brief.body || '本期无正文内容。')); detail.append(body);
    const options = filter();
    const items = brief.items.filter(p => matchingOccurrences({metadata: p, occurrences: [{title:p.title, topics:p.topics, keywords:p.keywords, summary:p.summary, editors_pick:p.editors_pick}]}, options).length);
    detail.append(node('p', 'paper-meta', `本期 ${brief.items.length} 条，当前筛选显示 ${items.length} 条`));
    items.forEach(p => detail.append(paperCard(p)));
    renderCalendar(); if (scroll) detail.scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (e) { if (token === request) detail.replaceChildren(node('p', 'error', e.message)); }
}

function route() {
  selected = new URLSearchParams(location.hash.slice(1)).get('date');
  if (selected && /^\d{4}-\d{2}-\d{2}$/.test(selected)) {
    setMonth(Number(selected.slice(0,4)), Number(selected.slice(5,7))); showBrief(selected);
  } else { selected = null; request++; $('detail').hidden = true; renderCalendar(); }
}

async function start() {
  try {
    [index, db] = await Promise.all([json('data/index.json'), json('data/papers.json')]);
    if (index.schema_version !== 1 || db.schema_version !== 1) throw new Error('不支持的归档数据版本');
    $('load-status').textContent = `归档读取成功${index.latest_date ? ` · 最新 ${index.latest_date}` : ' · 尚无简报'}`;
    $('stats').append(node('span', '', `${index.briefs.length} 期归档`), node('span', '', `${db.papers.filter(p=>p.occurrences.length).length} 篇去重文献`),
      node('span', '', `${db.papers.filter(p=>p.occurrences.some(o=>o.editors_pick)).length} 篇精选`));
    $('excel-notice').textContent = index.database_status.notice;
    $('import-notice').textContent = index.historical_import_status === 'not_imported' ? '历史原 HTML / ZIP 尚未导入；页面不展示推测的历史日期。' : '历史记录按来源标签与实际覆盖区间导入。';
    for (let m = 1; m <= 12; m++) { const o = node('option', '', `${m} 月`); o.value = m; $('month').append(o); }
    $('year').addEventListener('change', () => setMonth(Number($('year').value), month));
    $('month').addEventListener('change', () => setMonth(year, Number($('month').value)));
    $('prev').addEventListener('click', () => setMonth(year, month - 1));
    $('next').addEventListener('click', () => setMonth(year, month + 1));
    $('today').addEventListener('click', () => setMonth(Number(now.slice(0,4)), Number(now.slice(5,7))));
    $('search').addEventListener('input', render); $('topic').addEventListener('change', render);
    $('reset').addEventListener('click', () => { $('search').value = ''; $('topic').value = ''; render(); });
    for (const name of ['archive', 'papers', 'picks']) $(`${name}-tab`).addEventListener('click', () => { view = name; render(); });
    $('export').addEventListener('click', () => {
      const url = URL.createObjectURL(new Blob([JSON.stringify(db, null, 2)], {type: 'application/json'}));
      const a = node('a'); a.href = url; a.download = 'research-papers-index.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    if (index.latest_date) { year = Number(index.latest_date.slice(0,4)); month = Number(index.latest_date.slice(5,7)); }
    setMonth(year, month); render(); route(); window.addEventListener('hashchange', route);
  } catch (e) { $('load-status').textContent = e.message + '。请通过网站网址或本地 HTTP 服务打开本页。'; $('load-status').className = 'error'; }
}
start();
