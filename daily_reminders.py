# -*- coding: utf-8 -*-
"""
Created on Fri Apr 24 22:34:05 2026

@author: hp
"""

from datetime import datetime
from email.message import EmailMessage
from psycopg2.extras import RealDictCursor
import psycopg2
import smtplib
import os


DATABASE_URL = os.environ.get("DATABASE_URL")

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USERNAME)


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL n'est pas défini.")
    return psycopg2.connect(DATABASE_URL)


def send_email(to_email, subject, text_body, html_body):
    if not all([SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM]):
        print("SMTP non configuré. Email non envoyé.")
        print("Destinataire :", to_email)
        print("Sujet :", subject)
        print(text_body)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = to_email

    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)


def build_tasks_html(username, tasks):
    tasks_items = ""

    for task in tasks:
        deadline = task["deadline"] if task["deadline"] else "Aujourd'hui"
        priority = task["priority"] if task["priority"] else "Moyenne"
        category = task["category"] if task["category"] else "Général"
        note = task["note"] if task["note"] else ""

        note_html = ""
        if note:
            note_html = f"""
            <p style="margin:8px 0 0 0; color:#4b5563;">
                <strong>Note :</strong> {note}
            </p>
            """

        tasks_items += f"""
        <div style="
            background:#f9fafb;
            border:1px solid #e5e7eb;
            border-radius:12px;
            padding:14px;
            margin-bottom:12px;
        ">
            <h3 style="margin:0 0 8px 0; color:#111827;">
                {task["title"]}
            </h3>

            <p style="margin:0; color:#374151;">
                <strong>Catégorie :</strong> {category}
            </p>

            <p style="margin:4px 0 0 0; color:#374151;">
                <strong>Priorité :</strong> {priority}
            </p>

            <p style="margin:4px 0 0 0; color:#374151;">
                <strong>Date prévue :</strong> {deadline}
            </p>

            {note_html}
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <body style="margin:0; padding:0; background:#f4f6fb; font-family:Arial, sans-serif;">
        <div style="
            max-width:620px;
            margin:40px auto;
            background:white;
            border-radius:18px;
            overflow:hidden;
            box-shadow:0 8px 24px rgba(0,0,0,0.08);
        ">
            <div style="background:#4f46e5; color:white; padding:24px 30px;">
                <h1 style="margin:0; font-size:26px;">Gestionnaire de tâches</h1>
                <p style="margin:8px 0 0 0;">
                    Rappel quotidien de vos tâches
                </p>
            </div>

            <div style="padding:30px;">
                <h2 style="color:#111827; margin-top:0;">
                    Bonjour {username},
                </h2>

                <p style="color:#374151; font-size:16px; line-height:1.6;">
                    Voici les tâches prévues pour aujourd'hui.
                </p>

                {tasks_items}

                <p style="color:#6b7280; font-size:14px; margin-top:24px;">
                    Bon courage pour votre journée !
                </p>
            </div>
        </div>
    </body>
    </html>
    """


def get_today_tasks_by_user():
    today = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            users.id AS user_id,
            users.username,
            users.email,
            tasks.title,
            tasks.note,
            tasks.category,
            tasks.priority,
            tasks.deadline
        FROM tasks
        JOIN users ON users.id = tasks.user_id
        WHERE tasks.done = 0
        AND tasks.deadline = %s
        AND users.email IS NOT NULL
        ORDER BY users.id, tasks.priority, tasks.id
    """, (today,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    users_tasks = {}

    for row in rows:
        user_id = row["user_id"]

        if user_id not in users_tasks:
            users_tasks[user_id] = {
                "username": row["username"],
                "email": row["email"],
                "tasks": []
            }

        users_tasks[user_id]["tasks"].append(row)

    return users_tasks


def send_daily_reminders():
    users_tasks = get_today_tasks_by_user()

    if not users_tasks:
        print("Aucune tâche prévue aujourd'hui. Aucun email envoyé.")
        return

    for user_data in users_tasks.values():
        username = user_data["username"]
        email = user_data["email"]
        tasks = user_data["tasks"]

        subject = "Vos tâches prévues aujourd'hui"

        text_body = f"Bonjour {username},\n\nVoici vos tâches prévues pour aujourd'hui :\n\n"

        for task in tasks:
            text_body += f"- {task['title']} | Priorité : {task['priority']} | Catégorie : {task['category']}\n"

        text_body += "\nBon courage pour votre journée !"

        html_body = build_tasks_html(username, tasks)

        send_email(email, subject, text_body, html_body)

        print(f"Email envoyé à {email} avec {len(tasks)} tâche(s).")


if __name__ == "__main__":
    send_daily_reminders()