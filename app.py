"""PackTrack – Flask application."""
import os
from datetime import date, datetime
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, send_file, jsonify)

import db
import reports
import ekokom_export

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "packtrack-dev-secret-change-me")

MONTHS_CZ = reports.MONTHS_CZ
QUARTER_MONTHS = reports.QUARTER_MONTHS


# ── Init ──────────────────────────────────────────────────────────────────────

@app.before_request
def _ensure_db():
    pass   # DB is initialised once at startup below


# ── Helpers ───────────────────────────────────────────────────────────────────

def _current_year_month():
    t = date.today()
    return t.year, t.month


def _quarter_of(month):
    return (month - 1) // 3 + 1


# ── Health / keep-alive ───────────────────────────────────────────────────────

@app.route("/ping")
def ping():
    """Lightweight keep-alive endpoint – called by UptimeRobot / cron."""
    return "pong", 200


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    stats = reports.get_dashboard_stats()
    return render_template("dashboard.html", stats=stats,
                           months_cz=MONTHS_CZ)


# ── Materials ─────────────────────────────────────────────────────────────────

@app.route("/materials")
def materials_list():
    mats = db.get_materials()
    return render_template("materials_list.html",
                           materials=mats,
                           ekokom_mats=reports.EKOKOM_MATERIALS,
                           naturpack_mats=reports.NATURPACK_MATERIALS)


@app.route("/materials/add", methods=["GET", "POST"])
def material_add():
    if request.method == "POST":
        data = _material_from_form()
        db.create_material(data)
        flash("Materiál byl přidán.", "success")
        return redirect(url_for("materials_list"))
    return render_template("material_form.html",
                           material=None,
                           ekokom_mats=reports.EKOKOM_MATERIALS,
                           ekokom_forms=reports.EKOKOM_FORMS,
                           ekokom_origins=reports.EKOKOM_ORIGINS,
                           ekokom_sheets=reports.EKOKOM_SHEETS,
                           naturpack_mats=reports.NATURPACK_MATERIALS,
                           naturpack_apps=reports.NATURPACK_APPENDICES,
                           action=url_for("material_add"))


@app.route("/materials/<int:mid>/edit", methods=["GET", "POST"])
def material_edit(mid):
    mat = db.get_material(mid)
    if not mat:
        flash("Materiál nenalezen.", "danger")
        return redirect(url_for("materials_list"))
    if request.method == "POST":
        data = _material_from_form()
        db.update_material(mid, data)
        flash("Materiál byl uložen.", "success")
        return redirect(url_for("materials_list"))
    return render_template("material_form.html",
                           material=dict(mat),
                           ekokom_mats=reports.EKOKOM_MATERIALS,
                           ekokom_forms=reports.EKOKOM_FORMS,
                           ekokom_origins=reports.EKOKOM_ORIGINS,
                           ekokom_sheets=reports.EKOKOM_SHEETS,
                           naturpack_mats=reports.NATURPACK_MATERIALS,
                           naturpack_apps=reports.NATURPACK_APPENDICES,
                           action=url_for("material_edit", mid=mid))


@app.route("/materials/<int:mid>/toggle", methods=["POST"])
def material_toggle(mid):
    db.toggle_material(mid)
    return redirect(url_for("materials_list"))


@app.route("/materials/<int:mid>/delete", methods=["POST"])
def material_delete(mid):
    ok, reason = db.delete_material(mid)
    if ok:
        flash("Materiál byl trvale smazán.", "success")
    else:
        flash(reason, "danger")
    return redirect(url_for("materials_list"))


def _material_from_form():
    f = request.form
    return {
        "name":               f.get("name", "").strip(),
        "description":        f.get("description", "").strip(),
        "weight_g":           round(float(f.get("weight_kg_input") or 0) * 1000, 4),
        "supplier":           f.get("supplier", "").strip(),
        "ekokom_sheet":       f.get("ekokom_sheet", "J1-1A"),
        "ekokom_material":    f.get("ekokom_material", "") or None,
        "ekokom_form":        f.get("ekokom_form", "soft"),
        "ekokom_origin":      f.get("ekokom_origin", "domestic_primary"),
        "naturpack_material": f.get("naturpack_material", "") or None,
        "naturpack_appendix": f.get("naturpack_appendix", "consumer"),
        "notes":              f.get("notes", "").strip(),
        "initial_stock":      int(f.get("initial_stock") or 0),
    }


# ── Receipts ──────────────────────────────────────────────────────────────────

@app.route("/receipts")
def receipts_list():
    year = request.args.get("year", type=int, default=date.today().year)
    month = request.args.get("month", type=int, default=None)
    mid = request.args.get("material_id", type=int, default=None)
    receipts = db.get_receipts(material_id=mid, year=year, month=month)
    mats = db.get_materials(active_only=False)
    years = db.get_available_years() or [date.today().year]
    return render_template("receipts_list.html",
                           receipts=receipts, materials=mats,
                           selected_year=year, selected_month=month,
                           selected_material=mid,
                           years=years, months_cz=MONTHS_CZ)


@app.route("/receipts/add", methods=["GET", "POST"])
def receipt_add():
    if request.method == "POST":
        f = request.form
        db.create_receipt({
            "material_id":      int(f["material_id"]),
            "receipt_date":     f["receipt_date"],
            "quantity_pcs":     int(f["quantity_pcs"]),
            "price_per_unit":   float(f["price_per_unit"]) if f.get("price_per_unit") else None,
            "supplier_invoice": f.get("supplier_invoice", "").strip() or None,
            "notes":            f.get("notes", "").strip() or None,
        })
        flash("Příjem byl zaznamenán.", "success")
        next_url = request.form.get("next") or url_for("receipts_list")
        return redirect(next_url)
    mats = db.get_materials(active_only=True)
    today = date.today().isoformat()
    pre_mid = request.args.get("material_id", type=int)
    return render_template("receipt_add.html",
                           materials=mats, today=today,
                           pre_material_id=pre_mid)


@app.route("/receipts/<int:rid>/delete", methods=["POST"])
def receipt_delete(rid):
    db.delete_receipt(rid)
    flash("Příjem byl smazán.", "warning")
    return redirect(request.referrer or url_for("receipts_list"))


# ── Inventory ─────────────────────────────────────────────────────────────────

@app.route("/inventory")
def inventory_list():
    year = request.args.get("year", type=int, default=date.today().year)
    years = db.get_available_years() or [date.today().year]
    if year not in years:
        years = sorted(set(years + [year]))
    months_done = db.get_months_with_inventory(year)
    return render_template("inventory_list.html",
                           year=year, years=years,
                           months_done=months_done,
                           months_cz=MONTHS_CZ,
                           today=date.today())


@app.route("/inventory/<int:year>/<int:month>", methods=["GET", "POST"])
def inventory_entry(year, month):
    mats = db.get_materials(active_only=True)

    if request.method == "POST":
        for m in mats:
            closing_str = request.form.get(f"closing_{m['id']}")
            if closing_str is not None and closing_str.strip() != "":
                closing = int(closing_str)
                notes = request.form.get(f"notes_{m['id']}", "").strip()
                db.upsert_inventory(m["id"], year, month, closing, notes)
        flash(f"Inventura za {MONTHS_CZ[month]} {year} byla uložena.", "success")
        return redirect(url_for("inventory_list", year=year))

    # Build table with opening, incoming, current closing (bulk queries)
    inv_year     = db.get_inventory_for_year(year)
    receipts_year = db.get_receipts_totals_for_year(year)
    prev_inv     = db.get_inventory_for_year(year - 1)
    inv_month_full = db.get_inventory_for_month(year, month)  # for notes
    inv_notes = {row["material_id"]: row for row in inv_month_full}

    rows = []
    for m in mats:
        c = reports._consumption_from_bulk(m, year, month, inv_year, receipts_year, prev_inv)
        inv_row = inv_notes.get(m["id"])
        rows.append({
            **dict(m),
            "opening": c["opening"],
            "incoming": c["incoming"],
            "closing": inv_row["closing_stock_pcs"] if inv_row else "",
            "notes_val": inv_row["notes"] if inv_row else "",
        })

    return render_template("inventory_entry.html",
                           year=year, month=month,
                           month_name=MONTHS_CZ[month],
                           rows=rows)


# ── History ───────────────────────────────────────────────────────────────────

@app.route("/history")
def history():
    year  = request.args.get("year",  type=int, default=date.today().year)
    month = request.args.get("month", type=int, default=None)
    if month == 0:
        month = None
    years = db.get_available_years() or [date.today().year]
    if year not in years:
        years = sorted(set(years + [year]))
    data = reports.get_history_table(year)
    mats = db.get_materials(active_only=False)
    return render_template("history.html",
                           year=year, month=month, years=years,
                           min_year=min(years), max_year=max(years),
                           data=data, materials=mats,
                           months_cz=MONTHS_CZ,
                           today=date.today())


# ── Country distribution ──────────────────────────────────────────────────────

COUNTRIES = [
    ("CZ", "Česká republika"),
    ("SK", "Slovensko"),
    ("DE", "Německo"),
    ("AT", "Rakousko"),
    ("FR", "Francie"),
    ("PL", "Polsko"),
    ("HU", "Maďarsko"),
    ("RO", "Rumunsko"),
    ("NL", "Nizozemsko"),
    ("BE", "Belgie"),
    ("IT", "Itálie"),
    ("CH", "Švýcarsko"),
]
COUNTRY_NAMES = {code: name for code, name in COUNTRIES}

REPORT_FLAGS = {
    "CZ": ("report_ekokom",    "EKO-KOM"),
    "SK": ("report_naturpack", "NATUR-PACK"),
    "DE": ("report_annual",    "Roční DE"),
    "FR": ("report_annual",    "Roční FR"),
}


@app.route("/distribution")
def distribution():
    year = request.args.get("year", type=int, default=date.today().year)
    quarter = request.args.get("quarter", type=int, default=_quarter_of(date.today().month))
    rows = db.get_distribution(year, quarter)
    total_pct = sum(float(r["percentage"]) for r in rows)
    years = list(range(date.today().year - 2, date.today().year + 2))
    return render_template("distribution.html",
                           year=year, quarter=quarter,
                           rows=rows, total_pct=total_pct,
                           countries=COUNTRIES,
                           country_names=COUNTRY_NAMES,
                           report_flags=REPORT_FLAGS,
                           years=years)


@app.route("/distribution/save", methods=["POST"])
def distribution_save():
    year = int(request.form["year"])
    quarter = int(request.form["quarter"])
    # Delete rows that were removed (empty percentage)
    country_codes = request.form.getlist("country_code")
    percentages   = request.form.getlist("percentage")
    re_flags      = request.form.getlist("report_ekokom")
    rn_flags      = request.form.getlist("report_naturpack")
    ra_flags      = request.form.getlist("report_annual")

    # First delete all existing rows for this period
    existing = db.get_distribution(year, quarter)
    for row in existing:
        db.delete_distribution_row(row["id"])

    for i, code in enumerate(country_codes):
        code = code.strip().upper()
        pct_str = percentages[i].strip() if i < len(percentages) else ""
        if not code or not pct_str:
            continue
        pct = float(pct_str)
        if pct == 0:
            continue
        country_name = COUNTRY_NAMES.get(code, code)
        db.upsert_distribution(year, quarter, code, country_name, pct,
                               code == "CZ",
                               code == "SK",
                               code in ("DE", "FR"))
    flash("Rozdělení tržeb bylo uloženo.", "success")
    return redirect(url_for("distribution", year=year, quarter=quarter))


@app.route("/distribution/copy", methods=["POST"])
def distribution_copy():
    from_year    = int(request.form["from_year"])
    from_quarter = int(request.form["from_quarter"])
    to_year      = int(request.form["to_year"])
    to_quarter   = int(request.form["to_quarter"])
    db.copy_distribution(from_year, from_quarter, to_year, to_quarter)
    flash(f"Rozdělení bylo zkopírováno do {to_quarter}Q {to_year}.", "success")
    return redirect(url_for("distribution", year=to_year, quarter=to_quarter))


# ── Reports ───────────────────────────────────────────────────────────────────

@app.route("/reports")
def reports_index():
    year = request.args.get("year", type=int, default=date.today().year)
    years = db.get_available_years() or [date.today().year]
    if year not in years:
        years = sorted(set(years + [year]))
    return render_template("reports_index.html",
                           year=year, years=years,
                           quarter_months=QUARTER_MONTHS,
                           months_cz=MONTHS_CZ,
                           today=date.today())


@app.route("/reports/ekokom/<int:year>/<int:quarter>")
def report_ekokom(year, quarter):
    consumption = reports.get_quarter_consumption(year, quarter)
    cell_data   = reports.build_ekokom_data(year, quarter)
    cz_pct      = db.get_country_pct(year, quarter, "CZ")
    dist        = db.get_distribution(year, quarter)
    months      = QUARTER_MONTHS[quarter]
    ekokom_label = {code: label for code, label, *_ in reports.EKOKOM_MATERIALS}
    form_label   = {code: label for code, label in reports.EKOKOM_FORMS}
    origin_label = {code: label for code, label in reports.EKOKOM_ORIGINS}
    return render_template("report_ekokom.html",
                           year=year, quarter=quarter,
                           consumption=consumption,
                           cell_data=cell_data,
                           cz_pct=cz_pct,
                           dist=dist,
                           months=months,
                           months_cz=MONTHS_CZ,
                           ekokom_label=ekokom_label,
                           form_label=form_label,
                           origin_label=origin_label)


@app.route("/reports/ekokom/<int:year>/<int:quarter>/export")
def report_ekokom_export(year, quarter):
    settings   = db.get_settings()
    cell_data  = reports.build_ekokom_data(year, quarter)
    buf        = ekokom_export.generate_ekokom(year, quarter, cell_data, settings)
    filename   = f"EKOKOM_{settings.get('ekokom_id','')}_Q{quarter}_{year}.xlsx"
    return send_file(buf, as_attachment=True,
                     download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/reports/naturpack/<int:year>/<int:quarter>")
def report_naturpack(year, quarter):
    consumption  = reports.get_quarter_consumption(year, quarter)
    np_data      = reports.build_naturpack_data(year, quarter)
    sk_pct       = db.get_country_pct(year, quarter, "SK")
    dist         = db.get_distribution(year, quarter)
    months       = QUARTER_MONTHS[quarter]
    mat_label    = {code: label for code, label in reports.NATURPACK_MATERIALS}
    np_groups    = reports.NATURPACK_GROUPS
    group_order  = ["SKLO","PLASTY bez PET","PET","PAPIER A LEPENKA",
                    "NÁPOJOVÝ KARTON","ŽELEZNÉ KOVY","HLINÍK","DREVO","OSTATNÉ"]
    return render_template("report_naturpack.html",
                           year=year, quarter=quarter,
                           consumption=consumption,
                           np_data=np_data,
                           sk_pct=sk_pct,
                           dist=dist,
                           months=months,
                           months_cz=MONTHS_CZ,
                           mat_label=mat_label,
                           np_groups=np_groups,
                           group_order=group_order)


@app.route("/reports/naturpack/<int:year>/<int:quarter>/export")
def report_naturpack_export(year, quarter):
    settings = db.get_settings()
    np_data  = reports.build_naturpack_data(year, quarter)
    buf      = ekokom_export.generate_naturpack_summary(year, quarter, np_data, settings)
    filename = f"NATURPACK_Q{quarter}_{year}.xlsx"
    return send_file(buf, as_attachment=True,
                     download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── Settings ──────────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        keys = ["company_name", "company_address", "company_ico", "company_dic",
                "ekokom_id", "contact_person", "contact_phone",
                "contact_email", "invoice_email"]
        data = {k: request.form.get(k, "").strip() for k in keys}
        db.save_settings(data)
        flash("Nastavení bylo uloženo.", "success")
        return redirect(url_for("settings"))
    s = db.get_settings()
    return render_template("settings.html", settings=s)


# ── API helpers ───────────────────────────────────────────────────────────────

@app.route("/api/material/<int:mid>/consumption")
def api_material_consumption(mid):
    """Return consumption for a material for a given month (AJAX)."""
    year  = request.args.get("year",  type=int, default=date.today().year)
    month = request.args.get("month", type=int, default=date.today().month)
    mat   = db.get_material(mid)
    if not mat:
        return jsonify({"error": "not found"}), 404
    c = reports.calc_consumption(mat, year, month)
    return jsonify(c)


# ── Template context processors ───────────────────────────────────────────────

@app.context_processor
def inject_globals():
    today = date.today()
    return {
        "current_year":  today.year,
        "current_month": today.month,
        "current_quarter": _quarter_of(today.month),
        "nav_year": today.year,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db.init_db()
    app.run(debug=True)
