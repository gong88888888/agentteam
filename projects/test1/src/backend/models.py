"""
src/backend/models.py
核心数据模型定义
包含: 装备, 角色, 房间, 存档, 本地同屏状态
"""

from __future__ import annotations
import json
import hashlib
import time
import random
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
import sqlite3
import os
import shutil

# ==============================================================================
# 枚举与常量定义
# ==============================================================================

class Rarity(Enum):
    """装备品质"""
    COMMON = "common"      # 白色
    UNCOMMON = "uncommon"  # 绿色
    RARE = "rare"          # 蓝色
    EPIC = "epic"          # 紫色
    LEGENDARY = "legendary" # 橙色

class ItemType(Enum):
    """物品类型"""
    WEAPON = "weapon"
    ARMOR = "armor"
    ACCESSORY = "accessory"
    CONSUMABLE = "consumable"

class AffixType(Enum):
    """词条类型"""
    ATTACK_POWER = "attack_power"
    CRITICAL_RATE = "critical_rate"
    LUCK = "luck"
    HP_MAX = "hp_max"
    DEFENSE = "defense"

class SaveVersion(Enum):
    """存档版本，用于兼容迁移"""
    V1_0_0 = "1.0.0"
    CURRENT = "1.1.0"  # 当前版本

# MVP 配置常量
MAX_SAVE_SLOTS = 3
BACKUP_SUFFIX = ".bak"
CRC_SIZE = 4096  # CRC校验读取字节数

# ==============================================================================
# 数据模型类
# ==============================================================================

@dataclass
class Affix:
    """装备词条"""
    affix_type: AffixType
    value: float
    
    def to_dict(self):
        return {
            "type": self.affix_type.value,
            "value": self.value
        }
    
    @staticmethod
    def from_dict(data: dict) -> Affix:
        return Affix(
            affix_type=AffixType(data["type"]),
            value=data["value"]
        )

@dataclass
class Equipment:
    """装备数据"""
    item_id: str  # UUID或ID
    name: str
    rarity: Rarity
    item_type: ItemType
    base_stats: Dict[str, float] = field(default_factory=dict)
    affixes: List[Affix] = field(default_factory=list)
    level: int = 1
    
    def get_total_attack(self) -> float:
        """计算总攻击力 (简化版，仅示例)"""
        return self.base_stats.get("attack", 0.0) + \
               sum(a.value for a in self.affixes if a.affix_type == AffixType.ATTACK_POWER)

    def to_dict(self):
        return {
            "item_id": self.item_id,
            "name": self.name,
            "rarity": self.rarity.value,
            "item_type": self.item_type.value,
            "base_stats": self.base_stats,
            "affixes": [a.to_dict() for a in self.affixes],
            "level": self.level
        }

    @staticmethod
    def from_dict(data: dict) -> Equipment:
        return Equipment(
            item_id=data["item_id"],
            name=data["name"],
            rarity=Rarity(data["rarity"]),
            item_type=ItemType(data["item_type"]),
            base_stats=data.get("base_stats", {}),
            affixes=[Affix.from_dict(a) for a in data.get("affixes", [])],
            level=data.get("level", 1)
        )

@dataclass
class PlayerState:
    """玩家状态 (用于存档和同步)"""
    player_id: str
    name: str
    class_type: str  # e.g., "warrior", "mage"
    level: int = 1
    exp: float = 0.0
    
    # 属性
    hp: float = 100.0
    max_hp: float = 100.0
    mp: float = 50.0
    max_mp: float = 50.0
    attack: float = 10.0
    defense: float = 0.0
    
    # 位置 (用于本地同屏同步)
    x: float = 0.0
    y: float = 0.0
    direction: int = 1  # 1 right, -1 left
    
    # 背包与装备
    inventory: List[Equipment] = field(default_factory=list)
    equipped_weapon: Optional[Equipment] = None
    equipped_armor: Optional[Equipment] = None
    
    # 进度
    gold: int = 0
    unlocked_rooms: List[str] = field(default_factory=list)
    current_room_id: str = "start_room"
    
    # 成就/图鉴 (简化)
    kills: Dict[str, int] = field(default_factory=dict)
    discovered_monsters: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "player_id": self.player_id,
            "name": self.name,
            "class_type": self.class_type,
            "level": self.level,
            "exp": self.exp,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "