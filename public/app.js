const [gamesResponse, reviewResponse] = await Promise.all([
  fetch('./data/games.json'),
  fetch('./data/review-queue.json'),
]);
const payload = await gamesResponse.json();
const reviewPayload = await reviewResponse.json();
const games = payload.games ?? [];
const unresolved = [...(reviewPayload.unresolved_aliases ?? [])].sort((a, b) =>
  (b.observation_count ?? 0) - (a.observation_count ?? 0)
  || (b.channel_count ?? 0) - (a.channel_count ?? 0)
  || String(b.last_seen ?? '').localeCompare(String(a.last_seen ?? ''))
);
const search = document.querySelector('#search');
const verification = document.querySelector('#verification');
const container = document.querySelector('#games');
const summary = document.querySelector('#summary');
const template = document.querySelector('#game-template');
const reviewCount = document.querySelector('#review-count');
const reviewList = document.querySelector('#review-list');

const normalize = (value) => (value ?? '').normalize('NFKC').toLocaleLowerCase().replace(/[\s\u3000]+/g, ' ').trim();
const fmt = (value) => value ? new Date(value).toLocaleString('ja-JP') : '未観測';

function render() {
  const q = normalize(search.value);
  const verify = verification.value;
  const filtered = games.filter((game) => {
    if (verify && game.verification?.status !== verify) return false;
    if (!q) return true;
    const haystack = [
      game.id,
      game.titles?.primary,
      game.titles?.ja,
      game.titles?.en,
      ...(game.aliases ?? []).flatMap((a) => [a.text, a.normalized, ...(a.variants ?? [])]),
      ...(game.observed_aliases ?? []).flatMap((a) => [a.display, a.normalized]),
    ].filter(Boolean).map(normalize);
    return haystack.some((value) => value.includes(q));
  });

  const filteredReviews = unresolved.filter((entry) => !q || [
    entry.normalized,
    entry.display,
    ...(entry.latest_streams ?? []).flatMap((stream) => [stream.title, stream.channel_title]),
  ].filter(Boolean).map(normalize).some((value) => value.includes(q)));
  summary.textContent = `${filtered.length} / ${games.length} ゲーム・未解決候補 ${filteredReviews.length}件`;
  container.replaceChildren(...filtered.map(renderGame));
  renderReviews(filteredReviews);
}

function renderGame(game) {
  const node = template.content.cloneNode(true);
  node.querySelector('.game-id').textContent = game.id;
  node.querySelector('h2').textContent = game.titles.primary;
  const badge = node.querySelector('.badge');
  badge.textContent = game.verification?.status ?? 'unknown';

  const localized = [
    game.titles?.ja && `JA: ${game.titles.ja}`,
    game.titles?.en && `EN: ${game.titles.en}`,
  ].filter(Boolean).join(' / ');
  node.querySelector('.localized').textContent = localized || '正式ローカライズ名: 未確認';

  const facts = node.querySelector('.facts');
  const rows = [
    ['発売', (game.releases ?? []).map((r) => `${r.date}${r.region ? ` (${r.region})` : ''}`).join(', ') || '未登録'],
    ['機種', (game.platforms ?? []).join(', ') || '未登録'],
    ['会社', (game.companies ?? []).map((c) => `${c.name} / ${c.role}`).join(', ') || '未登録'],
    ['Wikidata', game.external_ids?.wikidata ?? '未紐付け'],
  ];
  for (const [term, value] of rows) {
    const dt = document.createElement('dt'); dt.textContent = term;
    const dd = document.createElement('dd'); dd.textContent = value;
    facts.append(dt, dd);
  }

  const aliasBox = node.querySelector('.aliases');
  const seeded = (game.aliases ?? []).flatMap((a) => a.variants ?? [a.text]);
  const observed = game.observed_aliases ?? [];
  const observedItems = observed.length
    ? `<ul class="alias-observed">${observed.map((alias) => `<li><span>${escapeHtml(alias.display || alias.normalized)}</span><small>${Number(alias.observation_count ?? 0).toLocaleString('ja-JP')}回・最終 ${escapeHtml(fmt(alias.last_seen))}</small></li>`).join('')}</ul>`
    : '<p>まだありません。</p>';
  aliasBox.innerHTML = `
    <strong>登録済み表記</strong>
    <p>${escapeHtml([...new Set(seeded)].join(' / ') || 'なし')}</p>
    <strong>配信で観測した表記ゆれ</strong>
    ${observedItems}`;

  const activity = node.querySelector('.activity');
  const streams = game.stream_activity?.latest_streams ?? [];
  const activityMeta = game.stream_activity
    ? `<p class="activity-meta">観測 ${Number(game.stream_activity.observation_count ?? 0).toLocaleString('ja-JP')}件・${escapeHtml(fmt(game.stream_activity.first_seen))} 〜 ${escapeHtml(fmt(game.stream_activity.last_seen))}</p>`
    : '';
  if (!streams.length) {
    activity.innerHTML = `<strong>配信観測</strong>${activityMeta}<p>まだ同期されていません。</p>`;
  } else {
    const links = streams.map((stream) => `<li><a href="${escapeAttr(stream.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(stream.channel_title || stream.channel_id || '配信')}</a><span>${escapeHtml(fmt(stream.observed_at))}</span></li>`).join('');
    activity.innerHTML = `<strong>配信観測</strong>${activityMeta}<ul>${links}</ul>`;
  }
  return node;
}

function renderReviews(entries) {
  reviewCount.textContent = `${entries.length}件`;
  const visible = entries.slice(0, 100);
  reviewList.innerHTML = visible.length
    ? visible.map((entry) => {
      const sample = entry.latest_streams?.[0];
      const sampleLink = sample?.url
        ? `<a href="${escapeAttr(sample.url)}" target="_blank" rel="noopener noreferrer">最新の配信例</a>`
        : '';
      return `<article class="review-item">
        <div><strong>${escapeHtml(entry.display || entry.normalized)}</strong><small>${escapeHtml(entry.normalized)}</small></div>
        <p>観測 ${Number(entry.observation_count ?? 0).toLocaleString('ja-JP')}回・${Number(entry.channel_count ?? 0).toLocaleString('ja-JP')}チャンネル・最終 ${escapeHtml(fmt(entry.last_seen))}</p>
        ${sampleLink}
      </article>`;
    }).join('')
    : '<p>該当候補はありません。</p>';
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}
function escapeAttr(value) { return escapeHtml(value ?? ''); }

search.addEventListener('input', render);
verification.addEventListener('change', render);
render();
