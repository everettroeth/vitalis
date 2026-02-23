"""Canonical biomarker name normalisation and unit conversion.

The biomarker dictionary lives in the database (``biomarker_dictionary`` table),
but we embed a copy of all known aliases here so the parser engine can operate
fully offline (no DB round-trip during PDF parsing).

Canonical names are snake_case strings matching
``biomarker_dictionary.canonical_name``.  All alias matching is
case-insensitive.  Fuzzy matching uses ``rapidfuzz`` with an 85 % threshold.
"""

from __future__ import annotations

import logging
import re

try:
    from rapidfuzz import fuzz, process as rfprocess
    _HAS_RAPIDFUZZ = True
except ImportError:  # pragma: no cover
    _HAS_RAPIDFUZZ = False
    logging.getLogger("vitalis.normalizer").warning(
        "rapidfuzz not installed — fuzzy matching disabled"
    )

logger = logging.getLogger("vitalis.normalizer")

# ---------------------------------------------------------------------------
# Biomarker alias dictionary
# Mirrors the seed data from schema.sql's biomarker_dictionary table.
# Each entry: canonical_name → list[alias_strings]
# All aliases are stored lowercase; matching is also done lowercase.
# ---------------------------------------------------------------------------

BIOMARKER_ALIASES: dict[str, list[str]] = {
    # ── Metabolic / CMP ──────────────────────────────────────────────────────
    "glucose": [
        "glucose", "blood glucose", "fasting glucose", "glu", "gluc",
        "glucose, plasma", "glucose serum", "plasma glucose",
        "serum glucose", "glucose (fasting)",
    ],
    "bun": [
        "bun", "blood urea nitrogen", "urea nitrogen", "urea",
        "nitrogen, urea", "urea (serum)", "bun/creatinine",
    ],
    "creatinine": [
        "creatinine", "creat", "crea", "scr", "serum creatinine",
        "creatinine, serum", "creatinine serum",
    ],
    "egfr": [
        "egfr", "gfr", "estimated gfr", "creatinine egfr",
        "egfr non-afr. american", "egfr african american",
        "egfr (non-african american)", "egfr (african american)",
        "estimated glomerular filtration rate",
        "glomerular filtration rate", "gfr estimated",
        "gfr, estimated", "egfr non-african american",
        "egfr if non-african am.", "egfr if african am.",
        "mdrd gfr", "ckd-epi gfr",
    ],
    "bun_creatinine_ratio": [
        "bun/creatinine ratio", "bun creatinine ratio",
        "bun:creatinine", "urea/creatinine ratio",
    ],
    "sodium": ["sodium", "na", "na+", "serum sodium", "sodium, serum"],
    "potassium": ["potassium", "k", "k+", "serum potassium", "potassium, serum"],
    "chloride": ["chloride", "cl", "cl-", "serum chloride", "chloride, serum"],
    "carbon_dioxide": [
        "co2", "carbon dioxide", "bicarbonate", "hco3",
        "co2, total", "total co2", "carbon dioxide, total",
    ],
    "calcium": [
        "calcium", "ca", "calcium, total", "serum calcium",
        "calcium, serum", "total calcium",
    ],
    "protein_total": [
        "total protein", "protein, total", "protein total", "tp",
        "serum protein", "protein, serum",
    ],
    "albumin": ["albumin", "alb", "serum albumin", "albumin, serum"],
    "globulin": [
        "globulin", "glob", "calculated globulin",
        "globulin, total", "total globulin",
    ],
    "albumin_globulin_ratio": [
        "a/g ratio", "albumin/globulin ratio", "alb/glob",
        "albumin globulin ratio", "a:g ratio",
    ],
    "bilirubin_total": [
        "bilirubin", "total bilirubin", "bilirubin total", "bilirubin, total",
        "t. bili", "tbili", "serum bilirubin",
    ],
    "alkaline_phosphatase": [
        "alkaline phosphatase", "alk phos", "alp",
        "alk phosphatase", "alkaline phosphatase, serum",
        "phosphatase, alkaline",
    ],
    "ast": [
        "ast", "sgot", "aspartate aminotransferase",
        "ast (sgot)", "aspartate transaminase",
        "ast/sgot",
    ],
    "alt": [
        "alt", "sgpt", "alanine aminotransferase",
        "alt (sgpt)", "alanine transaminase",
        "alt/sgpt",
    ],
    # ── Metabolic standalone ─────────────────────────────────────────────────
    "hba1c": [
        "hba1c", "hemoglobin a1c", "a1c", "glycated hemoglobin",
        "glycohemoglobin", "hemoglobin a1c %",
        "hgb a1c", "hemoglobin a1c, %",
    ],
    "magnesium": [
        "magnesium", "mg", "mg2+", "serum magnesium",
        "magnesium, serum", "magnesium rbc",
    ],
    "uric_acid": ["uric acid", "urate", "uric acid, serum"],
    "ggt": [
        "ggt", "gamma gt", "gamma-glutamyltransferase",
        "gamma glutamyl transferase", "gamma-glutamyl transferase",
        "ggt, serum",
    ],
    "amylase": ["amylase", "amy", "serum amylase"],
    "lipase": ["lipase", "lps", "serum lipase"],
    # ── Inflammation ─────────────────────────────────────────────────────────
    "hs_crp": [
        "hs-crp", "hscrp", "hs crp", "crp", "c-reactive protein",
        "c reactive protein", "high sensitivity crp",
        "high-sensitivity c-reactive protein",
        "c-reactive protein, high sensitivity",
        "c-reactive protein (high sensitivity)",
        "crp, high sensitivity",
    ],
    "homocysteine": [
        "homocysteine", "hcy", "homocyst(e)ine",
        "homocysteine, plasma",
    ],
    # ── Thyroid ──────────────────────────────────────────────────────────────
    "tsh": [
        "tsh", "thyroid stimulating hormone",
        "thyroid-stimulating hormone", "thyrotropin",
        "tsh, 3rd generation", "tsh reflex",
    ],
    "t4_free": [
        "free t4", "t4, free", "t4 free", "thyroxine, free",
        "ft4", "free thyroxine", "t4 (free)",
    ],
    "t3_free": [
        "free t3", "t3, free", "t3 free",
        "triiodothyronine, free", "ft3",
        "free triiodothyronine", "t3 (free)",
    ],
    "thyroglobulin_ab": [
        "thyroglobulin antibodies", "anti-thyroglobulin",
        "tg ab", "thyroglobulin ab",
        "thyroglobulin antibody",
        "anti-thyroglobulin antibodies",
    ],
    "tpo_ab": [
        "tpo antibodies", "anti-tpo",
        "thyroid peroxidase antibodies", "tpo ab",
        "anti-thyroid peroxidase",
        "thyroid peroxidase (tpo) antibodies",
        "thyroid peroxidase ab",
    ],
    # ── Hormones ─────────────────────────────────────────────────────────────
    "testosterone_total": [
        "testosterone", "total testosterone",
        "testosterone, total", "test total",
        "testosterone, serum", "testosterone total",
    ],
    "testosterone_free": [
        "free testosterone", "testosterone, free",
        "test free", "testosterone (free)",
        "testosterone free",
    ],
    "estradiol": [
        "estradiol", "e2", "17β-estradiol", "estradiol, serum",
        "17-beta estradiol",
    ],
    "shbg": [
        "shbg", "sex hormone binding globulin",
        "sex hormone-binding globulin",
    ],
    "dhea_s": [
        "dhea-s", "dhea-sulfate", "dhea sulfate",
        "dehydroepiandrosterone sulfate",
        "dhea-s, serum",
    ],
    "fsh": [
        "fsh", "follicle stimulating hormone",
        "follicle-stimulating hormone",
        "fsh, serum",
    ],
    "lh": [
        "lh", "luteinizing hormone",
        "luteinising hormone", "lh, serum",
    ],
    "prolactin": ["prolactin", "prl", "prolactin, serum"],
    "cortisol": [
        "cortisol", "serum cortisol",
        "cortisol, serum", "cortisol, a.m.",
    ],
    "insulin": [
        "insulin", "serum insulin",
        "fasting insulin", "insulin, fasting",
    ],
    "leptin": ["leptin", "leptin, serum"],
    "psa_total": [
        "psa", "total psa", "psa, total",
        "prostate specific antigen",
        "prostate-specific antigen",
        "psa (total)",
    ],
    # ── Hematology / CBC ─────────────────────────────────────────────────────
    "wbc": [
        "wbc", "white blood cell count", "white blood cells",
        "leukocytes", "white blood cell", "white cells",
        "wbc count",
    ],
    "rbc": [
        "rbc", "red blood cell count", "red blood cells",
        "erythrocytes", "red cell count", "rbc count",
    ],
    "hemoglobin": [
        "hemoglobin", "hgb", "hb", "hgb",
        "haemoglobin",
    ],
    "hematocrit": [
        "hematocrit", "hct", "pcv",
        "packed cell volume", "haematocrit",
    ],
    "mcv": ["mcv", "mean corpuscular volume"],
    "mch": ["mch", "mean corpuscular hemoglobin"],
    "mchc": [
        "mchc", "mean corpuscular hemoglobin concentration",
        "mean cell hemoglobin concentration",
    ],
    "rdw": [
        "rdw", "red cell distribution width",
        "rdw-cv", "rdw-sd",
    ],
    "platelets": [
        "platelets", "plt", "platelet count",
        "thrombocytes", "platelet",
    ],
    "mpv": ["mpv", "mean platelet volume"],
    "neutrophils_abs": [
        "neutrophils", "neutrophil count", "neut",
        "abs neutrophils", "neutrophils (absolute)",
        "neutrophils, absolute", "absolute neutrophils",
        "neutrophil, absolute",
    ],
    "lymphocytes_abs": [
        "lymphocytes", "lymphocyte count", "lymph",
        "abs lymphocytes", "lymphocytes (absolute)",
        "lymphocytes, absolute", "absolute lymphocytes",
    ],
    "monocytes_abs": [
        "monocytes", "monocyte count", "mono",
        "abs monocytes", "monocytes (absolute)",
        "monocytes, absolute", "absolute monocytes",
    ],
    "eosinophils_abs": [
        "eosinophils", "eosinophil count", "eos",
        "abs eosinophils", "eosinophils (absolute)",
        "eosinophils, absolute", "absolute eosinophils",
    ],
    "basophils_abs": [
        "basophils", "basophil count", "baso",
        "abs basophils", "basophils (absolute)",
        "basophils, absolute", "absolute basophils",
    ],
    "neutrophils_pct": [
        "neutrophils %", "% neutrophils", "neutrophil %",
        "neut %", "neutrophils percent",
    ],
    "lymphocytes_pct": [
        "lymphocytes %", "% lymphocytes", "lymphocyte %",
        "lymph %", "lymphocytes percent",
    ],
    "monocytes_pct": [
        "monocytes %", "% monocytes", "monocyte %",
        "mono %", "monocytes percent",
    ],
    "eosinophils_pct": [
        "eosinophils %", "% eosinophils", "eosinophil %",
        "eos %", "eosinophils percent",
    ],
    "basophils_pct": [
        "basophils %", "% basophils", "basophil %",
        "baso %", "basophils percent",
    ],
    # ── Iron / Nutrition ─────────────────────────────────────────────────────
    "iron": ["iron", "serum iron", "iron, serum", "fe"],
    "tibc": [
        "tibc", "total iron binding capacity",
        "iron binding capacity",
        "iron-binding capacity, total",
    ],
    "iron_saturation": [
        "iron saturation", "transferrin saturation",
        "% saturation", "iron sat",
        "iron saturation %",
    ],
    "ferritin": ["ferritin", "serum ferritin", "ferritin, serum"],
    # ── Vitamins ─────────────────────────────────────────────────────────────
    "vitamin_d_25oh": [
        "vitamin d", "25-oh vitamin d", "25-hydroxyvitamin d",
        "vitamin d, 25-hydroxy", "25-oh vit d",
        "vitamin d 25-oh", "calcidiol",
        "25-hydroxyvitamin d3", "25(oh)d",
        "vitamin d, 25 hydroxy", "vit d 25-oh",
    ],
    "methylmalonic_acid": [
        "methylmalonic acid", "mma",
        "methylmalonic acid, plasma",
    ],
    "zinc": ["zinc", "zinc, serum", "zn"],
    # ── Heavy metals ─────────────────────────────────────────────────────────
    "mercury": ["mercury", "mercury, blood", "hg"],
    "lead": ["lead", "lead, blood", "pb"],
    # ── Lipids ───────────────────────────────────────────────────────────────
    "cholesterol_total": [
        "total cholesterol", "cholesterol", "cholesterol, total",
        "chol", "cholesterol, serum",
    ],
    "hdl_cholesterol": [
        "hdl", "hdl cholesterol", "hdl-c",
        "high-density lipoprotein", "hdl-cholesterol",
        "cholesterol, hdl",
    ],
    "ldl_cholesterol": [
        "ldl", "ldl cholesterol", "ldl-c",
        "low-density lipoprotein", "ldl-cholesterol",
        "cholesterol, ldl", "ldl cholesterol, calc",
        "ldl chol calc", "ldl (calculated)",
    ],
    "triglycerides": [
        "triglycerides", "tg", "trig", "trigs",
        "triglyceride",
    ],
    "chol_hdl_ratio": [
        "cholesterol/hdl ratio", "chol/hdl",
        "total/hdl", "chol:hdl", "cholesterol hdl ratio",
    ],
    "non_hdl_cholesterol": [
        "non-hdl cholesterol", "non-hdl",
        "non hdl cholesterol", "cholesterol, non-hdl",
    ],
    "apolipoprotein_b": [
        "apob", "apolipoprotein b", "apo b",
        "apolipoprotein b-100",
    ],
    "lipoprotein_a": [
        "lp(a)", "lipoprotein(a)", "lipoprotein a",
        "lipoprotein little a",
    ],
    # ── Lipids advanced (NMR) ────────────────────────────────────────────────
    "ldl_particle_number": [
        "ldl-p", "ldl particle number",
        "ldl particle count", "ldl particles",
    ],
    "ldl_small": [
        "small ldl-p", "small ldl particles",
        "small ldl", "sdldl",
    ],
    "ldl_medium": [
        "medium ldl-p", "medium ldl particles",
        "medium ldl",
    ],
    "hdl_large": [
        "large hdl-p", "large hdl particles",
        "large hdl",
    ],
    "ldl_peak_size": [
        "ldl peak size", "ldl size", "ldl particle size",
    ],
    # ── Fatty acids ──────────────────────────────────────────────────────────
    "omega3_total": [
        "total omega-3", "omega-3 total", "omega 3 total",
        "omega-3 fatty acids",
    ],
    "epa": ["epa", "eicosapentaenoic acid"],
    "dpa": ["dpa", "docosapentaenoic acid"],
    "dha": ["dha", "docosahexaenoic acid"],
    "omega6_total": [
        "total omega-6", "omega-6 total", "omega 6 total",
        "omega-6 fatty acids",
    ],
    "arachidonic_acid": [
        "arachidonic acid", "aa", "arachidonate",
    ],
    "linoleic_acid": ["linoleic acid", "la"],
    "omega6_omega3_ratio": [
        "omega-6/omega-3 ratio", "omega 6/3 ratio",
        "omega-6:omega-3",
    ],
    "aa_epa_ratio": [
        "aa/epa ratio", "arachidonic acid/epa",
        "aa:epa",
    ],
    # ── Immunology ───────────────────────────────────────────────────────────
    "rheumatoid_factor": [
        "rheumatoid factor", "rf", "ra factor",
        "rheumatoid factor, quant",
    ],
    "ana_screen": [
        "ana screen", "antinuclear antibodies", "ana",
        "anti-nuclear antibody", "antinuclear antibody",
    ],
}

# ---------------------------------------------------------------------------
# Flat lookup table: lowercase alias → canonical_name
# ---------------------------------------------------------------------------

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canonical, _aliases in BIOMARKER_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_CANONICAL[_alias.lower()] = _canonical

# All lowercase alias strings (for fuzzy matching candidates)
_ALL_ALIASES: list[str] = list(_ALIAS_TO_CANONICAL.keys())


# ---------------------------------------------------------------------------
# Unit normalisation
# ---------------------------------------------------------------------------

# Map from raw unit → canonical unit
UNIT_ALIASES: dict[str, str] = {
    # Cell counts
    "10^3/ul": "10^3/µL",
    "10^3/μl": "10^3/µL",
    "k/ul": "10^3/µL",
    "k/μl": "10^3/µL",
    "thou/ul": "10^3/µL",
    "10^6/ul": "10^6/µL",
    "10^6/μl": "10^6/µL",
    "m/ul": "10^6/µL",
    "m/μl": "10^6/µL",
    # Mass concentrations
    "ug/dl": "µg/dL",
    "μg/dl": "µg/dL",
    "ug/ml": "µg/mL",
    "μg/ml": "µg/mL",
    "ng/dl": "ng/dL",
    "pg/ml": "pg/mL",
    # Enzyme activity
    "u/l": "U/L",
    "iu/l": "IU/L",
    "iu/ml": "IU/mL",
    "miu/l": "mIU/L",
    "miu/ml": "mIU/mL",
    "uiu/ml": "µIU/mL",
    "μiu/ml": "µIU/mL",
    # Micro-symbols
    "umol/l": "µmol/L",
    "μmol/l": "µmol/L",
    "nmol/l": "nmol/L",
    "pmol/l": "pmol/L",
}

# Value conversion factors: (from_unit, to_unit) → multiply_by
UNIT_CONVERSIONS: dict[tuple[str, str], float] = {
    # Glucose: mmol/L → mg/dL
    ("mmol/L", "mg/dL"): 18.0,
    ("mg/dL", "mmol/L"): 1 / 18.0,
    # Cholesterol / lipids: mmol/L → mg/dL
    ("mmol/L cholesterol", "mg/dL"): 38.67,
    # Creatinine: µmol/L → mg/dL
    ("µmol/L", "mg/dL"): 0.01131,
    # Calcium: mmol/L → mg/dL
    ("mmol/L calcium", "mg/dL"): 4.008,
    # Hemoglobin: mmol/L → g/dL
    ("mmol/L", "g/dL"): 1.6113,
}


def normalize_unit(raw_unit: str) -> str:
    """Return the canonical form of a unit string."""
    cleaned = raw_unit.strip()
    return UNIT_ALIASES.get(cleaned.lower(), cleaned)


def convert_value(value: float, from_unit: str, to_unit: str) -> float | None:
    """Convert *value* from *from_unit* to *to_unit*.

    Returns the converted value, or ``None`` if no conversion factor is known.
    """
    factor = UNIT_CONVERSIONS.get((from_unit, to_unit))
    if factor is not None:
        return value * factor
    return None


# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

_FUZZY_THRESHOLD = 85  # minimum similarity score (0–100) for a match


def normalize_marker_name(
    raw_name: str,
    *,
    fuzzy_threshold: int = _FUZZY_THRESHOLD,
) -> tuple[str | None, float]:
    """Resolve a raw marker name to its canonical form.

    Uses exact lookup first, then falls back to fuzzy matching via rapidfuzz.

    Args:
        raw_name:        Name as extracted from the PDF.
        fuzzy_threshold: Minimum rapidfuzz score (0–100) to accept a match.

    Returns:
        ``(canonical_name, match_score)`` where ``match_score`` is 0.0–1.0.
        Returns ``(None, 0.0)`` if no acceptable match is found.
    """
    if not raw_name or not raw_name.strip():
        return None, 0.0

    key = raw_name.strip().lower()

    # 1. Exact match
    if key in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[key], 1.0

    # 2. Substring / prefix match (handles "Glucose, Plasma" → "glucose")
    for alias, canonical in _ALIAS_TO_CANONICAL.items():
        if alias in key or key in alias:
            # Only accept if the overlap is meaningful (>= 6 chars)
            overlap_len = max(len(alias), len(key))
            if overlap_len >= 6:
                return canonical, 0.92

    # 3. Fuzzy match
    if not _HAS_RAPIDFUZZ:
        return None, 0.0

    result = rfprocess.extractOne(
        key,
        _ALL_ALIASES,
        scorer=fuzz.WRatio,
        score_cutoff=fuzzy_threshold,
    )
    if result is not None:
        matched_alias, score, _ = result
        canonical = _ALIAS_TO_CANONICAL[matched_alias]
        normalised_score = score / 100.0
        logger.debug(
            "Fuzzy match: %r → %r (alias=%r, score=%.1f)",
            raw_name,
            canonical,
            matched_alias,
            score,
        )
        return canonical, normalised_score

    logger.debug("No match for marker name: %r", raw_name)
    return None, 0.0


def get_display_name(canonical_name: str) -> str:
    """Return a human-friendly display name for a canonical marker.

    Falls back to title-casing the canonical_name if not found.
    """
    return _DISPLAY_NAMES.get(canonical_name, canonical_name.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Display names — first alias is used as the default display name
# ---------------------------------------------------------------------------

_DISPLAY_NAMES: dict[str, str] = {
    "glucose": "Glucose",
    "bun": "BUN",
    "creatinine": "Creatinine",
    "egfr": "eGFR",
    "bun_creatinine_ratio": "BUN/Creatinine Ratio",
    "sodium": "Sodium",
    "potassium": "Potassium",
    "chloride": "Chloride",
    "carbon_dioxide": "CO2",
    "calcium": "Calcium",
    "protein_total": "Total Protein",
    "albumin": "Albumin",
    "globulin": "Globulin",
    "albumin_globulin_ratio": "A/G Ratio",
    "bilirubin_total": "Bilirubin, Total",
    "alkaline_phosphatase": "Alkaline Phosphatase",
    "ast": "AST",
    "alt": "ALT",
    "hba1c": "HbA1c",
    "magnesium": "Magnesium",
    "uric_acid": "Uric Acid",
    "ggt": "GGT",
    "amylase": "Amylase",
    "lipase": "Lipase",
    "hs_crp": "hs-CRP",
    "homocysteine": "Homocysteine",
    "tsh": "TSH",
    "t4_free": "Free T4",
    "t3_free": "Free T3",
    "thyroglobulin_ab": "Thyroglobulin Antibodies",
    "tpo_ab": "TPO Antibodies",
    "testosterone_total": "Total Testosterone",
    "testosterone_free": "Free Testosterone",
    "estradiol": "Estradiol",
    "shbg": "SHBG",
    "dhea_s": "DHEA-S",
    "fsh": "FSH",
    "lh": "LH",
    "prolactin": "Prolactin",
    "cortisol": "Cortisol",
    "insulin": "Insulin",
    "leptin": "Leptin",
    "psa_total": "PSA, Total",
    "wbc": "WBC",
    "rbc": "RBC",
    "hemoglobin": "Hemoglobin",
    "hematocrit": "Hematocrit",
    "mcv": "MCV",
    "mch": "MCH",
    "mchc": "MCHC",
    "rdw": "RDW",
    "platelets": "Platelets",
    "mpv": "MPV",
    "neutrophils_abs": "Neutrophils",
    "lymphocytes_abs": "Lymphocytes",
    "monocytes_abs": "Monocytes",
    "eosinophils_abs": "Eosinophils",
    "basophils_abs": "Basophils",
    "neutrophils_pct": "Neutrophils %",
    "lymphocytes_pct": "Lymphocytes %",
    "monocytes_pct": "Monocytes %",
    "eosinophils_pct": "Eosinophils %",
    "basophils_pct": "Basophils %",
    "iron": "Iron",
    "tibc": "TIBC",
    "iron_saturation": "Iron Saturation",
    "ferritin": "Ferritin",
    "vitamin_d_25oh": "Vitamin D, 25-Hydroxy",
    "methylmalonic_acid": "Methylmalonic Acid",
    "zinc": "Zinc",
    "mercury": "Mercury",
    "lead": "Lead",
    "cholesterol_total": "Total Cholesterol",
    "hdl_cholesterol": "HDL Cholesterol",
    "ldl_cholesterol": "LDL Cholesterol",
    "triglycerides": "Triglycerides",
    "chol_hdl_ratio": "Cholesterol/HDL Ratio",
    "non_hdl_cholesterol": "Non-HDL Cholesterol",
    "apolipoprotein_b": "Apolipoprotein B",
    "lipoprotein_a": "Lipoprotein(a)",
    "ldl_particle_number": "LDL Particle Number",
    "ldl_small": "Small LDL-P",
    "ldl_medium": "Medium LDL-P",
    "hdl_large": "Large HDL-P",
    "ldl_peak_size": "LDL Peak Size",
    "omega3_total": "Total Omega-3",
    "epa": "EPA",
    "dpa": "DPA",
    "dha": "DHA",
    "omega6_total": "Total Omega-6",
    "arachidonic_acid": "Arachidonic Acid",
    "linoleic_acid": "Linoleic Acid",
    "omega6_omega3_ratio": "Omega-6/Omega-3 Ratio",
    "aa_epa_ratio": "AA/EPA Ratio",
    "rheumatoid_factor": "Rheumatoid Factor",
    "ana_screen": "ANA Screen",
}
