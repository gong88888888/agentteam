/**
 * Game Core Module
 * Handles Hit Stop, Screen Shake, Loot Generation, and Save System.
 * MVP Scope: Chapter 1 Logic, Local Co-op State, Equipment Weighted Drop.
 */

// ==========================================
// 1. CONFIGURATION & CONSTANTS (Section 7.2)
// ==========================================
const GAME_CONFIG = {
    EQUIPMENT_QUALITY: {
        WHITE: { id: 'white', weight: 40, color: '#ffffff', name: 'Common' },
        GREEN: { id: 'green', weight: 30, color: '#2ecc71', name: 'Uncommon' },
        BLUE:  { id: 'blue',  weight: 20, color: '#3498db', name: 'Rare' },
        PURPLE:{ id: 'purple',weight: 8,  color: '#9b59b6', name: 'Epic' },
        ORANGE:{ id: 'orange',weight: 2,  color: '#e67e22', name: 'Legendary' }
    },
    HIT_STOP_DURATION: 80, // ms (Section 6.4)
    SCREEN_SHAKE_INTENSITY: 5,
    SAVE_BACKUPS: 2,
    MAX_INVENTORY_SLOTS: 60,
    MAX_WAREHOUSE_SLOTS: 200
};

// ==========================================
// 2. BATTLE FEEDBACK SYSTEM (Section 6.4)
// ==========================================
class FeedbackSystem {
    constructor() {
        this.shakeOffset = { x: 0, y: 0 };
        this.isHitStopping = false;
        this.hitStopTimer = null;
        this.shakeIntensity = 0;
    }

    /**
     * Triggers hit stop (freeze frame) and screen shake.
     * @param {number} duration - Duration in ms
     */
    triggerHitStop(duration = GAME_CONFIG.HIT_STOP_DURATION) {
        if (this.isHitStopping) return;
        
        this.isHitStopping = true;
        
        // 1. Trigger Screen Shake immediately
        this.triggerShake();

        // 2. Freeze logic for specified duration
        this.hitStopTimer = setTimeout(() => {
            this.isHitStopping = false;
            this.shakeIntensity = 0; // Reset shake
            this.shakeOffset = { x: 0, y: 0 };
        }, duration);
    }

    triggerShake() {
        const intensity = GAME_CONFIG.SCREEN_SHAKE_INTENSITY;
        const randomX = (Math.random() - 0.5) * 2 * intensity;
        const randomY = (Math.random() - 0.5) * 2 * intensity;
        
        this.shakeOffset = { x: randomX, y: randomY };
        
        // Apply to DOM container or Unity Canvas via postMessage
        this.applyVisualEffect();
    }

    applyVisualEffect() {
        // In a real Unity WebGL build, this would send commands to the canvas
        // For MVP prototype, we simulate visual feedback on the HUD
        const gameContainer = document.getElementById('game-container');
        if (gameContainer) {
            gameContainer.style.transform = `translate(${this.shakeOffset.x}px, ${this.shakeOffset.y}px)`;
            
            // Flash effect for hit
            const flashOverlay = document.getElementById('hit-flash-overlay');
            if (flashOverlay) {
                flashOverlay.style.opacity = '0.5';
                setTimeout(() => flashOverlay.style.opacity = '0', 50);
            }
        }
    }

    // Update loop for continuous shake decay
    update() {
        if (this.shakeIntensity > 0) {
            this.triggerShake();
            this.shakeIntensity *= 0.9; // Decay
            if (this.shakeIntensity < 0.1) this.shakeIntensity = 0;
        }
    }
}

// ==========================================
// 3. EQUIPMENT & LOOT SYSTEM (Section 7.2)
// ==========================================
class LootSystem {
    constructor() {
        this.statsPool = [
            'attack', 'crit_rate', 'attack_speed', 'max_hp', 'move_speed', 'skill_cd'
        ];
    }

    /**
     * Generates a random item based on drop weights.
     * @param {boolean} isBossDrop - If true, forces minimum Blue quality and higher odds for Purple/Orange.
     * @returns {Object} Generated Item Data
     */
    generateItem(isBossDrop = false) {
        let qualityKey;
        
        if (isBossDrop) {
            // Boss Drop Logic: Guaranteed Blue+, 20% Purple, 5% Orange
            const roll = Math.random() * 100;
            if (roll < 5) qualityKey = 'ORANGE';
            else if (roll < 25) qualityKey = 'PURPLE'; // 20% chance
            else qualityKey = 'BLUE'; // Guaranteed Blue minimum
        } else {