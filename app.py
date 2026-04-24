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


def send_email_message(to_email, subject, body, html_body=None):
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_from = os.environ.get("SMTP_FROM", smtp_username)

    if not all([smtp_host, smtp_username, smtp_password, smtp_from]):
        app.logger.warning("SMTP non configuré. Email non envoyé à %s. Sujet: %s", to_email, subject)
        app.logger.warning("Contenu email:\n%s", body)
        if html_body:
            app.logger.warning("Contenu HTML email:\n%s", html_body)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = to_email
    message.set_content(body)

    if html_body:
        message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)


def build_email_html(title, message_html, action_text=None, action_link=None):
    action_button = ""
    if action_text and action_link:
        action_button = f"""
        <div style="text-align:center; margin: 30px 0;">
            <a href="{action_link}"
               style="
                   background-color:#4f46e5;
                   color:white;
                   text-decoration:none;
                   padding:14px 22px;
                   border-radius:10px;
                   display:inline-block;
                   font-weight:bold;
                   font-family:Arial, sans-serif;
               ">
                {action_text}
            </a>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>{title}</title>
    </head>
    <body style="margin:0; padding:0; background-color:#f4f6fb; font-family:Arial, sans-serif;">
        <div style="max-width:600px; margin:40px auto; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 8px 24px rgba(0,0,0,0.08);">
            <div style="background:#4f46e5; color:white; padding:24px 30px;">
                <h1 style="margin:0; font-size:26px;">Gestionnaire de tâches</h1>
                <p style="margin:8px 0 0 0; opacity:0.95;">Application de gestion personnelle</p>
            </div>

            <div style="padding:30px;">
                <h2 style="margin-top:0; color:#1f2937;">{title}</h2>

                <div style="color:#374151; font-size:16px; line-height:1.7;">
                    {message_html}
                </div>

                {action_button}

                <div style="margin-top:30px; padding-top:20px; border-top:1px solid #e5e7eb; color:#6b7280; font-size:14px;">
                    Merci d'utiliser <strong>Gestionnaire de tâches</strong>.
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def send_reset_email(to_email, username):
    token = generate_reset_token(to_email)
    reset_link = url_for("reset_password", token=token, _external=True)

    subject = "Réinitialisation de votre mot de passe"

    body = f"""
Bonjour {username},

Vous avez demandé la réinitialisation de votre mot de passe.

Cliquez sur ce lien pour choisir un nouveau mot de passe :
{reset_link}

Ce lien expire dans 1 heure.

Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet email.
"""

    html_body = build_email_html(
        title="Réinitialisation du mot de passe",
        message_html=f"""
            <p>Bonjour <strong>{username}</strong>,</p>
            <p>Vous avez demandé la réinitialisation de votre mot de passe.</p>
            <p>Cliquez sur le bouton ci-dessous pour choisir un nouveau mot de passe.</p>
            <p style="color:#b91c1c;"><strong>Ce lien expire dans 1 heure.</strong></p>
            <p>Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.</p>
        """,
        action_text="Réinitialiser mon mot de passe",
        action_link=reset_link
    )

    send_email_message(to_email, subject, body, html_body)


def send_welcome_email(to_email, username):
    subject = "Bienvenue sur Gestionnaire de tâches"

    body = f"""
Bonjour {username},

Bienvenue sur Gestionnaire de tâches.

Votre compte a bien été créé et vous pouvez maintenant :
- ajouter des tâches
- définir une priorité
- ajouter une note
- fixer une date limite
- personnaliser l'interface

Nous vous souhaitons une excellente utilisation de l'application.

À bientôt !
"""

    html_body = build_email_html(
        title="Bienvenue sur Gestionnaire de tâches",
        message_html=f"""
            <p>Bonjour <strong>{username}</strong>,</p>
            <p>Votre compte a bien été créé avec succès.</p>
            <p>Vous pouvez maintenant :</p>
            <ul style="padding-left:20px; color:#374151;">
                <li>ajouter des tâches</li>
                <li>définir une priorité</li>
                <li>ajouter une note</li>
                <li>fixer une date limite</li>
                <li>personnaliser votre interface</li>
            </ul>
            <p>Nous vous souhaitons une excellente utilisation de l'application.</p>
        """
    )

    send_email_message(to_email, subject, body, html_body)


def send_account_deleted_email(to_email, username):
    subject = "Confirmation de suppression de votre compte"

    body = f"""
Bonjour {username},

Votre compte sur Gestionnaire de tâches a bien été supprimé.

Toutes vos données (tâches, notes, paramètres) ont été définitivement effacées.

Si cette action n'est pas de votre fait, nous vous recommandons de recréer un compte rapidement.

Merci d'avoir utilisé notre application.

À bientôt !
"""

    html_body = build_email_html(
        title="Compte supprimé",
        message_html=f"""
            <p>Bonjour <strong>{username}</strong>,</p>
            <p>Votre compte sur <strong>Gestionnaire de tâches</strong> a bien été supprimé.</p>
            <p>Toutes vos données personnelles liées à l'application ont été effacées :</p>
            <ul style="padding-left:20px; color:#374151;">
                <li>vos tâches</li>
                <li>vos notes</li>
                <li>vos préférences de personnalisation</li>
            </ul>
            <p style="color:#b91c1c;"><strong>Si cette action n'est pas de votre fait, recréez un compte dès que possible.</strong></p>
            <p>Merci d'avoir utilisé notre application.</p>
        """
    )

    send_email_message(to_email, subject, body, html_body)


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
            category TEXT NOT NULL DEFAULT 'Général',
            done INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'Moyenne',
            deadline TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            subtitle TEXT NOT NULL,
            bg_color TEXT NOT NULL,
            card_color TEXT NOT NULL,
            primary_color TEXT NOT NULL
        )
    """)

    cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS note TEXT")
    cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'Général'")
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

    conn.commit()
    cur.close()
    conn.close()


def ensure_user_settings(user_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
    settings = cur.fetchone()

    if not settings:
        cur.execute("""
            INSERT INTO user_settings (user_id, subtitle, bg_color, card_color, primary_color)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user_id,
            DEFAULT_SETTINGS["subtitle"],
            DEFAULT_SETTINGS["bg_color"],
            DEFAULT_SETTINGS["card_color"],
            DEFAULT_SETTINGS["primary_color"]
        ))
        conn.commit()

    cur.close()
    conn.close()


def get_settings():
    user_id = session.get("user_id")

    if not user_id:
        return DEFAULT_SETTINGS.copy()

    ensure_user_settings(user_id)

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
    user_settings = cur.fetchone()
    cur.close()
    conn.close()

    settings = DEFAULT_SETTINGS.copy()

    if user_settings:
        settings["subtitle"] = user_settings["subtitle"]
        settings["bg_color"] = user_settings["bg_color"]
        settings["card_color"] = user_settings["card_color"]
        settings["primary_color"] = user_settings["primary_color"]

    return settings


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


def get_user_categories(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT category
        FROM tasks
        WHERE user_id = %s AND category IS NOT NULL AND category <> ''
        ORDER BY category ASC
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    categories = [row[0] for row in rows]
    if "Général" not in categories:
        categories.insert(0, "Général")
    return categories


def get_filtered_and_sorted_tasks(user_id, filter_value, sort_value, category_filter):
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

    if category_filter and category_filter != "toutes":
        tasks = [task for task in tasks if task.get("category", "Général") == category_filter]

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

                cur.execute("""
                    INSERT INTO user_settings (user_id, subtitle, bg_color, card_color, primary_color)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    new_user["id"],
                    DEFAULT_SETTINGS["subtitle"],
                    DEFAULT_SETTINGS["bg_color"],
                    DEFAULT_SETTINGS["card_color"],
                    DEFAULT_SETTINGS["primary_color"]
                ))
                conn.commit()

                session["user_id"] = new_user["id"]
                session["username"] = username

                cur.close()
                conn.close()

                send_welcome_email(email, username)

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
        category = request.form.get("category", "Général").strip() or "Général"
        priority = request.form.get("priority", "Moyenne")
        deadline = request.form.get("deadline", "").strip()

        if task_text:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO tasks (user_id, title, note, category, done, priority, deadline)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session["user_id"],
                    task_text,
                    note if note else None,
                    category,
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
    category_filter = request.args.get("category_filter", "toutes")

    tasks = get_filtered_and_sorted_tasks(session["user_id"], filter_value, sort_value, category_filter)
    categories = get_user_categories(session["user_id"])
    now = datetime.now().strftime("%Y-%m-%d")
    settings = get_settings()
    user = get_current_user()

    return render_template(
        "index.html",
        tasks=tasks,
        categories=categories,
        now=now,
        current_filter=filter_value,
        current_sort=sort_value,
        current_category_filter=category_filter,
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
        new_category = request.form.get("category", "Général").strip() or "Général"
        new_priority = request.form.get("priority", "Moyenne")
        new_deadline = request.form.get("deadline", "").strip()

        if new_title:
            cur.execute(
                """
                UPDATE tasks
                SET title = %s, note = %s, category = %s, priority = %s, deadline = %s
                WHERE id = %s AND user_id = %s
                """,
                (
                    new_title,
                    new_note if new_note else None,
                    new_category,
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
    categories = get_user_categories(session["user_id"])
    return render_template("edit.html", task=task, settings=settings, categories=categories)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    current_settings = get_settings()

    if request.method == "POST":
        subtitle = request.form.get("subtitle", "").strip() or DEFAULT_SETTINGS["subtitle"]
        bg_color = request.form.get("bg_color", "").strip() or DEFAULT_SETTINGS["bg_color"]
        card_color = request.form.get("card_color", "").strip() or DEFAULT_SETTINGS["card_color"]
        primary_color = request.form.get("primary_color", "").strip() or DEFAULT_SETTINGS["primary_color"]

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE user_settings
            SET subtitle = %s, bg_color = %s, card_color = %s, primary_color = %s
            WHERE user_id = %s
        """, (
            subtitle,
            bg_color,
            card_color,
            primary_color,
            session["user_id"]
        ))
        conn.commit()
        cur.close()
        conn.close()

        flash("Personnalisation enregistrée.", "success")
        return redirect(url_for("index"))

    user = get_current_user()
    return render_template("settings.html", settings=current_settings, user=user)


@app.route("/reset-settings")
@login_required
def reset_settings():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE user_settings
        SET subtitle = %s, bg_color = %s, card_color = %s, primary_color = %s
        WHERE user_id = %s
    """, (
        DEFAULT_SETTINGS["subtitle"],
        DEFAULT_SETTINGS["bg_color"],
        DEFAULT_SETTINGS["card_color"],
        DEFAULT_SETTINGS["primary_color"],
        session["user_id"]
    ))
    conn.commit()
    cur.close()
    conn.close()

    flash("Personnalisation réinitialisée.", "info")
    return redirect(url_for("settings_page"))


@app.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    password = request.form.get("password", "").strip()
    user = get_current_user()

    if not user:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("login"))

    if not password:
        flash("Veuillez entrer votre mot de passe.", "warning")
        return redirect(url_for("settings_page"))

    if not check_password_hash(user["password_hash"], password):
        flash("Mot de passe incorrect.", "error")
        return redirect(url_for("settings_page"))

    if user.get("email"):
        send_account_deleted_email(user["email"], user["username"])

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user["id"],))
    conn.commit()
    cur.close()
    conn.close()

    session.clear()
    flash("Votre compte a été supprimé.", "info")
    return redirect(url_for("register"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)