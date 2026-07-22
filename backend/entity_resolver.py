"""
entity_resolver.py — resolve raw asset mentions to canonical asset_ids.

Strategy:
1. A static registry defines every known asset with its canonical ID,
   name, type, location, and a list of aliases (alternative names /
   abbreviations / natural-language references that appear in the docs).
2. resolve(mention) does a case-insensitive lookup across all aliases.
3. Unknown mentions are auto-registered as new assets with type "unknown".
4. The full registry is persisted to / reloaded from SQLite via upsert.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AssetRecord:
    asset_id: str
    name:     str
    type:     str             # tank, pump, sensor, ladle_furnace, crane, …
    location: str
    aliases:  list[str] = field(default_factory=list)


# ── Static seed registry — covers everything in the synthetic dataset ─────────
SEED_REGISTRY: list[AssetRecord] = [
    # ── Horizon Chemicals (LGP incident) ─────────────────────────────────────
    AssetRecord("ST-09", "Styrene Storage Tank 09", "tank",
                "Horizon_Chemicals/Tank_Farm",
                ["tank st-09", "st09", "tank-09", "storage tank 9", "st 09"]),
    AssetRecord("ST-10", "Styrene Storage Tank 10", "tank",
                "Horizon_Chemicals/Tank_Farm",
                ["tank st-10", "st10", "tank-10", "storage tank 10", "st 10"]),
    AssetRecord("ST-11", "Styrene Storage Tank 11", "tank",
                "Horizon_Chemicals/Tank_Farm",
                ["tank st-11", "st11", "tank-11", "styrene storage tank st-11",
                 "storage tank 11", "st 11", "m-11", "tank m-11"]),
    AssetRecord("CHR-01", "Brine Chiller Unit 01", "chiller",
                "Horizon_Chemicals/Utilities",
                ["chiller chr-01", "chr01", "brine chiller", "chiller compressor chr-01",
                 "chiller unit chr-01"]),
    AssetRecord("RTD-11", "Temperature Sensor RTD-11 (ST-11)", "sensor",
                "Horizon_Chemicals/Tank_Farm/ST-11",
                ["rtd-11", "rtd11", "temperature sensor rtd-11", "st-11 rtd",
                 "st-11 temperature sensor"]),
    AssetRecord("FT-11", "Flow Transmitter FT-11 (ST-11 Chiller Loop)", "sensor",
                "Horizon_Chemicals/Tank_Farm/ST-11",
                ["ft-11", "ft11", "flow transmitter ft-11", "st-11 flow sensor",
                 "chiller flow sensor ft-11"]),
    AssetRecord("NV-11", "Nitrogen Blanket Valve NV-11 (ST-11)", "valve",
                "Horizon_Chemicals/Tank_Farm/ST-11",
                ["nv-11", "nv11", "blanketing valve nv-11", "nitrogen valve st-11"]),
    AssetRecord("P-01", "Transfer Pump P-01", "pump",
                "Horizon_Chemicals/Tank_Farm",
                ["pump p-01", "p01", "transfer pump p-01"]),
    AssetRecord("P-02", "Transfer Pump P-02", "pump",
                "Horizon_Chemicals/Tank_Farm",
                ["pump p-02", "p02", "transfer pump p-02"]),
    AssetRecord("P-03", "Transfer Pump P-03", "pump",
                "Horizon_Chemicals/Tank_Farm",
                ["pump p-03", "p03"]),
    AssetRecord("P-04", "Transfer Pump P-04", "pump",
                "Horizon_Chemicals/Tank_Farm",
                ["pump p-04", "p04"]),
    AssetRecord("IRIR-PORTABLE", "Portable Infrared Thermometer", "instrument",
                "Horizon_Chemicals",
                ["portable ir", "irir-portable", "infrared thermometer", "ir thermometer"]),

    # ── Bharat Steel Works (VSP incident) ────────────────────────────────────
    AssetRecord("APS-3", "Argon Purging Station 3", "purging_station",
                "Bharat_Steel_Works/SMS-1",
                ["aps-3", "aps3", "argon purging station aps-3",
                 "argon purge station", "purging station 3"]),
    AssetRecord("FCV-APS3", "Flow Control Valve FCV-APS3 (APS-3)", "valve",
                "Bharat_Steel_Works/SMS-1/APS-3",
                ["fcv-aps3", "fcvaps3", "argon flow control valve", "flow controller aps-3"]),
    AssetRecord("LF-3", "Ladle Furnace 3", "ladle_furnace",
                "Bharat_Steel_Works/SMS-1",
                ["lf-3", "lf3", "ladle furnace lf-3", "ladle furnace 3",
                 "ladle lf-3", "ladle furnace"]),
    AssetRecord("LD-003", "Ladle LD-003 (LF-3 service ladle)", "ladle",
                "Bharat_Steel_Works/SMS-1",
                ["ld-003", "ld003", "ladle ld-003", "ladle ld003",
                 "ladle ld-003 (lf-3 service ladle)"]),
    AssetRecord("LF-2", "Ladle Furnace 2", "ladle_furnace",
                "Bharat_Steel_Works/SMS-1",
                ["lf-2", "lf2", "ladle furnace lf-2"]),
    AssetRecord("COB-3", "Coke Oven Battery 3", "coke_oven_battery",
                "Bharat_Steel_Works/Coke_Ovens",
                ["cob-3", "cob3", "coke oven battery cob-3", "coke oven battery 3",
                 "battery cob-3"]),
    AssetRecord("BF-2", "Blast Furnace 2", "blast_furnace",
                "Bharat_Steel_Works/Blast_Furnaces",
                ["bf-2", "bf2", "blast furnace bf-2", "blast furnace 2"]),
    AssetRecord("CRANE-07", "Overhead Crane 07 (SMS-1)", "crane",
                "Bharat_Steel_Works/SMS-1",
                ["crane-07", "crane07", "crane crane-07", "overhead crane 07"]),
    AssetRecord("SMS-1", "Steel Melting Shop 1", "process_unit",
                "Bharat_Steel_Works",
                ["sms-1", "sms1", "steel melting shop 1", "steel melting shop sms-1",
                 "steel melt shop"]),
    AssetRecord("CCM-1", "Continuous Casting Machine 1 / Caster-1", "casting_machine",
                "Bharat_Steel_Works/SMS-1",
                ["caster-1", "caster1", "ccd", "ccm-1", "caster 1",
                 "continuous casting machine 1"]),

    # ── Facility-level assets ────────────────────────────────────────────────
    AssetRecord("FACILITY-LGP", "Horizon Chemicals Pvt. Ltd.", "facility",
                "Eastport_Industrial_Zone",
                ["horizon chemicals", "horizon chemicals pvt. ltd.",
                 "horizon chemicals pvt ltd", "lgp", "lgp facility"]),
    AssetRecord("FACILITY-VSP", "Bharat Steel Works Ltd.", "facility",
                "Visakhapatnam",
                ["bharat steel works", "bharat steel works ltd.",
                 "vsp", "rinl", "visakhapatnam steel plant",
                 "bharat steel works ltd"]),
]


class EntityResolver:
    """Resolves raw string mentions to canonical asset_ids."""

    def __init__(self):
        self._registry: dict[str, AssetRecord] = {}   # asset_id → record
        self._alias_index: dict[str, str] = {}         # lower(alias) → asset_id
        for rec in SEED_REGISTRY:
            self._add(rec)

    def _add(self, rec: AssetRecord):
        self._registry[rec.asset_id] = rec
        # Index the canonical ID itself as an alias
        self._alias_index[rec.asset_id.lower()] = rec.asset_id
        for alias in rec.aliases:
            self._alias_index[alias.lower()] = rec.asset_id

    # ── Public API ─────────────────────────────────────────────────────────────

    def resolve(self, mention: str) -> Optional[str]:
        """Return canonical asset_id for a mention, or None if not found."""
        key = mention.strip().lower()
        if key in self._alias_index:
            return self._alias_index[key]
        # Try partial match on the canonical ID pattern (e.g. "ST-11" anywhere)
        for alias, cid in self._alias_index.items():
            if alias in key or key in alias:
                return cid
        return None

    def resolve_all(self, mentions: list[str]) -> list[str]:
        """Resolve a list of mentions; drop unresolvable ones."""
        seen = set()
        out = []
        for m in mentions:
            cid = self.resolve(m)
            if cid and cid not in seen:
                seen.add(cid)
                out.append(cid)
        return out

    def get_or_create(self, mention: str) -> str:
        """Resolve or auto-register an unknown asset, returning its ID."""
        cid = self.resolve(mention)
        if cid:
            return cid
        # Auto-register with a sanitised ID
        new_id = re.sub(r"[^A-Z0-9\-]", "", mention.upper())[:20] or "UNKNOWN"
        if new_id in self._registry:
            return new_id
        rec = AssetRecord(
            asset_id=new_id,
            name=mention,
            type="unknown",
            location="unknown",
            aliases=[mention.lower()],
        )
        self._add(rec)
        print(f"[resolver] Auto-registered unknown asset: {new_id!r} ← {mention!r}")
        return new_id

    def all_records(self) -> list[AssetRecord]:
        return list(self._registry.values())

    def get(self, asset_id: str) -> Optional[AssetRecord]:
        return self._registry.get(asset_id)
