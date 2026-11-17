// HUD：血蓝、技能CD、金币、小地图、队友血条
import { TOKENS } from './ui-tokens.js';
import { el, clamp, safeNum } from './ui-dom.js';

export function createHud(root, bus) {
  const wrap = el('div', { class: 'ui-hud', attrs: { role: 'status', 'aria-live': 'polite' } });
  const hpBar = el('div', { class: 'bar bar-hp' }, [el('div', { class: 'bar-fill' })]);
  const mpBar = el('div', { class: 'bar bar-mp' }, [el('div', { class: 'bar-fill' })]);
  const gold = el('div', { class: 'hud-gold', text: '0' });
  const skills = el('div', { class: 'hud-skills' });
  const party = el('div', { class: 'hud-party' });
  const minimap = el('canvas', { class: 'hud-minimap', attrs: { width: 128, height: 96, 'aria-label': '小地图' } });
  wrap.append(hpBar, mpBar, gold, skills, party, minimap);
  root.appendChild(wrap);

  const ctx = minimap.getContext('2d');
  let last = {};

  function renderSkills(list) {
    skills.textContent = '';
    for (const s of Array.isArray(list) ? list : []) {
      const cd = clamp(safeNum(s.cd, 0), 0, 1);
      const cell = el('div', { class: 'skill', text: s.name || '?' });
      cell.style.setProperty('--cd', String(cd));
      skills.appendChild(cell);
    }
  }

  function renderParty(list) {
    party.textContent = '';
    for (const p of Array.isArray(list) ? list : []) {
      const row = el('div', { class: 'party-row' }, [
        el('span', { class: 'party-name', text: p.name || 'P' }),
        el('div', { class: 'bar bar-hp small' }, [el('div', { class: 'bar-fill' })])
      ]);
      const fill = row.querySelector('.bar-fill');
      fill.style.width = `${clamp(safeNum(p.hpRatio, 1), 0, 1) * 100}%`;
      party.appendChild(row);
    }
  }

  function renderMinimap(rooms) {
    ctx.clearRect(0, 0, minimap.width, minimap.height);
    ctx.fillStyle = TOKENS.color.bg;
    ctx.fillRect(0, 0, minimap.width, minimap.height);
    for (const r of Array.isArray(rooms) ? rooms : []) {
      if (!r.explored) continue;
      ctx.fillStyle = r.type === 'boss' ? TOKENS.color.danger : r.type === 'campfire' ? TOKENS.color.gold : TOKENS.color.panelAlt;
      ctx.fillRect(safeNum(r.x, 0), safeNum(r.y, 0), 10, 8);
    }
  }

  function update(snap) {
    last = snap || {};
    const hp = clamp(safeNum(last.hpRatio, 1), 0, 1);
    const mp = clamp(safeNum(last.mpRatio, 1), 0, 1);
    hpBar.firstChild.style.width = `${hp * 100}%`;
    mpBar.firstChild.style.width = `${mp * 100}%`;
    gold.textContent = String(safeNum(last.gold, 0));
    renderSkills(last.skills);
    renderParty(last.party);
    renderMinimap(last.rooms);
  }

  const off = bus.on('state:update', update);
  update(bus.getSnapshot());

  return { update, destroy() { off && off(); wrap.remove(); } };
}
