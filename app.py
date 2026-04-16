# -*- coding: utf-8 -*-
"""
Created on Thu Apr 16 09:13:35 2026

@author: hp
"""

from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import sqlite3

app = Flask(__name__)
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
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            note TEXT,
            done INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'Moyenne',
            deadline TEXT
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


def get_priority_rank(priority):
    order = {
        "Élevée": 0,
        "Moyenne": 1,
        "Faible": 2
    }
    return order.get(priority, 1)


def get_filtered_and_sorted_tasks(filter_value, sort_value):
    conn = get_connection()
    tasks = conn.execute("SELECT * FROM tasks").fetchall()
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


@app.route("/", methods=["GET", "POST"])
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
                INSERT INTO tasks (title, note, done, priority, deadline)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_text, note if note else None, 0, priority, deadline if deadline else None)
            )
            conn.commit()
            conn.close()

        return redirect(url_for("index"))

    filter_value = request.args.get("filter", "toutes")
    sort_value = request.args.get("sort", "ordre_ajout")

    tasks = get_filtered_and_sorted_tasks(filter_value, sort_value)
    now = datetime.now().strftime("%Y-%m-%d")
    settings = get_settings()

    return render_template(
        "index.html",
        tasks=tasks,
        now=now,
        current_filter=filter_value,
        current_sort=sort_value,
        settings=settings
    )


@app.route("/complete/<int:task_id>")
def complete_task(task_id):
    conn = get_connection()
    conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>")
def delete_task(task_id):
    conn = get_connection()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
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
                WHERE id = ?
                """,
                (
                    new_title,
                    new_note if new_note else None,
                    new_priority,
                    new_deadline if new_deadline else None,
                    task_id
                )
            )
            conn.commit()

        conn.close()
        return redirect(url_for("index"))

    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()

    conn.close()
    settings = get_settings()
    return render_template("edit.html", task=task, settings=settings)


@app.route("/settings", methods=["GET", "POST"])
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