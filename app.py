# -*- coding: utf-8 -*-
"""
Created on Thu Apr 16 09:13:35 2026

@author: hp
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2.extras import RealDictCursor
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from email.message import EmailMessage
import psycopg2
import smtplib
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

DATABASE_URL = os.environ.get("DATABASE_URL")

DEFAULT_SETTINGS = {
    "app_title": "Gestionnaire de tâches",
    "subtitle": "Ajoutez, filtrez, triez et organisez vos tâches",
    "bg_color": "#f4f6fb",
    "card_color": "#ffffff",
    "primary_color": "#4f46e5"
}


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL n'est pas défini.")
    return psycopg2.connect(DATABASE_URL)


def get_serializer():
    return URLSafeTimedSerializer(app.secret_key)


def generate_reset_token(email):
    serializer = get_serializer()
    return serializer.dumps(email, salt="password-reset-salt")


def verify_reset_token(token, max_age=3600):
    serializer = get_serializer()
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=max_age)
        return email
    except (BadSignature, SignatureExpired):
        return None


def send_reset_email(to_email, username):
    token = generate_reset_token(to_email)
    reset_link = url_for("reset_password", token=token, _external=True)

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_from = os.environ.get("SMTP_FROM", smtp_username)

    subject = "Réinitialisation de votre mot de passe"
    body = f"""
Bonjour {username},

Vous avez demandé la réinitialisation de votre mot de passe.

Cliquez sur ce lien pour choisir un nouveau mot de passe :
{reset_link}

Ce lien expire dans 1 heure.

Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet email.
"""

    if not all([smtp_host, smtp_username, smtp_password, smtp_from]):
        app.logger.warning("SMTP non configuré. Lien de réinitialisation : %s", reset_link)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            note TEXT,
            done INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'Moyenne',
            deadline TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            app_title TEXT NOT NULL,
            subtitle TEXT NOT NULL,
            bg_color TEXT NOT NULL,
            card_color TEXT NOT NULL,
            primary_color TEXT NOT NULL
        )
    """)

    cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS note TEXT")
    cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority TEXT NOT NULL DEFAULT 'Moyenne'")
    cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deadline TEXT")
    cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS user_id INTEGER")
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique_idx ON users(email)")

    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE table_name = 'tasks'
                AND constraint_type = 'FOREIGN KEY'
                AND constraint_name = 'tasks_user_id_fkey'
            ) THEN
                ALTER TABLE tasks
                ADD CONSTRAINT tasks_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
            END IF;
        END $$;
    """)

    cur.execute("SELECT * FROM settings WHERE id = 1")
    existing_settings = cur.fetchone()

    if not existing_settings:
        cur.execute("""
            INSERT INTO settings (id, app_title, subtitle, bg_color, card_color, primary_color)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            1,
            DEFAULT_SETTINGS["app_title"],
            DEFAULT_SETTINGS["subtitle"],
            DEFAULT_SETTINGS["bg_color"],
            DEFAULT_SETTINGS["card_color"],
            DEFAULT_SETTINGS["primary_color"]
        ))

    conn.commit()
    cur.close()
    conn.close()


def get_settings():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM settings WHERE id = 1")
    settings = cur.fetchone()
    cur.close()
    conn.close()

    if settings:
        return dict(settings)

    return DEFAULT_SETTINGS.copy()


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    return dict(user) if user else None


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Veuillez vous connecter pour accéder à l'application.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


def get_priority_rank(priority):
    order = {
        "Élevée": 0,
        "Moyenne": 1,
        "Faible": 2
    }
    return order.get(priority, 1)


def get_filtered_and_sorted_tasks(user_id, filter_value, sort_value):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM tasks WHERE user_id = %s", (user_id,))
    tasks = cur.fetchall()
    cur.close()
    conn.close()

    tasks = [dict(task) for task in tasks]

    if filter_value == "en_cours":
        tasks = [task for task in tasks if task["done"] == 0]
    elif filter_value == "terminees":
        tasks = [task for task in tasks if task["done"] == 1]
    elif filter_value == "retard":
        today = datetime.now().strftime("%Y-%m-%d")
        tasks = [
            task for task in tasks
            if task["done"] == 0 and task["deadline"] and task["deadline"] < today
        ]

    if sort_value == "priorite":
        tasks.sort(
            key=lambda task: (
                task["done"],
                get_priority_rank(task["priority"]),
                task["id"]
            )
        )
    elif sort_value == "date":
        tasks.sort(
            key=lambda task: (
                task["done"],
                task["deadline"] is None or task["deadline"] == "",
                task["deadline"] or "9999-12-31",
                task["id"]
            )
        )
    elif sort_value == "date_priorite":
        tasks.sort(
            key=lambda task: (
                task["done"],
                task["deadline"] is None or task["deadline"] == "",
                task["deadline"] or "9999-12-31",
                get_priority_rank(task["priority"]),
                task["id"]
            )
        )
    else:
        tasks.sort(key=lambda task: task["id"], reverse=True)

    return tasks


@app.route("/register", methods=["GET", "POST"])
def register():
    settings = get_settings()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not username or not email or not password or not confirm_password:
            flash("Veuillez remplir tous les champs.", "error")
        elif password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "error")
        elif len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
        else:
            conn = get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            existing_user = cur.fetchone()

            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            existing_email = cur.fetchone()

            if existing_user:
                flash("Ce nom d'utilisateur existe déjà.", "error")
            elif existing_email:
                flash("Cet email est déjà utilisé.", "error")
            else:
                password_hash = generate_password_hash(password)
                cur.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                    (username, email, password_hash)
                )
                new_user = cur.fetchone()
                conn.commit()

                session["user_id"] = new_user["id"]
                session["username"] = username

                cur.close()
                conn.close()
                flash("Compte créé avec succès. Bienvenue !", "success")
                return redirect(url_for("index"))

            cur.close()
            conn.close()

    return render_template("register.html", settings=settings)


@app.route("/login", methods=["GET", "POST"])
def login():
    settings = get_settings()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Heureux de vous revoir, {user['username']} !", "success")
            return redirect(url_for("index"))

        flash("Nom d'utilisateur ou mot de passe incorrect.", "error")

    return render_template("login.html", settings=settings)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    settings = get_settings()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash("Veuillez entrer votre email.", "warning")
            return render_template("forgot_password.html", settings=settings)

        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            send_reset_email(user["email"], user["username"])

        flash("Si cet email existe, un lien de réinitialisation a été envoyé.", "info")
        return redirect(url_for("login"))

    return render_template("forgot_password.html", settings=settings)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    settings = get_settings()
    email = verify_reset_token(token)

    if not email:
        flash("Le lien de réinitialisation est invalide ou expiré.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not password or not confirm_password:
            flash("Veuillez remplir tous les champs.", "warning")
        elif password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "error")
        elif len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "error")
        else:
            password_hash = generate_password_hash(password)

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE email = %s",
                (password_hash, email)
            )
            conn.commit()
            cur.close()
            conn.close()

            flash("Votre mot de passe a été réinitialisé avec succès.", "success")
            return redirect(url_for("login"))

    return render_template("reset_password.html", settings=settings)


@app.route("/logout")
def logout():
    session.clear()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        task_text = request.form.get("task", "").strip()
        note = request.form.get("note", "").strip()
        priority = request.form.get("priority", "Moyenne")
        deadline = request.form.get("deadline", "").strip()

        if task_text:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO tasks (user_id, title, note, done, priority, deadline)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    session["user_id"],
                    task_text,
                    note if note else None,
                    0,
                    priority,
                    deadline if deadline else None
                )
            )
            conn.commit()
            cur.close()
            conn.close()
            flash("Tâche ajoutée avec succès.", "success")
        else:
            flash("Veuillez entrer une tâche.", "warning")

        return redirect(url_for("index"))

    filter_value = request.args.get("filter", "toutes")
    sort_value = request.args.get("sort", "ordre_ajout")

    tasks = get_filtered_and_sorted_tasks(session["user_id"], filter_value, sort_value)
    now = datetime.now().strftime("%Y-%m-%d")
    settings = get_settings()
    user = get_current_user()

    return render_template(
        "index.html",
        tasks=tasks,
        now=now,
        current_filter=filter_value,
        current_sort=sort_value,
        settings=settings,
        user=user
    )


@app.route("/complete/<int:task_id>")
@login_required
def complete_task(task_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE tasks SET done = 1 WHERE id = %s AND user_id = %s",
        (task_id, session["user_id"])
    )
    conn.commit()
    cur.close()
    conn.close()
    flash("Tâche marquée comme terminée.", "success")
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>")
@login_required
def delete_task(task_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM tasks WHERE id = %s AND user_id = %s",
        (task_id, session["user_id"])
    )
    conn.commit()
    cur.close()
    conn.close()
    flash("Tâche supprimée.", "info")
    return redirect(url_for("index"))


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":
        new_title = request.form.get("task", "").strip()
        new_note = request.form.get("note", "").strip()
        new_priority = request.form.get("priority", "Moyenne")
        new_deadline = request.form.get("deadline", "").strip()

        if new_title:
            cur.execute(
                """
                UPDATE tasks
                SET title = %s, note = %s, priority = %s, deadline = %s
                WHERE id = %s AND user_id = %s
                """,
                (
                    new_title,
                    new_note if new_note else None,
                    new_priority,
                    new_deadline if new_deadline else None,
                    task_id,
                    session["user_id"]
                )
            )
            conn.commit()
            cur.close()
            conn.close()
            flash("Tâche modifiée avec succès.", "success")
            return redirect(url_for("index"))

        cur.close()
        conn.close()
        flash("Le titre de la tâche ne peut pas être vide.", "warning")
        return redirect(url_for("edit_task", task_id=task_id))

    cur.execute(
        "SELECT * FROM tasks WHERE id = %s AND user_id = %s",
        (task_id, session["user_id"])
    )
    task = cur.fetchone()

    cur.close()
    conn.close()

    if not task:
        flash("Tâche introuvable.", "error")
        return redirect(url_for("index"))

    settings = get_settings()
    return render_template("edit.html", task=task, settings=settings)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    current_settings = get_settings()

    if request.method == "POST":
        app_title = request.form.get("app_title", "").strip() or DEFAULT_SETTINGS["app_title"]
        subtitle = request.form.get("subtitle", "").strip() or DEFAULT_SETTINGS["subtitle"]
        bg_color = request.form.get("bg_color", "").strip() or DEFAULT_SETTINGS["bg_color"]
        card_color = request.form.get("card_color", "").strip() or DEFAULT_SETTINGS["card_color"]
        primary_color = request.form.get("primary_color", "").strip() or DEFAULT_SETTINGS["primary_color"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE settings
            SET app_title = %s, subtitle = %s, bg_color = %s, card_color = %s, primary_color = %s
            WHERE id = 1
        """, (app_title, subtitle, bg_color, card_color, primary_color))
        conn.commit()
        cur.close()
        conn.close()

        flash("Personnalisation enregistrée.", "success")
        return redirect(url_for("index"))

    return render_template("settings.html", settings=current_settings)


@app.route("/reset-settings")
@login_required
def reset_settings():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE settings
        SET app_title = %s, subtitle = %s, bg_color = %s, card_color = %s, primary_color = %s
        WHERE id = 1
    """, (
        DEFAULT_SETTINGS["app_title"],
        DEFAULT_SETTINGS["subtitle"],
        DEFAULT_SETTINGS["bg_color"],
        DEFAULT_SETTINGS["card_color"],
        DEFAULT_SETTINGS["primary_color"]
    ))
    conn.commit()
    cur.close()
    conn.close()

    flash("Personnalisation réinitialisée.", "info")
    return redirect(url_for("settings_page"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
