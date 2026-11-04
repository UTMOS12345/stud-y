# stud-y

> A study planner with a daily schedule, a Pomodoro timer and progress statistics.

stud-y is a Django web app that helps students plan and track their study time. You build your day out of time blocks, reuse days you like as templates, focus with a built-in Pomodoro timer, and see how much you actually studied on the statistics tab.

## Table of Contents

- [Background](#background)
- [Features](#features)
- [Install](#install)
- [Usage](#usage)
- [Project structure](#project-structure)
- [Roadmap](#roadmap)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Background

Most study apps do one thing: a to-do list, a timer, or a calendar. stud-y puts the plan, the timer and the results in one place, so the time you spend in a Pomodoro session counts toward the block you planned, and the statistics show plan vs. reality.

## Features

- **Accounts:** sign up and log in with email or Google (django-allauth)
- **Dashboard:** an overview of your day
- **Schedule:** plan a day with time blocks, pick days from a date selector, and save a day as a reusable template
- **Pomodoro:** focus sessions with configurable times
- **Statistics:** how your study time was spent (demo)
- **Settings:** profile and app settings, including a light theme

## Install

### Dependencies

- Python 3.12+
- PostgreSQL
- Node.js (only to rebuild the Tailwind CSS)

### Setup

```bash
git clone https://github.com/UTMOS12345/stud-y
cd stud-y

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt django-allauth psycopg2-binary

npm install
```

Create the database and user:

```sql
CREATE USER planner_user WITH PASSWORD 'your-password';
CREATE DATABASE planner_db OWNER planner_user;
```

Copy `.env.example` to `.env` next to `requirements.txt`, and fill in `SECRET_KEY` and `DB_PASSWORD`:

```bash
cp .env.example .env
```

Then run the migrations:

```bash
cd study
python manage.py migrate
python manage.py createsuperuser
```

## Usage

```bash
# Terminal 1: rebuild CSS on change
npm run watch:css

# Terminal 2: run the server
cd study
python manage.py runserver
```

Open http://127.0.0.1:8000 and sign up.

| URL | Page |
|---|---|
| `/` | Dashboard |
| `/accounts/login/`, `/accounts/signup/` | Log in and sign up |
| `/schedule/` | Day schedule, templates and statistics |
| `/pomodoro/` | Pomodoro timer |
| `/settings/` | Settings |
| `/admin/` | Django admin |

## Project structure

| App | Role |
|---|---|
| `accounts` | Custom `User` and `Profile` models, login and signup |
| `dashboard` | Home page |
| `schedule` | `DaySchedule`, `ScheduleBlock`, `BlockSession`, `DayTemplate`, `TemplateBlock`, and `Action` models |
| `pomodoro` | Pomodoro timer |
| `settings` | User settings |

The front end uses Django templates with [Tailwind CSS](https://tailwindcss.com) and [daisyUI](https://daisyui.com).

## Roadmap

- [ ] Finish the statistics tab with real charts (daily, weekly and per subject)
- [ ] Link Pomodoro sessions to schedule blocks automatically
- [x] Move `SECRET_KEY`, the database password and `DEBUG` to environment variables
- [ ] Add `django-allauth` and `psycopg2` to `requirements.txt`
- [ ] Stop tracking `node_modules/` and `__pycache__/` in git
- [ ] Reminders and notifications before a block starts
- [ ] Mobile-friendly layout
- [ ] Tests for the schedule and Pomodoro logic
- [ ] Deploy a public demo

## Maintainers

[@UTMOS12345](https://github.com/UTMOS12345)

## Contributing

Bug reports and ideas are welcome in [Issues](https://github.com/UTMOS12345/stud-y/issues).

## License

No license has been chosen yet. Until one is added, all rights are reserved © Imomaliyev Maksudali.
