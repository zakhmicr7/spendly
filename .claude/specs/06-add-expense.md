# Spec: Add Expense

## Overview
This feature allows a logged-in user to submit a new expense via a form at `/expenses/add`. It converts the existing stub route into a fully functional GET (render form) + POST (handle submission) pair, writes the new record to the `expenses` table, and redirects back to the profile page on success. This is the first write operation a user performs after viewing their expense summary.

## Depends on
- Step 01 — Database Setup (expenses table exists)
- Step 02 — Registration (users table, session)
- Step 03 — Login and Logout (session-based auth)
- Step 04 — Profile Page (redirect destination after save)

## Routes
- `GET /expenses/add` — Render the add-expense form — logged-in only
- `POST /expenses/add` — Validate and save the new expense, redirect to profile — logged-in only

## Database changes
No new tables or columns. The `expenses` table already has all required columns:
`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

A new DB helper `create_expense()` must be added to `database/db.py`.

## Templates
- **Create:** `templates/add_expense.html` — form with fields: amount, category, date, description (optional)

## Files to change
- `app.py` — replace the `add_expense` stub with GET + POST implementation
- `database/db.py` — add `create_expense(user_id, amount, category, date, description)` helper
- `app.py` import line — add `create_expense` to the import from `database.db`

## Files to create
- `templates/add_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings in SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Route must redirect to login if `session['user_id']` is absent
- `amount` must be validated as a positive number server-side; reject non-numeric or ≤ 0 values
- `category` must be one of the allowed values: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- `date` must be a valid `YYYY-MM-DD` string; use the existing `_parse_date()` helper in `app.py`
- On validation failure, re-render the form with a `flash()` message — do not lose the user's input
- On success, redirect to `url_for('profile')` with a success flash message
- `description` is optional — store `None` if blank
- `create_expense()` belongs in `database/db.py`, not inline in the route
- Use `abort(403)` if a logged-out user POSTs directly to the route

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders a form with amount, category, date, and description fields
- [ ] Submitting the form with valid data saves a new row to `expenses` and redirects to `/profile`
- [ ] The new expense appears in the profile page expense summary immediately after redirect
- [ ] Submitting with a missing or invalid amount shows a flash error and re-renders the form
- [ ] Submitting with an invalid category shows a flash error and re-renders the form
- [ ] Submitting with an invalid or missing date shows a flash error and re-renders the form
- [ ] Description field is optional — form submits successfully when left blank
- [ ] Currency is displayed in ₹ (INR) — no $ signs anywhere
