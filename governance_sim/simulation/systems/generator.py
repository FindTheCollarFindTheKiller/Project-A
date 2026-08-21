"""
Procedural country generator. Geographic seed drives everything else.
"""
from __future__ import annotations
import random
import math
from typing import Dict, List, Optional, Tuple
import uuid

from ..models.country import Country
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
    TerrainType, ClimateZone, ResourceType, DisasterType,
    GovernmentType, ElectionSystem, SuccessionType,
    Religion, EconomicSystem, EconomicSector,
    TechTier, MilitaryDoctrine,
    LanguageFamily, ScriptSystem, LanguagePolicy,
)


# Archetype definitions: (terrain_weights, climate, resources, culture_seeds)
ARCHETYPES = {
    "river_valley": {
        "terrains": [TerrainType.PLAINS, TerrainType.WETLANDS],
        "climate": ClimateZone.TEMPERATE,
        "resources": {ResourceType.ARABLE_LAND: 0.9, ResourceType.FRESHWATER: 0.8},
        "disasters": {DisasterType.FLOOD: 0.4, DisasterType.DROUGHT: 0.2},
        "pop_scale": 1.4, "trade_scale": 0.8, "gdp_scale": 1.0,
        "gov_bias": [GovernmentType.DEMOCRACY, GovernmentType.REPUBLIC, GovernmentType.ABSOLUTE_MONARCHY],
        "tech_bias": TechTier.INDUSTRIAL,
    },
    "coastal_trade": {
        "terrains": [TerrainType.COASTAL, TerrainType.PLAINS],
        "climate": ClimateZone.MEDITERRANEAN,
        "resources": {ResourceType.FISH: 0.7, ResourceType.ARABLE_LAND: 0.5},
        "disasters": {DisasterType.HURRICANE: 0.3, DisasterType.TSUNAMI: 0.1},
        "pop_scale": 1.0, "trade_scale": 1.4, "gdp_scale": 1.2,
        "gov_bias": [GovernmentType.DEMOCRACY, GovernmentType.REPUBLIC, GovernmentType.OLIGARCHY],
        "tech_bias": TechTier.INDUSTRIAL,
    },
    "island_nation": {
        "terrains": [TerrainType.ISLAND, TerrainType.COASTAL],
        "climate": ClimateZone.TROPICAL,
        "resources": {ResourceType.FISH: 0.8, ResourceType.ARABLE_LAND: 0.3},
        "disasters": {DisasterType.HURRICANE: 0.5, DisasterType.TSUNAMI: 0.3},
        "pop_scale": 0.5, "trade_scale": 1.3, "gdp_scale": 0.9,
        "gov_bias": [GovernmentType.DEMOCRACY, GovernmentType.CONSTITUTIONAL_MONARCHY],
        "tech_bias": TechTier.INDUSTRIAL,
    },
    "mountain_fortress": {
        "terrains": [TerrainType.MOUNTAINS, TerrainType.FOREST],
        "climate": ClimateZone.CONTINENTAL,
        "resources": {ResourceType.IRON: 0.7, ResourceType.TIMBER: 0.6, ResourceType.COPPER: 0.4},
        "disasters": {DisasterType.EARTHQUAKE: 0.3, DisasterType.BLIZZARD: 0.4},
        "pop_scale": 0.6, "trade_scale": 0.5, "gdp_scale": 0.85,
        "gov_bias": [GovernmentType.AUTOCRACY, GovernmentType.CONSTITUTIONAL_MONARCHY, GovernmentType.REPUBLIC],
        "tech_bias": TechTier.INDUSTRIAL,
    },
    "desert_kingdom": {
        "terrains": [TerrainType.DESERT, TerrainType.PLAINS],
        "climate": ClimateZone.ARID,
        "resources": {ResourceType.OIL: 0.85, ResourceType.NATURAL_GAS: 0.75, ResourceType.GOLD: 0.3},
        "disasters": {DisasterType.DROUGHT: 0.6, DisasterType.WILDFIRE: 0.3},
        "pop_scale": 0.7, "trade_scale": 0.9, "gdp_scale": 1.3,
        "gov_bias": [GovernmentType.ABSOLUTE_MONARCHY, GovernmentType.THEOCRACY, GovernmentType.AUTOCRACY],
        "tech_bias": TechTier.INDUSTRIAL,
    },
    "steppe_empire": {
        "terrains": [TerrainType.PLAINS, TerrainType.TUNDRA],
        "climate": ClimateZone.CONTINENTAL,
        "resources": {ResourceType.ARABLE_LAND: 0.7, ResourceType.COAL: 0.6, ResourceType.IRON: 0.6},
        "disasters": {DisasterType.BLIZZARD: 0.5, DisasterType.DROUGHT: 0.3},
        "pop_scale": 1.2, "trade_scale": 0.6, "gdp_scale": 0.9,
        "gov_bias": [GovernmentType.AUTOCRACY, GovernmentType.COMMUNISM, GovernmentType.REPUBLIC],
        "tech_bias": TechTier.INDUSTRIAL,
    },
    "jungle_state": {
        "terrains": [TerrainType.JUNGLE, TerrainType.COASTAL],
        "climate": ClimateZone.TROPICAL,
        "resources": {ResourceType.TIMBER: 0.8, ResourceType.ARABLE_LAND: 0.5, ResourceType.GOLD: 0.3},
        "disasters": {DisasterType.FLOOD: 0.5, DisasterType.HURRICANE: 0.4},
        "pop_scale": 0.8, "trade_scale": 0.6, "gdp_scale": 0.65,
        "gov_bias": [GovernmentType.AUTOCRACY, GovernmentType.REPUBLIC, GovernmentType.OLIGARCHY],
        "tech_bias": TechTier.EARLY_INDUSTRIAL,
    },
    "arctic_outpost": {
        "terrains": [TerrainType.TUNDRA, TerrainType.MOUNTAINS],
        "climate": ClimateZone.POLAR,
        "resources": {ResourceType.OIL: 0.4, ResourceType.URANIUM: 0.3, ResourceType.FISH: 0.5},
        "disasters": {DisasterType.BLIZZARD: 0.7},
        "pop_scale": 0.2, "trade_scale": 0.4, "gdp_scale": 0.9,
        "gov_bias": [GovernmentType.DEMOCRACY, GovernmentType.REPUBLIC],
        "tech_bias": TechTier.DIGITAL,
    },
}

_RELIGION_BY_REGION: List[Religion] = [
    Religion.CHRISTIANITY, Religion.ISLAM, Religion.HINDUISM,
    Religion.BUDDHISM, Religion.SECULAR, Religion.FOLK_RELIGION,
]

_LANGUAGE_FAMILIES: List[LanguageFamily] = list(LanguageFamily)
_SCRIPT_BY_FAMILY: Dict[LanguageFamily, ScriptSystem] = {
    LanguageFamily.INDO_EUROPEAN: ScriptSystem.LATIN,
    LanguageFamily.SINO_TIBETAN: ScriptSystem.CJK,
    LanguageFamily.AFROASIATIC: ScriptSystem.ARABIC,
    LanguageFamily.AUSTRONESIAN: ScriptSystem.LATIN,
    LanguageFamily.DRAVIDIAN: ScriptSystem.DEVANAGARI,
    LanguageFamily.TURKIC: ScriptSystem.LATIN,
    LanguageFamily.NIGER_CONGO: ScriptSystem.LATIN,
    LanguageFamily.JAPONIC: ScriptSystem.CJK,
    LanguageFamily.KOREANIC: ScriptSystem.CJK,
    LanguageFamily.SEMITIC: ScriptSystem.ARABIC,
    LanguageFamily.URALIC: ScriptSystem.LATIN,
    LanguageFamily.ISOLATE: ScriptSystem.INDIGENOUS,
}

_COUNTRY_NAME_PARTS = {
    "prefix": ["New", "Greater", "North", "South", "East", "West", "Free", "United"],
    "root": [
        "Valdor", "Kestrel", "Arvon", "Meldor", "Surath", "Palenta", "Irendia",
        "Thrace", "Morvath", "Selene", "Dravan", "Corath", "Elsvara", "Nimbar",
        "Torvan", "Asthelm", "Caldris", "Fenrath", "Gorvalen", "Hestara",
        "Istmark", "Jervon", "Kaldane", "Lyrath", "Mundavar", "Nelthar",
    ],
    "suffix": ["ia", "istan", "land", "ar", "on", "ora", "ovia", "enia", "aria"],
}


def _gen_name(rng: random.Random) -> Tuple[str, str, str]:
    """Returns (country_name, adjective, capital_name)."""
    use_prefix = rng.random() < 0.15
    prefix = rng.choice(_COUNTRY_NAME_PARTS["prefix"]) + " " if use_prefix else ""
    root = rng.choice(_COUNTRY_NAME_PARTS["root"])
    suffix = rng.choice(_COUNTRY_NAME_PARTS["suffix"])
    name = f"{prefix}{root}{suffix}"
    adjective = root + "ian" if not suffix.endswith("ia") else root + suffix[:-1] + "ian"
    capital = rng.choice(_COUNTRY_NAME_PARTS["root"]) + rng.choice(["polis", "burg", "city", "haven", "port", "ford"])
    return name, adjective, capital


class CountryGenerator:
    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self.rng = rng or random.Random()

    def _jitter(self, val: float, spread: float = 0.15) -> float:
        return max(0.0, min(1.0, val + self.rng.uniform(-spread, spread)))

    def generate(
        self,
        archetype: Optional[str] = None,
        start_year: int = 1900,
        name: Optional[str] = None,
        country_id: Optional[str] = None,
    ) -> Country:
        if archetype is None or archetype not in ARCHETYPES:
            archetype = self.rng.choice(list(ARCHETYPES.keys()))
        arch = ARCHETYPES[archetype]

        geo = self._gen_geography(arch)
        culture = self._gen_culture(arch, geo)
        language = self._gen_language(arch, culture)
        gov = self._gen_government(arch, culture)
        economy = self._gen_economy(arch, geo, gov, language)
        demog = self._gen_demographics(arch, geo, economy, language)
        tech = self._gen_technology(arch, gov, economy, demog)
        mil = self._gen_military(arch, geo, gov, economy, tech)
        stability = self._gen_stability(gov, culture, economy, demog)

        # Reconcile gdp_per_capita with gdp_total and actual population
        economy.gdp_per_capita = (economy.gdp_total * 1e9) / max(1, demog.population)

        cname, adj, capital = _gen_name(self.rng)
        if name:
            cname = name

        return Country(
            id=country_id or str(uuid.uuid4())[:8],
            name=cname,
            adjective=adj,
            capital=capital,
            founding_year=start_year - self.rng.randint(50, 500),
            current_year=start_year,
            geography=geo,
            government=gov,
            culture=culture,
            language=language,
            economy=economy,
            demographics=demog,
            military=mil,
            technology=tech,
            stability=stability,
        )

    def _gen_geography(self, arch: dict) -> Geography:
        r = self.rng
        area = r.uniform(50_000, 3_000_000)
        coast = 0.0
        landlocked = True
        for t in arch["terrains"]:
            if t in (TerrainType.COASTAL, TerrainType.ISLAND):
                coast = r.uniform(500, 8_000)
                landlocked = False
                break
        if TerrainType.PLAINS in arch["terrains"] and r.random() < 0.4:
            coast = r.uniform(200, 2_000)
            landlocked = False

        resources = {}
        for rt, abundance in arch["resources"].items():
            resources[rt] = self._jitter(abundance, 0.2)
        # Add a few random minor resources
        extra = r.sample(list(ResourceType), k=r.randint(0, 3))
        for rt in extra:
            if rt not in resources:
                resources[rt] = r.uniform(0.05, 0.35)

        disasters = {dt: max(0.0, v + r.uniform(-0.1, 0.1)) for dt, v in arch["disasters"].items()}

        return Geography(
            terrain_types=arch["terrains"],
            climate_zone=arch["climate"],
            area_km2=area,
            coastline_km=coast,
            is_landlocked=landlocked,
            river_count=r.randint(1, 8),
            natural_resources=resources,
            neighbor_count=r.randint(1, 7),
            border_defensibility=self._jitter(
                0.7 if TerrainType.MOUNTAINS in arch["terrains"] else 0.35, 0.2
            ),
            natural_disaster_risk=disasters,
            elevation_mean_m=r.uniform(50, 2500) if TerrainType.MOUNTAINS in arch["terrains"] else r.uniform(0, 800),
            arable_fraction=resources.get(ResourceType.ARABLE_LAND, 0.25),
        )

    def _gen_culture(self, arch: dict, geo: Geography) -> Culture:
        r = self.rng
        religion = r.choice(_RELIGION_BY_REGION)
        is_arid = geo.climate_zone in (ClimateZone.ARID, ClimateZone.SEMI_ARID)

        individualism = self._jitter(0.35 if is_arid else 0.50, 0.2)
        power_distance = self._jitter(0.60 if is_arid else 0.45, 0.2)
        uncertainty_avoidance = self._jitter(0.55, 0.2)
        long_term = self._jitter(0.45, 0.2)
        indulgence = self._jitter(0.50, 0.2)
        competition = self._jitter(0.45, 0.2)

        ethnic_diversity = self._jitter(0.4 if geo.neighbor_count > 4 else 0.25, 0.2)
        ethnic_tension = self._jitter(ethnic_diversity * 0.5, 0.15)

        gov_bias_authoritarian = GovernmentType.AUTOCRACY in arch["gov_bias"] or GovernmentType.ABSOLUTE_MONARCHY in arch["gov_bias"]
        civil_culture = 1.0 - power_distance * 0.5

        return Culture(
            individualism=individualism,
            power_distance=power_distance,
            uncertainty_avoidance=uncertainty_avoidance,
            long_term_orientation=long_term,
            indulgence=indulgence,
            competition=competition,
            dominant_religion=religion,
            minority_religions=r.sample([rel for rel in _RELIGION_BY_REGION if rel != religion], k=r.randint(0, 2)),
            religious_influence=self._jitter(0.6 if religion in (Religion.ISLAM, Religion.HINDUISM) else 0.30, 0.2),
            secularism=self._jitter(0.7 if religion == Religion.SECULAR else 0.4, 0.2),
            ethnic_diversity=ethnic_diversity,
            ethnic_tension=ethnic_tension,
            national_identity=self._jitter(0.55 if not gov_bias_authoritarian else 0.70, 0.2),
            class_rigidity=self._jitter(0.55 if is_arid else 0.40, 0.2),
            gender_equality=self._jitter(civil_culture * 0.7, 0.2),
            cultural_output=r.uniform(0.1, 0.6),
            diaspora_influence=r.uniform(0.05, 0.4),
        )

    def _gen_language(self, arch: dict, culture: Culture) -> Language:
        r = self.rng
        family = r.choice(_LANGUAGE_FAMILIES)
        script = _SCRIPT_BY_FAMILY.get(family, ScriptSystem.LATIN)
        n_official = 1 if culture.ethnic_diversity < 0.35 else r.randint(1, 3)
        official = [f"Language {chr(65 + i)}" for i in range(n_official)]
        literacy = self._jitter(0.55 + culture.gender_equality * 0.3, 0.15)
        diversity = self._jitter(culture.ethnic_diversity * 0.8, 0.15)
        return Language(
            official_languages=official,
            dominant_family=family,
            script_system=script,
            linguistic_diversity=diversity,
            literacy_rate=literacy,
            lingua_franca="English" if r.random() < 0.4 else None,
            policy=r.choice(list(LanguagePolicy)),
            diaspora_language_reach=culture.diaspora_influence * 0.7,
        )

    def _gen_government(self, arch: dict, culture: Culture) -> Government:
        r = self.rng
        gov_type = r.choice(arch["gov_bias"])
        from ..models.government import _GOV_CIVIL_LIBERTIES, _GOV_CORRUPTION_BASE
        civil_lib = self._jitter(_GOV_CIVIL_LIBERTIES.get(gov_type, 0.5), 0.15)
        corruption = self._jitter(_GOV_CORRUPTION_BASE.get(gov_type, 0.4), 0.15)

        is_democratic = gov_type in (GovernmentType.DEMOCRACY, GovernmentType.REPUBLIC)
        election = r.choice([ElectionSystem.FPTP, ElectionSystem.PROPORTIONAL]) if is_democratic else ElectionSystem.NONE
        succession = SuccessionType.ELECTION if is_democratic else (
            SuccessionType.HEREDITARY if gov_type == GovernmentType.ABSOLUTE_MONARCHY else SuccessionType.APPOINTMENT
        )

        # Budget seeded from archetype
        budget = {
            "military": self._jitter(0.15 if gov_type != GovernmentType.COMMUNISM else 0.25, 0.05),
            "education": self._jitter(0.14, 0.04),
            "healthcare": self._jitter(0.11, 0.04),
            "infrastructure": self._jitter(0.12, 0.04),
            "social_welfare": self._jitter(0.10, 0.04),
            "administration": self._jitter(0.08, 0.03),
            "research": self._jitter(0.04, 0.02),
            "other": 0.0,
        }
        total = sum(budget.values())
        budget["other"] = max(0.0, 1.0 - total)

        gov = Government(
            type=gov_type,
            election_system=election,
            succession_type=succession,
            executive_strength=self._jitter(0.7 if gov_type in (GovernmentType.AUTOCRACY, GovernmentType.COMMUNISM) else 0.5, 0.15),
            legislative_strength=self._jitter(0.7 if is_democratic else 0.3, 0.15),
            judicial_independence=self._jitter(0.7 if is_democratic else 0.25, 0.15),
            corruption=corruption,
            civil_liberties=civil_lib,
            press_freedom=self._jitter(civil_lib, 0.1),
            military_loyalty=self._jitter(0.75, 0.10),   # raised from 0.70 ±0.15
            legitimacy=self._jitter(0.6, 0.15),
            years_in_power=r.randint(0, 20),
            tax_rate=self._jitter(0.25, 0.08),
            budget_allocation=budget,
            policy_reform_speed=self._jitter(0.7 if is_democratic else 0.4, 0.1),
        )
        return gov

    def _gen_economy(self, arch: dict, geo: Geography, gov: Government, lang: Language) -> Economy:
        r = self.rng
        gdp_scale = arch["gdp_scale"]
        trade_scale = arch["trade_scale"]
        pop_scale = arch.get("pop_scale", 1.0)

        base_gdp = r.uniform(20, 500) * gdp_scale
        base_gdp_pc = r.uniform(2000, 30_000) * gdp_scale
        resource_income = geo.resource_wealth * 0.25

        system_bias = {
            GovernmentType.COMMUNISM: EconomicSystem.COMMAND,
            GovernmentType.AUTOCRACY: EconomicSystem.MIXED,
            GovernmentType.DEMOCRACY: EconomicSystem.FREE_MARKET if r.random() < 0.5 else EconomicSystem.MIXED,
            GovernmentType.REPUBLIC: EconomicSystem.MIXED,
            GovernmentType.OLIGARCHY: EconomicSystem.FREE_MARKET,
            GovernmentType.ABSOLUTE_MONARCHY: EconomicSystem.MIXED,
            GovernmentType.THEOCRACY: EconomicSystem.MIXED,
            GovernmentType.CONSTITUTIONAL_MONARCHY: EconomicSystem.WELFARE_STATE if r.random() < 0.5 else EconomicSystem.MIXED,
        }
        econ_system = system_bias.get(gov.type, EconomicSystem.MIXED)

        sectors = {
            EconomicSector.AGRICULTURE.value: self._jitter(0.15 + geo.agricultural_potential * 0.1, 0.05),
            EconomicSector.MANUFACTURING.value: self._jitter(0.25, 0.08),
            EconomicSector.SERVICES.value: self._jitter(0.35, 0.08),
            EconomicSector.TECHNOLOGY.value: self._jitter(0.08, 0.05),
            EconomicSector.EXTRACTION.value: self._jitter(resource_income, 0.05),
            EconomicSector.TOURISM.value: self._jitter(0.05 * trade_scale, 0.04),
            EconomicSector.FINANCE.value: self._jitter(0.07, 0.04),
        }
        total = sum(sectors.values())
        sectors = {k: v / total for k, v in sectors.items()}

        return Economy(
            system=econ_system,
            gdp_total=base_gdp,
            gdp_per_capita=base_gdp_pc,
            gdp_growth=self._jitter(0.025, 0.01),
            gini_coefficient=self._jitter(0.38, 0.1),
            inflation=self._jitter(0.04, 0.03),
            unemployment=self._jitter(0.08, 0.05),
            trade_balance=r.uniform(-10, 15) * trade_scale,
            foreign_debt_gdp=self._jitter(0.45, 0.2),
            trade_agreements=int(r.uniform(1, 6) * trade_scale),
            sector_weights=sectors,
            resource_income_fraction=resource_income,
            sanctions_level=0.0,
        )

    def _gen_demographics(self, arch: dict, geo: Geography, econ: Economy, lang: Language) -> Demographics:
        r = self.rng
        pop_scale = arch.get("pop_scale", 1.0)
        base_pop = int(r.uniform(1_000_000, 80_000_000) * pop_scale)
        dev = econ.development_level
        median_age = 20 + dev * 20  # richer = older
        urbanization = self._jitter(0.30 + dev * 0.5, 0.15)
        edu = self._jitter(0.25 + dev * 0.6, 0.15)
        health = self._jitter(0.30 + dev * 0.55, 0.15)
        happiness = self._jitter(0.30 + dev * 0.5, 0.15)

        return Demographics(
            population=base_pop,
            growth_rate=self._jitter(0.03 - dev * 0.025, 0.01),
            median_age=median_age,
            urbanization=urbanization,
            education_index=edu,
            healthcare_index=health,
            happiness=happiness,
            immigration_rate=r.uniform(0.5, 4.0),
            emigration_rate=r.uniform(0.5, 4.0),
            youth_bulge=self._jitter(-0.1 + (1.0 - dev) * 0.3, 0.1),
            social_mobility=self._jitter(dev * 0.7, 0.15),
        )

    def _gen_technology(self, arch: dict, gov: Government, econ: Economy, demog: Demographics) -> Technology:
        r = self.rng
        dev = econ.development_level
        tier_val = min(5, max(0, round(dev * 4 + r.randint(0, 1))))
        tier = TechTier(tier_val)
        rd_spend = self._jitter(dev * 0.04, 0.01)
        return Technology(
            tier=tier,
            rd_spending_gdp=rd_spend,
            innovation_index=self._jitter(dev * 0.6, 0.15),
            tech_adoption_rate=self._jitter(gov.civil_liberties * 0.6, 0.15),
            digital_penetration=self._jitter(dev * 0.8, 0.15),
            education_quality=self._jitter(demog.education_index, 0.1),
            brain_drain=self._jitter(-0.1 + (1.0 - gov.civil_liberties) * 0.4, 0.15),
            patent_output=self._jitter(dev * 0.4, 0.1),
        )

    def _gen_military(self, arch: dict, geo: Geography, gov: Government,
                      econ: Economy, tech: Technology) -> Military:
        r = self.rng
        base_pop = 10_000_000  # placeholder, real pop set in demographics
        mil_budget_frac = gov.budget_allocation.get("military", 0.15)
        size = int(econ.gdp_total * 1e9 * mil_budget_frac / 50_000)  # ~$50k per soldier
        size = max(5_000, min(5_000_000, size))

        is_landlocked = geo.is_landlocked
        has_coast = geo.coastline_km > 500
        doctrine = r.choice([
            MilitaryDoctrine.DEFENSIVE if geo.border_defensibility > 0.6 else MilitaryDoctrine.CONVENTIONAL,
            MilitaryDoctrine.NAVAL if has_coast else MilitaryDoctrine.CONVENTIONAL,
            MilitaryDoctrine.CONVENTIONAL,
        ])

        return Military(
            size=size,
            reserve_size=size * 2,
            tech_tier=tech.tier,
            defense_spending_gdp=self._jitter(mil_budget_frac, 0.01),
            doctrine=doctrine,
            has_nuclear=r.random() < 0.05,
            morale=self._jitter(0.65, 0.15),
            training_quality=self._jitter(econ.development_level * 0.7, 0.15),
            equipment_quality=self._jitter(tech.tier.value / 5.0, 0.15),
            veteran_ratio=self._jitter(0.15, 0.1),
            paramilitary_strength=self._jitter(
                0.5 if gov.is_authoritarian else 0.25, 0.15
            ),
        )

    def _gen_stability(self, gov: Government, culture: Culture,
                       econ: Economy, demog: Demographics) -> Stability:
        overall = (gov.legitimacy * 0.35 + demog.happiness * 0.30
                   + econ.economic_stability * 0.20 + culture.social_cohesion * 0.15)
        return Stability(
            overall=max(0.1, min(0.95, overall)),
            political=self._jitter(gov.legitimacy, 0.1),
            social=self._jitter(culture.social_cohesion, 0.1),
            economic=self._jitter(econ.economic_stability, 0.1),
            revolution_risk=max(0.0, (1.0 - overall) * 0.3),
            coup_risk=max(0.0, gov.coup_vulnerability * 0.3),
            separatism_risk=max(0.0, culture.ethnic_diversity * culture.ethnic_tension * 0.5),
            protest_level=self._jitter((1.0 - overall) * 0.4, 0.1),
            civil_war_risk=0.01,
        )
