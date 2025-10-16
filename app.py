# app.py
from flask import Flask, jsonify, abort, send_file
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError

_engine = None

def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("Missing DB_URL (or DATABASE_URL) environment variable.")
    # Normalize old 'postgres://' scheme to 'postgresql://'
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]
    _engine = create_engine(
        db_url,
        pool_pre_ping=True,
    )
    return _engine

def create_app():
    app = Flask(__name__)

    @app.get("/", endpoint="health")
    def health():
        return "<p>Server working!</p>"

    @app.get("/img", endpoint="show_img")
    def show_img():
        return send_file("amygdala.gif", mimetype="image/gif")

    @app.get("/dissociate/terms/<term_a>/<term_b>", endpoint="dissociate_terms")
    def dissociate_terms(term_a, term_b):
        """Find studies mentioning term_a but not term_b."""
        eng = get_engine()
        with eng.begin() as conn:
            term_a = term_a.replace("_", " ")
            term_b = term_b.replace("_", " ")

            query = text("""
                SELECT DISTINCT study_id, title
                FROM ns.metadata
                WHERE fts @@ plainto_tsquery(:term_a)
                  AND study_id NOT IN (
                      SELECT study_id FROM ns.metadata
                      WHERE fts @@ plainto_tsquery(:term_b)
                  )
                LIMIT 10;
            """)

            rows = conn.execute(query, {"term_a": term_a, "term_b": term_b}).mappings().all()

        return jsonify([dict(r) for r in rows])

    @app.get("/dissociate/locations/<coords_a>/<coords_b>", endpoint="dissociate_locations")
    def dissociate_locations(coords_a, coords_b):
        """Find studies mentioning coordinate A but not B."""
        eng = get_engine()
        with eng.begin() as conn:
            # parse coordinates (e.g., "0_-52_26")
            x1, y1, z1 = map(float, coords_a.split("_"))
            x2, y2, z2 = map(float, coords_b.split("_"))

            # 查離指定座標最近的 study（使用 ST_Distance）
            query = text("""
                SELECT DISTINCT m.study_id, m.title
                FROM ns.metadata AS m
                JOIN ns.coordinates AS c ON m.study_id = c.study_id
                WHERE ST_DWithin(c.geom, ST_SetSRID(ST_MakePoint(:x1, :y1, :z1), 4326)::geometry, 3)
                  AND m.study_id NOT IN (
                      SELECT study_id FROM ns.coordinates
                      WHERE ST_DWithin(c.geom, ST_SetSRID(ST_MakePoint(:x2, :y2, :z2), 4326)::geometry, 3)
                  )
                LIMIT 10;
            """)

            rows = conn.execute(query, {"x1": x1, "y1": y1, "z1": z1, "x2": x2, "y2": y2, "z2": z2}).mappings().all()

        return jsonify([dict(r) for r in rows])
    
    @app.get("/dissociate/terms_dual/<term_a>/<term_b>", endpoint="dissociate_terms_dual")
    def dissociate_terms_dual(term_a, term_b):
        """Return both A_not_B and B_not_A term dissociations."""
        eng = get_engine()
        with eng.begin() as conn:
            # --- A not B ---
            query_a = text("""
                SELECT DISTINCT study_id, title
                FROM ns.metadata
                WHERE fts @@ plainto_tsquery(:term_a)
                AND study_id NOT IN (
                    SELECT study_id FROM ns.metadata
                    WHERE fts @@ plainto_tsquery(:term_b)
                )
                LIMIT 10;
            """)
            rows_a = conn.execute(query_a, {"term_a": term_a, "term_b": term_b}).mappings().all()

            # --- B not A ---
            query_b = text("""
                SELECT DISTINCT study_id, title
                FROM ns.metadata
                WHERE fts @@ plainto_tsquery(:term_b)
                AND study_id NOT IN (
                    SELECT study_id FROM ns.metadata
                    WHERE fts @@ plainto_tsquery(:term_a)
                )
                LIMIT 10;
            """)
            rows_b = conn.execute(query_b, {"term_a": term_a, "term_b": term_b}).mappings().all()

        return jsonify({
            "A_not_B": [dict(r) for r in rows_a],
            "B_not_A": [dict(r) for r in rows_b]
        })
    
    @app.get("/dissociate/locations_dual/<coords_a>/<coords_b>", endpoint="dissociate_locations_dual")
    def dissociate_locations_dual(coords_a, coords_b):
        """Return both A_not_B and B_not_A spatial dissociations."""
        eng = get_engine()
        with eng.begin() as conn:
            x1, y1, z1 = map(float, coords_a.split("_"))
            x2, y2, z2 = map(float, coords_b.split("_"))

            # --- A not B ---
            query_a = text("""
                SELECT DISTINCT m.study_id, m.title
                FROM ns.metadata AS m
                JOIN ns.coordinates AS c ON m.study_id = c.study_id
                WHERE ST_DWithin(
                        c.geom,
                        ST_SetSRID(ST_MakePoint(:x1, :y1, :z1), 4326)::geometry,
                        3
                    )
                AND m.study_id NOT IN (
                    SELECT study_id FROM ns.coordinates
                    WHERE ST_DWithin(
                        geom,
                        ST_SetSRID(ST_MakePoint(:x2, :y2, :z2), 4326)::geometry,
                        3
                    )
                )
                LIMIT 10;
            """)

            # --- B not A ---
            query_b = text("""
                SELECT DISTINCT m.study_id, m.title
                FROM ns.metadata AS m
                JOIN ns.coordinates AS c ON m.study_id = c.study_id
                WHERE ST_DWithin(
                        c.geom,
                        ST_SetSRID(ST_MakePoint(:x2, :y2, :z2), 4326)::geometry,
                        3
                    )
                AND m.study_id NOT IN (
                    SELECT study_id FROM ns.coordinates
                    WHERE ST_DWithin(
                        geom,
                        ST_SetSRID(ST_MakePoint(:x1, :y1, :z1), 4326)::geometry,
                        3
                    )
                )
                LIMIT 10;
            """)

            rows_a = conn.execute(query_a, {
                "x1": x1, "y1": y1, "z1": z1,
                "x2": x2, "y2": y2, "z2": z2
            }).mappings().all()

            rows_b = conn.execute(query_b, {
                "x1": x1, "y1": y1, "z1": z1,
                "x2": x2, "y2": y2, "z2": z2
            }).mappings().all()

        return jsonify({
            "A_not_B": [dict(r) for r in rows_a],
            "B_not_A": [dict(r) for r in rows_b]
        })


    @app.get("/test_db", endpoint="test_db")
    
    def test_db():
        eng = get_engine()
        payload = {"ok": False, "dialect": eng.dialect.name}

        try:
            with eng.begin() as conn:
                # Ensure we are in the correct schema
                conn.execute(text("SET search_path TO ns, public;"))
                payload["version"] = conn.exec_driver_sql("SELECT version()").scalar()

                # Counts
                payload["coordinates_count"] = conn.execute(text("SELECT COUNT(*) FROM ns.coordinates")).scalar()
                payload["metadata_count"] = conn.execute(text("SELECT COUNT(*) FROM ns.metadata")).scalar()
                payload["annotations_terms_count"] = conn.execute(text("SELECT COUNT(*) FROM ns.annotations_terms")).scalar()

                # Samples
                try:
                    rows = conn.execute(text(
                        "SELECT study_id, ST_X(geom) AS x, ST_Y(geom) AS y, ST_Z(geom) AS z FROM ns.coordinates LIMIT 3"
                    )).mappings().all()
                    payload["coordinates_sample"] = [dict(r) for r in rows]
                except Exception:
                    payload["coordinates_sample"] = []

                try:
                    # Select a few columns if they exist; otherwise select a generic subset
                    rows = conn.execute(text("SELECT * FROM ns.metadata LIMIT 3")).mappings().all()
                    payload["metadata_sample"] = [dict(r) for r in rows]
                except Exception:
                    payload["metadata_sample"] = []

                try:
                    rows = conn.execute(text(
                        "SELECT study_id, contrast_id, term, weight FROM ns.annotations_terms LIMIT 3"
                    )).mappings().all()
                    payload["annotations_terms_sample"] = [dict(r) for r in rows]
                except Exception:
                    payload["annotations_terms_sample"] = []

            payload["ok"] = True
            return jsonify(payload), 200

        except Exception as e:
            payload["error"] = str(e)
            return jsonify(payload), 500

    return app

# WSGI entry point (no __main__)
app = create_app()
