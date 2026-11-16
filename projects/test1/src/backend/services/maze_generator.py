"""
Maze Generator Service for "Dungeon Adventurer" MVP.

Responsibilities:
1. Generate a linear chain of rooms (8-12) + 1 Boss room per chapter layer.
2. Ensure connectivity via a "Key Path" to prevent soft-locks.
3. Assign room types based on probability and constraints (e.g., exactly 1 Campfire, 1 Shop).
4. Support deterministic seeding for save/load consistency.

Design Constraints:
- MVP Scope: Chapter 1 only (5 layers).
- Single-player baseline; Multiplayer scaling is handled by `multiplayer_scaler`.
- No network sync logic here; pure state generation.
"""

import random
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# Importing internal config for MVP constants
# In a real project, this would be imported from src/backend/config/chapter_1.py
# For this single-file output, we define minimal necessary configs inline or assume they exist.
# We will use the `config` module if available, otherwise fallback to defaults.

try:
    from src.backend.config.chapter_1 import CHAPTER_1_LAYERS, ROOM_TEMPLATES
except ImportError:
    # Fallback for standalone execution or if config is not yet written
    CHAPTER_1_LAYERS = 5
    
    class RoomType(Enum):
        COMBAT = "combat"
        PLATFORM = "platform"
        TREASURE = "treasure"
        SHOP = "shop"
        CAMPFIRE = "campfire"
        EVENT = "event"
        ELITE = "elite"
        BOSS = "boss"

    ROOM_TEMPLATES = {
        RoomType.COMBAT: {"min_waves": 2, "max_waves": 4},
        RoomType.PLATFORM: {"min_platforms": 3, "max_platforms": 6},
        RoomType.TREASURE: {"min_chests": 1, "max_chests": 3},
        RoomType.SHOP: {"inventory_size": 5},
        RoomType.CAMPFIRE: {"heal_amount": 0.5},
        RoomType.EVENT: {"event_types": ["gamble", "curse", "blessing"]},
        RoomType.ELITE: {"affix_count": 2},
        RoomType.BOSS: {"phase_count": 3},
    }

@dataclass
class RoomNode:
    """Represents a single room in the maze graph."""
    room_id: str
    room_type: RoomType
    layer_index: int
    is_key_path: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime state (populated during generation/execution)
    enemies_spawned: List[Dict] = field(default_factory=list)
    is_cleared: bool = False
    has_been_visited: bool = False

@dataclass
class MazeLayer:
    """Represents one layer of the dungeon."""
    layer_index: int
    seed: int
    rooms: List[RoomNode] = field(default_factory=list)
    
    def get_key_path_rooms(self) -> List[RoomNode]:
        return [r for r in self.rooms if r.is_key_path]

@dataclass
class GeneratedMaze:
    """The complete generated dungeon structure."""
    chapter_id: str
    layers: List[MazeLayer] = field(default_factory=list)
    
    def get_start_room(self) -> RoomNode:
        return self.layers[0].rooms[0]

    def get_boss_room(self) -> RoomNode:
        # Boss is always the last room of the last layer in MVP
        if not self.layers:
            raise ValueError("Maze has no layers")
        last_layer = self.layers[-1]
        boss_rooms = [r for r in last_layer.rooms if r.room_type == RoomType.BOSS]
        if not boss_rooms:
            raise ValueError("Boss room not found in last layer")
        return boss_rooms[0]


class MazeGeneratorService:
    """
    Generates deterministic mazes based on seeds and chapter configs.
    
    Algorithm:
    1. For each layer, create a "Key Path" of N rooms.
    2. Insert mandatory special rooms (Campfire, Shop) into the Key Path at fixed intervals.
    3. Add side branches (Treasure/Event rooms) to non-key-path slots if space permits.
    4. Ensure the last room of the final layer is the Boss Room.
    """

    def __init__(self):
        self._rng = random.Random()

    def generate_chapter(self, chapter_id: str, seed: int) -> GeneratedMaze:
        """
        Generate a full chapter maze.
        
        Args:
            chapter_id: e.g., 'chapter_1'
            seed: Deterministic seed for reproducible generation.
            
        Returns:
            GeneratedMaze object containing all layers and rooms.
        """
        self._rng.seed(seed)
        maze = GeneratedMaze(chapter_id=chapter_id)
        
        # Determine number of layers based on chapter config
        num_layers = CHAPTER_1_LAYERS if chapter_id == "chapter_1" else 5
        
        for layer_idx in range(num_layers):
            layer_seed = seed + layer_idx * 1000
            layer = self._generate_layer(layer_idx, layer_seed)
            maze.layers.append(layer)
            
        return maze

    def _generate_layer(self, layer_index: int, seed: int) -> MazeLayer:
        """Generate a single layer with 8-12 rooms."""
        rng = random.Random(seed)
        
        # MVP Constraint: 8-12 rooms per layer
        num_rooms = rng.randint(8, 12)
        
        # Key Path Length: Must be at least half the rooms to ensure connectivity and pacing
        # But we want a linear feel, so key path is roughly 60-70% of total
        key_path_len = max(5, int(num_rooms * 0.6))
        
        rooms: List[RoomNode] = []
        
        # 1. Build Key Path
        for i in range(key_path_len):
            room_type = self._determine_key_room_type(layer_index, i, key_path_len)
            room_id = f"L{layer_index+1}_KP{i}"
            node = RoomNode(
                room_id=room_id,
                room_type=room_type,
                layer_index=layer_index,
                is_key_path=True
            )
            rooms.append(node)
            
        # 2. Fill remaining slots with Side Rooms (Treasure/Event)
        side_rooms_count = num_rooms - key_path_len
        for i in range(side_rooms_count):
            room_type = rng.choice([RoomType.TREASURE, RoomType.EVENT])
            room_id = f"L{layer_index+1}_S{i}"
            node = RoomNode(
                room_id=room_id,
                room_type=room_type,
                layer_index=layer_index,
                is_key_path=False
            )
            rooms.append(node)
            
        # 3. Post-processing: Ensure Mandatory Rooms exist in Key Path
        self._enforce_mandatory_rooms(rooms, layer_index)
        
        return MazeLayer(layer_index=layer_index, seed=seed, rooms=rooms)

    def _determine_key_room_type(self, layer_idx: int, index: int, total_len: int) -> RoomType:
        """Determine the type of a room on the key path."""
        # Last room of the last layer is always Boss (handled in post-process or here)
        if layer_idx == CHAPTER_1_LAYERS - 1 and index == total_len - 1:
            return RoomType.BOSS
            
        # Early game teaching: First few rooms are Combat/Platform
        if layer_idx == 0 and index < 3:
            return RoomType.COMBAT if index % 2 == 0 else RoomType.PLATFORM
            
        # General distribution for Key Path
        roll = random.random()
        if roll < 0.4:
            return RoomType.COMBAT
        elif roll < 0.6:
            return RoomType.ELITE
        elif roll < 0.8:
            return RoomType.PLATFORM
        else:
            return RoomType.TREASURE

    def _enforce_mandatory_rooms(self, rooms: List[RoomNode], layer_idx: int):
        """Ensure every layer has exactly one Campfire and one Shop on the key path."""
        has_campfire = any(r.room_type == RoomType.CAMPFIRE for r in rooms)
        has_shop = any(r.room_type == RoomType.SHOP for r in rooms)
        
        # Find a suitable candidate to replace if missing
        # Prefer replacing a Combat or Platform room to maintain flow
        
        if not has_campfire:
            # Place campfire roughly 1/3rd through the key path
            target_idx = max(0, len(rooms) // 3)
            self._replace_room_type(rooms, target_idx, RoomType.CAMPFIRE)
            
        if not has_shop:
            # Place shop roughly 2/3rds through the key path
            target_idx = max(len(rooms) // 2, len(rooms) - 2)
            self._replace_room_type(rooms, target_idx, RoomType.SHOP)

    def _replace_room_type(self, rooms: List[RoomNode], index: int, new_type: RoomType):
        """Safely replace a room's type, ensuring we don't overwrite the Boss."""
        if index < len(rooms):
            # Don't overwrite the final boss room
            if rooms[index].room_type == RoomType.BOSS and new_type != RoomType.BOSS:
                return
            rooms[index].room_type = new_type

    def get_room_by_id(self, maze: GeneratedMaze, room_id: str) -> Optional[RoomNode]:
        """Helper to retrieve a specific room node from the generated maze."""
        for layer in maze.layers:
            for room in layer.rooms:
                if room.room_id == room_id:
                    return room
        return None