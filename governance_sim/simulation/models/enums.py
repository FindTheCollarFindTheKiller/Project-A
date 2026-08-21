from enum import Enum, auto


class GovernmentType(Enum):
    DEMOCRACY = "Democracy"
    REPUBLIC = "Republic"
    CONSTITUTIONAL_MONARCHY = "Constitutional Monarchy"
    ABSOLUTE_MONARCHY = "Absolute Monarchy"
    THEOCRACY = "Theocracy"
    OLIGARCHY = "Oligarchy"
    AUTOCRACY = "Autocracy"
    COMMUNISM = "Communism"
    ANARCHY = "Anarchy"


class ElectionSystem(Enum):
    FPTP = "First-Past-the-Post"
    PROPORTIONAL = "Proportional Representation"
    RANKED_CHOICE = "Ranked Choice"
    MIXED = "Mixed"
    NONE = "No Elections"


class SuccessionType(Enum):
    ELECTION = "Election"
    HEREDITARY = "Hereditary"
    COUP = "Military Coup"
    APPOINTMENT = "Appointment"
    REVOLUTION = "Revolution"


class TerrainType(Enum):
    PLAINS = "Plains"
    MOUNTAINS = "Mountains"
    DESERT = "Desert"
    FOREST = "Forest"
    JUNGLE = "Jungle"
    TUNDRA = "Tundra"
    COASTAL = "Coastal"
    ISLAND = "Island"
    WETLANDS = "Wetlands"


class ClimateZone(Enum):
    TROPICAL = "Tropical"
    ARID = "Arid"
    SEMI_ARID = "Semi-Arid"
    TEMPERATE = "Temperate"
    CONTINENTAL = "Continental"
    POLAR = "Polar"
    MEDITERRANEAN = "Mediterranean"
    MONSOON = "Monsoon"


class ResourceType(Enum):
    OIL = "Oil"
    NATURAL_GAS = "Natural Gas"
    COAL = "Coal"
    IRON = "Iron"
    COPPER = "Copper"
    GOLD = "Gold"
    URANIUM = "Uranium"
    RARE_EARTH = "Rare Earth Minerals"
    ARABLE_LAND = "Arable Land"
    TIMBER = "Timber"
    FRESHWATER = "Freshwater"
    FISH = "Fish"
    DIAMONDS = "Diamonds"


class DisasterType(Enum):
    EARTHQUAKE = "Earthquake"
    FLOOD = "Flood"
    HURRICANE = "Hurricane / Cyclone"
    DROUGHT = "Drought"
    VOLCANO = "Volcanic Eruption"
    TSUNAMI = "Tsunami"
    WILDFIRE = "Wildfire"
    BLIZZARD = "Blizzard"


class EconomicSystem(Enum):
    COMMAND = "Command Economy"
    FREE_MARKET = "Free Market"
    MIXED = "Mixed Economy"
    SUBSISTENCE = "Subsistence / Feudal"
    WELFARE_STATE = "Welfare State"


class TechTier(Enum):
    PREINDUSTRIAL = 0
    AGRICULTURAL = 1
    EARLY_INDUSTRIAL = 2
    INDUSTRIAL = 3
    DIGITAL = 4
    ADVANCED = 5


class Religion(Enum):
    CHRISTIANITY = "Christianity"
    ISLAM = "Islam"
    HINDUISM = "Hinduism"
    BUDDHISM = "Buddhism"
    JUDAISM = "Judaism"
    SIKHISM = "Sikhism"
    FOLK_RELIGION = "Folk Religion"
    SECULAR = "Secular / Atheist"
    SYNCRETIC = "Syncretic"
    OTHER = "Other"


class MilitaryDoctrine(Enum):
    CONVENTIONAL = "Conventional"
    GUERRILLA = "Guerrilla Warfare"
    NAVAL = "Naval Power"
    AIR_POWER = "Air Superiority"
    NUCLEAR_DETERRENT = "Nuclear Deterrent"
    DEFENSIVE = "Fortress Defense"
    EXPEDITIONARY = "Expeditionary"


class EconomicSector(Enum):
    AGRICULTURE = "Agriculture"
    MANUFACTURING = "Manufacturing"
    SERVICES = "Services"
    TECHNOLOGY = "Technology"
    FINANCE = "Finance"
    TOURISM = "Tourism"
    EXTRACTION = "Resource Extraction"
    MILITARY_INDUSTRIAL = "Military-Industrial"


class PolicyDomain(Enum):
    TAX = "Tax Policy"
    BUDGET = "Budget Allocation"
    SOCIAL = "Social Policy"
    MILITARY = "Military Policy"
    TRADE = "Trade Policy"
    DIPLOMACY = "Foreign Policy"
    INFRASTRUCTURE = "Infrastructure"
    EDUCATION = "Education"
    HEALTHCARE = "Healthcare"


class EventType(Enum):
    RANDOM = "Random"
    TRIGGERED = "Triggered"
    DIPLOMATIC = "Diplomatic"
    ECONOMIC = "Economic"
    MILITARY = "Military"
    CULTURAL = "Cultural"


class LanguageFamily(Enum):
    INDO_EUROPEAN = "Indo-European"
    SINO_TIBETAN = "Sino-Tibetan"
    AFROASIATIC = "Afro-Asiatic"
    AUSTRONESIAN = "Austronesian"
    DRAVIDIAN = "Dravidian"
    TURKIC = "Turkic"
    NIGER_CONGO = "Niger-Congo"
    JAPONIC = "Japonic"
    KOREANIC = "Koreanic"
    SEMITIC = "Semitic"
    URALIC = "Uralic"
    ISOLATE = "Language Isolate"


class ScriptSystem(Enum):
    LATIN = "Latin"
    ARABIC = "Arabic"
    CYRILLIC = "Cyrillic"
    CJK = "CJK (Chinese / Japanese / Korean)"
    DEVANAGARI = "Devanagari"
    GREEK = "Greek"
    HEBREW = "Hebrew"
    GEORGIAN = "Georgian"
    INDIGENOUS = "Indigenous Script"


class DiplomaticStance(Enum):
    ALLIED = "Allied"
    FRIENDLY = "Friendly"
    NEUTRAL = "Neutral"
    TENSE = "Tense"
    HOSTILE = "Hostile"
    AT_WAR = "At War"


class LanguagePolicy(Enum):
    SUPPRESS = "Language Suppression"
    TOLERATE = "Toleration"
    PROMOTE = "Active Promotion"
    BILINGUAL = "Bilingual Education"
    MULTILINGUAL = "Multilingual Policy"
