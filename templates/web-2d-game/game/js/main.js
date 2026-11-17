import {
  CLASSES, QUALITIES, createRun, mulberry32, rollLoot,
  roomCleared, encodeSave, decodeSave, snapshot,
} from "./core.js";

const W = 1280;
const H = 720;
const FLOOR = 600;
const SAVE_KEY = "agentteam-maze-adventurer-save";

const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");
const menu = document.getElementById("menu");
const classCards = [...document.querySelectorAll(".class-card")];
const coopBox = document.getElementById("coop");
const startBtn = document.getElementById("start");
const hud = {
  hp: document.getElementById("hp-fill"),
  hpText: document.getElementById("hp-text"),
  p2: document.getElementById("p2-hud"),
  p2hp: document.getElementById("p2-fill"),
  p2Text: document.getElementById("p2-text"),
  gold: document.getElementById("gold"),
  room: document.getElementById("room"),
  objective: document.getElementById("objective"),
  message: document.getElementById("message"),
  loot: document.getElementById("loot-log"),
};

const keys = new Set();
let selectedClass = "swordsman";
let mode = "menu";
let run = null;
let room = null;
let enemies = [];
let loot = [];
let effects = [];
let rand = null;
let lastTime = 0;
let message = "";
let messageTimer = 0;

function showMessage(text, seconds = 3) {
  message = text;
  messageTimer = seconds;
  hud.message.textContent = text;
  hud.message.classList.add("show");
}

function setSelected(classId) {
  selectedClass = classId;
  classCards.forEach((card) => {
    card.classList.toggle("selected", card.dataset.class === classId);
  });
}

classCards.forEach((card) => card.addEventListener("click", () => setSelected(card.dataset.class)));
startBtn.addEventListener("click", () => startGame(selectedClass, coopBox.checked));

function startGame(classId = selectedClass, coop = false) {
  run = createRun(classId, coop, (Date.now() ^ 0x5f3759df) >>> 0);
  run.startedAt = performance.now();
  rand = mulberry32(run.seed);
  enemies = [];
  loot = [];
  effects = [];
  mode = "playing";
  menu.classList.add("hidden");
  loadRoom(0);
  showMessage("房间已生成：清空敌人后，右侧的门会打开。", 4);
}

function playerAt(index) {
  return run.players[index] || null;
}

function loadRoom(index) {
  run.roomIndex = Math.min(index, run.dungeon.length - 1);
  room = run.dungeon[run.roomIndex];
  const remaining = room.enemies.filter((e) => !run.defeated.includes(e.id));
  enemies = remaining.map((spec) => ({
    ...spec,
    maxHp: spec.hp,
    x: spec.x,
    y: 540,
    w: spec.boss ? 88 : spec.kind === "elite" ? 54 : 42,
    h: spec.boss ? 104 : 54,
    vx: 0,
    vy: 0,
    onGround: false,
    hit: 0,
    atkCd: 0,
  }));
  loot = [];
  effects = [];
  run.players.forEach((p, i) => {
    p.x = 80 + i * 58;
    p.y = 500;
    p.vx = 0;
    p.vy = 0;
    p.cooldown = 0;
    p.hitTimer = 0;
  });
  showMessage(`${room.name} · ${room.boss ? "BOSS 房" : "清空房间后开门"}`, 2.8);
  updateHud();
}

function platformsForCurrentRoom() {
  return [{ x: 0, y: FLOOR, w: W, h: 120 }, ...room.platforms];
}

function aabb(a, b) {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

function resolvePlatforms(body, dt) {
  body.vy += 1800 * dt;
  body.x += body.vx * dt;
  body.y += body.vy * dt;
  body.onGround = false;
  for (const platform of platformsForCurrentRoom()) {
    const box = { x: body.x - body.w / 2, y: body.y - body.h, w: body.w, h: body.h };
    if (!aabb(box, platform)) continue;
    if (body.vy >= 0 && box.y + box.h - platform.y < 28) {
      body.y = platform.y;
      body.vy = 0;
      body.onGround = true;
    }
  }
  body.x = Math.max(40, Math.min(W - 40, body.x));
  if (body.y > H + 200) {
    body.x = 90;
    body.y = 500;
    body.vy = 0;
    body.hp = Math.max(1, body.hp - 8);
  }
}

function inputFor(index) {
  if (index === 0) {
    return {
      left: keys.has("KeyA"), right: keys.has("KeyD"),
      jump: keys.has("KeyW") || keys.has("Space"), attack: keys.has("KeyJ"),
    };
  }
  return {
    left: keys.has("ArrowLeft"), right: keys.has("ArrowRight"),
    jump: keys.has("ArrowUp"), attack: keys.has("KeyK"),
  };
}

function stepPlayer(p, index, dt) {
  const input = inputFor(index);
  const dir = (input.right ? 1 : 0) - (input.left ? 1 : 0);
  p.vx = dir * p.speed;
  if (input.jump && p.onGround) {
    p.vy = -p.jump;
    p.onGround = false;
  }
  resolvePlatforms(p, dt);
  p.cooldown = Math.max(0, p.cooldown - dt);
  p.hitTimer = Math.max(0, p.hitTimer - dt);
  if (input.attack && p.cooldown <= 0) attack(p);
}

function attack(player) {
  player.cooldown = 0.38;
  let hits = 0;
  enemies.forEach((enemy) => {
    const dx = Math.abs(enemy.x - player.x);
    const dy = Math.abs(enemy.y - player.y);
    if (dx <= player.range && dy <= 90) {
      enemy.hp -= player.damage;
      enemy.hit = 0.12;
      hits += 1;
      effects.push({ x: enemy.x, y: enemy.y - 40, life: 0.2, color: player.color, text: `-${player.damage}` });
    }
  });
  if (hits) showMessage(`${player.name} 命中 ${hits} 个敌人`, 0.8);
}

function dropLoot(enemy) {
  const item = rollLoot(rand);
  loot.push({
    ...item,
    x: enemy.x,
    y: enemy.y - 18,
    vy: -120,
    life: 18,
    bob: 0,
  });
  run.lootLog.push(item);
  if (run.lootLog.length > 40) run.lootLog.shift();
}

function stepEnemies(dt) {
  const alivePlayers = run.players.filter((p) => p.hp > 0);
  if (!alivePlayers.length) return;
  enemies.forEach((enemy) => {
    const target = alivePlayers.reduce((best, p) =>
      Math.abs(p.x - enemy.x) < Math.abs(best.x - enemy.x) ? p : best, alivePlayers[0]);
    const dx = target.x - enemy.x;
    enemy.vx = Math.abs(dx) > 34 ? Math.sign(dx) * enemy.speed : 0;
    resolvePlatforms(enemy, dt);
    enemy.hit = Math.max(0, enemy.hit - dt);
    enemy.atkCd = Math.max(0, enemy.atkCd - dt);
    if (Math.abs(target.x - enemy.x) < 42 && Math.abs(target.y - enemy.y) < 70 && enemy.atkCd <= 0) {
      enemy.atkCd = 1.1;
      target.hp = Math.max(0, target.hp - enemy.damage);
      target.hitTimer = 0.18;
      effects.push({ x: target.x, y: target.y - 50, life: 0.35, color: "#ef4444", text: `-${enemy.damage}` });
      if (target.hp <= 0) {
        target.hp = target.maxHp;
        target.x = 90;
        target.y = 500;
        run.gold = Math.max(0, run.gold - 5);
        showMessage(`${target.name} 倒下了，损失 5 金币并回到入口`, 3);
      }
    }
  });
  const before = enemies.length;
  enemies = enemies.filter((enemy) => {
    if (enemy.hp > 0) return true;
    run.defeated.push(enemy.id);
    dropLoot(enemy);
    effects.push({ x: enemy.x, y: enemy.y - 60, life: 0.5, color: "#facc15", text: "击破!" });
    return false;
  });
  if (enemies.length !== before) {
    if (roomCleared(room, run.defeated)) {
      room.door.locked = false;
      showMessage(room.boss ? "Boss 已击败，出口已开启" : "房间已清空，右侧门已开启", 3);
    }
  }
}

function stepLoot(dt) {
  loot.forEach((item) => {
    item.vy += 900 * dt;
    item.y += item.vy * dt;
    if (item.y > FLOOR - 14) {
      item.y = FLOOR - 14;
      item.vy = 0;
    }
    item.life -= dt;
    item.bob += dt * 4;
  });
  loot = loot.filter((item) => {
    if (item.life <= 0) return false;
    for (const p of run.players) {
      if (Math.abs(p.x - item.x) < 38 && Math.abs(p.y - item.y) < 70) {
        run.gold += item.gold;
        showMessage(`拾取 ${item.name} · +${item.gold} 金币`, 2.4);
        effects.push({ x: item.x, y: item.y - 20, life: 0.6, color: item.color, text: `+${item.gold}` });
        return false;
      }
    }
    return true;
  });
}

function checkDoor() {
  if (!room || !roomCleared(room, run.defeated)) return;
  room.door.locked = false;
  const reached = run.players.some((p) => p.x > room.door.x - 28);
  if (!reached) return;
  if (run.roomIndex >= run.dungeon.length - 1) {
    run.victory = true;
    mode = "victory";
    menu.classList.remove("hidden");
    menu.innerHTML = `<div class="victory">
      <p class="eyebrow">DEMO CLEAR</p>
      <h1>第一章切片通关</h1>
      <p>你完成了 4 个房间、3 类职业和本地双人验证。</p>
      <button id="again">再玩一次</button>
    </div>`;
    const again = document.getElementById("again");
    if (again) again.addEventListener("click", () => location.reload());
  } else {
    loadRoom(run.roomIndex + 1);
  }
}

function step(dt) {
  if (mode !== "playing") return;
  run.players.forEach((p, i) => stepPlayer(p, i, dt));
  stepEnemies(dt);
  stepLoot(dt);
  checkDoor();
  effects.forEach((e) => { e.life -= dt; });
  effects = effects.filter((e) => e.life > 0);
  if (messageTimer > 0) {
    messageTimer -= dt;
    if (messageTimer <= 0) hud.message.classList.remove("show");
  }
  updateHud();
}

function updateHud() {
  if (!run) return;
  const p = run.players[0];
  hud.hp.style.width = `${Math.max(0, p.hp / p.maxHp) * 100}%`;
  hud.hpText.textContent = `${Math.ceil(p.hp)} / ${p.maxHp} · ${p.name}`;
  hud.gold.textContent = `${run.gold}`;
  hud.room.textContent = `${run.roomIndex + 1}/${run.dungeon.length}`;
  hud.objective.textContent = roomCleared(room, run.defeated)
    ? (run.roomIndex === run.dungeon.length - 1 ? "Boss 已击破，向右离开" : "房间已清空，向右开门")
    : `剩余敌人 ${enemies.length}`;
  if (run.players[1]) {
    const p2 = run.players[1];
    hud.p2.classList.remove("hidden");
    hud.p2hp.style.width = `${Math.max(0, p2.hp / p2.maxHp) * 100}%`;
    hud.p2Text.textContent = `P2 ${p2.name} ${Math.ceil(p2.hp)}/${p2.maxHp}`;
  } else {
    hud.p2.classList.add("hidden");
  }
  const recent = run.lootLog.slice(-3).reverse();
  hud.loot.innerHTML = recent.map((item) =>
    `<div class="loot-row"><span class="dot" style="background:${item.color}"></span>${item.name} <b>+${item.gold}</b></div>`).join("");
}

function rounded(x, y, w, h, r, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
}

function render() {
  const gradient = ctx.createLinearGradient(0, 0, 0, H);
  gradient.addColorStop(0, room && room.boss ? "#1c1028" : "#0d1424");
  gradient.addColorStop(1, "#05070d");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, W, H);
  if (!room) return;

  for (let i = 0; i < 4; i += 1) {
    ctx.fillStyle = i % 2 ? "rgba(255,255,255,.018)" : "rgba(255,255,255,.035)";
    ctx.fillRect(i * 320, 0, 160, H);
  }
  platformsForCurrentRoom().forEach((platform) => {
    rounded(platform.x, platform.y, platform.w, platform.h, 3, platform.x === 0 ? "#23324a" : "#31425f");
    ctx.fillStyle = "rgba(255,255,255,.12)";
    ctx.fillRect(platform.x, platform.y, platform.w, 2);
  });

  // Door
  const door = room.door;
  rounded(door.x, door.y, door.w, door.h, 6, room.door.locked ? "#7f1d1d" : "#166534");
  ctx.fillStyle = room.door.locked ? "#fca5a5" : "#86efac";
  ctx.font = "bold 16px system-ui";
  ctx.fillText(room.door.locked ? "LOCK" : "OPEN", door.x + 7, door.y + 70);

  // Loot
  loot.forEach((item) => {
    const y = item.y + Math.sin(item.bob) * 4;
    ctx.save();
    ctx.translate(item.x, y - 18);
    ctx.rotate(Math.PI / 4);
    ctx.fillStyle = item.color;
    ctx.shadowColor = item.color;
    ctx.shadowBlur = 14;
    ctx.fillRect(-10, -10, 20, 20);
    ctx.restore();
  });

  // Enemies
  enemies.forEach((enemy) => {
    const color = enemy.boss ? "#f97316" : enemy.kind === "elite" ? "#a855f7" : "#ef4444";
    ctx.fillStyle = enemy.hit > 0 ? "#fff" : color;
    ctx.beginPath();
    ctx.roundRect(enemy.x - enemy.w / 2, enemy.y - enemy.h, enemy.w, enemy.h, 7);
    ctx.fill();
    ctx.fillStyle = "#111827";
    ctx.fillRect(enemy.x - 10, enemy.y - enemy.h + 14, 6, 6);
    ctx.fillRect(enemy.x + 4, enemy.y - enemy.h + 14, 6, 6);
    if (enemy.boss) {
      ctx.fillStyle = "#fde68a";
      ctx.fillText("BOSS", enemy.x - 22, enemy.y - enemy.h - 18);
    }
    const hpW = 54;
    ctx.fillStyle = "rgba(0,0,0,.55)";
    ctx.fillRect(enemy.x - hpW / 2, enemy.y - enemy.h - 12, hpW, 5);
    ctx.fillStyle = "#ef4444";
    ctx.fillRect(enemy.x - hpW / 2, enemy.y - enemy.h - 12, hpW * Math.max(0, enemy.hp / enemy.maxHp), 5);
  });

  // Players
  run.players.forEach((p) => {
    ctx.fillStyle = p.hitTimer > 0 ? "#ffffff" : p.color;
    ctx.beginPath();
    ctx.roundRect(p.x - p.w / 2, p.y - p.h, p.w, p.h, 8);
    ctx.fill();
    ctx.fillStyle = "#0b1020";
    ctx.fillRect(p.x + (p.id === 1 ? 7 : 3), p.y - p.h + 16, 5, 5);
    ctx.fillStyle = "rgba(255,255,255,.85)";
    ctx.font = "bold 12px system-ui";
    ctx.fillText(`P${p.id}`, p.x - 8, p.y - p.h - 8);
  });

  effects.forEach((e) => {
    ctx.globalAlpha = Math.max(0, Math.min(1, e.life * 2.5));
    ctx.fillStyle = e.color;
    ctx.font = "bold 20px system-ui";
    ctx.fillText(e.text, e.x - 12, e.y - (1 - e.life) * 36);
    ctx.globalAlpha = 1;
  });

  ctx.fillStyle = "rgba(255,255,255,.45)";
  ctx.font = "14px system-ui";
  ctx.fillText("WASD/方向键移动 · Space/↑ 跳跃 · J/K 攻击 · F5 存档 · F9 读档 · R 重开", 24, H - 18);
}

function loop(now) {
  const dt = Math.min(0.033, (now - (lastTime || now)) / 1000);
  lastTime = now;
  step(dt);
  render();
  requestAnimationFrame(loop);
}

function saveGame() {
  if (!run) return;
  localStorage.setItem(SAVE_KEY, encodeSave(snapshot(run)));
  showMessage("已存档（localStorage，带 CRC 校验）", 2.2);
}

function loadGame() {
  const raw = localStorage.getItem(SAVE_KEY);
  const data = decodeSave(raw);
  if (!data) {
    showMessage("没有可用存档，或 CRC 校验失败", 2.5);
    return;
  }
  run = createRun(data.players[0]?.classId || "swordsman", data.players.length > 1, data.seed);
  run.gold = data.gold || 0;
  run.defeated = data.defeated || [];
  run.lootLog = data.lootLog || [];
  run.players.forEach((p, i) => {
    const saved = data.players[i];
    if (!saved) return;
    p.hp = saved.hp;
    p.x = saved.x;
    p.y = saved.y;
  });
  mode = "playing";
  menu.classList.add("hidden");
  loadRoom(data.roomIndex || 0);
  showMessage("已读档", 2.2);
}

window.addEventListener("keydown", (event) => {
  if (["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.code)) event.preventDefault();
  keys.add(event.code);
  if (event.code === "F5") { event.preventDefault(); saveGame(); }
  if (event.code === "F9") { event.preventDefault(); loadGame(); }
  if (event.code === "KeyR" && mode === "playing") location.reload();
  if (mode === "menu") {
    if (event.code === "Digit1") startGame("swordsman", coopBox.checked);
    if (event.code === "Digit2") startGame("mage", coopBox.checked);
    if (event.code === "Digit3") startGame("ranger", coopBox.checked);
    if (event.code === "Enter") startGame(selectedClass, coopBox.checked);
  }
});
window.addEventListener("keyup", (event) => keys.delete(event.code));
window.addEventListener("blur", () => keys.clear());

window.__AGENTTEAM_GAME__ = {
  startGame,
  get run() { return run; },
  get enemies() { return enemies; },
  get room() { return room; },
  step: (dt) => step(dt),
  attack: (index = 0) => attack(run.players[index]),
  saveGame,
  loadGame,
};

setSelected("swordsman");
const bootParams = new URLSearchParams(location.search);
if (bootParams.get("play") && CLASSES[bootParams.get("play")]) {
  startGame(bootParams.get("play"), bootParams.get("coop") === "1");
}
requestAnimationFrame(loop);
