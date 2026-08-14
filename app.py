import os
import json
import uuid
import tempfile
from datetime import datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, abort
from dotenv import load_dotenv

from database import SessionLocal, engine, Base
from models import ProductCostVersion, ProductCost
from sqlalchemy import func

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

with app.app_context():
    Base.metadata.create_all(bind=engine)

PREVIEW_DIR = os.path.join(tempfile.gettempdir(), "cost_app_previews")
os.makedirs(PREVIEW_DIR, exist_ok=True)

REQUIRED_COLUMNS = ["Product Name", "Product Category", "Unit", "HYD", "BLR", "MUM", "PUNE", "NCR"]
LOCATIONS = ["HYD", "BLR", "MUM", "PUNE", "NCR"]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "xlsx"


def safe_float(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() == "nan" or s == "<NA>":
        return None
    try:
        f = float(s)
        return f
    except (ValueError, TypeError):
        raise ValueError(f"Invalid numeric cost value: {val}")


def normalize_text(val):
    if val is None:
        return ""
    return str(val).strip().lower()


def validate_version_date(value):
    if not value:
        raise ValueError("Version Date is required.")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Version Date must be in YYYY-MM-DD format.")


def parse_excel(file_stream):
    import pandas as pd
    df = pd.read_excel(file_stream, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    def is_blank(val):
        if val is None:
            return True
        if isinstance(val, float) and str(val) == "nan":
            return True
        s = str(val).strip()
        return s == "" or s.lower() == "nan" or s == "<NA>"

    records = []
    for idx, row in df.iterrows():
        raw_name = row.get("Product Name", "")
        if is_blank(raw_name):
            continue
        product_name = str(raw_name).strip()
        if not product_name:
            continue

        raw_cat = row.get("Product Category", "")
        product_category = None if is_blank(raw_cat) else str(raw_cat).strip()

        raw_unit = row.get("Unit", "")
        unit = None if is_blank(raw_unit) else str(raw_unit).strip()

        for loc in LOCATIONS:
            cost = safe_float(row.get(loc))
            records.append({
                "product_name": product_name,
                "product_category": product_category,
                "unit": unit,
                "location": loc,
                "cost": cost,
            })
    return records


def save_preview_to_disk(records, metadata):
    token = str(uuid.uuid4())
    path = os.path.join(PREVIEW_DIR, token + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"records": records, "metadata": metadata}, f)
    return token


def load_preview_from_disk(token):
    path = os.path.join(PREVIEW_DIR, token + ".json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_preview_from_disk(token):
    path = os.path.join(PREVIEW_DIR, token + ".json")
    if os.path.exists(path):
        os.remove(path)


def clear_session_preview():
    session.pop("preview_token", None)
    session.pop("preview_is_base", None)


@app.route("/")
def dashboard():
    db = SessionLocal()
    try:
        base = db.query(ProductCostVersion).filter_by(is_base=1).first()
        total_versions = db.query(ProductCostVersion).count()
        latest = db.query(ProductCostVersion).order_by(ProductCostVersion.created_at.desc()).first()
        latest_count = 0
        if latest:
            latest_count = db.query(ProductCost).filter_by(version_id=latest.id).count()
        return render_template("dashboard.html",
                               base_exists=base is not None,
                               base_name=base.name if base else None,
                               total_versions=total_versions,
                               latest_version=latest,
                               latest_product_count=latest_count)
    finally:
        db.close()


@app.route("/upload-base", methods=["GET", "POST"])
def upload_base():
    db = SessionLocal()
    try:
        existing_base = db.query(ProductCostVersion).filter_by(is_base=1).first()
        if existing_base and request.method == "GET":
            return render_template("upload_base.html", existing_base=existing_base)

        if request.method == "POST":
            if existing_base:
                flash("A Base Price already exists. Delete it first before creating a new one.", "error")
                return redirect(url_for("upload_base"))

            version_name = request.form.get("version_name", "").strip()
            version_date = request.form.get("version_date", "").strip()

            if not version_name or not version_date:
                flash("Version Name and Version Date are required.", "error")
                return redirect(url_for("upload_base"))

            try:
                validate_version_date(version_date)
            except ValueError as e:
                flash(str(e), "error")
                return redirect(url_for("upload_base"))

            if "file" not in request.files:
                flash("No file uploaded.", "error")
                return redirect(url_for("upload_base"))

            file = request.files["file"]
            if file.filename == "":
                flash("No file selected.", "error")
                return redirect(url_for("upload_base"))

            if not allowed_file(file.filename):
                flash("Only .xlsx files are allowed.", "error")
                return redirect(url_for("upload_base"))

            try:
                records = parse_excel(file)
            except Exception as e:
                flash(f"Invalid Excel file: {str(e)}", "error")
                return redirect(url_for("upload_base"))

            if not records:
                flash("No valid product records found in the Excel file.", "error")
                return redirect(url_for("upload_base"))

            preview = {}
            for rec in records:
                key = (rec["product_name"], rec["location"])
                preview[key] = rec

            preview_records = [v for v in preview.values()]
            token = save_preview_to_disk(preview_records, {
                "version_name": version_name,
                "version_date": version_date,
                "is_base": True,
            })
            session["preview_token"] = token
            session["preview_is_base"] = True

            return render_template("upload_base.html",
                                   preview=True,
                                   version_name=version_name,
                                   version_date=version_date,
                                   preview_records=preview_records)

        return render_template("upload_base.html", existing_base=existing_base, preview=False)
    finally:
        db.close()


@app.route("/save-base", methods=["POST"])
def save_base():
    db = SessionLocal()
    try:
        token = session.get("preview_token")
        if not token:
            flash("No preview data found. Please upload a file first.", "error")
            return redirect(url_for("upload_base"))

        preview_data = load_preview_from_disk(token)
        if not preview_data:
            flash("Preview data expired or missing. Please upload again.", "error")
            clear_session_preview()
            return redirect(url_for("upload_base"))

        metadata = preview_data["metadata"]
        records = preview_data["records"]

        if not metadata.get("is_base"):
            flash("Invalid preview session.", "error")
            clear_session_preview()
            delete_preview_from_disk(token)
            return redirect(url_for("upload_base"))

        existing_base = db.query(ProductCostVersion).filter_by(is_base=1).first()
        if existing_base:
            flash("A Base Price already exists.", "error")
            clear_session_preview()
            delete_preview_from_disk(token)
            return redirect(url_for("upload_base"))

        version_name = metadata["version_name"]
        version_date = metadata["version_date"]

        duplicate = db.query(ProductCostVersion).filter_by(name=version_name).first()
        if duplicate:
            flash(f"Version name '{version_name}' already exists.", "error")
            clear_session_preview()
            delete_preview_from_disk(token)
            return redirect(url_for("upload_base"))

        version = ProductCostVersion(
            name=version_name,
            version_date=version_date,
            is_base=1,
        )
        db.add(version)
        db.flush()

        db.bulk_insert_mappings(ProductCost, [
            {
                "version_id": version.id,
                "product_name": rec["product_name"],
                "product_category": rec["product_category"],
                "unit": rec["unit"],
                "location": rec["location"],
                "cost": rec["cost"],
            }
            for rec in records
        ])

        db.commit()

        clear_session_preview()
        delete_preview_from_disk(token)

        flash("Base Price saved successfully.", "success")
        return redirect(url_for("versions"))
    except Exception as e:
        db.rollback()
        flash(f"Failed to save Base Price: {str(e)}", "error")
        return redirect(url_for("upload_base"))
    finally:
        db.close()


@app.route("/upload-version", methods=["GET", "POST"])
def upload_version():
    if request.method == "POST":
        version_name = request.form.get("version_name", "").strip()
        version_date = request.form.get("version_date", "").strip()

        if not version_name or not version_date:
            flash("Version Name and Version Date are required.", "error")
            return redirect(url_for("upload_version"))

        try:
            validate_version_date(version_date)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(url_for("upload_version"))

        if "file" not in request.files:
            flash("No file uploaded.", "error")
            return redirect(url_for("upload_version"))

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected.", "error")
            return redirect(url_for("upload_version"))

        if not allowed_file(file.filename):
            flash("Only .xlsx files are allowed.", "error")
            return redirect(url_for("upload_version"))

        try:
            records = parse_excel(file)
        except Exception as e:
            flash(f"Invalid Excel file: {str(e)}", "error")
            return redirect(url_for("upload_version"))

        if not records:
            flash("No valid product records found in the Excel file.", "error")
            return redirect(url_for("upload_version"))

        token = save_preview_to_disk(records, {
            "version_name": version_name,
            "version_date": version_date,
            "is_base": False,
        })
        session["preview_token"] = token
        session["preview_is_base"] = False

        return render_template("upload_version.html",
                               preview=True,
                               version_name=version_name,
                               version_date=version_date,
                               preview_records=records)

    return render_template("upload_version.html", preview=False)


@app.route("/save-version", methods=["POST"])
def save_version():
    db = SessionLocal()
    try:
        token = session.get("preview_token")
        if not token:
            flash("No preview data found. Please upload a file first.", "error")
            return redirect(url_for("upload_version"))

        preview_data = load_preview_from_disk(token)
        if not preview_data:
            flash("Preview data expired or missing. Please upload again.", "error")
            clear_session_preview()
            return redirect(url_for("upload_version"))

        metadata = preview_data["metadata"]
        records = preview_data["records"]

        if metadata.get("is_base"):
            flash("Invalid preview session.", "error")
            clear_session_preview()
            delete_preview_from_disk(token)
            return redirect(url_for("upload_version"))

        version_name = metadata["version_name"]
        version_date = metadata["version_date"]

        duplicate = db.query(ProductCostVersion).filter_by(name=version_name).first()
        if duplicate:
            flash(f"Version name '{version_name}' already exists.", "error")
            clear_session_preview()
            delete_preview_from_disk(token)
            return redirect(url_for("upload_version"))

        version = ProductCostVersion(
            name=version_name,
            version_date=version_date,
            is_base=0,
        )
        db.add(version)
        db.flush()

        db.bulk_insert_mappings(ProductCost, [
            {
                "version_id": version.id,
                "product_name": rec["product_name"],
                "product_category": rec["product_category"],
                "unit": rec["unit"],
                "location": rec["location"],
                "cost": rec["cost"],
            }
            for rec in records
        ])

        db.commit()

        clear_session_preview()
        delete_preview_from_disk(token)

        flash("Version saved successfully.", "success")
        return redirect(url_for("versions"))
    except Exception as e:
        db.rollback()
        flash(f"Failed to save version: {str(e)}", "error")
        return redirect(url_for("upload_version"))
    finally:
        db.close()


@app.route("/versions")
def versions():
    db = SessionLocal()
    try:
        versions_list = db.query(
            ProductCostVersion,
            func.count(ProductCost.id).label("product_count")
        ).outerjoin(
            ProductCost, ProductCost.version_id == ProductCostVersion.id
        ).group_by(
            ProductCostVersion.id
        ).order_by(
            ProductCostVersion.created_at.desc()
        ).all()

        result = []
        for v, product_count in versions_list:
            result.append({
                "id": v.id,
                "name": v.name,
                "version_date": v.version_date,
                "is_base": bool(v.is_base),
                "product_count": product_count,
                "created_at": v.created_at,
            })
        return render_template("versions.html", versions=result)
    finally:
        db.close()


@app.route("/version/<int:version_id>")
def version_detail(version_id):
    db = SessionLocal()
    try:
        version = db.query(ProductCostVersion).filter_by(id=version_id).first()
        if not version:
            abort(404)
        other_versions = db.query(ProductCostVersion).filter(ProductCostVersion.id != version_id).order_by(ProductCostVersion.created_at.desc()).all()
        return render_template("comparison.html",
                               current_version=version,
                               other_versions=other_versions)
    finally:
        db.close()


@app.route("/version/<int:version_id>/matrix")
def version_matrix(version_id):
    db = SessionLocal()
    try:
        version = db.query(ProductCostVersion).filter_by(id=version_id).first()
        if not version:
            abort(404)

        costs = db.query(ProductCost).filter_by(version_id=version_id).all()

        products = {}
        for c in costs:
            key = normalize_text(c.product_name)
            if key not in products:
                products[key] = {
                    "product_name": c.product_name,
                    "product_category": c.product_category,
                    "unit": c.unit,
                    "costs": {},
                }
            products[key]["costs"][c.location] = c.cost

        matrix_rows = []
        for prod in products.values():
            vals = [v for v in prod["costs"].values() if v is not None]
            avg = sum(vals) / len(vals) if vals else None

            deviations = {}
            for loc in LOCATIONS:
                cost = prod["costs"].get(loc)
                if cost is not None and avg is not None:
                    deviations[loc] = cost - avg
                else:
                    deviations[loc] = None

            matrix_rows.append({
                "product_name": prod["product_name"],
                "product_category": prod["product_category"],
                "unit": prod["unit"],
                "costs": prod["costs"],
                "average": avg,
                "deviations": deviations,
            })

        return render_template("matrix.html",
                               version=version,
                               locations=LOCATIONS,
                               matrix_rows=matrix_rows)
    finally:
        db.close()


def build_comparison_rows(current_id, compare_id=None, compare_base=False, search="", category_filter="", location_filter="", summary_filter=""):
    db = SessionLocal()
    try:
        current_version = db.query(ProductCostVersion).filter_by(id=current_id).first()
        if not current_version:
            return None, None

        compare_version = None
        if compare_id:
            compare_version = db.query(ProductCostVersion).filter_by(id=compare_id).first()
        elif compare_base:
            compare_version = db.query(ProductCostVersion).filter_by(is_base=1).first()

        if compare_base and not compare_version:
            return None, None
        if compare_id and not compare_version:
            return None, None

        current_costs = db.query(ProductCost).filter_by(version_id=current_id).all()
        compare_costs = db.query(ProductCost).filter_by(version_id=compare_version.id).all() if compare_version else []

        current_map = {}
        for c in current_costs:
            key = normalize_text(c.product_name)
            if key not in current_map:
                current_map[key] = {}
            current_map[key][c.location] = {
                "product_name": c.product_name,
                "product_category": c.product_category,
                "unit": c.unit,
                "location": c.location,
                "cost": c.cost,
            }

        compare_map = {}
        for c in compare_costs:
            key = normalize_text(c.product_name)
            if key not in compare_map:
                compare_map[key] = {}
            compare_map[key][c.location] = {
                "product_name": c.product_name,
                "product_category": c.product_category,
                "unit": c.unit,
                "location": c.location,
                "cost": c.cost,
            }

        def matches_summary(r):
            if not summary_filter:
                return True
            if summary_filter == "increased":
                return r["diff"] is not None and r["diff"] > 0
            if summary_filter == "decreased":
                return r["diff"] is not None and r["diff"] < 0
            if summary_filter == "unchanged":
                return r["diff"] is not None and r["diff"] == 0
            if summary_filter == "missing":
                return r["diff"] is None
            return True

        all_keys = set(current_map.keys()) | set(compare_map.keys())
        rows = []
        for key in sorted(all_keys):
            current_locs = current_map.get(key, {})
            compare_locs = compare_map.get(key, {})
            all_locs = set(current_locs.keys()) | set(compare_locs.keys())
            for loc in sorted(all_locs):
                c_rec = current_locs.get(loc)
                p_rec = compare_locs.get(loc)

                c_cost = c_rec["cost"] if c_rec else None
                p_cost = p_rec["cost"] if p_rec else None

                product_name = c_rec["product_name"] if c_rec else (p_rec["product_name"] if p_rec else key)
                category = c_rec["product_category"] if c_rec else (p_rec["product_category"] if p_rec else None)
                unit = c_rec["unit"] if c_rec else (p_rec["unit"] if p_rec else None)

                if search and search not in normalize_text(product_name):
                    continue
                if category_filter and normalize_text(category) != category_filter:
                    continue
                if location_filter and loc != location_filter:
                    continue

                diff = None
                diff_pct = None
                if c_cost is not None and p_cost is not None:
                    diff = c_cost - p_cost
                    if p_cost != 0:
                        diff_pct = (diff / p_cost) * 100

                row = {
                    "product_name": product_name,
                    "product_category": category,
                    "unit": unit,
                    "location": loc,
                    "current_cost": c_cost,
                    "compared_cost": p_cost,
                    "diff": diff,
                    "diff_pct": diff_pct,
                }
                if matches_summary(row):
                    rows.append(row)

        increased = sum(1 for r in rows if r["diff"] is not None and r["diff"] > 0)
        decreased = sum(1 for r in rows if r["diff"] is not None and r["diff"] < 0)
        unchanged = sum(1 for r in rows if r["diff"] is not None and r["diff"] == 0)
        missing = sum(1 for r in rows if r["diff"] is None)

        valid_pcts = [r["diff_pct"] for r in rows if r["diff_pct"] is not None and r["diff"] != 0]
        increase_pcts = [p for p in valid_pcts if p > 0]
        decrease_pcts = [p for p in valid_pcts if p < 0]
        highest_increase = max(increase_pcts) if increase_pcts else None
        highest_decrease = min(decrease_pcts) if decrease_pcts else None

        summary = {
            "total": len(rows),
            "increased": increased,
            "decreased": decreased,
            "unchanged": unchanged,
            "missing": missing,
            "highest_increase": highest_increase,
            "highest_decrease": highest_decrease,
        }
        return rows, summary
    finally:
        db.close()


@app.route("/api/compare")
def api_compare():
    current_id = request.args.get("current_id", type=int)
    compare_id = request.args.get("compare_id", type=int)
    compare_base = request.args.get("compare_base")
    search = request.args.get("search", "").strip().lower()
    category_filter = request.args.get("category", "").strip().lower()
    location_filter = request.args.get("location", "").strip().upper()
    summary_filter = request.args.get("summary_filter", "").strip().lower()

    if not current_id:
        return jsonify({"error": "current_id is required"}), 400

    rows, summary = build_comparison_rows(current_id, compare_id, compare_base, search, category_filter, location_filter, summary_filter)
    if rows is None:
        return jsonify({"error": "Version not found"}), 404

    return jsonify({"rows": rows, "summary": summary})


@app.route("/api/export")
def api_export():
    current_id = request.args.get("current_id", type=int)
    compare_id = request.args.get("compare_id", type=int)
    compare_base = request.args.get("compare_base")
    search = request.args.get("search", "").strip().lower()
    category_filter = request.args.get("category", "").strip().lower()
    location_filter = request.args.get("location", "").strip().upper()
    summary_filter = request.args.get("summary_filter", "").strip().lower()

    if not current_id:
        return jsonify({"error": "current_id is required"}), 400

    rows, summary = build_comparison_rows(current_id, compare_id, compare_base, search, category_filter, location_filter, summary_filter)
    if rows is None:
        return jsonify({"error": "Version not found"}), 404

    db2 = SessionLocal()
    try:
        current_version = db2.query(ProductCostVersion).filter_by(id=current_id).first()
        compare_version = None
        if compare_id:
            compare_version = db2.query(ProductCostVersion).filter_by(id=compare_id).first()
        elif compare_base:
            compare_version = db2.query(ProductCostVersion).filter_by(is_base=1).first()
    finally:
        db2.close()

    current_name = current_version.name if current_version else "current"
    compare_name = compare_version.name if compare_version else "base"
    filename = f"comparison_{current_name}_vs_{compare_name}.csv".replace(" ", "_").replace("/", "_")

    csv_lines = ["Product Name,Product Category,Unit,Location,Current Cost,Compared Cost,Diff,Diff %"]
    for r in rows:
        def fmt(val):
            if val is None:
                return ""
            if isinstance(val, float):
                return f"{val:.2f}"
            return str(val)
        csv_lines.append(",".join([
            '"' + str(r["product_name"]).replace('"', '""') + '"',
            '"' + (r["product_category"] or "").replace('"', '""') + '"',
            '"' + (r["unit"] or "").replace('"', '""') + '"',
            r["location"],
            fmt(r["current_cost"]),
            fmt(r["compared_cost"]),
            fmt(r["diff"]),
            fmt(r["diff_pct"]),
        ]))

    from flask import Response
    return Response("\n".join(csv_lines), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/version/<int:version_id>/delete", methods=["POST"])
def delete_version(version_id):
    db = SessionLocal()
    try:
        version = db.query(ProductCostVersion).filter_by(id=version_id).first()
        if not version:
            abort(404)
        if version.is_base:
            flash("Base Price cannot be deleted.", "error")
            return redirect(url_for("versions"))

        db.delete(version)
        db.commit()
        flash("Version deleted successfully.", "success")
        return redirect(url_for("versions"))
    except Exception as e:
        db.rollback()
        flash(f"Failed to delete version: {str(e)}", "error")
        return redirect(url_for("versions"))
    finally:
        db.close()


if __name__ == "__main__":
    app.run(debug=False)
