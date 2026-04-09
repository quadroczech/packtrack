"""Consumption calculations and report data assembly for PackTrack."""
from datetime import date
import db

MONTHS_CZ = ["", "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
              "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec"]

QUARTER_MONTHS = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}


# ── EKO-KOM material catalogue ────────────────────────────────────────────────
# (code, label_cs, sheet, row_J1_1A, section)
# section: 'plastic_metal' → cols E-P per form+origin
#          'other'         → cols E,G,I,K per origin only
EKOKOM_MATERIALS = [
    ("PET_transparent",     "PET – průhledné",                    "J1-1A", 10, "plastic_metal"),
    ("PET_barevne_pruh",    "PET – průhledně barevné",            "J1-1A", 11, "plastic_metal"),
    ("PET_barevne_nepruh",  "PET – neprůhledně barevné",          "J1-1A", 12, "plastic_metal"),
    ("PE_transparent",      "PE – průhledné (sáčky, fólie)",      "J1-1A", 13, "plastic_metal"),
    ("PE_barevne",          "PE – barevné (sáčky, obálky)",       "J1-1A", 14, "plastic_metal"),
    ("PP_transparent",      "PP – průhledné",                     "J1-1A", 15, "plastic_metal"),
    ("PP_barevne",          "PP – barevné",                       "J1-1A", 16, "plastic_metal"),
    ("PS_transparent",      "PS – průhledné",                     "J1-1A", 17, "plastic_metal"),
    ("PS_barevne",          "PS – barevné",                       "J1-1A", 18, "plastic_metal"),
    ("XPS_transparent",     "XPS – průhledné",                    "J1-1A", 19, "plastic_metal"),
    ("XPS_barevne",         "XPS – barevné",                      "J1-1A", 20, "plastic_metal"),
    ("EPS_transparent",     "EPS (pěnový polystyrén) – průhledný","J1-1A", 21, "plastic_metal"),
    ("EPS_barevny",         "EPS – barevný",                      "J1-1A", 22, "plastic_metal"),
    ("PVC_transparent",     "PVC – průhledné",                    "J1-1A", 23, "plastic_metal"),
    ("PVC_barevne",         "PVC – barevné",                      "J1-1A", 24, "plastic_metal"),
    ("Jine_transparent",    "Jiné plasty – průhledné",            "J1-1A", 25, "plastic_metal"),
    ("Jine_barevne",        "Jiné plasty – barevné",              "J1-1A", 26, "plastic_metal"),
    ("Biodeg_transparent",  "Biologicky rozložitelné – průhledné","J1-1A", 27, "plastic_metal"),
    ("Biodeg_barevne",      "Biologicky rozložitelné – barevné",  "J1-1A", 28, "plastic_metal"),
    ("Al",                  "Hliník (Al)",                        "J1-1A", 31, "plastic_metal"),
    ("Fe",                  "Ocel / železo (Fe)",                 "J1-1A", 32, "plastic_metal"),
    ("Napojovy_karton",     "Nápojový karton",                    "J1-1A", 35, "plastic_metal"),
    ("Sklo_transparent",    "Sklo – průhledné",                   "J1-1A", 41, "other"),
    ("Sklo_barevne",        "Sklo – barevné",                     "J1-1A", 42, "other"),
    ("Papir",               "Papír",                              "J1-1A", 44, "other"),
    ("Hladka_lepenka",      "Hladká lepenka",                     "J1-1A", 45, "other"),
    ("Vlnita_lepenka",      "Vlnitá lepenka (krabice, kartony)",  "J1-1A", 46, "other"),
    ("Nasyvany_karton",     "Násývaný kartonáž",                  "J1-1A", 47, "other"),
    ("Drevo",               "Dřevo a dřevotříska",                "J1-1A", 49, "other"),
    ("Textil",              "Textil",                             "J1-1A", 51, "other"),
    ("Jine_ostatni",        "Jiné (ostatní)",                     "J1-1A", 52, "other"),
]

# For J1-1B the rows are shifted by +1 compared to J1-1A for plastics/metals;
# paper sub-table starts at row 42 (Papír), 43 Hladká, 44 Vlnitá, etc.
EKOKOM_J11B_OFFSET = 1  # plastic/metal rows: J1-1B_row = J1-1A_row + 1

EKOKOM_FORMS = [
    ("soft",       "Měkké / flexibilní  (sáčky, fólie, obálky)"),
    ("rigid_s",    "Pevné / duté do 3 L  (lahve, kelímky, malé krabičky)"),
    ("rigid_l",    "Pevné / duté nad 3 L  (velké nádoby, kanystry)"),
]

EKOKOM_ORIGINS = [
    ("domestic_primary",    "Primární materiál – vyrobeno/nakoupeno v ČR"),
    ("import_primary",      "Primární materiál – importováno do ČR"),
    ("domestic_recyclate",  "Recyklát – vyrobeno/nakoupeno v ČR"),
    ("import_recyclate",    "Recyklát – importováno do ČR"),
]

EKOKOM_SHEETS = [
    ("J1-1A", "J1-1A – Jednorázové, zpoplatněné, prodejní (retail)"),
    ("J1-1B", "J1-1B – Jednorázové, zpoplatněné, skupinové/přepravní"),
    ("J3",    "J3  – Jednorázové, neplacené"),
    ("J4",    "J4  – Jednorázové, exportované"),
]

# NATUR-PACK
NATURPACK_MATERIALS = [
    ("HDPE",          "HDPE (tvrdý polyetylén)"),
    ("LDPE",          "LDPE (mäkký polyetylén)"),
    ("PP",            "PP (polypropylén)"),
    ("PS",            "PS (polystyrén)"),
    ("PET",           "PET"),
    ("EPS",           "EPS (penový polystyrén)"),
    ("PVC",           "PVC"),
    ("ine_plasty",    "Iné plasty"),
    ("biodeg",        "Biologicky rozložiteľné plasty"),
    ("sklo",          "Sklo"),
    ("lepenka",       "Lepenka (kartón)"),
    ("papier",        "Papier"),
    ("zelezne_kovy",  "Železné kovy (Fe)"),
    ("hlinik",        "Hliník (Al)"),
    ("drevo",         "Drevo"),
    ("napojovy_kart", "Nápojový karton"),
    ("ostatne",       "Ostatné"),
]

NATURPACK_APPENDICES = [
    ("consumer", "Spotrebiteľské obaly  (Príloha č. 2)"),
    ("group",    "Skupinové a prepravné obaly  (Príloha č. 3)"),
]

# Slovak labels for NATUR-PACK material grouping in report
NATURPACK_GROUPS = {
    "sklo":         "SKLO",
    "HDPE":         "PLASTY bez PET",
    "LDPE":         "PLASTY bez PET",
    "PP":           "PLASTY bez PET",
    "PS":           "PLASTY bez PET",
    "EPS":          "PLASTY bez PET",
    "PVC":          "PLASTY bez PET",
    "ine_plasty":   "PLASTY bez PET",
    "biodeg":       "PLASTY bez PET",
    "PET":          "PET",
    "lepenka":      "PAPIER A LEPENKA",
    "papier":       "PAPIER A LEPENKA",
    "napojovy_kart":"NÁPOJOVÝ KARTON",
    "zelezne_kovy": "ŽELEZNÉ KOVY",
    "hlinik":       "HLINÍK",
    "drevo":        "DREVO",
    "ostatne":      "OSTATNÉ",
}


# ── Consumption calculation ───────────────────────────────────────────────────

def calc_consumption(material, year, month):
    """
    Returns dict with opening, incoming, closing, consumption (all in pcs)
    and weight_kg for consumption.
    """
    mid = material["id"]
    closing_row = db.get_inventory_entry(mid, year, month)
    closing = closing_row["closing_stock_pcs"] if closing_row else None

    prev = db.get_previous_closing(mid, year, month)
    if prev is None:
        opening = material["initial_stock"] or 0
    else:
        opening = prev

    incoming = db.get_receipts_by_month(mid, year, month)
    consumption = opening + int(incoming) - (closing if closing is not None else opening + int(incoming))

    weight_g = float(material["weight_g"] or 0)
    weight_kg = round(consumption * weight_g / 1000, 4) if consumption > 0 else 0

    return {
        "opening": opening,
        "incoming": int(incoming),
        "closing": closing,
        "consumption": consumption if closing is not None else None,
        "weight_kg": weight_kg,
        "weight_t": round(weight_kg / 1000, 6),
        "has_inventory": closing is not None,
    }


def _consumption_from_bulk(material, year, month, inv, receipts, prev_inv):
    """
    Calculate consumption for one material using pre-fetched bulk data.
    inv        = {(mid, month): closing}  for `year`
    receipts   = {(mid, month): total}    for `year`
    prev_inv   = {(mid, month): closing}  for `year-1`  (used for Jan opening)
    """
    mid = material["id"]
    closing = inv.get((mid, month))

    if month == 1:
        prev_closing = prev_inv.get((mid, 12))
    else:
        prev_closing = inv.get((mid, month - 1))

    opening = prev_closing if prev_closing is not None else (material["initial_stock"] or 0)
    incoming = receipts.get((mid, month), 0)

    has_inventory = closing is not None
    consumption = (opening + incoming - closing) if has_inventory else None

    weight_g = float(material["weight_g"] or 0)
    weight_kg = round(consumption * weight_g / 1000, 4) if consumption and consumption > 0 else 0

    return {
        "opening": opening,
        "incoming": incoming,
        "closing": closing,
        "consumption": consumption,
        "weight_kg": weight_kg,
        "weight_t": round(weight_kg / 1000, 6),
        "has_inventory": has_inventory,
    }


def get_monthly_summary(year, month):
    """Full consumption table for all materials for a given month (2 bulk queries)."""
    materials = db.get_materials(active_only=False)
    inv      = db.get_inventory_for_year(year)
    receipts = db.get_receipts_totals_for_year(year)
    prev_inv = db.get_inventory_for_year(year - 1)
    rows = []
    for m in materials:
        c = _consumption_from_bulk(m, year, month, inv, receipts, prev_inv)
        rows.append({**dict(m), **c})
    return rows


def get_history_table(year):
    """
    Returns { material_id: { 'material': {...}, 'months': {1: {...}, ...} } }
    Uses 3 bulk queries instead of N×12×3 individual queries.
    """
    materials = db.get_materials(active_only=False)
    inv      = db.get_inventory_for_year(year)
    receipts = db.get_receipts_totals_for_year(year)
    prev_inv = db.get_inventory_for_year(year - 1)

    result = {}
    for m in materials:
        months_data = {}
        for month in range(1, 13):
            months_data[month] = _consumption_from_bulk(m, year, month, inv, receipts, prev_inv)
        result[m["id"]] = {"material": dict(m), "months": months_data}
    return result


# ── Quarter report data ───────────────────────────────────────────────────────

def get_quarter_consumption(year, quarter):
    """
    Returns total consumption per material for a quarter.
    { material_id: { 'material': {...}, 'total_pcs': int, 'total_kg': float, 'total_t': float } }
    Uses 3 bulk queries for the whole quarter.
    """
    months = QUARTER_MONTHS[quarter]
    materials = db.get_materials(active_only=False)
    inv      = db.get_inventory_for_year(year)
    receipts = db.get_receipts_totals_for_year(year)
    prev_inv = db.get_inventory_for_year(year - 1)

    result = {}
    for m in materials:
        total_pcs = 0
        valid = True
        for month in months:
            c = _consumption_from_bulk(m, year, month, inv, receipts, prev_inv)
            if c["consumption"] is None:
                valid = False
                break
            total_pcs += c["consumption"]
        weight_g = float(m["weight_g"] or 0)
        total_kg = round(total_pcs * weight_g / 1000, 4)
        result[m["id"]] = {
            "material": dict(m),
            "total_pcs": total_pcs,
            "total_kg": total_kg,
            "total_t": round(total_kg / 1000, 6),
            "data_complete": valid,
        }
    return result


def build_ekokom_data(year, quarter):
    """
    Aggregates consumption for EKO-KOM report.
    Returns { (sheet, row, col): weight_t } for each material entry.
    CZ percentage is applied here.
    Only materials with include_in_reports=True are included.
    """
    cz_pct = db.get_country_pct(year, quarter, "CZ") / 100.0
    consumption = get_quarter_consumption(year, quarter)
    cell_data = {}

    for mid, entry in consumption.items():
        m = entry["material"]
        if not m.get("ekokom_material"):
            continue
        if not m.get("include_in_reports", True):
            continue
        weight_t_total = entry["total_t"]
        rc = m.get("report_country")
        # If material is pinned to a specific country, only count it for CZ
        if rc is None:
            weight_t_cz = round(weight_t_total * cz_pct, 6)
        elif rc == "CZ":
            weight_t_cz = round(weight_t_total, 6)
        else:
            continue  # pinned to another country, skip EKO-KOM

        sheet = m.get("ekokom_sheet", "J1-1A")
        row = _ekokom_row(m)
        col = _ekokom_col(m)

        if row and col:
            key = (sheet, row, col)
            cell_data[key] = round(cell_data.get(key, 0) + weight_t_cz, 6)

    return cell_data


def _ekokom_row(material):
    """Return the Excel row index for a material in its EKO-KOM sheet."""
    mat_code = material.get("ekokom_material")
    sheet = material.get("ekokom_sheet", "J1-1A")
    for code, label, base_sheet, row_j11a, section in EKOKOM_MATERIALS:
        if code == mat_code:
            if sheet == "J1-1B":
                if section == "plastic_metal":
                    return row_j11a + EKOKOM_J11B_OFFSET
                else:
                    # paper/wood in J1-1B: Papír starts at 42
                    offsets = {44: 42, 45: 43, 46: 44, 47: 45, 49: 47, 51: 49, 52: 50}
                    return offsets.get(row_j11a, row_j11a)
            return row_j11a
    return None


def _ekokom_col(material):
    """Return the 1-based Excel column index."""
    mat_code = material.get("ekokom_material")
    section = None
    for code, label, base_sheet, row_j11a, sec in EKOKOM_MATERIALS:
        if code == mat_code:
            section = sec
            break
    if section is None:
        return None

    origin = material.get("ekokom_origin", "domestic_primary")
    form = material.get("ekokom_form", "soft")

    if section == "plastic_metal":
        form_base = {"soft": 4, "rigid_s": 8, "rigid_l": 12}
        origin_offset = {
            "domestic_primary": 0, "import_primary": 1,
            "domestic_recyclate": 2, "import_recyclate": 3
        }
        return form_base.get(form, 4) + origin_offset.get(origin, 0) + 1
    else:
        # other: cols E(5), G(7), I(9), K(11)
        mapping = {
            "domestic_primary": 5, "import_primary": 7,
            "domestic_recyclate": 9, "import_recyclate": 11,
        }
        return mapping.get(origin, 5)


def build_naturpack_data(year, quarter):
    """
    Aggregates consumption for NATUR-PACK report.
    Returns { (appendix, material_code): weight_t } after applying SK%.
    Only materials with include_in_reports=True are included.
    """
    sk_pct = db.get_country_pct(year, quarter, "SK") / 100.0
    consumption = get_quarter_consumption(year, quarter)
    data = {}
    for mid, entry in consumption.items():
        m = entry["material"]
        np_mat = m.get("naturpack_material")
        if not np_mat:
            continue
        if not m.get("include_in_reports", True):
            continue
        appendix = m.get("naturpack_appendix", "consumer")
        rc = m.get("report_country")
        if rc is None:
            weight_t_sk = round(entry["total_t"] * sk_pct, 6)
        elif rc == "SK":
            weight_t_sk = round(entry["total_t"], 6)
        else:
            continue  # pinned to another country, skip NATUR-PACK
        key = (appendix, np_mat)
        data[key] = round(data.get(key, 0) + weight_t_sk, 6)
    return data


def get_dashboard_stats():
    """Data for the dashboard overview. Uses bulk queries."""
    today = date.today()
    year, month = today.year, today.month
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1

    materials = db.get_materials(active_only=True)
    n_active = len(materials)
    avg_prices = db.get_avg_prices_all()

    # Bulk fetch for current year (covers current + previous month if same year)
    inv      = db.get_inventory_for_year(year)
    receipts = db.get_receipts_totals_for_year(year)
    prev_inv = db.get_inventory_for_year(year - 1)

    # If prev month is in a different year, fetch that year's data
    if prev_year != year:
        prev_year_inv      = db.get_inventory_for_year(prev_year)
        prev_year_receipts = db.get_receipts_totals_for_year(prev_year)
        prev_year_prev_inv = prev_inv
    else:
        prev_year_inv      = inv
        prev_year_receipts = receipts
        prev_year_prev_inv = prev_inv

    cur_kg = cur_cost = prev_kg = prev_cost = 0.0
    for m in materials:
        mid = m["id"]
        price = avg_prices.get(mid, 0) or 0
        c_cur = _consumption_from_bulk(m, year, month, inv, receipts, prev_inv)
        cur_kg   += c_cur.get("weight_kg", 0) or 0
        cur_cost += (c_cur.get("consumption") or 0) * price
        c_prev = _consumption_from_bulk(m, prev_year, prev_month,
                                        prev_year_inv, prev_year_receipts, prev_year_prev_inv)
        prev_kg   += c_prev.get("weight_kg", 0) or 0
        prev_cost += (c_prev.get("consumption") or 0) * price

    cost_pct = (round((cur_cost - prev_cost) / prev_cost * 100, 1)
                if prev_cost > 0 else None)

    # Receipt count this month
    receipts_list = db.get_receipts(year=year, month=month)
    n_receipts = len(receipts_list)

    # Months with missing inventory this year
    inv_months = db.get_months_with_inventory(year)
    missing = [m for m in range(1, month) if m not in inv_months]

    return {
        "n_active": n_active,
        "cur_month": month,
        "cur_year": year,
        "cur_kg":   round(cur_kg, 2),
        "prev_kg":  round(prev_kg, 2),
        "cur_cost":  round(cur_cost, 0),
        "prev_cost": round(prev_cost, 0),
        "cost_pct":  cost_pct,
        "prev_month": prev_month,
        "n_receipts_this_month": n_receipts,
        "missing_inventory_months": missing,
        "month_name":      MONTHS_CZ[month],
        "prev_month_name": MONTHS_CZ[prev_month],
    }


def get_monthly_costs(year):
    """Total cost of consumed materials per month: {month: czk or None}."""
    materials  = db.get_materials(active_only=False)
    avg_prices = db.get_avg_prices_all()
    inv        = db.get_inventory_for_year(year)
    receipts   = db.get_receipts_totals_for_year(year)
    prev_inv   = db.get_inventory_for_year(year - 1)

    result = {}
    for month in range(1, 13):
        total = 0.0
        has_any = False
        for m in materials:
            price = avg_prices.get(m["id"], 0) or 0
            if not price:
                continue
            c = _consumption_from_bulk(m, year, month, inv, receipts, prev_inv)
            if c["has_inventory"] and (c["consumption"] or 0) > 0:
                total += c["consumption"] * price
                has_any = True
        result[month] = round(total, 0) if has_any else None
    return result


def get_marketing_report():
    """Stock-level overview for marketing-type materials, sorted by urgency."""
    today = date.today()
    year, month = today.year, today.month

    materials = db.get_materials(material_type="marketing")
    if not materials:
        return []

    avg_prices = db.get_avg_prices_all()
    inv      = db.get_inventory_for_year(year)
    receipts = db.get_receipts_totals_for_year(year)
    prev_inv = db.get_inventory_for_year(year - 1)
    prev2_inv    = db.get_inventory_for_year(year - 2)
    prev_receipts = db.get_receipts_totals_for_year(year - 1)

    report = []
    for m in materials:
        mid = m["id"]

        # Latest closing stock (search backwards up to current month)
        current_stock = None
        for mo in range(month, 0, -1):
            v = inv.get((mid, mo))
            if v is not None:
                current_stock = v
                break
        if current_stock is None:
            current_stock = prev_inv.get((mid, 12)) or m.get("initial_stock") or 0

        # Avg monthly consumption from last ≤3 months that have inventory
        consumptions = []
        for offset in range(6):
            mo = month - offset
            yi = year
            if mo <= 0:
                mo += 12
                yi = year - 1
            if yi == year:
                c = _consumption_from_bulk(m, yi, mo, inv, receipts, prev_inv)
            else:
                c = _consumption_from_bulk(m, yi, mo, prev_inv, prev_receipts, prev2_inv)
            if c["has_inventory"] and c["consumption"] is not None and c["consumption"] >= 0:
                consumptions.append(c["consumption"])
            if len(consumptions) >= 3:
                break

        avg_monthly = round(sum(consumptions) / len(consumptions)) if consumptions else None

        months_remaining = None
        if avg_monthly and avg_monthly > 0:
            months_remaining = round(current_stock / avg_monthly, 1)

        if current_stock == 0:
            status = "critical"
        elif months_remaining is None:
            status = "unknown"
        elif months_remaining < 1:
            status = "critical"
        elif months_remaining < 2:
            status = "warning"
        else:
            status = "ok"

        report.append({
            "material":        dict(m),
            "current_stock":   current_stock,
            "avg_monthly":     avg_monthly,
            "months_remaining": months_remaining,
            "status":          status,
            "price":           avg_prices.get(mid),
        })

    order = {"critical": 0, "warning": 1, "ok": 2, "unknown": 3}
    report.sort(key=lambda x: (order.get(x["status"], 3), x["current_stock"] or 0))
    return report
