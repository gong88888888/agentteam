// Minimal deterministic enemy AI contract.
export function stepAI(actor, { playerX = 0, dt = 0.016 } = {}) {
  const distance = Math.abs(playerX - actor.x);
  if (distance < 48) actor.state = "attack";
  else if (distance < 420) actor.state = "chase";
  else actor.state = "patrol";
  actor.dt = dt;
  return actor;
}
