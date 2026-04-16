# -*- coding: utf-8 -*-
"""
Created on Thu Apr 16 09:13:35 2026

@author: hp
"""

from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = "change-cette-cle-secrete"
DATABASE = "database.db"

DEFAULT_SETTINGS = {
    "app_title": "Gestionnaire de tâches",
    "subtitle": "Ajoutez, filtrez, triez et organisez vos tâches",
    "bg_color": "#f4f6fb",
    "card_color": "#ffffff",
    "primary_color": "#4f46e5"
}


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            note TEXT,
            done INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'Moyenne',
            deadline TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            app_title TEXT NOT NULL,
            subtitle TEXT NOT NULL,
            bg_color TEXT NOT NULL,
            card_color TEXT NOT NULL,
            primary_color TEXT NOT NULL
        )
    """)

    columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]

    if "priority" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'Moyenne'")

    if "deadline" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN deadline TEXT")

    if "note" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN note TEXT")

    if "user_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN user_id INTEGER")

    existing_settings = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    if not existing_settings:
        conn.execute("""
            INSERT INTO settings (id, app_title, subtitle, bg_color, card_color, primary_color)
            VALUES (1, ?, ?, ?, ?, ?)
        """, (
            DEFAULT_SETTINGS["app_title"],
            DEFAULT_SETTINGS["subtitle"],
            DEFAULT_SETTINGS["bg_color"],
            DEFAULT_SETTINGS["card_color"],
            DEFAULT_SETTINGS["primary_color"]
        ))

    conn.commit()
    conn.close()


def get_settings():
    conn = get_connection()
    settings = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    conn.close()

    if settings:
        return dict(settings)

    return DEFAULT_SETTINGS.copy()


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    return dict(user) if user else None


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
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
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ?",
        (user_id,)
    ).fetchall()
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
    error = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not username or not password or not confirm_password:
            error = "Veuillez remplir tous les champs."
        elif password != confirm_password:
            error = "Les mots de passe ne correspondent pas."
        elif len(password) < 6:
            error = "Le mot de passe doit contenir au moins 6 caractères."
        else:
            conn = get_connection()
            existing_user = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            ).fetchone()

            if existing_user:
                error = "Ce nom d'utilisateur existe déjà."
            else:
                password_hash = generate_password_hash(password)
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash)
                )
                conn.commit()

                session["user_id"] = cursor.lastrowid
                session["username"] = username

                conn.close()
                return redirect(url_for("index"))

            conn.close()

    return render_template("register.html", settings=settings, error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    settings = get_settings()
    error = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))

        error = "Nom d'utilisateur ou mot de passe incorrect."

    return render_template("login.html", settings=settings, error=error)


@app.route("/logout")
def logout():
    session.clear()
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
            conn.execute(
                """
                INSERT INTO tasks (user_id, title, note, done, priority, deadline)
                VALUES (?, ?, ?, ?, ?, ?)
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
            conn.close()

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
    conn.execute(
        "UPDATE tasks SET done = 1 WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>")
@login_required
def delete_task(task_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    conn = get_connection()

    if request.method == "POST":
        new_title = request.form.get("task", "").strip()
        new_note = request.form.get("note", "").strip()
        new_priority = request.form.get("priority", "Moyenne")
        new_deadline = request.form.get("deadline", "").strip()

        if new_title:
            conn.execute(
                """
                UPDATE tasks
                SET title = ?, note = ?, priority = ?, deadline = ?
                WHERE id = ? AND user_id = ?
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

        conn.close()
        return redirect(url_for("index"))

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    ).fetchone()

    conn.close()

    if not task:
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
        conn.execute("""
            UPDATE settings
            SET app_title = ?, subtitle = ?, bg_color = ?, card_color = ?, primary_color = ?
            WHERE id = 1
        """, (app_title, subtitle, bg_color, card_color, primary_color))
        conn.commit()
        conn.close()

        return redirect(url_for("index"))

    return render_template("settings.html", settings=current_settings)


@app.route("/reset-settings")
@login_required
def reset_settings():
    conn = get_connection()
    conn.execute("""
        UPDATE settings
        SET app_title = ?, subtitle = ?, bg_color = ?, card_color = ?, primary_color = ?
        WHERE id = 1
    """, (
        DEFAULT_SETTINGS["app_title"],
        DEFAULT_SETTINGS["subtitle"],
        DEFAULT_SETTINGS["bg_color"],
        DEFAULT_SETTINGS["card_color"],
        DEFAULT_SETTINGS["primary_color"]
    ))
    conn.commit()
    conn.close()

    return redirect(url_for("settings_page"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)