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

- **Accounts:** sign up and log in with email and password
- **Dashboard:** what is on now and what is next, today's plan, focus time today and this week, a week chart and your focus streak
- **Schedule:** plan a day with time blocks that can run past midnight (each new action gets its own color), pick days from a date selector, and save a day as a reusable template
- **Pomodoro:** focus sessions with configurable times; pick the block you are working on (the timer takes its color), or switch to block mode to time the whole block
- **Focus tracking:** every finished session is saved (and kept in the browser until the server has it, so going offline loses nothing)
- **Habits:** a month calendar with a row per habit, checked as done or not, three states, or a percent that fills the box
- **Statistics:** planned vs focused time per day, per week and per block, all-time records, a 5-week focus calendar and the hours you focus best
- **Settings:** profile, Pomodoro times, time zone, password change and a light theme

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
pip install -r requirements.txt

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
| `schedule` | `DaySchedule`, `ScheduleBlock`, `DayTemplate`, `TemplateBlock`, `Action`, and `BlockSession` (one finished focus session) models; `stats.py` holds the planned vs focused numbers |
| `pomodoro` | Pomodoro timer and the endpoint that saves sessions |
| `habits` | `Habit` and `HabitEntry` models and the habits calendar |
| `settings` | User settings |

The front end uses Django templates with [Tailwind CSS](https://tailwindcss.com) and [daisyUI](https://daisyui.com).

## Roadmap

- [x] Finish the statistics tab with real charts (daily, weekly and per block)
- [x] Link Pomodoro sessions to schedule blocks
- [x] A real dashboard
- [x] Move `SECRET_KEY`, the database password and `DEBUG` to environment variables
- [x] Add `psycopg2` to `requirements.txt`
- [ ] Sign in with Google
- [x] Stop tracking `node_modules/` and `__pycache__/` in git
- [ ] Reminders and notifications before a block starts
- [ ] Mobile-friendly layout
- [x] Tests for the schedule and login (`python manage.py test`)
- [x] Tests for the Pomodoro timer, statistics and dashboard
- [ ] Password reset by email
- [ ] Deploy a public demo

## Maintainers

[@UTMOS12345](https://github.com/UTMOS12345)

## Contributing

Bug reports and ideas are welcome in [Issues](https://github.com/UTMOS12345/stud-y/issues).

## License

[MIT](LICENSE) © Imomaliyev Maksudali
