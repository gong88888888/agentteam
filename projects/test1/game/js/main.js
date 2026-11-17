import {
  CLASSES, DIFFICULTIES, ROOM_LABEL, QUALITIES, createRun, currentRoom,
  currentFloor, rollLoot, makeItem, shopStock, eventChoice, derivedStats,
  equipItem, addInventory, decomposeValue, reforgeItem, tryUpgrade,
  upgradeCost, chapterProgress, multiplayerScale, encodeSave, decodeSave,
  snapshot, restoreRun, mulberry32, itemScore, addXp, questProgress, claimQuest,
} from "./core.js";

const W = 1280;
const H = 720;
const FLOOR = 600;
const SAVE_PREFIX = "maze-adventurer-save-";
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");
const minimap = document.getElementById("minimap");
const mctx = minimap.getContext("2d");
const menu = document.getElementById("menu");
const panel = document.getElementById("panel");
const panelTitle = document.getElementById("panel-title");
const panelBody = document.getElementById("panel-body");
const classCards = [...document.querySelectorAll(".class-card")];
const diffBtns = [...document.querySelectorAll(".diff-btn")];
const coopBox = document.getElementById("coop");
const startBtn = document.getElementById("start");
const saveSlots = document.getElementById("save-slots");
const hud = {
  hp: document.getElementById("hp-fill"), hpText: document.getElementById("hp-text"),
  mp: document.getElementById("mp-fill"), mpText: document.getElementById("mp-text"),
  p2: document.getElementById("p2-hud"), p2hp: document.getElementById("p2-fill"),
  p2mp: document.getElementById("p2-mp-fill"), p2Text: document.getElementById("p2-text"),
  p2MpText: document.getElementById("p2-mp-text"),
  gold: document.getElementById("gold"), level: document.getElementById("level"), floor: document.getElementById("floor"),
  room: document.getElementById("room"), potions: document.getElementById("potions"),
  difficulty: document.getElementById("difficulty-chip"),
  objective: document.getElementById("objective"), loot: document.getElementById("loot-log"),
  message: document.getElementById("message"), hint: document.getElementById("interact-hint"),
  boss: document.getElementById("boss-hud"), bossName: document.getElementById("boss-name"),
  bossPhase: document.getElementById("boss-phase"), bossFill: document.getElementById("boss-fill"),
};
const toastEl = document.getElementById("toast");

const keys = new Set();
let selectedClass = "swordsman";
let difficulty = 2;
let coop = false;
let mode = "menu";
let panelKind = null;
let run = null;
let floor = null;
let room = null;
let enemies = [];
let ground = [];
let projectiles = [];
let effects = [];
let rand = mulberry32(1);
let lastTime = 0;
let messageTimer = 0;
let shake = 0;
let hitStop = 0;
let interactableDone = false;
let currentSlot = 1;
let shop = null;
let eventData = null;
let boss = null;
let audio = null;
let paused = false;

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));

function toast(text, seconds = 2.6) {
  toastEl.textContent = text;
  toastEl.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toastEl.classList.remove("show"), seconds * 1000);
}

function showMessage(text, seconds = 2.2) {
  hud.message.textContent = text;
  hud.message.classList.add("show");
  messageTimer = seconds;
}

function beep(freq = 440, duration = 0.06, type = "square", gain = 0.03) {
  try {
    if (!audio) audio = new AudioContext();
    const osc = audio.createOscillator();
    const vol = audio.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    vol.gain.value = gain;
    osc.connect(vol);
    vol.connect(audio.destination);
    osc.start();
    osc.stop(audio.currentTime + duration);
  } catch { /* audio is optional */ }
}

function setSelected(classId) {
  selectedClass = classId;
  classCards.forEach((card) => card.classList.toggle("selected", card.dataset.class === classId));
}

function setDifficulty(value) {
  difficulty = Number(value);
  diffBtns.forEach((btn) => btn.classList.toggle("selected", Number(btn.dataset.diff) === difficulty));
}

classCards.forEach((card) => card.addEventListener("click", () => setSelected(card.dataset.class)));
diffBtns.forEach((btn) => btn.addEventListener("click", () => setDifficulty(btn.dataset.diff)));
startBtn.addEventListener("click", () => startGame(selectedClass, coopBox.checked, difficulty));
coopBox.addEventListener("change", () => { coop = coopBox.checked; });
$("panel-close").addEventListener("click", closePanel);

function startGame(classId = selectedClass, isCoop = false, diff = 2, seed = null) {
  run = createRun(classId, isCoop, diff, seed ?? (Date.now() >>> 0));
  run.startedAt = performance.now();
  rand = mulberry32(run.seed ^ 0x9e3779b9);
  mode = "playing";
  paused = false;
  panelKind = null;
  panel.classList.add("hidden");
  menu.classList.add("hidden");
  currentSlot = currentSlot || 1;
  loadRoom(run.floorIndex, run.roomIndex, true);
  showMessage("第一章 · 蘑菇林：清空房间，探索商店/篝火，最后击败蘑菇王。", 5);
  toast(`难度：${DIFFICULTIES[run.difficulty - 1].name} · ${isCoop ? "本地双人" : "单人"}`, 3);
  autoSave();
}

function scaledEnemiesForRoom() {
  const diff = DIFFICULTIES[run.difficulty - 1] || DIFFICULTIES[1];
  const coopScale = multiplayerScale(run.players.length, room.type === "boss");
  return room.enemies.map((spec, index) => {
    const maxHp = Math.max(1, Math.round(spec.maxHp * coopScale.hp * diff.hp));
    return {
      ...spec, maxHp, hp: maxHp,
      damage: Math.max(1, Math.round(spec.damage * coopScale.damage * diff.damage)),
      w: spec.boss ? 92 : spec.elite ? 58 : 44,
      h: spec.boss ? 112 : spec.elite ? 62 : 52,
      x: 300 + index * 180, y: 540, vx: 0, vy: 0, onGround: false,
      hit: 0, atkCd: 1.2 + rand(), phase: 1,
    };
  });
}

function loadRoom(floorIndex, roomIndex, initial = false) {
  run.floorIndex = Math.max(0, Math.min(floorIndex, run.chapter.floors.length - 1));
  floor = currentFloor(run);
  run.roomIndex = Math.max(0, Math.min(roomIndex, floor.rooms.length - 1));
  room = currentRoom(run);
  run.currentRoom = room;
  const key = `${run.floorIndex + 1}-${run.roomIndex}`;
  interactableDone = !room.interactable || Boolean(run.cleared[key]);
  enemies = run.cleared[key] ? [] : scaledEnemiesForRoom();
  boss = enemies.find((e) => e.boss) || null;
  ground = [];
  projectiles = [];
  effects = [];
  run.players.forEach((p, i) => {
    p.x = 90 + i * 58;
    p.y = 540;
    p.vx = 0;
    p.vy = 0;
    p.cooldown = 0;
    p.attackCooldown = 0;
    p.skillCooldown = 0;
    p.dodgeCooldown = 0;
    p.invuln = 0;
    if (!p.downed) p.hp = Math.max(p.hp, 1);
  });
  room.door.locked = !roomCleared();
  showMessage(`${room.label} · ${room.name}${room.type === "boss" ? " · BOSS" : ""}`, 2.6);
  autoSave();
  updateHud();
}

function roomCleared() {
  return enemies.length === 0 && interactableDone;
}

function markClearedIfReady() {
  if (!roomCleared()) return;
  const key = `${run.floorIndex + 1}-${run.roomIndex}`;
  if (!run.cleared[key]) {
    run.cleared[key] = true;
    room.door.locked = false;
    questProgress(run, "room", 1);
    showMessage(room.type === "boss" ? "本层 Boss 已击败，出口开启" : "房间已清空，右侧门已开启", 3);
    autoSave();
  }
}

function platformsForRoom() {
  return [{ x: 0, y: FLOOR, w: W, h: 120 }, ...(room?.platforms || [])];
}

function aabb(a, b) {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function resolvePlatforms(body, dt) {
  body.vy += 1800 * dt;
  body.x += body.vx * dt;
  body.y += body.vy * dt;
  body.onGround = false;
  for (const platform of platformsForRoom()) {
    const box = { x: body.x - body.w / 2, y: body.y - body.h, w: body.w, h: body.h };
    if (!aabb(box, platform)) continue;
    if (body.vy >= 0 && box.y + box.h - platform.y < 30) {
      body.y = platform.y;
      body.vy = 0;
      body.onGround = true;
    }
  }
  body.x = Math.max(44, Math.min(W - 44, body.x));
  if (body.y > H + 180) {
    body.x = 90;
    body.y = 500;
    body.vy = 0;
    if (body.maxHp) body.hp = Math.max(1, body.hp - 8);
  }
}

function playerInput(index) {
  if (index === 0) {
    return {
      left: keys.has("KeyA"), right: keys.has("KeyD"),
      jump: keys.has("KeyW") || keys.has("Space"),
    };
  }
  return {
    left: keys.has("ArrowLeft"), right: keys.has("ArrowRight"),
    jump: keys.has("ArrowUp"),
  };
}

function stepPlayer(p, index, dt) {
  if (p.downed) return;
  const stats = derivedStats(p);
  const input = playerInput(index);
  const dir = (input.right ? 1 : 0) - (input.left ? 1 : 0);
  p.vx = dir * stats.speed;
  if (dir) p.facing = dir;
  if (input.jump && p.onGround) {
    p.vy = -CLASSES[p.classId].jump;
    p.onGround = false;
    beep(520, 0.05, "square", 0.015);
  }
  if (p.dodgeCooldown > 0) p.vx *= 0.25;
  resolvePlatforms(p, dt);
  p.attackCooldown = Math.max(0, p.attackCooldown - dt);
  p.skillCooldown = Math.max(0, p.skillCooldown - dt);
  p.skill2Cooldown = Math.max(0, p.skill2Cooldown - dt);
  p.dodgeCooldown = Math.max(0, p.dodgeCooldown - dt);
  p.invuln = Math.max(0, p.invuln - dt);
  p.hitTimer = Math.max(0, p.hitTimer - dt);
  p.mp = Math.min(stats.maxMp, p.mp + dt * 2);
}

function damageEnemy(enemy, amount, crit = false) {
  const reduced = Math.max(1, Math.round(amount * (1 - (enemy.defense || 0))));
  enemy.hp -= reduced;
  enemy.hit = 0.12;
  effects.push({
    x: enemy.x, y: enemy.y - 50, life: 0.5, color: crit ? "#fde047" : "#fff",
    text: `${crit ? "暴击 " : ""}-${reduced}`,
  });
  beep(crit ? 880 : 660, 0.045, "square", 0.02);
  if (enemy.hp <= 0) killEnemy(enemy);
}

function attack(player, heavy = false) {
  if (player.attackCooldown > 0 || player.downed) return;
  player.attackCooldown = heavy ? 0.85 : 0.34;
  const stats = derivedStats(player);
  let hits = 0;
  const range = stats.range + (heavy ? 24 : 0);
  const vertical = 86;
  enemies.forEach((enemy) => {
    const dx = Math.abs(enemy.x - player.x);
    const dy = Math.abs(enemy.y - player.y);
    if (dx <= range && dy <= vertical) {
      const crit = Math.random() < 0.06 + stats.crit;
      const raw = stats.attack * (heavy ? 1.7 : 1) * (crit ? 1.8 : 1);
      damageEnemy(enemy, raw, crit);
      hits += 1;
    }
  });
  effects.push({
    x: player.x + player.facing * (range / 2), y: player.y - 40,
    life: 0.18, arc: true, color: player.color, radius: range,
  });
  if (heavy) { shake = Math.max(shake, 7); hitStop = 0.06; }
  if (hits) showMessage(`${player.name} ${heavy ? "重击" : "普攻"}命中 ${hits} 个敌人`, 0.8);
}

function skill(player, slot = 1) {
  if (player.downed) return;
  if (slot === 2) return skill2(player);
  if (player.skillCooldown > 0) return;
  const spec = CLASSES[player.classId];
  const skill = spec.skill;
  if (player.mp < skill.mp) {
    showMessage(`MP 不足：${skill.name} 需要 ${skill.mp}`, 1.6);
    return;
  }
  player.mp -= skill.mp;
  player.skillCooldown = skill.cooldown;
  const stats = derivedStats(player);
  let hits = 0;
  enemies.forEach((enemy) => {
    if (Math.abs(enemy.x - player.x) <= skill.radius && Math.abs(enemy.y - player.y) < 120) {
      const damage = stats.attack * (skill.damage / 20);
      damageEnemy(enemy, damage, false);
      hits += 1;
    }
  });
  effects.push({ x: player.x, y: player.y - 40, life: 0.5, skill: true,
    color: player.color, radius: skill.radius });
  shake = Math.max(shake, 5);
  beep(320, 0.18, "sawtooth", 0.03);
  showMessage(`${skill.name}！${hits ? `命中 ${hits} 个敌人` : "没有命中"}`, 1.5);
}

function skill2(player) {
  if (player.skill2Cooldown > 0) return;
  const spec = CLASSES[player.classId];
  const skill = spec.skill2;
  if (player.mp < skill.mp) {
    showMessage(`MP 不足：${skill.name} 需要 ${skill.mp}`, 1.6);
    return;
  }
  player.mp -= skill.mp;
  player.skill2Cooldown = skill.cooldown;
  const stats = derivedStats(player);
  let hits = 0;
  enemies.forEach((enemy) => {
    if (Math.abs(enemy.x - player.x) <= skill.radius && Math.abs(enemy.y - player.y) < 120) {
      damageEnemy(enemy, stats.attack * (skill.damage / 20) * 1.2, false);
      hits += 1;
    }
  });
  if (spec.id === "ranger") {
    player.vx = -player.facing * 520;
    player.invuln = 0.2;
  }
  effects.push({ x: player.x, y: player.y - 40, life: 0.5, skill: true,
    color: player.color, radius: skill.radius });
  shake = Math.max(shake, 4);
  beep(440, 0.14, "triangle", 0.025);
  showMessage(`${skill.name}！${hits ? `命中 ${hits} 个敌人` : "没有命中"}`, 1.5);
}

function dodge(player) {
  if (player.dodgeCooldown > 0 || player.downed) return;
  player.dodgeCooldown = 1.2;
  player.invuln = 0.38;
  player.vx = player.facing * 760;
  player.vy = -120;
  effects.push({ x: player.x, y: player.y - 30, life: 0.25, dodge: true, color: player.color });
  beep(760, 0.05, "sine", 0.015);
}

function usePotion(player) {
  if (player.downed || run.potions <= 0) {
    showMessage("没有药水了", 1.4);
    return;
  }
  run.potions -= 1;
  const stats = derivedStats(player);
  const amount = Math.round(stats.maxHp * 0.4);
  player.hp = Math.min(stats.maxHp, player.hp + amount);
  showMessage(`喝下药水，恢复 ${amount} 生命`, 1.6);
  effects.push({ x: player.x, y: player.y - 60, life: 0.6, color: "#22c55e", text: `+${amount}` });
  beep(920, 0.08, "sine", 0.02);
}

function damagePlayer(player, amount) {
  if (player.invuln > 0 || player.downed) return;
  const stats = derivedStats(player);
  const reduced = Math.max(1, Math.round(amount * (1 - Math.min(0.5, stats.defense / 100))));
  player.hp -= reduced;
  player.invuln = 0.45;
  player.hitTimer = 0.2;
  shake = Math.max(shake, 4);
  effects.push({ x: player.x, y: player.y - 50, life: 0.5, color: "#ef4444", text: `-${reduced}` });
  if (player.hp <= 0) {
    player.hp = 0;
    player.downed = true;
    player.reviveProgress = 0;
    showMessage(`${player.name} 倒下了${run.players.length > 1 ? "，队友靠近按 E 扶起" : "，自动回到房间入口"}`, 3);
    if (run.players.length === 1) {
      player.downed = false;
      player.hp = Math.round(stats.maxHp * 0.5);
      player.x = 90;
      player.y = 500;
      run.gold = Math.max(0, run.gold - 10);
    } else if (run.players.every((p) => p.downed)) {
      gameOver();
    }
  }
}

function killEnemy(enemy) {
  if (enemy.dead) return;
  enemy.dead = true;
  enemies = enemies.filter((e) => e !== enemy);
  const loot = rollLoot(rand, run.floorIndex + 1, enemy.boss);
  run.gold += loot.gold;
  if (loot.item) {
    if (!addInventory(run.players[0], loot.item, 60)) {
      ground.push({ x: enemy.x, y: 540, item: loot.item, bob: 0 });
    } else {
      showMessage(`获得 ${loot.item.name} · +${loot.gold} 金币`, 2.2);
    }
  } else {
    showMessage(`+${loot.gold} 金币`, 1.2);
  }
  run.lootLog = (run.lootLog || []).concat(loot.item ? [loot.item] : []).slice(-6);
  const owner = run.players[0];
  if (owner) {
    addXp(owner, enemy.boss ? 60 : enemy.elite ? 22 : 10);
    questProgress(run, "kill", 1);
    if (enemy.boss) questProgress(run, "boss", 1);
  }
  effects.push({ x: enemy.x, y: enemy.y - 60, life: 0.7, color: "#facc15", text: "击破!" });
  if (enemy.boss) {
    boss = null;
    showMessage("蘑菇王被击败！本层出口开启。", 3);
  }
  markClearedIfReady();
}

function stepRevives(dt) {
  run.players.forEach((p) => {
    if (!p.downed) return;
    const helper = run.players.some((other) => other !== p && !other.downed
      && Math.abs(other.x - p.x) < 80 && Math.abs(other.y - p.y) < 100);
    if (helper && keys.has("KeyE")) p.reviveProgress = Math.min(3, (p.reviveProgress || 0) + dt);
    if (p.reviveProgress >= 3) {
      p.downed = false;
      p.hp = Math.round(derivedStats(p).maxHp * 0.45);
      showMessage(`扶起 ${p.name}`, 1.8);
    }
  });
}

function stepEnemies(dt) {
  const alive = run.players.filter((p) => !p.downed);
  if (!alive.length) return;
  enemies.forEach((enemy) => {
    if (enemy.dead) return;
    const target = alive.reduce((best, p) =>
      Math.abs(p.x - enemy.x) < Math.abs(best.x - enemy.x) ? p : best, alive[0]);
    const dx = target.x - enemy.x;
    enemy.atkCd = Math.max(0, enemy.atkCd - dt);
    enemy.hit = Math.max(0, enemy.hit - dt);
    if (enemy.boss) {
      const ratio = enemy.hp / enemy.maxHp;
      const phase = ratio > 0.66 ? 1 : ratio > 0.33 ? 2 : 3;
      if (phase !== enemy.phase) {
        enemy.phase = phase;
        showMessage(`蘑菇王进入第 ${phase} 阶段`, 2);
        shake = 6;
      }
      enemy.vx = Math.abs(dx) > 120 ? Math.sign(dx) * enemy.speed : 0;
      resolvePlatforms(enemy, dt);
      if (enemy.atkCd <= 0) {
        enemy.atkCd = phase === 3 ? 1.2 : 1.8;
        for (let i = -1; i <= 1; i += 1) {
          projectiles.push({ x: enemy.x, y: enemy.y - 70, vx: i * 120, vy: -100 + phase * 20,
            damage: enemy.damage, life: 3, color: "#f97316" });
        }
      }
      return;
    }
    if (enemy.kind === "archer") {
      if (Math.abs(dx) > 260) enemy.vx = Math.sign(dx) * enemy.speed;
      else enemy.vx = 0;
      resolvePlatforms(enemy, dt);
      if (enemy.atkCd <= 0 && Math.abs(dx) < 520) {
        enemy.atkCd = 2;
        projectiles.push({ x: enemy.x, y: enemy.y - 50, vx: Math.sign(dx) * 320,
          vy: 0, damage: enemy.damage, life: 2.2, color: "#f97316" });
      }
      return;
    }
    if (enemy.kind === "bomber") {
      enemy.vx = Math.sign(dx) * enemy.speed;
      resolvePlatforms(enemy, dt);
      if (Math.abs(dx) < 58 && enemy.atkCd <= 0) {
        enemy.atkCd = 4;
        alive.forEach((p) => { if (Math.abs(p.x - enemy.x) < 100) damagePlayer(p, enemy.damage + 8); });
        enemy.hp = 0;
        killEnemy(enemy);
      }
      return;
    }
    if (enemy.kind === "flyer") {
      enemy.x += Math.sign(dx) * enemy.speed * dt;
      enemy.y = 470 + Math.sin(performance.now() / 500 + enemy.x) * 45;
      if (Math.abs(dx) < 42 && enemy.atkCd <= 0) {
        enemy.atkCd = 1.4;
        damagePlayer(target, enemy.damage);
      }
      return;
    }
    enemy.vx = Math.abs(dx) > 38 ? Math.sign(dx) * enemy.speed : 0;
    resolvePlatforms(enemy, dt);
    if (Math.abs(dx) < 48 && Math.abs(target.y - enemy.y) < 80 && enemy.atkCd <= 0) {
      enemy.atkCd = 1.2;
      damagePlayer(target, enemy.damage);
      if (enemy.affix === "vampiric") enemy.hp = Math.min(enemy.maxHp, enemy.hp + 3);
    }
  });
  markClearedIfReady();
}

function stepProjectiles(dt) {
  projectiles.forEach((p) => {
    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.life -= dt;
    run.players.forEach((player) => {
      if (player.downed) return;
      if (Math.abs(p.x - player.x) < 26 && Math.abs(p.y - player.y) < 42) {
        damagePlayer(player, p.damage);
        p.life = 0;
      }
    });
  });
  projectiles = projectiles.filter((p) => p.life > 0 && p.x > -20 && p.x < W + 20);
}

function stepGround(dt) {
  ground.forEach((item) => { item.bob += dt * 4; });
  ground = ground.filter((g) => {
    if (Math.abs(run.players[0].x - g.x) < 42 && Math.abs(run.players[0].y - g.y) < 70) {
      if (addInventory(run.players[0], g.item, 60)) {
        toast(`拾取 ${g.item.name}`, 1.8);
        return false;
      }
    }
    return true;
  });
}

function near(x, y, radius = 52) {
  return run.players.some((p) => !p.downed && Math.abs(p.x - x) < radius && Math.abs(p.y - y) < 90);
}

function interact() {
  if (!room || mode !== "playing") return;
  const downed = run.players.find((p) => p.downed && near(p.x, p.y, 70));
  if (downed) {
    showMessage("靠近倒地队友，按住 E 3 秒扶起", 1.5);
    return;
  }
  if (room.door && room.door.x && !room.door.locked && near(room.door.x, 540, 64)) {
    nextRoom();
    return;
  }
  if (!interactableDone && near(980, 540, 90)) {
    if (room.interactable === "chest") openChest();
    if (room.interactable === "merchant") openShop();
    if (room.interactable === "campfire") openCampfire();
    if (room.interactable === "event") openEvent();
  }
}

function openChest() {
  const loot = rollLoot(rand, run.floorIndex + 1, false);
  run.gold += loot.gold + 15;
  if (loot.item) addInventory(run.players[0], loot.item, 60);
  interactableDone = true;
  showMessage(`打开宝箱：+${loot.gold + 15} 金币${loot.item ? ` · ${loot.item.name}` : ""}`, 2.4);
  markClearedIfReady();
  autoSave();
}

function openShop() {
  shop = shopStock(rand, run.floorIndex + 1);
  openPanel("shop", "流浪商人", renderShop());
}

function openCampfire() {
  openPanel("campfire", "篝火", renderCampfire());
}

function openEvent() {
  eventData = eventChoice(rand, run.floorIndex + 1);
  openPanel("event", eventData.title, renderEvent());
}

function nextRoom() {
  if (run.roomIndex + 1 < floor.rooms.length) {
    loadRoom(run.floorIndex, run.roomIndex + 1);
  } else if (run.floorIndex + 1 < run.chapter.floors.length) {
    loadRoom(run.floorIndex + 1, 0);
    showMessage(`进入第 ${run.floorIndex + 1} 层：${floor.name}`, 3);
  } else {
    victory();
  }
}

function victory() {
  mode = "victory";
  openPanel("victory", "第一章通关", `
    <p class="panel-note">你完成了 5 层迷宫与蘑菇王，当前金币 <b>${run.gold}</b>。</p>
    <p class="panel-note">MVP 切片验证了 3 职业、装备/词条、商店/篝火/事件、Boss、存档和本地双人。</p>
    <div class="panel-actions"><button data-act="new">再玩一次</button></div>`);
  saveSlot(currentSlot);
}

function gameOver() {
  mode = "gameover";
  openPanel("gameover", "全员倒下", `
    <p class="panel-note">别担心，回到最近篝火或读档继续。</p>
    <div class="panel-actions">
      <button data-act="load">读取存档</button>
      <button data-act="new">重新开始</button>
    </div>`);
}

function openPanel(kind, title, html) {
  panelKind = kind;
  panelTitle.textContent = title;
  panelBody.innerHTML = html;
  panel.classList.remove("hidden");
  mode = "panel";
}

function closePanel() {
  const kind = panelKind;
  panel.classList.add("hidden");
  panelKind = null;
  if (kind === "pause") paused = false;
  if (kind === "shop" || kind === "campfire") {
    interactableDone = true;
    markClearedIfReady();
    autoSave();
  }
  if (kind === "inventory" || kind === "pause" || kind === "shop" || kind === "campfire" || kind === "quests") {
    mode = "playing";
  }
}

function renderInventory() {
  const p = run.players[0];
  const stats = derivedStats(p);
  const slots = Object.entries(p.equipment).map(([slot, item]) => `
    <div class="slot-row"><span class="slot-name">${esc(slot)}</span>
      <span class="slot-item" style="border-left:4px solid ${item ? QUALITIES.find((q) => q.id === item.quality)?.color : "transparent"}">
        ${item ? `${esc(item.name)} +${item.upgrade}` : "空"}</span></div>`).join("");
  const items = p.inventory.length ? p.inventory.map((item, index) => `
    <div class="item-card" style="border-left-color:${QUALITIES.find((q) => q.id === item.quality)?.color}">
      <div class="item-name">${esc(item.name)} +${item.upgrade}</div>
      <div class="item-meta">${esc(item.slotName)} · ${QUALITIES.find((q) => q.id === item.quality)?.name} · 评分 ${itemScore(item)}</div>
      <div class="item-affixes">${item.affixes.map((a) => `${a.name}+${a.value}`).join(" · ")}</div>
      <div class="item-actions">
        <button data-act="equip" data-index="${index}">装备</button>
        <button data-act="decompose" data-index="${index}">分解 +${decomposeValue(item)}g</button>
      </div>
    </div>`).join("") : `<p class="panel-note">背包为空，打怪或开宝箱获得装备。</p>`;
  return `<div class="panel-note">攻击 ${stats.attack} · 防御 ${stats.defense} · 暴击 ${(stats.crit * 100).toFixed(0)}% · 背包 ${p.inventory.length}/60</div>
    <h3>装备</h3>${slots}<h3>背包</h3><div class="item-grid">${items}</div>`;
}

function renderShop() {
  const items = shop.items.map((item, index) => {
    const price = Math.round(itemScore(item) * 1.6);
    return `<div class="item-card" style="border-left-color:${QUALITIES.find((q) => q.id === item.quality)?.color}">
      <div class="item-name">${esc(item.name)}</div>
      <div class="item-meta">${esc(item.slotName)} · ${item.affixes.map((a) => `${a.name}+${a.value}`).join(" · ")}</div>
      <div class="item-actions"><button data-act="buy-item" data-index="${index}" data-price="${price}">购买 ${price} 金币</button></div>
    </div>`;
  }).join("");
  return `<p class="panel-note">金币 <b id="shop-gold">${run.gold}</b> · 治疗药水 10 金币 · 重铸武器 30 金币</p>
    <div class="panel-actions"><button data-act="buy-potion">买药水（10）</button>
      <button data-act="reforge">重铸武器（30）</button></div>
    <div class="item-grid">${items}</div>
    <p class="panel-note">关闭商店后，本房间标记完成。</p>`;
}

function renderCampfire() {
  const p = run.players[0];
  const weapon = p.equipment.weapon;
  const cost = weapon ? upgradeCost(weapon) : 0;
  return `<p class="panel-note">篝火可以恢复生命、自动存档、强化武器和重铸词条。</p>
    <div class="panel-actions">
      <button data-act="rest">休息（恢复 50% 生命）</button>
      <button data-act="save-slot">保存到槽位 ${currentSlot}</button>
      ${weapon ? `<button data-act="upgrade">强化武器（${cost} 金币）</button>` : `<span class="panel-note">没有装备武器</span>`}
      ${weapon ? `<button data-act="reforge">重铸武器（30 金币）</button>` : ""}
    </div>
    <p class="panel-note">当前金币：${run.gold} · 武器：${weapon ? `${esc(weapon.name)} +${weapon.upgrade}` : "无"}</p>`;
}

function renderEvent() {
  return `<p class="panel-note">${esc(eventData.text)}</p>
    <div class="panel-actions">
      <button class="choice-card" data-act="event-accept"><b>接受</b><small>${eventData.effect === "curse" ? "获得紫装，受到 20 伤害" : "按描述生效"}</small></button>
      <button class="choice-card" data-act="event-skip"><b>离开</b><small>不承担风险</small></button>
    </div>`;
}

function renderPause() {
  return `<p class="panel-note">游戏已暂停。</p>
    <div class="panel-actions">
      <button data-act="resume">继续</button>
      <button data-act="save-slot">保存到槽位 ${currentSlot}</button>
      <button data-act="new">返回主菜单</button>
    </div>
    <p class="panel-note">F5 快速存档 · F9 读档 · I 背包 · Esc 暂停</p>`;
}

function renderQuests() {
  return `<p class=\"panel-note\">第一章任务与奖励，完成后可领取。</p>` +
    run.quests.map((q) => `<div class="item-card">
      <div class="item-name">${esc(q.title)} ${q.done ? "· 可领取" : ""}</div>
      <div class="item-meta">${esc(q.desc)} · ${q.progress}/${q.target} · 奖励 ${q.reward} 金币</div>
      <div class="item-actions">${q.done && !q.claimed
        ? `<button data-act="claim-quest" data-quest="${esc(q.id)}">领取</button>` : q.claimed ? "已领取" : "进行中"}</div>
    </div>`).join("");
}

function openQuests() {
  openPanel("quests", "任务板", renderQuests());
}

function openInventory() {
  openPanel("inventory", "背包与装备", renderInventory());
}

function handlePanelAction(act, target) {
  const p = run.players[0];
  if (act === "equip") {
    const item = p.inventory.splice(Number(target.dataset.index), 1)[0];
    const old = equipItem(p, item);
    if (old) addInventory(p, old, 60);
    p.hp = Math.min(derivedStats(p).maxHp, p.hp);
    panelBody.innerHTML = renderInventory();
    showMessage(`装备 ${item.name}`, 1.5);
  }
  if (act === "decompose") {
    const item = p.inventory.splice(Number(target.dataset.index), 1)[0];
    run.gold += decomposeValue(item);
    panelBody.innerHTML = renderInventory();
  }
  if (act === "buy-item") {
    const item = shop.items[Number(target.dataset.index)];
    const price = Number(target.dataset.price);
    if (run.gold >= price && addInventory(p, item, 60)) {
      run.gold -= price;
      shop.items.splice(Number(target.dataset.index), 1);
      panelBody.innerHTML = renderShop();
      showMessage(`购买 ${item.name}`, 1.5);
    } else showMessage("金币不足或背包已满", 1.8);
  }
  if (act === "buy-potion") {
    if (run.gold >= 10) {
      run.gold -= 10; run.potions += 1; panelBody.innerHTML = renderShop();
    } else showMessage("金币不足", 1.5);
  }
  if (act === "reforge") {
    const weapon = p.equipment.weapon || p.inventory[0];
    if (!weapon) { showMessage("没有可重铸的装备", 1.5); return; }
    if (run.gold < 30) { showMessage("金币不足", 1.5); return; }
    run.gold -= 30;
    reforgeItem(weapon, rand);
    panelBody.innerHTML = panelKind === "campfire" ? renderCampfire() : renderShop();
    showMessage("词条已重铸", 1.5);
  }
  if (act === "rest") {
    const stats = derivedStats(p);
    p.hp = Math.min(stats.maxHp, p.hp + stats.maxHp * 0.5);
    showMessage("篝火休息，恢复生命", 1.8);
    panelBody.innerHTML = renderCampfire();
  }
  if (act === "upgrade") {
    const weapon = p.equipment.weapon;
    if (!weapon) return;
    const result = tryUpgrade(weapon, run.gold);
    if (result.ok) {
      run.gold -= result.cost;
      showMessage(`武器强化到 +${weapon.upgrade}`, 1.8);
    } else showMessage(result.reason, 1.8);
    panelBody.innerHTML = renderCampfire();
  }
  if (act === "save-slot") {
    saveSlot(currentSlot);
    showMessage(`已保存到槽位 ${currentSlot}`, 1.8);
  }
  if (act === "event-accept") {
    if (eventData.effect === "attack") {
      if (run.gold >= eventData.cost) {
        run.gold -= eventData.cost;
        p.baseAttack += 2;
        showMessage("永久攻击 +2", 2);
      } else showMessage("金币不足", 1.5);
    } else if (eventData.effect === "heal") {
      const stats = derivedStats(p);
      p.maxHp = Math.max(20, p.maxHp - 5);
      p.hp = Math.min(p.maxHp, p.hp + stats.maxHp * 0.35);
      showMessage("恢复生命，最大生命 -5", 2);
    } else if (eventData.effect === "gold") {
      run.gold += 40; showMessage("获得 40 金币", 2);
    } else if (eventData.effect === "curse") {
      addInventory(p, makeItem(rand, run.floorIndex + 1, "purple"), 60);
      p.hp = Math.max(1, p.hp - 20);
      showMessage("获得紫装，受到 20 伤害", 2);
    }
    interactableDone = true;
    closePanel();
    autoSave();
  }
  if (act === "event-skip") {
    interactableDone = true;
    closePanel();
  }
  if (act === "claim-quest") {
    const reward = claimQuest(run, target.dataset.quest);
    if (reward) showMessage(`领取任务奖励 +${reward} 金币`, 1.8);
    panelBody.innerHTML = renderQuests();
  }
  if (act === "resume") closePanel();
  if (act === "load") loadSlot(currentSlot);
  if (act === "new") { panel.classList.add("hidden"); mode = "menu"; menu.classList.remove("hidden"); renderSaveSlots(); }
}

panelBody.addEventListener("click", (event) => {
  const target = event.target.closest("button[data-act]");
  if (!target) return;
  handlePanelAction(target.dataset.act, target);
});

function autoSave() {
  if (!run || mode === "menu") return;
  saveSlot(currentSlot, true);
}

function saveSlot(slot = currentSlot, silent = false) {
  if (!run) return;
  try {
    localStorage.setItem(`${SAVE_PREFIX}${slot}`, encodeSave(snapshot(run, slot)));
    if (!silent) toast(`已保存到槽位 ${slot}`, 1.8);
    renderSaveSlots();
  } catch { if (!silent) toast("存档失败：浏览器存储不可用", 2); }
}

function loadSlot(slot = currentSlot) {
  try {
    const data = decodeSave(localStorage.getItem(`${SAVE_PREFIX}${slot}`));
    if (!data) { toast("没有可用存档", 1.8); return false; }
    run = restoreRun(data);
    currentSlot = slot;
    rand = mulberry32(run.seed ^ 0x9e3779b9);
    menu.classList.add("hidden");
    panel.classList.add("hidden");
    paused = false;
    mode = "playing";
    loadRoom(run.floorIndex, run.roomIndex);
    showMessage(`读取槽位 ${slot} · 第 ${run.floorIndex + 1} 层`, 2.5);
    return true;
  } catch {
    toast("存档损坏或版本不兼容", 2);
    return false;
  }
}

function renderSaveSlots() {
  const html = [1, 2, 3].map((slot) => {
    const data = decodeSave(localStorage.getItem(`${SAVE_PREFIX}${slot}`));
    const label = data
      ? `第 ${(data.floorIndex || 0) + 1} 层 · 房间 ${(data.roomIndex || 0) + 1} · ${data.gold || 0}g`
      : "空槽位";
    return `<button class="save-slot" data-slot="${slot}"><b>槽位 ${slot}</b>${label}</button>`;
  }).join("");
  saveSlots.innerHTML = html;
  saveSlots.querySelectorAll("button").forEach((btn) => btn.addEventListener("click", () => {
    const slot = Number(btn.dataset.slot);
    if (localStorage.getItem(`${SAVE_PREFIX}${slot}`)) {
      currentSlot = slot;
      loadSlot(slot);
    } else {
      currentSlot = slot;
      toast(`已选择槽位 ${slot}，开始游戏后自动保存`, 1.8);
    }
  }));
}

function updateHud() {
  if (!run) return;
  const p = run.players[0];
  const stats = derivedStats(p);
  hud.hp.style.width = `${Math.max(0, Math.min(100, p.hp / stats.maxHp * 100))}%`;
  hud.hpText.textContent = `${Math.ceil(p.hp)} / ${stats.maxHp} · ${p.name}`;
  hud.mp.style.width = `${Math.max(0, Math.min(100, p.mp / stats.maxMp * 100))}%`;
  hud.mpText.textContent = `${Math.ceil(p.mp)} / ${stats.maxMp} · K ${p.skillCooldown > 0 ? p.skillCooldown.toFixed(1) + "s" : "就绪"} · O ${p.skill2Cooldown > 0 ? p.skill2Cooldown.toFixed(1) + "s" : "就绪"}`;
  hud.gold.textContent = run.gold;
  hud.level.textContent = `${p.level} (${p.xp || 0}xp)`;
  hud.floor.textContent = run.floorIndex + 1;
  hud.room.textContent = `${run.roomIndex + 1}/${floor.rooms.length}`;
  hud.potions.textContent = run.potions;
  hud.difficulty.textContent = DIFFICULTIES[run.difficulty - 1].name;
  const prog = chapterProgress(run);
  hud.objective.textContent = roomCleared()
    ? (run.roomIndex + 1 === floor.rooms.length ? "Boss 已清空，向右门前进" : "房间完成，向右门前进")
    : `剩余敌人 ${enemies.length}${room.interactable && !interactableDone ? " · 房间事件待处理" : ""} · 总进度 ${prog.percent}%`;
  hud.loot.innerHTML = (run.lootLog || []).slice(-3).reverse().map((item) =>
    `<div class="loot-row"><span class="dot" style="background:${QUALITIES.find((q) => q.id === item.quality)?.color}"></span>${esc(item.name)}</div>`).join("");
  if (run.players[1]) {
    const p2 = run.players[1];
    const s2 = derivedStats(p2);
    hud.p2.classList.remove("hidden");
    hud.p2hp.style.width = `${Math.max(0, p2.hp / s2.maxHp * 100)}%`;
    hud.p2mp.style.width = `${Math.max(0, p2.mp / s2.maxMp * 100)}%`;
    hud.p2Text.textContent = `P2 ${p2.name} ${Math.ceil(p2.hp)}/${s2.maxHp}${p2.downed ? " 倒地" : ""}`;
    hud.p2MpText.textContent = `MP ${Math.ceil(p2.mp)}/${s2.maxMp}`;
  } else hud.p2.classList.add("hidden");
  if (boss) {
    hud.boss.classList.remove("hidden");
    hud.bossName.textContent = boss.name;
    hud.bossPhase.textContent = `P${boss.phase}`;
    hud.bossFill.style.width = `${Math.max(0, boss.hp / boss.maxHp * 100)}%`;
  } else hud.boss.classList.add("hidden");
  let hint = "";
  if (room && room.door && !room.door.locked && near(room.door.x, 540, 70)) hint = "E 进入下一房间";
  else if (room?.interactable && !interactableDone && near(980, 540, 90)) {
    hint = room.interactable === "chest" ? "E 打开宝箱" : room.interactable === "merchant"
      ? "E 与商人交易" : room.interactable === "campfire" ? "E 在篝火休息" : "E 查看事件";
  } else if (run.players.some((p) => p.downed && near(p.x, p.y, 70))) hint = "E 扶起队友";
  hud.hint.textContent = hint;
  hud.hint.classList.toggle("show", Boolean(hint));
  drawMinimap();
}

function drawMinimap() {
  mctx.clearRect(0, 0, minimap.width, minimap.height);
  mctx.fillStyle = "rgba(5,8,15,.65)";
  mctx.fillRect(0, 0, minimap.width, minimap.height);
  const rooms = floor.rooms;
  const cols = 4;
  rooms.forEach((r, i) => {
    const x = 10 + (i % cols) * 54;
    const y = 12 + Math.floor(i / cols) * 34;
    const current = i === run.roomIndex;
    const color = r.type === "boss" ? "#f97316" : r.type === "campfire" ? "#22c55e"
      : r.type === "shop" ? "#3b82f6" : r.type === "elite" ? "#a855f7" : "#64748b";
    mctx.fillStyle = current ? "#f8fafc" : color;
    mctx.fillRect(x, y, 44, 22);
    if (run.cleared[`${run.floorIndex + 1}-${i}`]) {
      mctx.fillStyle = "rgba(0,0,0,.45)";
      mctx.fillRect(x, y, 44, 22);
    }
    mctx.strokeStyle = current ? "#f8fafc" : "rgba(255,255,255,.18)";
    mctx.strokeRect(x, y, 44, 22);
  });
  mctx.fillStyle = "#94a3b8";
  mctx.font = "10px system-ui";
  mctx.fillText(`第 ${run.floorIndex + 1} 层 / 共 5 层`, 10, minimap.height - 8);
}

function rounded(x, y, w, h, r, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
}

function render() {
  ctx.save();
  if (shake > 0) ctx.translate((Math.random() - 0.5) * shake, (Math.random() - 0.5) * shake);
  const bg = ctx.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, room?.type === "boss" ? "#221022" : ["#0d1424", "#17130d", "#111a16", "#0d1524", "#20121a"][run?.floorIndex || 0]);
  bg.addColorStop(1, "#05070d");
  ctx.fillStyle = bg;
  ctx.fillRect(-20, -20, W + 40, H + 40);
  if (!room) { ctx.restore(); return; }
  for (let i = 0; i < 8; i += 1) {
    ctx.fillStyle = i % 2 ? "rgba(255,255,255,.018)" : "rgba(255,255,255,.035)";
    ctx.fillRect(i * 160, 0, 80, H);
  }
  // Torches/decor
  for (let i = 0; i < 4; i += 1) {
    const x = 160 + i * 320;
    ctx.fillStyle = "#f59e0b";
    ctx.beginPath(); ctx.arc(x, 190 + (i % 2) * 30, 5 + Math.sin(performance.now() / 300 + i) * 2, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "rgba(245,158,11,.18)";
    ctx.beginPath(); ctx.arc(x, 190 + (i % 2) * 30, 18, 0, Math.PI * 2); ctx.fill();
  }
  platformsForRoom().forEach((platform) => {
    rounded(platform.x, platform.y, platform.w, platform.h, 3, platform.x === 0 ? "#23324a" : "#31425f");
    ctx.fillStyle = "rgba(255,255,255,.12)";
    ctx.fillRect(platform.x, platform.y, platform.w, 2);
  });
  // interactables
  if (room.interactable && !interactableDone) {
    const y = 540;
    if (room.interactable === "chest") {
      rounded(950, 520, 60, 40, 6, "#b45309");
      ctx.fillStyle = "#fde68a"; ctx.fillRect(968, 532, 24, 6);
    } else if (room.interactable === "merchant") {
      rounded(960, 500, 40, 60, 8, "#334155");
      ctx.fillStyle = "#93c5fd"; ctx.beginPath(); ctx.arc(980, 488, 14, 0, Math.PI * 2); ctx.fill();
    } else if (room.interactable === "campfire") {
      ctx.fillStyle = "#f97316"; ctx.beginPath(); ctx.arc(980, 540, 18 + Math.sin(performance.now() / 150) * 3, 0, Math.PI * 2); ctx.fill();
    } else {
      rounded(958, 500, 44, 48, 6, "#6d28d9");
      ctx.fillStyle = "#ddd6fe"; ctx.font = "18px system-ui"; ctx.fillText("?", 972, 532);
    }
  }
  const door = room.door;
  rounded(door.x, door.y, door.w, door.h, 6, room.door.locked ? "#7f1d1d" : "#166534");
  ctx.fillStyle = room.door.locked ? "#fca5a5" : "#86efac";
  ctx.font = "bold 15px system-ui";
  ctx.fillText(room.door.locked ? "LOCK" : "OPEN", door.x + 6, door.y + 70);
  // ground loot
  ground.forEach((g) => {
    ctx.save(); ctx.translate(g.x, g.y - 20 + Math.sin(g.bob) * 4); ctx.rotate(Math.PI / 4);
    ctx.fillStyle = QUALITIES.find((q) => q.id === g.item.quality)?.color || "#fff";
    ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = 14; ctx.fillRect(-9, -9, 18, 18); ctx.restore();
  });
  // enemies
  enemies.forEach((e) => {
    const color = e.hit > 0 ? "#fff" : e.color;
    ctx.fillStyle = color;
    ctx.beginPath(); ctx.roundRect(e.x - e.w / 2, e.y - e.h, e.w, e.h, 7); ctx.fill();
    ctx.fillStyle = "#111827";
    ctx.fillRect(e.x - 10, e.y - e.h + 14, 6, 6);
    ctx.fillRect(e.x + 4, e.y - e.h + 14, 6, 6);
    if (e.boss) { ctx.fillStyle = "#fde68a"; ctx.font = "bold 12px system-ui"; ctx.fillText("BOSS", e.x - 22, e.y - e.h - 10); }
    if (e.affix) { ctx.fillStyle = "#c084fc"; ctx.font = "10px system-ui"; ctx.fillText(e.affix, e.x - 18, e.y - e.h - 22); }
    const w = e.boss ? 100 : 50;
    ctx.fillStyle = "rgba(0,0,0,.55)"; ctx.fillRect(e.x - w / 2, e.y - e.h - 12, w, 5);
    ctx.fillStyle = "#ef4444"; ctx.fillRect(e.x - w / 2, e.y - e.h - 12, w * Math.max(0, e.hp / e.maxHp), 5);
  });
  // players
  run.players.forEach((p) => {
    if (p.downed) {
      ctx.fillStyle = "#64748b"; ctx.fillRect(p.x - 20, p.y - 18, 40, 16);
      ctx.fillStyle = "#cbd5e1"; ctx.font = "11px system-ui"; ctx.fillText("倒地 E", p.x - 20, p.y - 24);
      return;
    }
    ctx.fillStyle = p.hitTimer > 0 ? "#fff" : p.color;
    ctx.beginPath(); ctx.roundRect(p.x - p.w / 2, p.y - p.h, p.w, p.h, 8); ctx.fill();
    ctx.fillStyle = "#0b1020"; ctx.fillRect(p.x + (p.id === 1 ? 7 : 3), p.y - p.h + 16, 5, 5);
    ctx.fillStyle = "rgba(255,255,255,.85)"; ctx.font = "bold 11px system-ui"; ctx.fillText(`P${p.id}`, p.x - 8, p.y - p.h - 8);
    if (p.invuln > 0) { ctx.globalAlpha = .5; ctx.strokeStyle = "#93c5fd"; ctx.strokeRect(p.x - p.w / 2 - 4, p.y - p.h - 4, p.w + 8, p.h + 8); ctx.globalAlpha = 1; }
  });
  // projectiles
  projectiles.forEach((p) => {
    ctx.fillStyle = p.color; ctx.beginPath(); ctx.arc(p.x, p.y, 6, 0, Math.PI * 2); ctx.fill();
  });
  // effects
  effects.forEach((e) => {
    const alpha = Math.max(0, Math.min(1, e.life * 3));
    ctx.globalAlpha = alpha;
    if (e.arc) {
      ctx.strokeStyle = e.color; ctx.lineWidth = 4; ctx.beginPath();
      const start = playerFacingAngle();
      ctx.arc(e.x, e.y, e.radius * .7, -0.8, 0.8); ctx.stroke();
    } else if (e.skill) {
      ctx.strokeStyle = e.color; ctx.lineWidth = 3; ctx.beginPath();
      ctx.arc(e.x, e.y, e.radius * (1 - e.life), 0, Math.PI * 2); ctx.stroke();
    } else if (e.dodge) {
      ctx.fillStyle = e.color; ctx.globalAlpha = alpha * .35; ctx.fillRect(e.x - 20, e.y - 40, 40, 50);
    } else {
      ctx.fillStyle = e.color; ctx.font = "bold 18px system-ui"; ctx.fillText(e.text || "", e.x - 12, e.y - (1 - e.life) * 30);
    }
    ctx.globalAlpha = 1;
  });
  ctx.fillStyle = "rgba(255,255,255,.45)"; ctx.font = "13px system-ui";
  ctx.fillText("P1 A/D Space J/U K/O L/E Shift | P2 ←/→ ↑ / M . ? , Enter | I 背包 · Q 任务 · Esc 暂停", 24, H - 16);
  ctx.restore();
}

function playerFacingAngle() {
  return run.players[0]?.facing > 0 ? 0 : Math.PI;
}

function loop(now) {
  const raw = Math.min(0.033, (now - (lastTime || now)) / 1000);
  lastTime = now;
  if (mode === "playing" && !paused) {
    const dt = hitStop > 0 ? raw * 0.15 : raw;
    hitStop = Math.max(0, hitStop - raw);
    run.players.forEach((p, i) => stepPlayer(p, i, dt));
    stepRevives(dt);
    stepEnemies(dt);
    stepProjectiles(dt);
    stepGround(dt);
    effects.forEach((e) => { e.life -= dt; });
    effects = effects.filter((e) => e.life > 0);
    if (shake > 0) shake = Math.max(0, shake - dt * 28);
    if (messageTimer > 0) {
      messageTimer -= dt;
      if (messageTimer <= 0) hud.message.classList.remove("show");
    }
    updateHud();
  }
  render();
  requestAnimationFrame(loop);
}

function handleAction(code) {
  if (!run || mode !== "playing") return;
  const p1 = run.players[0];
  const p2 = run.players[1];
  if (code === "KeyJ") attack(p1, false);
  if (code === "KeyU") attack(p1, true);
  if (code === "KeyK") skill(p1, 1);
  if (code === "KeyO") skill(p1, 2);
  if (code === "KeyL") usePotion(p1);
  if (code === "ShiftLeft") dodge(p1);
  if (code === "KeyE") interact();
  if (p2) {
    if (code === "Slash") attack(p2, false);
    if (code === "KeyM") attack(p2, true);
    if (code === "Period") skill(p2, 1);
    if (code === "QuestionMark") skill(p2, 2);
    if (code === "Comma") usePotion(p2);
    if (code === "ControlRight") dodge(p2);
    if (code === "Enter") interact();
  }
}

window.addEventListener("keydown", (event) => {
  if (["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.code)) event.preventDefault();
  if (!keys.has(event.code) && !event.repeat) handleAction(event.code);
  keys.add(event.code);
  if (event.code === "KeyI" && mode === "playing") { event.preventDefault(); openInventory(); }
  if (event.code === "KeyQ" && mode === "playing") { event.preventDefault(); openQuests(); }
  if (event.code === "Escape") {
    event.preventDefault();
    if (mode === "panel") closePanel();
    else if (mode === "playing") { paused = true; openPanel("pause", "暂停", renderPause()); }
  }
  if (event.code === "F5") { event.preventDefault(); if (run) saveSlot(currentSlot); }
  if (event.code === "F9") { event.preventDefault(); if (run) loadSlot(currentSlot); }
  if (event.code === "KeyR") location.reload();
});
window.addEventListener("keyup", (event) => keys.delete(event.code));
window.addEventListener("blur", () => keys.clear());

window.__AGENTTEAM_GAME__ = {
  startGame,
  loadSlot,
  get run() { return run; },
  get room() { return room; },
  get enemies() { return enemies; },
  get floor() { return floor; },
  attack: (index = 0, heavy = false) => attack(run.players[index], heavy),
  skill: (index = 0, slot = 1) => skill(run.players[index], slot),
  interact,
  step: (dt) => {
    run.players.forEach((p, i) => stepPlayer(p, i, dt));
    stepEnemies(dt); stepProjectiles(dt); stepGround(dt);
    updateHud();
  },
  save: (slot = currentSlot) => saveSlot(slot),
  load: (slot = currentSlot) => loadSlot(slot),
};

setSelected("swordsman");
setDifficulty(2);
coop = false;
renderSaveSlots();
const params = new URLSearchParams(location.search);
if (params.get("play") && CLASSES[params.get("play")]) {
  startGame(params.get("play"), params.get("coop") === "1", Number(params.get("difficulty") || 2));
}
requestAnimationFrame(loop);
