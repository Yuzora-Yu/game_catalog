const [gamesResponse, reviewResponse] = await Promise.all([
  fetch('./data/games.json'),
  fetch('./data/review-queue.json'),
]);
if (!gamesResponse.ok || !reviewResponse.ok) throw new Error('ゲーム辞典を読み込めませんでした');

const payload = await gamesResponse.json();
const reviewPayload = await reviewResponse.json();
const games = payload.games ?? [];
const unresolved = [...(reviewPayload.unresolved_aliases ?? [])].sort((a, b) =>
  (b.observation_count ?? 0) - (a.observation_count ?? 0)
  || (b.channel_count ?? 0) - (a.channel_count ?? 0)
  || String(b.last_seen ?? '').localeCompare(String(a.last_seen ?? ''))
);

const $ = (selector) => document.querySelector(selector);
const search = $('#search');
const source = $('#source');
const platform = $('#platform');
const verification = $('#verification');
const activityFilter = $('#activity-filter');
const sort = $('#sort');
const container = $('#games');
const summary = $('#summary');
const template = $('#game-template');
const reviewCount = $('#review-count');
const reviewList = $('#review-list');
const loadMore = $('#load-more');
const clearSearch = $('#clear-search');
const emptyState = $('#empty-state');
const quickFilters = [...document.querySelectorAll('[data-quick]')];
const pageSize = 60;
let renderLimit = pageSize;
let renderTimer;

const sourceLabels = {
  steam: ['Steam公式', '🎮'],
  console: ['コンソール', '🕹️'],
  wikidata: ['Wikidata', '🌐'],
  stream_seed: ['配信シード', '📡'],
};
const verificationLabels = {
  verified: '確認済み',
  partially_verified: '一部確認',
  seed_unverified: '未確認',
  needs_review: '要確認',
};
const verificationOrder = {verified: 0, partially_verified: 1, seed_unverified: 2, needs_review: 3};

const normalize = (value) => (value ?? '')
  .normalize('NFKD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLocaleLowerCase()
  .replace(/[\s\u3000]+/g, ' ')
  .trim();
const fmt = (value) => value ? new Date(value).toLocaleString('ja-JP', {dateStyle: 'medium', timeStyle: 'short'}) : '未観測';
const numeric = (value) => Number(value ?? 0);

function sourceFor(game) {
  if (game.external_ids?.steam_app) return 'steam';
  const sources = game.verification?.sources ?? [];
  if (sources.some((entry) => entry.type === 'curated_seed')) return 'console';
  if (game.external_ids?.wikidata || sources.some((entry) => entry.type === 'wikidata')) return 'wikidata';
  return 'stream_seed';
}

const indexedGames = games.map((game, index) => {
  const registeredNames = (game.aliases ?? []).flatMap((entry) => entry.variants ?? [entry.text]);
  const observedNames = (game.observed_aliases ?? []).flatMap((entry) => [entry.display, entry.normalized]);
  const platforms = game.platforms ?? [];
  const companies = (game.companies ?? []).map((entry) => entry.name);
  const gameSource = sourceFor(game);
  const searchText = [
    game.id,
    game.titles?.primary,
    game.titles?.ja,
    game.titles?.en,
    ...registeredNames,
    ...observedNames,
    ...platforms,
    ...companies,
    sourceLabels[gameSource][0],
  ].filter(Boolean).map(normalize).join('\n');
  return {
    game,
    index,
    source: gameSource,
    platforms,
    registeredNames: [...new Set(registeredNames.filter(Boolean))],
    searchText,
    observationCount: numeric(game.stream_activity?.observation_count),
    latestObserved: Date.parse(game.stream_activity?.last_seen ?? '') || 0,
    streamCount: (game.stream_activity?.latest_streams ?? []).length,
    aliasCount: (game.aliases ?? []).length + (game.observed_aliases ?? []).length,
  };
});

function fillStatsAndPlatforms() {
  $('#stat-games').textContent = games.length.toLocaleString('ja-JP');
  $('#stat-aliases').textContent = indexedGames.reduce((sum, item) => sum + (item.game.aliases ?? []).length, 0).toLocaleString('ja-JP');
  $('#stat-observed').textContent = indexedGames.filter((item) => item.observationCount > 0).length.toLocaleString('ja-JP');

  const counts = new Map();
  for (const item of indexedGames) {
    for (const name of item.platforms) counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  const options = [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'ja'));
  for (const [name, count] of options) {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = `${name}（${count.toLocaleString('ja-JP')}）`;
    platform.append(option);
  }
}

function restoreFilters() {
  const params = new URLSearchParams(location.search);
  search.value = params.get('q') ?? '';
  source.value = params.get('source') ?? '';
  platform.value = params.get('platform') ?? '';
  verification.value = params.get('verification') ?? '';
  activityFilter.value = params.get('activity') ?? '';
  sort.value = params.get('sort') ?? 'name-ja';
}

function syncUrl() {
  const params = new URLSearchParams();
  if (search.value.trim()) params.set('q', search.value.trim());
  if (source.value) params.set('source', source.value);
  if (platform.value) params.set('platform', platform.value);
  if (verification.value) params.set('verification', verification.value);
  if (activityFilter.value) params.set('activity', activityFilter.value);
  if (sort.value !== 'name-ja') params.set('sort', sort.value);
  const next = `${location.pathname}${params.size ? `?${params}` : ''}${location.hash}`;
  history.replaceState(null, '', next);
}

function currentItems() {
  const tokens = normalize(search.value).split(' ').filter(Boolean);
  const filtered = indexedGames.filter((item) => {
    const game = item.game;
    if (source.value && item.source !== source.value) return false;
    if (platform.value && !item.platforms.includes(platform.value)) return false;
    if (verification.value && game.verification?.status !== verification.value) return false;
    if (activityFilter.value === 'observed' && item.observationCount === 0) return false;
    if (activityFilter.value === 'stream' && item.streamCount === 0) return false;
    if (activityFilter.value === 'unobserved' && item.observationCount > 0) return false;
    return tokens.every((token) => item.searchText.includes(token));
  });
  return filtered.sort(sorter(sort.value));
}

function sorter(mode) {
  const byJa = (a, b) => String(a.game.titles?.ja || a.game.titles?.primary).localeCompare(String(b.game.titles?.ja || b.game.titles?.primary), 'ja', {numeric: true});
  if (mode === 'name-en') return (a, b) => String(a.game.titles?.en || a.game.titles?.primary).localeCompare(String(b.game.titles?.en || b.game.titles?.primary), 'en', {numeric: true});
  if (mode === 'observed') return (a, b) => b.latestObserved - a.latestObserved || byJa(a, b);
  if (mode === 'observations') return (a, b) => b.observationCount - a.observationCount || byJa(a, b);
  if (mode === 'aliases') return (a, b) => b.aliasCount - a.aliasCount || byJa(a, b);
  if (mode === 'verification') return (a, b) => (verificationOrder[a.game.verification?.status] ?? 9) - (verificationOrder[b.game.verification?.status] ?? 9) || byJa(a, b);
  return byJa;
}

function render() {
  const items = currentItems();
  const visible = items.slice(0, renderLimit);
  const filteredReviews = filterReviews();
  container.replaceChildren(...visible.map(renderGame));
  emptyState.hidden = items.length > 0;
  loadMore.hidden = visible.length >= items.length;
  loadMore.textContent = `もっと見る（残り ${(items.length - visible.length).toLocaleString('ja-JP')}件）`;
  summary.innerHTML = `<strong>${items.length.toLocaleString('ja-JP')}</strong> 件が該当 <span>・${visible.length.toLocaleString('ja-JP')}件を表示中 / 全${games.length.toLocaleString('ja-JP')}件</span>`;
  clearSearch.hidden = !search.value;
  renderReviews(filteredReviews);
  updateQuickFilters();
  syncUrl();
}

function renderGame(item) {
  const game = item.game;
  const node = template.content.cloneNode(true);
  const card = node.querySelector('.card');
  card.dataset.source = item.source;
  node.querySelector('.game-id').textContent = game.id;
  node.querySelector('h2').textContent = game.titles.primary;

  const sourceBadge = node.querySelector('.source-badge');
  sourceBadge.textContent = `${sourceLabels[item.source][1]} ${sourceLabels[item.source][0]}`;
  const badge = node.querySelector('.badge');
  const verify = game.verification?.status ?? 'needs_review';
  badge.textContent = verificationLabels[verify] ?? verify;
  badge.dataset.verification = verify;

  const localized = [];
  if (game.titles?.ja && normalize(game.titles.ja) !== normalize(game.titles.primary)) localized.push(`日本語: ${game.titles.ja}`);
  if (game.titles?.en && normalize(game.titles.en) !== normalize(game.titles.primary)) localized.push(`English: ${game.titles.en}`);
  node.querySelector('.localized').textContent = localized.join('  ·  ') || '表示名と正式名は同じです';

  const latestText = item.latestObserved ? `最終 ${fmt(game.stream_activity.last_seen)}` : '配信未観測';
  node.querySelector('.mini-stats').innerHTML = `
    <span>🏷️ ${item.aliasCount.toLocaleString('ja-JP')}名称</span>
    <span class="${item.observationCount ? 'is-live' : ''}">📡 ${item.observationCount.toLocaleString('ja-JP')}観測</span>
    <span>🕘 ${escapeHtml(latestText)}</span>`;

  const preview = item.registeredNames.slice(0, 6);
  const remainder = item.registeredNames.length - preview.length;
  node.querySelector('.alias-preview').innerHTML = [
    ...preview.map((name) => `<span>${escapeHtml(name)}</span>`),
    remainder > 0 ? `<span class="more-chip">+${remainder}</span>` : '',
  ].join('');

  const facts = node.querySelector('.facts');
  const rows = [
    ['機種', (game.platforms ?? []).join(', ') || '未登録'],
    ['発売', (game.releases ?? []).map((entry) => `${entry.date}${entry.region ? ` (${entry.region})` : ''}`).join(', ') || '未登録'],
    ['会社', (game.companies ?? []).map((entry) => `${entry.name} / ${entry.role}`).join(', ') || '未登録'],
    ['Steam', game.external_ids?.steam_app ? `App ${game.external_ids.steam_app}` : '—'],
    ['Wikidata', game.external_ids?.wikidata ?? '—'],
  ];
  for (const [term, value] of rows) {
    const dt = document.createElement('dt'); dt.textContent = term;
    const dd = document.createElement('dd'); dd.textContent = value;
    facts.append(dt, dd);
  }

  const aliasBox = node.querySelector('.aliases');
  const observed = game.observed_aliases ?? [];
  const observedItems = observed.length
    ? `<ul class="alias-observed">${observed.map((alias) => `<li><span>${escapeHtml(alias.display || alias.normalized)}</span><small>${numeric(alias.observation_count).toLocaleString('ja-JP')}回・最終 ${escapeHtml(fmt(alias.last_seen))}</small></li>`).join('')}</ul>`
    : '<p class="muted">まだありません。</p>';
  aliasBox.innerHTML = `
    <strong>登録済みの正式名・表記</strong>
    <div class="detail-chips">${item.registeredNames.map((name) => `<span>${escapeHtml(name)}</span>`).join('') || '<span>なし</span>'}</div>
    <strong>配信で観測した表記ゆれ</strong>
    ${observedItems}`;

  const activity = node.querySelector('.activity');
  const streams = game.stream_activity?.latest_streams ?? [];
  const activityMeta = game.stream_activity
    ? `<p class="activity-meta">観測 ${item.observationCount.toLocaleString('ja-JP')}件・${escapeHtml(fmt(game.stream_activity.first_seen))} 〜 ${escapeHtml(fmt(game.stream_activity.last_seen))}</p>`
    : '';
  if (!streams.length) {
    activity.innerHTML = `<strong>配信観測</strong>${activityMeta}<p class="muted">まだ同期されていません。</p>`;
  } else {
    const links = streams.map((stream) => `<li><a href="${escapeAttr(stream.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(stream.channel_title || stream.channel_id || '配信を見る')} ↗</a><span>${escapeHtml(fmt(stream.observed_at))}</span></li>`).join('');
    activity.innerHTML = `<strong>配信観測</strong>${activityMeta}<ul>${links}</ul>`;
  }
  return node;
}

function filterReviews() {
  const tokens = normalize(search.value).split(' ').filter(Boolean);
  return unresolved.filter((entry) => {
    if (!tokens.length) return true;
    const text = [
      entry.normalized,
      entry.display,
      ...(entry.latest_streams ?? []).flatMap((stream) => [stream.title, stream.channel_title]),
    ].filter(Boolean).map(normalize).join('\n');
    return tokens.every((token) => text.includes(token));
  });
}

function renderReviews(entries) {
  reviewCount.textContent = `${entries.length.toLocaleString('ja-JP')}件`;
  const visible = entries.slice(0, 60);
  reviewList.innerHTML = visible.length
    ? visible.map((entry) => {
      const sample = entry.latest_streams?.[0];
      const sampleLink = sample?.url
        ? `<a href="${escapeAttr(sample.url)}" target="_blank" rel="noopener noreferrer">配信例を見る ↗</a>`
        : '';
      return `<article class="review-item">
        <div><strong>${escapeHtml(entry.display || entry.normalized)}</strong><small>${escapeHtml(entry.normalized)}</small></div>
        <p><b>${numeric(entry.observation_count).toLocaleString('ja-JP')}回</b>・${numeric(entry.channel_count).toLocaleString('ja-JP')}チャンネル・最終 ${escapeHtml(fmt(entry.last_seen))}</p>
        ${sampleLink}
      </article>`;
    }).join('')
    : '<p class="muted">検索語に該当する未解決候補はありません。</p>';
}

function updateQuickFilters() {
  const active = activityFilter.value === 'observed' ? 'observed'
    : source.value === 'steam' ? 'steam'
      : source.value === 'console' ? 'console'
        : verification.value === 'seed_unverified' ? 'review'
          : !source.value && !activityFilter.value && !verification.value ? 'all' : '';
  for (const chip of quickFilters) {
    const selected = chip.dataset.quick === active;
    chip.classList.toggle('active', selected);
    chip.setAttribute('aria-pressed', String(selected));
  }
}

function resetFilters() {
  search.value = '';
  source.value = '';
  platform.value = '';
  verification.value = '';
  activityFilter.value = '';
  sort.value = 'name-ja';
  renderLimit = pageSize;
  render();
}

function queueRender() {
  clearTimeout(renderTimer);
  renderLimit = pageSize;
  renderTimer = setTimeout(render, 80);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}
function escapeAttr(value) { return escapeHtml(value ?? ''); }

fillStatsAndPlatforms();
restoreFilters();
search.addEventListener('input', queueRender);
for (const control of [source, platform, verification, activityFilter, sort]) control.addEventListener('change', queueRender);
clearSearch.addEventListener('click', () => { search.value = ''; search.focus(); queueRender(); });
$('#reset-filters').addEventListener('click', resetFilters);
emptyState.querySelector('button').addEventListener('click', resetFilters);
loadMore.addEventListener('click', () => { renderLimit += pageSize; render(); });
for (const chip of quickFilters) {
  chip.addEventListener('click', () => {
    source.value = '';
    activityFilter.value = '';
    verification.value = '';
    if (chip.dataset.quick === 'observed') activityFilter.value = 'observed';
    if (chip.dataset.quick === 'steam') source.value = 'steam';
    if (chip.dataset.quick === 'console') source.value = 'console';
    if (chip.dataset.quick === 'review') verification.value = 'seed_unverified';
    renderLimit = pageSize;
    render();
  });
}
document.addEventListener('keydown', (event) => {
  const isTyping = ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement?.tagName);
  if (event.key === '/' && !isTyping) {
    event.preventDefault();
    search.focus();
  }
  if (event.key === 'Escape' && document.activeElement === search && search.value) {
    search.value = '';
    queueRender();
  }
});
render();
