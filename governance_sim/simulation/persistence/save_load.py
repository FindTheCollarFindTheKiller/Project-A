"""
JSON-based save/load for the world state.
"""
from __future__ import annotations
import json
import os
import dataclasses
from datetime import datetime
from typing import Any, Dict

from ..systems.world import World, BilateralRelation
from ..models.country import Country, HistoricalEvent
from ..models.geography import Geography
from ..models.government import Government
from ..models.culture import Culture
from ..models.language import Language
from ..models.economy import Economy
from ..models.demographics import Demographics
from ..models.military import Military
from ..models.technology import Technology
from ..models.stability import Stability
from ..models.enums import (
    GovernmentType, ElectionSystem, SuccessionType,
    TerrainType, ClimateZone, ResourceType, DisasterType,
    EconomicSystem, EconomicSector,
    TechTier, MilitaryDoctrine,
    Religion, LanguageFamily, ScriptSystem, LanguagePolicy,
)

_SAVES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "saves")


def _enum_val(v: Any) -> Any:
    if isinstance(v, type) and issubclass(v, object):
        pass
    from enum import Enum
    if isinstance(v, Enum):
        return v.value
    return v


_EK_PREFIX = "__EK__"  # sentinel for enum dict keys


def _serialize(obj: Any) -> Any:
    from enum import Enum
    if isinstance(obj, Enum):
        return {"__enum__": type(obj).__name__, "value": obj.value}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        # Iterate fields manually to avoid dataclasses.asdict's recursive conversion
        # which leaves enum keys as unhashable when re-serialized as dict keys.
        result = {}
        for f in dataclasses.fields(obj):
            result[f.name] = _serialize(getattr(obj, f.name))
        return result
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, Enum):
                # Encode enum keys as a special string: "__EK__EnumClass__value"
                sk = f"{_EK_PREFIX}{type(k).__name__}__{k.value}"
            elif not isinstance(k, str):
                sk = str(k)
            else:
                sk = k
            out[sk] = _serialize(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    return obj


# ── Enum lookup maps ──────────────────────────────────────────────────────────

_ENUM_MAP: Dict[str, Any] = {
    "GovernmentType": GovernmentType,
    "ElectionSystem": ElectionSystem,
    "SuccessionType": SuccessionType,
    "TerrainType": TerrainType,
    "ClimateZone": ClimateZone,
    "ResourceType": ResourceType,
    "DisasterType": DisasterType,
    "EconomicSystem": EconomicSystem,
    "TechTier": TechTier,
    "MilitaryDoctrine": MilitaryDoctrine,
    "Religion": Religion,
    "LanguageFamily": LanguageFamily,
    "ScriptSystem": ScriptSystem,
    "LanguagePolicy": LanguagePolicy,
    "EconomicSector": EconomicSector,
}


def _deserialize_enum(d: dict) -> Any:
    enum_cls = _ENUM_MAP.get(d["__enum__"])
    if enum_cls:
        # Try by value first, then by name
        try:
            return enum_cls(d["value"])
        except ValueError:
            return enum_cls[d["value"]]
    raise ValueError(f"Unknown enum type: {d['__enum__']}")


def _deserialize(obj: Any) -> Any:
    if isinstance(obj, dict):
        if "__enum__" in obj:
            return _deserialize_enum(obj)
        result = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith(_EK_PREFIX):
                # Decode enum key: "__EK__EnumClass__value"
                remainder = k[len(_EK_PREFIX):]
                cls_name, _, val = remainder.partition("__")
                enum_cls = _ENUM_MAP.get(cls_name)
                dk = enum_cls(val) if enum_cls else k
            else:
                dk = k
            result[dk] = _deserialize(v)
        return result
    if isinstance(obj, list):
        return [_deserialize(i) for i in obj]
    return obj


def _load_geography(d: dict) -> Geography:
    d = _deserialize(d)
    return Geography(**d)


def _load_government(d: dict) -> Government:
    d = _deserialize(d)
    return Government(**d)


def _load_culture(d: dict) -> Culture:
    d = _deserialize(d)
    return Culture(**d)


def _load_language(d: dict) -> Language:
    d = _deserialize(d)
    return Language(**d)


def _load_economy(d: dict) -> Economy:
    d = _deserialize(d)
    return Economy(**d)


def _load_demographics(d: dict) -> Demographics:
    d = _deserialize(d)
    return Demographics(**d)


def _load_military(d: dict) -> Military:
    d = _deserialize(d)
    return Military(**d)


def _load_technology(d: dict) -> Technology:
    d = _deserialize(d)
    return Technology(**d)


def _load_stability(d: dict) -> Stability:
    d = _deserialize(d)
    return Stability(**d)


def _load_country(d: dict) -> Country:
    return Country(
        id=d["id"],
        name=d["name"],
        adjective=d["adjective"],
        capital=d["capital"],
        founding_year=d["founding_year"],
        current_year=d["current_year"],
        geography=_load_geography(d["geography"]),
        government=_load_government(d["government"]),
        culture=_load_culture(d["culture"]),
        language=_load_language(d["language"]),
        economy=_load_economy(d["economy"]),
        demographics=_load_demographics(d["demographics"]),
        military=_load_military(d["military"]),
        technology=_load_technology(d["technology"]),
        stability=_load_stability(d["stability"]),
        history=[HistoricalEvent(**_deserialize(h)) for h in d.get("history", [])],
        neighbor_ids=d.get("neighbor_ids", []),
        pending_events=d.get("pending_events", []),
        event_cooldowns=d.get("event_cooldowns", {}),
    )


def _load_relation(d: dict) -> BilateralRelation:
    return BilateralRelation(**d)


def _serialize_world(world: World) -> dict:
    return {
        "year": world.year,
        "player_id": world.player_id,
        "countries": {cid: _serialize(c) for cid, c in world.countries.items()},
        "relations": {
            f"{a}|{b}": dataclasses.asdict(rel)
            for (a, b), rel in world._relations.items()
        },
        "world_events": world.world_events,
    }


def _deserialize_world(d: dict) -> World:
    world = World(year=d["year"])
    world.player_id = d.get("player_id")
    for cid, cd in d["countries"].items():
        world.countries[cid] = _load_country(cd)
    for key, rd in d.get("relations", {}).items():
        a, b = key.split("|")
        world._relations[(a, b)] = _load_relation(rd)
    world.world_events = d.get("world_events", [])
    return world


def save_game(world: World, slot: str = "autosave") -> str:
    os.makedirs(_SAVES_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{slot}_{timestamp}.json"
    path = os.path.join(_SAVES_DIR, filename)
    data = _serialize_world(world)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_game(path: str) -> World:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _deserialize_world(data)
