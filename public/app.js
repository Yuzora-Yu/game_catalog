const response = await fetch('./data/games.json');
const payload = await response.json();
const games = payload.games ?? [];
const search = document.querySelector('#search');
const verification = document.querySelector('#verification');
const container = document.querySelector('#games');
const summary = document.querySelector('#summary');
const template = document.querySelector('#game-template');

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

  summary.textContent = `${filtered.length} / ${games.length} ゲーム`;
  container.replaceChildren(...filtered.map(renderGame));
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
  const observed = (game.observed_aliases ?? []).map((a) => a.display || a.normalized);
  aliasBox.innerHTML = `<strong>呼称</strong><p>${escapeHtml([...new Set([...seeded, ...observed])].join(' / ') || 'なし')}</p>`;

  const activity = node.querySelector('.activity');
  const streams = game.stream_activity?.latest_streams ?? [];
  if (!streams.length) {
    activity.innerHTML = '<strong>直近配信</strong><p>まだ同期されていません。</p>';
  } else {
    const links = streams.map((stream) => `<li><a href="${escapeAttr(stream.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(stream.channel_title || stream.channel_id || '配信')}</a><span>${escapeHtml(fmt(stream.observed_at))}</span></li>`).join('');
    activity.innerHTML = `<strong>直近配信</strong><ul>${links}</ul>`;
  }
  return node;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}
function escapeAttr(value) { return escapeHtml(value ?? ''); }

search.addEventListener('input', render);
verification.addEventListener('change', render);
render();
