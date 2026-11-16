import React, { useEffect, useRef } from 'react';
import './HUD.css';

// Types for HUD data structure
interface PlayerStats {
  hp: number;
  maxHp: number;
  mp: number;
  maxMp: number;
  gold: number;
  skills: { id: string; name: string; cd: number; maxCd: number }[];
}

interface TeammateStats {
  playerId: string;
  hp: number;
  maxHp: number;
  isAlive: boolean;
}

interface HUDProps {
  player: PlayerStats;
  teammates?: TeammateStats[];
  miniMapData?: { currentRoom: string; exploredRooms: string[]; bossRoomUnlocked: boolean };
  isVisible: boolean;
  onInteract?: () => void; // Triggered by Enter/Space for context interaction
}

const HUD: React.FC<HUDProps> = ({ 
  player, 
  teammates = [], 
  miniMapData, 
  isVisible,
  onInteract 
}) => {
  const interactTimerRef = useRef<number | null>(null);

  // Handle context interaction (e.g., interacting with campfire or door)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isVisible) return;
      if (e.key === 'Enter' || e.key === ' ') {
        onInteract?.();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isVisible, onInteract]);

  if (!isVisible) return null;

  // Helper to calculate percentage for bars
  const getPercent = (current: number, max: number) => 
    Math.max(0, Math.min(100, (current / max) * 100));

  return (
    <div className="hud-container">
      {/* Top Left: Player Stats */}
      <div className="hud-player-stats">
        <div className="stat-bar hp-bar">
          <div 
            className="bar-fill hp-fill" 
            style={{ width: `${getPercent(player.hp, player.maxHp)}%` }}
          />
          <span className="bar-text">{player.hp} / {player.maxHp}</span>
        </div>
        <div className="stat-bar mp-bar">
          <div 
            className="bar-fill mp-fill" 
            style={{ width: `${getPercent(player.mp, player.maxMp)}%` }}
          />
          <span className="bar-text">{player.mp} / {player.maxMp}</span>
        </div>
        <div className="stat-gold">
          <span className="icon gold-icon">●</span>
          <span>{player.gold.toLocaleString()}</span>
        </div>
      </div>

      {/* Top Center: Mini Map */}
      {miniMapData && (
        <div className="hud-minimap">
          <div className="minimap-room current">
            <span className="room-icon">★</span>
          </div>
          {miniMapData.exploredRooms.map((roomId, idx) => (
            <div key={idx} className="minimap-room explored">
              <span className="room-icon">·</span>
            </div>
          ))}
          {miniMapData.bossRoomUnlocked && (
            <div className="minimap-room boss">
              <span className="room-icon">☠</span>
            </div>
          )}
        </div>
      )}

      {/* Top Right: Teammates (Local Co-op) */}
      {teammates.length > 0 && (
        <div className="hud-teammates">
          {teammates.map((tm) => (
            <div key={tm.playerId} className={`teammate-card ${!tm.isAlive ? 'dead' : ''}`}>
              <div className="teammate-hp-bar">
                <div 
                  className="bar-fill hp-fill" 
                  style={{ width: `${getPercent(tm.hp, tm.maxHp)}%` }}
                />
              </div>
              <span className="teammate-label">P{tm.playerId}</span>
            </div>
          ))}
        </div>
      )}

      {/* Bottom Center: Skills & Interact Prompt */}
      <div className="hud-skills">
        {player.skills.map((skill) => (
          <div key={skill.id} className="skill-slot">
            <div className="skill-icon" title={skill.name}>
              {skill.cd > 0 ? skill.cd : '✓'}
            </div>
            <div className="skill-cd-overlay" style={{ 
              height: `${(skill.cd / skill.maxCd) * 100}%` 
            }} />
          </div>
        ))}
      </div>

      {/* Bottom Left: Context Prompt */}
      <div className="hud-context-prompt">
        <span className="prompt-key">[E]</span>
        <span className="prompt-text">交互</span>
      </div>
    </div>
  );
};

export default HUD;