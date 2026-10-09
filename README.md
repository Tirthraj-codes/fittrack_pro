# FitTrack Pro: Integrated Fitness Club Management System

A web application that runs a fitness club: memberships, attendance (with QR codes), payments,
trainer scheduling, member progress, reminders and reports. Built with Django, HTML5, CSS3 and JavaScript.
It works on phones and PCs, and can be installed as an app (PWA).

Roles: **Admin**, **Trainer**, **Member**, each with its own dashboard.

## Quick start (Windows)

1. Install Python 3.12 or 3.13 (tick "Add python.exe to PATH") and open a terminal in this folder.
2. Create and activate a virtual environment, then install the packages:

```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
```

3. Create the database and an admin account:

```bash
   python manage.py migrate
   python manage.py createsuperuser
```

4. (Optional) Fill the app with demo data and create the app icons:

```bash
   python manage.py seed_demo
   python manage.py make_pwa_icons
```

5. Start the server and open http://127.0.0.1:8000/

```bash
   python manage.py runserver
```

On Mac or Linux, activate with `source venv/bin/activate`.

## Accounts

* **Admin:** the account you created with `createsuperuser`.
* **Demo trainers:** `arjun.mehta`, `priya.patel`, `rohan.shah`
* **Demo members:** for example `aarav.sharma`, `diya.nair`, `ananya.iyer` (username is `first.last` in lowercase)
* Every demo account uses the password `FitDemo@2026`. **Change or delete these before real use.**
* New members register themselves at `/accounts/register/`. Admins create trainers at **People > Users**.

## What is inside

| Area | What it does |
|---|---|
| Accounts | Registration, login, roles, profile photo, password change and reset, user management |
| Memberships | Plans, assign, renew, upgrade, cancel, automatic Active / Expiring / Expired flags |
| Attendance | Front desk, manual or QR check-in and out, history, monthly report |
| Payments | Demo checkout (card, UPI, net banking), PDF receipts, paid / pending / overdue tracking |
| Scheduling | Trainer availability, assignments, sessions with clash detection, weekly schedule, session logs |
| Progress | Weight, BMI and measurements with charts, goals, workout and diet plan |
| Reminders | Renewal, payment and session reminders in the app and by email |
| Reports | Revenue, membership growth and attendance trends, PDF and CSV export |
| PWA | Installable app with an offline page |

## Useful commands

| Command | Purpose |
|---|---|
| `python manage.py runserver` | Start the site locally |
| `python manage.py seed_demo` | Create demo data (`--reset` wipes members and trainers first) |
| `python manage.py send_reminders` | Create and email today's reminders (`--dry-run` to preview). Run it once a day. |
| `python manage.py backfill_payments` | Create payments for memberships that have none |
| `python manage.py make_pwa_icons` | Regenerate the app icons |
| `python manage.py check` | Check the project for problems |

## Settings (environment variables)

Local development needs none. For a hosted site set these:

| Variable | Meaning |
|---|---|
| `DJANGO_DEBUG` | `False` on a live site |
| `DJANGO_SECRET_KEY` | A long random secret (required when DEBUG is off) |
| `DJANGO_ALLOWED_HOSTS` | Comma separated host names, e.g. `yourname.pythonanywhere.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | e.g. `https://yourname.pythonanywhere.com` (only if forms are rejected) |
| `SITE_URL` | The public address, used for links in emails |
| `REMINDER_TOKEN` | Secret for the daily reminder link `/notifications/run/<token>/` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP details, to send real emails |

## Good to know

* The payment screen is a **demo**: no real money moves. It is one module and can be replaced by a real gateway.
* The database is a single SQLite file (`db.sqlite3`). Back it up by copying it.
* Emails print in the terminal until SMTP is configured. Reminders always appear inside the app.
* SMS and WhatsApp are not included.

## Troubleshooting

* *"python is not recognized"*: reinstall Python and tick "Add python.exe to PATH".
* *Page looks unstyled*: press `Ctrl + F5`.
* *Icons or install button missing*: run `python manage.py make_pwa_icons`.
* *Changed CSS or JS but the installed app looks old*: raise `PWA_VERSION` in `core/pwa_views.py`.