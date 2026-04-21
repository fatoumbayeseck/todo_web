# Gestionnaire de tâches

Ce projet consiste en la réalisation d’une application web de gestion de tâches développée en Python avec le framework Flask.

L’objectif est de permettre à un utilisateur de :

créer un compte
se connecter à son espace personnel
gérer ses tâches (ajout, modification, suppression)
organiser ses tâches selon leur priorité et leur date
personnaliser l’apparence de l’interface
récupérer l’accès à son compte en cas d’oubli de mot de passe

L’application est accessible en ligne et fonctionne sur ordinateur comme sur smartphone.
## Fonctionnalités
Gestion des utilisateurs : 
- Inscription avec email
- Connexion sécurisée
- Déconnexion
- Suppression du compte
- Réinitialisation du mot de passe par email

Gestion des tâches :
- Ajout de tâches
- Ajout de notes
- Définition de priorité (Faible, Moyenne, Élevée)
- Ajout de date limite
- Modification des tâches
- Suppression des tâches
- Marquer comme terminée

Personnalisation :
- Couleur de fond
- Couleur des cartes
- Couleur principale
- Sous-titre personnalisable
- Paramètres propres à chaque utilisateur

Emails automatiques :
- Email de bienvenue
- Email de réinitialisation du mot de passe
- Email de confirmation de suppression du compte

## Technologies
- Python 3
- Flask
- PostgreSQL (Render)
- HTML / CSS
- SMTP (Gmail) pour l’envoi d’emails
- Gunicorn pour le déploiement

## Installation locale
1. Cloner le projet
git clone <url-du-projet>
cd projet
2. Installer les dépendances
pip install -r requirements.txt
3. Lancer l’application
python app.py

Variables d'environnement
Pour faire fonctionner l’application, il faut configurer :

DATABASE_URL= postgresql://base_todo_web_user:EdOFENT0din3BrUUEqpVwgK6gzdVc864@dpg-d7hp0urbc2fs73ds26dg-a/base_todo_web
SECRET_KEY=...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME= ndeyefatous013@gmail.com
SMTP_PASSWORD=...
SMTP_FROM= ndeyefatous013@gmail.com

## Base de données
L’application utilise PostgreSQL avec les tables suivantes :

users : comptes utilisateurs
tasks : tâches liées aux utilisateurs
user_settings : personnalisation par utilisateur

## Sécurité
Mots de passe hashés avec Werkzeug
Sessions sécurisées avec Flask
Tokens sécurisés pour la réinitialisation de mot de passe
Validation des entrées utilisateur

## Fonctionnement
L’application est conçue pour fonctionner :

sur ordinateur
sur smartphone
sur tablette

## Lien de l'application
(https://todo-web-qu6a.onrender.com)

## Conclusion
Ce projet met en œuvre :

le développement backend avec Flask
la gestion d’une base de données
la création d’une interface utilisateur
la sécurisation des données
le déploiement d’une application web complète

Il constitue une application fonctionnelle et extensible.

## Auteur
Ndeye SECK
L3 EEA
