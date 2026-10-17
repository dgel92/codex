"""Pañol / Intendencia — MVP académico HU-01 a HU-06."""
from __future__ import annotations

import argparse
import functools
import os
import secrets
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
UNITS = ("unidad", "litro", "kg")
CATEGORIES = ("Limpieza", "Seguridad", "Herramientas", "Mantenimiento", "Otros")
LOCATIONS = ("Puerta 1", "Puerta 2", "Puerta 3", "Estante 1", "Estante 2", "Cajón Auxiliar 3")
SECTORS = ("Molino", "Fabricación", "Mantenimiento", "Tareas Generales", "Tarea POES")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('admin','operario'))
);
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY, code TEXT NOT NULL, code_key TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE,
 category TEXT NOT NULL, unit TEXT NOT NULL CHECK(unit IN ('unidad','litro','kg')),
 location TEXT NOT NULL, stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
 minimum INTEGER NOT NULL CHECK(minimum > 0),
 maximum INTEGER NOT NULL CHECK(maximum > minimum),
 updated_at TEXT NOT NULL, updated_by INTEGER NOT NULL REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS threshold_changes (
 id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id),
 minimum INTEGER NOT NULL, maximum INTEGER NOT NULL,
 user_id INTEGER NOT NULL REFERENCES users(id), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS movements (
 id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id),
 kind TEXT NOT NULL CHECK(kind IN ('entrada','salida')),
 quantity INTEGER NOT NULL CHECK(quantity > 0),
 sector TEXT NOT NULL DEFAULT '', reference TEXT NOT NULL DEFAULT '',
 observation TEXT NOT NULL DEFAULT '', user_id INTEGER NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE
);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def quantity(value, unit):
    """Fixed-point thousandths; no float arithmetic or silent rounding."""
    try:
        number = Decimal(str(value).strip().replace(",", "."))
        if not number.is_finite() or number <= 0 or number > 1_000_000:
            raise ValueError
        scaled = number * 1000
        if scaled != scaled.to_integral_value() or (unit == "unidad" and number != number.to_integral_value()):
            raise ValueError
        return int(scaled)
    except (InvalidOperation, ValueError):
        raise ValueError("Ingresá una cantidad mayor a cero, hasta 1.000.000; unidades enteras o hasta 3 decimales para litros y kg.") from None


def display_quantity(value):
    return format(Decimal(value) / 1000, "f").rstrip("0").rstrip(".") if value % 1000 else str(value // 1000)


def connect(path):
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 15000")
    return db


def db():
    if "db" not in g:
        g.db = connect(g.app_database)
    return g.db


def record_movement(connection, product_id, kind, amount, user_id, *, sector="", reference="", observation="", request_id):
    """Serialize stock validation + update + movement; retries never duplicate."""
    if kind not in ("entrada", "salida"):
        raise ValueError("Tipo de movimiento inválido.")
    if kind == "salida" and sector not in SECTORS:
        raise ValueError("Seleccioná un sector de destino.")
    if len(reference) > 120 or len(observation) > 500:
        raise ValueError("Referencia u observación demasiado extensa.")
    try:
        uuid.UUID(request_id)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Identificador de operación inválido.") from None
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute("SELECT * FROM movements WHERE request_id = ?", (request_id,)).fetchone()
        if existing:
            if (existing["product_id"], existing["kind"], existing["user_id"]) != (product_id, kind, user_id):
                raise ValueError("El identificador ya corresponde a otra operación.")
            connection.rollback()
            return False
        product = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if product is None:
            raise ValueError("El insumo no existe.")
        value = quantity(amount, product["unit"])
        if kind == "salida" and value > product["stock"]:
            raise ValueError("Stock insuficiente. No se registró la salida.")
        connection.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (value if kind == "entrada" else -value, product_id))
        connection.execute(
            "INSERT INTO movements(product_id,kind,quantity,sector,reference,observation,user_id,created_at,request_id) VALUES(?,?,?,?,?,?,?,?,?)",
            (product_id, kind, value, sector if kind == "salida" else "", reference, observation, user_id, now(), request_id),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise


def create_app(config=None):
    app = Flask(__name__)
    instance = Path(os.environ.get("MVP_INSTANCE", ROOT / "instance"))
    app.config.update(DATABASE=str(instance / "inventario.sqlite3"), SECRET_KEY=None,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=os.environ.get("MVP_SECURE_COOKIE") == "1",
                      MAX_CONTENT_LENGTH=32 * 1024)
    if config:
        app.config.update(config)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    if not app.config["SECRET_KEY"]:
        key_file = Path(app.config["DATABASE"]).parent / ".session-key"
        try:
            with open(key_file, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as handle:
                handle.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.config["SECRET_KEY"] = key_file.read_text().strip()
    with connect(app.config["DATABASE"]) as connection:
        connection.executescript(SCHEMA)
        connection.execute("PRAGMA journal_mode=WAL")

    @app.before_request
    def prepare_request():
        g.app_database = app.config["DATABASE"]
        g.user = db().execute("SELECT id,username,name,role FROM users WHERE id = ?", (session.get("user_id"),)).fetchone()
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(32)
        if request.method == "POST" and not secrets.compare_digest(session["csrf"], request.form.get("csrf", "")):
            abort(400, description="La sesión del formulario venció. Recargá la página.")

    @app.teardown_appcontext
    def close_connection(error):
        connection = g.pop("db", None)
        if connection:
            connection.close()

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
        return response

    def authenticated(role=None):
        def decorate(fn):
            @functools.wraps(fn)
            def wrapped(*args, **kwargs):
                if not g.user:
                    return redirect(url_for("login"))
                if role and g.user["role"] != role:
                    abort(403)
                return fn(*args, **kwargs)
            return wrapped
        return decorate

    @app.context_processor
    def context():
        return dict(categories=CATEGORIES, locations=LOCATIONS, units=UNITS, sectors=SECTORS,
                    csrf=session.get("csrf"), user=g.get("user"))

    app.jinja_env.filters["qty"] = display_quantity

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            # Always verify a hash to avoid an obvious user-enumeration timing branch.
            valid = check_password_hash(user["password_hash"] if user else app.config["DUMMY_HASH"], password)
            if user and valid:
                session.clear()
                session.update(user_id=user["id"], csrf=secrets.token_hex(32))
                return redirect(url_for("inventory"))
            flash("Credenciales incorrectas. Verificá usuario y contraseña.", "error")
            return render_template("login.html"), 401
        if g.user:
            return redirect(url_for("inventory"))
        return render_template("login.html")

    app.config["DUMMY_HASH"] = generate_password_hash(secrets.token_hex(16))

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @authenticated()
    def inventory():
        q = request.args.get("q", "").strip()
        category = request.args.get("category", "")
        location = request.args.get("location", "")
        products = db().execute("SELECT * FROM products ORDER BY name_key").fetchall()
        total = len(products)
        products = [p for p in products if (not q or normalized(q) in normalized(" ".join(str(p[k]) for k in ("name", "code", "category", "location"))))
                    and (not category or p["category"] == category) and (not location or p["location"] == location)]
        return render_template("inventory.html", products=products, total=total, q=q, category=category, location=location)

    @app.route("/insumos/nuevo", methods=["GET", "POST"])
    @authenticated("admin")
    def new_product():
        if request.method == "POST":
            values = {k: request.form.get(k, "").strip() for k in ("code", "name", "category", "unit", "location")}
            try:
                if not all(values.values()) or len(values["name"]) > 100 or len(values["code"]) > 30:
                    raise ValueError("Completá todos los campos. Nombre: hasta 100 caracteres; código: hasta 30.")
                if values["unit"] not in UNITS or values["category"] not in CATEGORIES or values["location"] not in LOCATIONS:
                    raise ValueError("Seleccioná categoría, unidad y ubicación de las opciones disponibles.")
                minimum = quantity(request.form.get("minimum", ""), values["unit"])
                maximum = quantity(request.form.get("maximum", ""), values["unit"])
                if minimum >= maximum:
                    raise ValueError("El stock mínimo debe ser menor que el máximo.")
                with db():
                    cursor = db().execute("INSERT INTO products(code,code_key,name,name_key,category,unit,location,minimum,maximum,updated_at,updated_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                          (values["code"], normalized(values["code"]), values["name"], normalized(values["name"]), values["category"], values["unit"], values["location"], minimum, maximum, now(), g.user["id"]))
                    db().execute("INSERT INTO threshold_changes(product_id,minimum,maximum,user_id,created_at) VALUES(?,?,?,?,?)", (cursor.lastrowid, minimum, maximum, g.user["id"], now()))
                flash("Insumo creado con stock inicial cero. Registrá una entrada para cargar existencias.", "success")
                return redirect(url_for("inventory"))
            except sqlite3.IntegrityError:
                flash("Ya existe un insumo con ese código o nombre.", "error")
            except ValueError as error:
                flash(str(error), "error")
            return render_template("product.html"), 400
        return render_template("product.html")

    @app.route("/insumos/<int:product_id>/umbrales", methods=["GET", "POST"])
    @authenticated("admin")
    def thresholds(product_id):
        product = db().execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        if product is None:
            abort(404)
        if request.method == "POST":
            try:
                minimum = quantity(request.form.get("minimum", ""), product["unit"])
                maximum = quantity(request.form.get("maximum", ""), product["unit"])
                if minimum >= maximum:
                    raise ValueError("El stock mínimo debe ser menor que el máximo.")
                with db():
                    db().execute("UPDATE products SET minimum=?, maximum=?, updated_at=?, updated_by=? WHERE id=?", (minimum, maximum, now(), g.user["id"], product_id))
                    db().execute("INSERT INTO threshold_changes(product_id,minimum,maximum,user_id,created_at) VALUES(?,?,?,?,?)", (product_id, minimum, maximum, g.user["id"], now()))
                flash("Umbrales actualizados. Se registraron fecha y administrador responsable.", "success")
                return redirect(url_for("inventory"))
            except ValueError as error:
                flash(str(error), "error")
                return render_template("thresholds.html", product=product), 400
        return render_template("thresholds.html", product=product)

    @app.route("/movimientos/<kind>", methods=["GET", "POST"])
    @authenticated()
    def movement(kind):
        if kind not in ("entrada", "salida"):
            abort(404)
        if request.method == "POST":
            try:
                product_id = int(request.form.get("product_id", "0"))
                created = record_movement(db(), product_id, kind, request.form.get("amount", ""), g.user["id"],
                                          sector=request.form.get("sector", ""), reference=request.form.get("reference", "").strip(),
                                          observation=request.form.get("observation", "").strip(), request_id=request.form.get("request_id", ""))
                flash("Entrada registrada. Stock actualizado." if kind == "entrada" else "Salida registrada. Stock actualizado.", "success") if created else flash("Esta operación ya fue registrada; no se duplicó el movimiento.", "success")
                return redirect(url_for("inventory"))
            except ValueError as error:
                flash(str(error), "error")
        products = db().execute("SELECT * FROM products ORDER BY name_key").fetchall()
        selected = request.form.get("product_id", request.args.get("product_id", ""))
        return render_template("movement.html", kind=kind, products=products, selected=selected,
                               request_id=request.form.get("request_id") or str(uuid.uuid4())), (400 if request.method == "POST" else 200)

    @app.get("/health")
    def health():
        db().execute("SELECT 1").fetchone()
        return {"status": "ok", "version": "1.0.0"}

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(400)
    def error_page(error):
        return render_template("error.html", error=error), error.code

    return app


def seed_demo(app):
    """Explicit, idempotent synthetic fixture; never replace existing users/data."""
    with connect(app.config["DATABASE"]) as connection:
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return False
        for username, name, role, password in (("admin", "Administrador demo", "admin", "AdminDemo2026!"), ("operario", "Operario demo", "operario", "OperarioDemo2026!")):
            connection.execute("INSERT INTO users(username,name,role,password_hash) VALUES(?,?,?,?)", (username, name, role, generate_password_hash(password)))
        for code, name, category, unit, location, minimum, maximum, stock in (
            ("LIM-001", "Lavandina", "Limpieza", "litro", "Puerta 1", 5, 40, 24),
            ("LIM-002", "Perfumina", "Limpieza", "litro", "Cajón Auxiliar 3", 2, 15, 8),
            ("SEG-001", "Guantes de protección", "Seguridad", "unidad", "Estante 1", 10, 60, 36),
            ("MAN-001", "Cinta aisladora", "Mantenimiento", "unidad", "Puerta 2", 5, 30, 18),
        ):
            cursor = connection.execute("INSERT INTO products(code,code_key,name,name_key,category,unit,location,stock,minimum,maximum,updated_at,updated_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,1)",
                                        (code, normalized(code), name, normalized(name), category, unit, location, stock * 1000, minimum * 1000, maximum * 1000, now()))
            connection.execute("INSERT INTO movements(product_id,kind,quantity,reference,user_id,created_at,request_id) VALUES(?,'entrada',?,'Apertura ficticia de demostración',1,?,?)", (cursor.lastrowid, stock * 1000, now(), str(uuid.uuid4())))
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inventario de Intendencia · MVP académico")
    parser.add_argument("--seed-demo", action="store_true", help="Crear datos y cuentas ficticias solo si la base está vacía")
    parser.add_argument("--init-only", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    application = create_app()
    if args.seed_demo:
        print("Datos ficticios creados." if seed_demo(application) else "Base existente preservada; no se cargaron datos.")
    if not args.init_only:
        application.run(host=args.host, port=args.port, debug=False)
