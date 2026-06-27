# Spec: Profile Page

## Overview
This step implements the `/profile` route, currently a stub returning a plain string. The profile page is the authenticated home base for a logged-in user — it displays their account details (name, email, member-since date) alongside a spending summary (total expenses, total amount spent, and a per-category breakdown). Because the `expenses` table already exists and is seeded, meaningful stats can be shown immediately. The page also serves as the natural post-login landing point and the hub from which future expense-management links will be anchored.

## Depends on
- Step 1 — Database Setup (`users` and `expenses` tables must exist)
- Step 2 — Registration (`users` rows must exist)
- Step 3 — Login and Logout (session must carry `user_id` and `user_name`)

## Routes
- `GET /profile` — fetch user details and expense summary, render `profile.html` — **logged-in only** (redirect to `/login` if `session['user_id']` is absent)

## Database changes
No new tables or columns. Two new query helpers in `database/db.py`:

- `get_user_by_id(user_id)` — returns the full `users` row for the logged-in user (needed for email and `created_at`)
- `get_expense_summary(user_id)` — returns aggregate stats:
  - `total_count` — total number of expense rows
  - `total_amount` — sum of all `amount` values
  - `by_category` — list of `(category, count, total)` rows, ordered by total descending

## Templates
- **Create:** `templates/profile.html` — extends `base.html`; shows user info card and spending summary section

## Files to change
- `app.py` — replace stub `/profile` route with a full implementation that guards for login, calls the two new DB helpers, and passes data to the template
- `database/db.py` — add `get_user_by_id()` and `get_expense_summary()`

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — page-specific styles (imported via `<link>` in `profile.html`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Passwords are never displayed or re-hashed on this page
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Auth guard: if `session.get('user_id')` is falsy, `redirect(url_for('login'))` immediately — no `abort()`
- DB helpers live in `database/db.py` — zero SQL in `app.py`
- Currency is ₹ (INR) everywhere — never `$` or USD
- Page-specific styles go in `static/css/profile.css`, not inline `<style>` tags

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Visiting `/profile` while logged in renders a page (no raw string, no 500)
- [ ] The page displays the logged-in user's name, email, and `created_at` date
- [ ] The page shows the total number of expenses and total amount spent in ₹
- [ ] The page shows a per-category breakdown (category name + total ₹ spent)
- [ ] All links in the template use `url_for()` — no hardcoded URLs
- [ ] `pytest` passes with no regressions
