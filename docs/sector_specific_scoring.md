# Sector-Specific Fundamental Scoring — Design & Extension Guide

> **Version**: v1.0 | **Date**: 2026-04-18  
> **Platform**: Nivesh Elite — Stock Fundamentals Module  
> **Prerequisite**: Read `docs/fundamental_scoring_design.md` first.  
> **Constraint**: Deterministic, rule-based. No AI/ML/LLM used.

---

## Table of Contents

1. [Why Sector-Specific Scoring](#1-why-sector-specific-scoring)
2. [Extension Architecture](#2-extension-architecture)
3. [Sector Configurations](#3-sector-configurations)
   - [Banking & NBFC (BFSI)](#31-banking--nbfc-bfsi)
   - [Information Technology](#32-information-technology)
   - [Pharmaceuticals & Healthcare](#33-pharmaceuticals--healthcare)
   - [Capital Goods & Infrastructure](#34-capital-goods--infrastructure)
   - [FMCG & Consumer Staples](#35-fmcg--consumer-staples)
   - [Metals, Mining & Commodities](#36-metals-mining--commodities)
   - [Real Estate (Realty)](#37-real-estate-realty)
   - [Energy & Oil and Gas](#38-energy--oil-and-gas)
4. [Implementation Design](#4-implementation-design)
5. [Sector Detection](#5-sector-detection)
6. [Validation & Rollout Plan](#6-validation--rollout-plan)

---

## 1. Why Sector-Specific Scoring

The generic scoring system (see `fundamental_scoring_design.md`) uses thresholds calibrated for **diversified Indian large/mid-cap non-financial companies**. Applying those thresholds uniformly across all sectors produces **systematically biased scores** because financial structures differ fundamentally across industries.

### Problem Illustration

| Metric | Generic Threshold | Bank | IT Company | Infrastructure |
|---|---|---|---|---|
| D/E ≤ 0.25 → 100 | Fair for most | ❌ Banks operate at 8–12× D/E by design | ✅ Correct | ❌ Project finance means 2–3× is healthy |
| CFO/PAT ≥ 1.2 → 100 | Fair for most | ❌ Banks don't separate CFO meaningfully | ❌ IT firms hit 0.9 CFO/PAT due to accruals | ✅ Correct |
| OPM ≥ 25% → 100 | Fair for most | ❌ Banks use NIM, not OPM | ❌ IT OPM 20–30% is exceptional | ❌ Infra OPM 8–15% is standard |
| CWIP/TA > 15% → −10 | Fair for most | ❌ Irrelevant | ❌ Near-zero CWIP always | ❌ High CWIP is expected during build phase |

### Design Principle

> **Generic scoring is the default.** Sector configs only **override specific thresholds** and **disable irrelevant metrics**. The module structure remains unchanged — sector configs are passed as an optional `sector_config: dict` parameter.

---

## 2. Extension Architecture

### 2.1 Config-Driven Override Pattern

Each sector is described by a config dictionary that selectively overrides generic thresholds. Functions `score_pl()`, `score_bs()`, `score_cf()` accept an optional `sector_config` parameter:

```python
def score_pl(periods: list[str], data: dict, sector_config: dict = None) -> dict:
    cfg = sector_config or {}
    # Use cfg.get("opm_thresholds", DEFAULT_OPM_THRESHOLDS)
    # Use cfg.get("pl_consistency_penalty", 20)   # default: 20 per loss year
```

### 2.2 Config Dictionary Schema

```python
SectorConfig = {
    # P&L overrides
    "revenue_key":              str,           # default: "sales"
    "opm_thresholds":           list[tuple],   # [(value, score), ...] descending
    "use_nim_instead_of_opm":   bool,          # Banking: use NIM not OPM
    "nim_thresholds":           list[tuple],
    "rev_cagr_thresholds":      list[tuple],
    "pat_cagr_thresholds":      list[tuple],
    "pat_cagr_years":           int,           # default: 5; Metals: 7
    "loss_year_penalty":        int,           # default: 20; Infra: 10
    "max_loss_year_penalty":    int,           # default: 30

    # Balance Sheet overrides
    "disable_de_scoring":       bool,          # Banking: True
    "use_car_instead_of_de":    bool,          # Banking: True
    "car_thresholds":           list[tuple],
    "de_thresholds":            list[tuple],   # custom D/E brackets
    "disable_cwip_penalty":     bool,          # Infra/Realty: True
    "cwip_penalty_threshold":   float,         # default: 0.15; IT: 0.05
    "ta_cagr_thresholds":       list[tuple],
    "res_cagr_thresholds":      list[tuple],
    "disable_liquidity_score":  bool,          # Banking: True (use LCR instead)
    "asset_quality_metric":     str,           # Banking: "gross_npa_pct"
    "asset_quality_thresholds": list[tuple],
    "bs_weights":               dict,          # override sub-score weights

    # Cash Flow overrides
    "skip_cf_scoring":          bool,          # Banking: True
    "cfo_pat_thresholds":       list[tuple],   # IT: lower ceiling needed
    "fcf_margin_thresholds":    list[tuple],   # Infra: different ranges
    "cf_weights":               dict,

    # Composite weight overrides
    "composite_weights":        dict,          # {"pl": 0.5, "bs": 0.5, "cf": 0.0}
}
```

### 2.3 Sector Config Map

```python
# pipeline/sector_configs.py  (new file)

SECTOR_CONFIG_MAP: dict[str, dict] = {
    # Exact sector strings from stocks.sector column
    "Banks":                      BFSI_CONFIG,
    "Finance":                    BFSI_CONFIG,
    "Financial Services":         BFSI_CONFIG,
    "Insurance":                  BFSI_CONFIG,
    "Technology":                 IT_CONFIG,
    "Information Technology":     IT_CONFIG,
    "Software & Services":        IT_CONFIG,
    "Healthcare":                 PHARMA_CONFIG,
    "Pharmaceuticals":            PHARMA_CONFIG,
    "Hospitals & Diagnostics":    PHARMA_CONFIG,
    "Capital Goods":              INFRA_CONFIG,
    "Construction":               INFRA_CONFIG,
    "Infrastructure":             INFRA_CONFIG,
    "Engineering":                INFRA_CONFIG,
    "FMCG":                       FMCG_CONFIG,
    "Consumer Staples":           FMCG_CONFIG,
    "Consumer Goods":             FMCG_CONFIG,
    "Metals & Mining":            METALS_CONFIG,
    "Mining":                     METALS_CONFIG,
    "Commodities":                METALS_CONFIG,
    "Real Estate":                REALTY_CONFIG,
    "Realty":                     REALTY_CONFIG,
    "Energy":                     ENERGY_CONFIG,
    "Oil & Gas":                  ENERGY_CONFIG,
    "Power":                      ENERGY_CONFIG,
}

def get_sector_config(sector: str | None) -> dict:
    """Returns sector config dict, or {} (generic defaults) if sector unknown."""
    if not sector:
        return {}
    return SECTOR_CONFIG_MAP.get(sector, {})
```

---

## 3. Sector Configurations

### 3.1 Banking & NBFC (BFSI)

**Applies to**: Private Banks, PSU Banks, NBFCs, Housing Finance Companies, MFIs, Insurance.

**Key structural differences**:
- D/E ratio of 8–12× is **normal** (they lend depositor money)
- Revenue = Net Interest Income (NII) or Net Interest Margin (NIM), not "sales"
- Profitability quality measured by NPA (Non-Performing Assets), not OPM
- Cash Flow classification is non-standard; CFO/CFF split is meaningless

#### P&L Overrides

| Generic Metric | BFSI Override |
|---|---|
| Revenue key = `sales` | Use `net_interest_income` or `total_income` |
| OPM (Operating Profit Margin) | **Disabled** — replace with NIM |
| NIM threshold (NEW) | ≥ 4.5% → 100, 3.5–4.5% → 80, 2.5–3.5% → 55, 2.0–2.5% → 30, < 2% → 0 |
| PAT CAGR range | Same brackets (PAT CAGR is meaningful for banks) |
| Loss year penalty | Increased to **25 pts/year** (bank losses signal severe stress) |

#### Balance Sheet Overrides

| Generic Metric | BFSI Override |
|---|---|
| D/E scoring | **Disabled** entirely (`disable_de_scoring: True`) |
| D/E replacement | **Capital Adequacy Ratio (CRAR)**: ≥ 18% → 100, 15–18% → 80, 12–15% → 55, 10–12% → 30, < 10% → 0 |
| Asset quality (CAGR) | **Replaced** by **Gross NPA %**: ≤ 1% → 100, 1–3% → 70, 3–5% → 40, 5–8% → 15, > 8% → 0 |
| Current Ratio | **Disabled** (use LCR if available; else skip) |
| CWIP penalty | **Disabled** |
| BS weights | Leverage(CRAR): 35%, Asset Quality(NPA): 35%, Reserves CAGR: 30% |

#### Cash Flow Override

```
# BFSI: Skip CF scoring entirely
skip_cf_scoring: True
composite_weights: {"pl": 0.50, "bs": 0.50, "cf": 0.00}
```

#### BFSI Config Dict

```python
BFSI_CONFIG = {
    "revenue_key":              "net_interest_income",
    "use_nim_instead_of_opm":   True,
    "nim_thresholds":           [(4.5, 100), (3.5, 80), (2.5, 55), (2.0, 30), (0.0, 0)],
    "pat_cagr_thresholds":      [(25, 100), (20, 85), (15, 70), (10, 55), (5, 35), (0, 15), (None, 0)],
    "loss_year_penalty":        25,
    "max_loss_year_penalty":    50,
    "disable_de_scoring":       True,
    "use_car_instead_of_de":    True,
    "car_thresholds":           [(18, 100), (15, 80), (12, 55), (10, 30), (0, 0)],
    "asset_quality_metric":     "gross_npa_pct",
    "asset_quality_thresholds": [(0, 100), (1, 70), (3, 40), (5, 15), (8, 0)],  # lower = better
    "cwip_penalty_threshold":   None,   # disabled
    "disable_liquidity_score":  True,
    "bs_weights":               {"leverage": 0.35, "liquidity": 0.00, "asset": 0.35, "networth": 0.30},
    "skip_cf_scoring":          True,
    "composite_weights":        {"pl": 0.50, "bs": 0.50, "cf": 0.00},
}
```

---

### 3.2 Information Technology

**Applies to**: TCS, Infosys, Wipro, HCL Tech, Persistent, Mphasis, LTIMindtree.

**Key structural differences**:
- Asset-light business model → very low or zero debt
- Very high CFO/PAT ratio due to cash-generative nature (debtors + advance billing)
- High OPM (20–35%) is standard, not exceptional
- Revenue growth more moderate for mature IT; faster for mid/small caps
- CWIP is negligible; IT companies don't build factories

#### P&L Overrides

| Metric | Generic | IT Override | Rationale |
|---|---|---|---|
| OPM ≥ 25% → 100 | Standard | **OPM ≥ 20% → 100** | IT OPM 20–35% is industry norm |
| OPM brackets | 0–35% | 10–35% | Compress lower end; IT rarely has < 10% |
| Revenue CAGR ≥ 20% → 100 | Standard | Same (growth rewarded equally) | — |
| PAT CAGR | Standard | Standard | — |
| Loss year penalty | 20/year | Same | Rare for IT; keep as signal |

#### Balance Sheet Overrides

| Metric | Generic | IT Override |
|---|---|---|
| D/E ≤ 0.25 → 100 | Standard | **Tightened**: ≤ 0.10 → 100, ≤ 0.25 → 80, ≤ 0.50 → 45, > 0.50 → 15 |
| CWIP penalty threshold | 15% | **5%** (IT carrying > 5% CWIP is unusual) |
| Asset CAGR ≥ 15% → 100 | Standard | **7–12% optimal**: ≥ 12% → 100, 7–12% → 75, 3–7% → 50, 0–3% → 25 |

#### Cash Flow Overrides

```
IT firms generate very high CFO/PAT (often > 1.0 naturally).
Lower ceiling: CFO/PAT ≥ 0.9 → 100 (not 1.2).
```

| CFO/PAT | Generic Score | IT Score |
|---|---|---|
| ≥ 1.2 | 100 | 100 |
| 0.9–1.2 | 85 → interpolate | **100** |
| 0.8–0.9 | 65 | 80 |
| 0.5–0.8 | 40 | 55 |
| < 0.5 | 10 | 20 |

#### IT Config Dict

```python
IT_CONFIG = {
    "opm_thresholds":       [(20, 100), (15, 75), (10, 50), (5, 20), (0, 0)],
    "de_thresholds":        [(0.10, 100), (0.25, 80), (0.50, 45), (1.0, 20), (None, 15)],
    "cwip_penalty_threshold": 0.05,
    "ta_cagr_thresholds":   [(12, 100), (7, 75), (3, 50), (0, 25), (None, 0)],
    "cfo_pat_thresholds":   [(0.9, 100), (0.7, 80), (0.5, 55), (0.3, 30), (0.0, 10), (None, 0)],
}
```

---

### 3.3 Pharmaceuticals & Healthcare

**Applies to**: Sun Pharma, Dr Reddy's, Cipla, Aurobindo, Apollo Hospitals, Fortis.

**Key structural differences**:
- R&D expenditure can be capitalized or expensed, causing lumpy PAT
- Regulatory risks (USFDA) can cause sudden one-time write-offs
- Generics have thinner margins (10–20%); innovators have higher (25–40%)
- CWIP common for API/formulation plant expansion
- Hospitals have higher CWIP and capex (physical infrastructure)

#### P&L Overrides

| Metric | Generic | Pharma Override |
|---|---|---|
| OPM ≥ 25% → 100 | Standard | **OPM ≥ 22% → 100** (generics rarely reach 25%) |
| Loss year tolerance | 20 pts/year | **−10 pts/year** for R&D-driven losses; max penalty = 20 |
| PAT CAGR | Standard | Standard (CAGR still meaningful) |

#### Balance Sheet Overrides

| Metric | Generic | Pharma Override |
|---|---|---|
| CWIP penalty | > 15% → −10 | **> 25% → −10** (greenfield plans need more CWIP) |
| D/E thresholds | Standard | Standard (pharma should be low-debt) |

#### Cash Flow Overrides

- R&D capex classified as investing activity → FCF appears more negative
- FCF margin threshold relaxed: **≥ 8% → 100** (vs generic 15%)

#### Pharma Config Dict

```python
PHARMA_CONFIG = {
    "opm_thresholds":         [(22, 100), (15, 75), (10, 50), (5, 20), (0, 0)],
    "loss_year_penalty":      10,
    "max_loss_year_penalty":  20,
    "cwip_penalty_threshold": 0.25,
    "fcf_margin_thresholds":  [(8, 100), (5, 75), (2, 50), (0, 25), (None, 0)],
}
```

---

### 3.4 Capital Goods & Infrastructure

**Applies to**: L&T, Bharat Forge, KEC International, IRB Infra, CESC, Siemens India.

**Key structural differences**:
- Revenue recognition on project completion → **lumpy PAT** is structurally normal
- High CWIP during project build phases is expected, not a red flag
- Project finance means D/E of 2–3× is acceptable
- Negative FCF is normal during construction; judge over full project cycle
- Order book is a better forward indicator than trailing revenue

#### P&L Overrides

| Metric | Generic | Infra Override |
|---|---|---|
| Loss year penalty | 20/year | **10/year** (project revenue timing causes lumpy profits) |
| OPM thresholds | 0–35% | **Compressed to 5–20%** (infra OPM 8–15% is standard) |

#### Balance Sheet Overrides

| Metric | Generic | Infra Override |
|---|---|---|
| D/E ≤ 1.0 → 65 | Standard | **Relaxed**: ≤ 1.5 → 65, ≤ 2.5 → 45, ≤ 3.5 → 25, > 3.5 → 10 |
| CWIP penalty | > 15% → −10 | **Disabled** completely |

#### Cash Flow Overrides

Negative FCF is expected for multi-year project companies. Adjust FCF margin:

| FCF Margin | Generic Score | Infra Score |
|---|---|---|
| ≥ 15% | 100 | 100 |
| 10–15% | 80 | 90 |
| 5–10% | 60 | 75 |
| 0–5% | 35 | 55 |
| −10 to 0% | 0 | 30 |
| < −10% | 0 | 10 |

#### Infra Config Dict

```python
INFRA_CONFIG = {
    "opm_thresholds":         [(18, 100), (12, 75), (8, 50), (4, 20), (0, 0)],
    "loss_year_penalty":      10,
    "max_loss_year_penalty":  20,
    "de_thresholds":          [(0.5, 100), (1.0, 80), (1.5, 65), (2.5, 45), (3.5, 25), (None, 10)],
    "cwip_penalty_threshold": None,   # disabled
    "fcf_margin_thresholds":  [(10, 100), (5, 75), (0, 55), (-10, 30), (None, 10)],
}
```

---

### 3.5 FMCG & Consumer Staples

**Applies to**: HUL, Nestle, Dabur, Marico, Britannia, Colgate, ITC.

**Key structural differences**:
- Mature businesses with **moderate** revenue growth (8–15% CAGR is exceptional)
- High OPM (18–40%) is standard; low debt is the norm
- Strong working capital discipline → high CFO/PAT naturally
- Brand moats mean PAT consistency is paramount

#### P&L Overrides

| Metric | Generic | FMCG Override |
|---|---|---|
| Revenue CAGR ≥ 20% → 100 | Standard | **≥ 12% → 100** (mature FMCG growing at 12% is excellent) |
| OPM ≥ 25% → 100 | Standard | **≥ 18% → 100** (FMCG margins 18–30% = healthy) |
| Loss year penalty | 20/year | **30/year** (FMCG losing money is a severe red flag) |

#### Balance Sheet Overrides

FMCG firms should be near debt-free. D/E > 0.3 is a **concern**:

| D/E | Generic | FMCG Override |
|---|---|---|
| ≤ 0.10 | 100 | 100 |
| ≤ 0.25 | 85 | 90 |
| ≤ 0.50 | 65 | **55** |
| ≤ 1.00 | 45 | **20** |
| > 1.00 | 25–10 | **5** |

#### FMCG Config Dict

```python
FMCG_CONFIG = {
    "rev_cagr_thresholds":    [(12, 100), (8, 80), (5, 60), (2, 35), (0, 15), (None, 0)],
    "opm_thresholds":         [(18, 100), (14, 80), (10, 55), (6, 25), (0, 0)],
    "loss_year_penalty":      30,
    "max_loss_year_penalty":  60,
    "de_thresholds":          [(0.10, 100), (0.25, 90), (0.50, 55), (1.0, 20), (None, 5)],
}
```

---

### 3.6 Metals, Mining & Commodities

**Applies to**: Tata Steel, JSW Steel, Hindalco, Vedanta, NMDC, Coal India.

**Key structural differences**:
- Revenue and PAT are **driven by commodity prices**, not management quality alone
- 5-year CAGR may miscapture cyclicality; **7-year CAGR preferred** to include a full cycle
- High capex for mines/smelters → high D/E and negative FCF are temporarily acceptable
- Volatility in margins is structural (not a quality signal)

#### P&L Overrides

| Metric | Generic | Metals Override |
|---|---|---|
| CAGR period | 5 years | **7 years** (capture full commodity cycle) |
| PAT CAGR range | −20% to 30% | **−40% to 50%** (commodity swings are wider) |
| OPM stability penalty | σ > 10% → −10 | **Disabled** (volatile margins are structural) |

#### Balance Sheet Overrides

D/E thresholds relaxed (capital-intensive, commodity-price cycles):

| D/E | Generic Score | Metals Score |
|---|---|---|
| ≤ 0.25 | 100 | 100 |
| ≤ 0.50 | 85 | 95 |
| ≤ 1.00 | 65 | 80 |
| ≤ 2.00 | 45 | **55** |
| ≤ 3.00 | 25 | **30** |
| > 3.00 | 10 | **10** |

#### Metals Config Dict

```python
METALS_CONFIG = {
    "pat_cagr_years":           7,
    "res_cagr_years":           7,
    "pat_cagr_thresholds":      [(30, 100), (20, 80), (10, 60), (0, 35), (-20, 15), (None, 0)],
    "de_thresholds":            [(0.5, 100), (1.0, 80), (2.0, 55), (3.0, 30), (None, 10)],
    "opm_stability_enabled":    False,  # disable σ adjustment
}
```

---

### 3.7 Real Estate (Realty)

**Applies to**: DLF, Godrej Properties, Prestige Estates, Sobha, Brigade.

**Key structural differences**:
- Revenue recognition on **project completion** (Ind AS 115) → multi-year revenue vacuums
- High inventory and CWIP are structural (land banks, under-construction projects)
- D/E of 2–3× common; even higher for land-heavy balance sheets
- Promoter pledging is a major risk metric (not captured in standard financials)

#### P&L Overrides

| Metric | Generic | Realty Override |
|---|---|---|
| Loss year tolerance | 20/year | **5/year** (project timing causes dips; don't over-penalize) |
| EPS consistency | Standard | **Lower weight** (40% → 15%) due to lumpy EPS |
| Revenue CAGR | Standard | **3-year CAGR preferred** (revenue can be zeroed out for years) |

#### Balance Sheet Overrides

| Metric | Generic | Realty Override |
|---|---|---|
| CWIP penalty | > 15% → −10 | **Disabled** (under-construction projects = high CWIP always) |
| Inventory | Not scored | *Future metric*: Inventory / Revenue (days) as liquidity signal |
| D/E thresholds | Standard | ≤ 1.0 → 85, ≤ 2.0 → 60, ≤ 3.0 → 35, > 3.0 → 10 |

#### Realty Config Dict

```python
REALTY_CONFIG = {
    "loss_year_penalty":      5,
    "max_loss_year_penalty":  15,
    "cwip_penalty_threshold": None,    # disabled
    "de_thresholds":          [(0.5, 100), (1.0, 85), (2.0, 60), (3.0, 35), (None, 10)],
    "pl_weights":             {"growth": 0.30, "margin": 0.35, "eps": 0.10, "consistency": 0.25},
}
```

---

### 3.8 Energy & Oil and Gas

**Applies to**: ONGC, Coal India, NTPC, Power Grid, Adani Green, Torrent Power.

**Key structural differences**:
- Regulated utilities: stable revenues but capped margins (CERC/SEBI regulated)
- Commodity-linked: ONGC/OIL revenue follows crude oil prices
- Very high capex for power plants/pipelines → high D/E and CWIP expected
- Dividend payout often mandated (PSUs) → FCF appears constrained

#### P&L Overrides

| Metric | Generic | Energy Override |
|---|---|---|
| OPM thresholds | 0–35% | **Adjusted**: ≥ 20% → 100 (regulated utilities cap upside) |
| Revenue CAGR | Standard | Standard (but interpret lower rates as structural, not bad) |

#### Balance Sheet Overrides

| Metric | Generic | Energy Override |
|---|---|---|
| D/E thresholds | Standard | ≤ 0.5 → 100, ≤ 1.5 → 75, ≤ 3.0 → 50, ≤ 5.0 → 25, > 5.0 → 10 |
| CWIP penalty | > 15% → −10 | **Disabled** (power plant build-up always has high CWIP) |

#### Energy Config Dict

```python
ENERGY_CONFIG = {
    "opm_thresholds":         [(20, 100), (14, 75), (8, 50), (4, 20), (0, 0)],
    "de_thresholds":          [(0.5, 100), (1.5, 75), (3.0, 50), (5.0, 25), (None, 10)],
    "cwip_penalty_threshold": None,    # disabled
}
```

---

## 4. Implementation Design

### 4.1 New File: `pipeline/sector_configs.py`

```python
"""
Sector-specific scoring configuration overrides.
All configs are plain dicts — no classes, no inheritance, no runtime magic.
Generic defaults are used when a key is absent from the config.
"""

# ── Generic defaults (reference only — not actually imported by scorer) ────────
GENERIC_DEFAULTS = {
    "revenue_key":              "sales",
    "opm_thresholds":           [(25, 100), (20, 85), (15, 65), (10, 45), (5, 25), (0, 0)],
    "rev_cagr_thresholds":      [(20, 100), (15, 80), (10, 60), (5, 40), (0, 20), (None, 0)],
    "pat_cagr_thresholds":      [(25, 100), (20, 85), (15, 70), (10, 55), (5, 35), (0, 15), (None, 0)],
    "pat_cagr_years":           5,
    "loss_year_penalty":        20,
    "max_loss_year_penalty":    30,
    "disable_de_scoring":       False,
    "de_thresholds":            [(0.25, 100), (0.5, 85), (1.0, 65), (1.5, 45), (2.5, 25), (None, 10)],
    "cwip_penalty_threshold":   0.15,
    "ta_cagr_thresholds":       [(15, 100), (10, 75), (5, 50), (0, 25), (None, 0)],
    "res_cagr_thresholds":      [(15, 100), (10, 80), (5, 60), (0, 35), (None, 0)],
    "skip_cf_scoring":          False,
    "cfo_pat_thresholds":       [(1.2, 100), (1.0, 85), (0.8, 65), (0.5, 40), (0.0, 10), (None, 0)],
    "fcf_margin_thresholds":    [(0.15, 100), (0.10, 80), (0.05, 60), (0.0, 35), (None, 0)],
    "composite_weights":        {"pl": 0.40, "bs": 0.35, "cf": 0.25},
    "pl_weights":               {"growth": 0.25, "margin": 0.25, "eps": 0.25, "consistency": 0.25},
    "bs_weights":               {"leverage": 0.30, "liquidity": 0.20, "asset": 0.20, "networth": 0.30},
    "cf_weights":               {"operating": 0.40, "capex": 0.35, "financing": 0.25},
}

BFSI_CONFIG   = { ... }   # as defined in Section 3.1
IT_CONFIG     = { ... }   # as defined in Section 3.2
PHARMA_CONFIG = { ... }   # as defined in Section 3.3
INFRA_CONFIG  = { ... }   # as defined in Section 3.4
FMCG_CONFIG   = { ... }   # as defined in Section 3.5
METALS_CONFIG = { ... }   # as defined in Section 3.6
REALTY_CONFIG = { ... }   # as defined in Section 3.7
ENERGY_CONFIG = { ... }   # as defined in Section 3.8

SECTOR_CONFIG_MAP = {
    "Banks": BFSI_CONFIG, "Finance": BFSI_CONFIG, ...
}

def get_sector_config(sector: str | None) -> dict:
    return SECTOR_CONFIG_MAP.get(sector or "", {})
```

### 4.2 Modified `statement_scorer.py` — Bracket Helper

Replace hard-coded bracket tables with config-driven lookups:

```python
def _bracket_score(value: float | None, thresholds: list[tuple]) -> float:
    """
    Generic bracket scorer.
    thresholds: [(min_value_inclusive, score), ...] in DESCENDING order of value.
    Returns score for the first bracket where value >= min_value.
    None value returns 50 (neutral).
    """
    if value is None:
        return 50.0
    for min_val, score in thresholds:
        if min_val is None:  # catch-all / last bracket
            return float(score)
        if value >= min_val:
            return float(score)
    return 0.0
```

### 4.3 Integration into Orchestrator

```python
# pipeline/statement_scorer.py — updated compute function

from pipeline.sector_configs import get_sector_config

async def compute_statement_scores_for_stock(stock_id: int, sector: str = None):
    sector_cfg = get_sector_config(sector)

    pl = await _get_merged_statement(stock_id, "PL")
    bs = await _get_merged_statement(stock_id, "BS")
    cf = await _get_merged_statement(stock_id, "CF")

    pl_r = score_pl(pl["periods"], pl["data"], sector_config=sector_cfg) if pl else {}
    bs_r = score_bs(bs["periods"], bs["data"], sector_config=sector_cfg) if bs else {}
    cf_r = {} if sector_cfg.get("skip_cf_scoring") else (
        score_cf(cf["periods"], cf["data"], pl_data=pl["data"] if pl else None,
                 sector_config=sector_cfg) if cf else {}
    )

    cw = sector_cfg.get("composite_weights", {"pl": 0.40, "bs": 0.35, "cf": 0.25})
    pairs = [
        (pl_r.get("pl_score"), cw["pl"]),
        (bs_r.get("bs_score"), cw["bs"]),
        (cf_r.get("cf_score"), cw["cf"]),
    ]
    valid   = [(s, w) for s, w in pairs if s is not None and w > 0]
    total_w = sum(w for _, w in valid)
    composite = round(sum(s * (w / total_w) for s, w in valid), 3) if valid else None

    period_end = await _get_latest_period_end_any(stock_id)
    await _upsert_fundamental_scores(stock_id, period_end, pl_r, bs_r, cf_r, composite)
```

### 4.4 Fetching Sector for a Stock

The `stocks` table already has a `sector` column:

```sql
SELECT s.id, s.symbol, s.sector
FROM   stocks s
WHERE  s.is_active = TRUE
  AND  s.is_index  = FALSE;
```

The orchestrator `run_statement_score_all()` queries this and passes `sector` to each compute call:

```python
async def run_statement_score_all():
    sql = "SELECT id, symbol, sector FROM stocks WHERE is_active = TRUE AND is_index = FALSE"
    async with raw_connection() as conn:
        stocks = await conn.fetch(sql)
    for stock in stocks:
        await compute_statement_scores_for_stock(stock["id"], sector=stock["sector"])
```

---

## 5. Sector Detection

### 5.1 Sector Column in `stocks` Table

The `stocks.sector` column is populated during the fundamental scrape from screener.in. Ensure the scraper stores the sector string as-is (e.g., `"Banks"`, `"Technology"`, `"FMCG"`).

### 5.2 Fallback Handling

```python
def get_sector_config(sector: str | None) -> dict:
    """
    Returns the sector override config.
    Falls back to empty dict (generic thresholds) for:
      - None (not scraped)
      - Unknown sector strings
      - "Diversified" / conglomerates
    """
    if not sector:
        return {}
    config = SECTOR_CONFIG_MAP.get(sector)
    if config is None:
        # Partial match: some scrapers return "Private Banks" not "Banks"
        for key in SECTOR_CONFIG_MAP:
            if key.lower() in sector.lower():
                return SECTOR_CONFIG_MAP[key]
    return config or {}
```

### 5.3 Sector String Mapping Table

Use this to map screener.in sector strings to config keys:

| screener.in Sector | Config Key | Config |
|---|---|---|
| Banks | Banks | BFSI_CONFIG |
| Finance | Finance | BFSI_CONFIG |
| NBFC | Finance | BFSI_CONFIG |
| Technology | Technology | IT_CONFIG |
| Software & Services | Technology | IT_CONFIG |
| Healthcare | Healthcare | PHARMA_CONFIG |
| Pharmaceuticals | Pharmaceuticals | PHARMA_CONFIG |
| Capital Goods | Capital Goods | INFRA_CONFIG |
| Construction | Construction | INFRA_CONFIG |
| FMCG | FMCG | FMCG_CONFIG |
| Consumer Goods | Consumer Goods | FMCG_CONFIG |
| Metals & Mining | Metals & Mining | METALS_CONFIG |
| Real Estate | Real Estate | REALTY_CONFIG |
| Power | Power | ENERGY_CONFIG |
| Oil & Gas | Oil & Gas | ENERGY_CONFIG |
| *anything else* | — | Generic (empty dict) |

---

## 6. Validation & Rollout Plan

### 6.1 Per-Sector Validation Checklist

Before enabling a sector override in production, complete all of the following:

- [ ] Select 10 representative stocks from the sector (mix of large-cap and mid-cap)
- [ ] Run generic scoring and sector scoring for all 10 stocks
- [ ] Compare scores against analyst ratings from Screener.in / Trendlyne / Motilal consensus
- [ ] Validate that the **rank order** (best to worst) aligns with expert view for at least 7/10 stocks
- [ ] Test edge cases: new listing (1 year data), loss year, recently deleveraged stock
- [ ] Document threshold rationale in comments within the config dict
- [ ] A/B test: run nightly scorer with `score_version = 'v1_sector'` and compare vs `'v1'`
- [ ] Confirm `stock_ratings` still populate correctly after sector scoring

### 6.2 Phased Rollout

| Phase | Scope | Timeline |
|---|---|---|
| Phase 0 | Generic scoring only (all sectors) | Immediately after `fundamental_scores` table created |
| Phase 1 | Add BFSI and IT configs (highest divergence from generic) | After Phase 0 validation |
| Phase 2 | Add Pharma, FMCG, Infra configs | After Phase 1 A/B testing passes |
| Phase 3 | Add Metals, Realty, Energy configs | After Phase 2 validation |
| Phase 4 | TTM (quarterly) scoring support | Future sprint |

### 6.3 Score Version Strategy

Use `score_version` column to A/B compare without losing historical data:

```
v1       = generic scoring (all sectors use same thresholds)
v1_bfsi  = generic + BFSI override applied to banking stocks
v2       = full sector-specific scoring enabled organization-wide
```

```sql
-- Compare generic vs sector scores for banks
SELECT s.symbol,
       generic.composite_fundamental_score AS generic_score,
       sector.composite_fundamental_score  AS sector_score
FROM   stocks s
JOIN   fundamental_scores generic ON generic.stock_id = s.id AND generic.score_version = 'v1'
JOIN   fundamental_scores sector  ON sector.stock_id  = s.id AND sector.score_version  = 'v1_bfsi'
WHERE  s.sector LIKE '%Bank%'
ORDER  BY generic_score DESC;
```

### 6.4 Metrics to Track

| Metric | Target | Method |
|---|---|---|
| Rank correlation vs. analyst consensus | Spearman ρ > 0.65 | Manual spot check for 10 stocks/sector |
| Score distribution | 10–90 range, no clustering at extremes | `SELECT MIN, MAX, AVG, STDDEV FROM fundamental_scores` |
| Zero-scoring rate | < 5% of stocks score 0 or 100 | Histogram query |
| Stability across re-runs | Same result from same data | Determinism test (run twice, diff output) |
| Coverage gap | < 10% missing scores (NULL composite) | Count NULLs in `composite_fundamental_score` |
