# Spec: Login and Logout

## Overview
Allow registered users to sign in to Spendly with their email and password, and
sign out when they are done. The POST /login handler looks up the user by email,
verifies the password with werkzeug, and on success stores the user's id and name
in Flask's signed session cookie. The /logout route clears the session and sends
the user back to the landing page. This step is the prerequisite for every
authenticated route (profile, expenses) that follows.

## Depends on
- Step 01 — Database Setup (`get_db()`, `users` table, `created_at` column must exist)
- Step 02 — Registration (users must be creatable so login can be tested)

## Routes
- `GET /login` — render login form — public (already exists as a stub, needs POST added)
- `POST /login` — validate credentials, set session, redirect to `/profile` — public
- `GET /logout` — clear session, redirect to `/` — logged-in (redirect gracefully if not)

## Database changes
No new tables or columns. The existing `users` table is sufficient.
Add one new helper to `database/db.py`:
- `get_user_by_email(email)` — returns the matching `sqlite3.Row` or `None`

## Templates
- **Modify:** `templates/login.html` — ensure the form has `method="POST"` and
  `action="{{ url_for('login') }}"`. Add a flash-message block if not present.
  No structural redesign needed.

## Files to change
- `database/db.py` — add `get_user_by_email(email)` helper
- `app.py` — add `POST` method to `/login` route; implement `/logout`; import
  `session` from flask; import `check_password_hash` from `werkzeug.security`;
  import `get_user_by_email` from `database.db`

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security` is already installed and imported in
`database/db.py`.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings in SQL
- Password verification must use `werkzeug.security.check_password_hash` — never
  compare plaintext
- `get_user_by_email()` must live in `database/db.py`, not inline in the route
- Store only `user_id` (int) and `user_name` (str) in `session` — never store
  the password hash or the full row
- Wrong email or wrong password → same generic flash message ("Invalid email or
  password.") — do not reveal which field was wrong
- On successful login → `redirect(url_for('profile'))`, not a raw string
- On logout → `session.clear()`, then `redirect(url_for('landing'))`
- `/logout` should work even if the user is already logged out (no crash)
- Use CSS variables — never hardcode hex values in any template changes
- All templates extend `base.html`
- Use `abort()` for unexpected server errors, not bare string returns

## Definition of done
- [ ] Submitting correct email + password starts a session and redirects to `/profile`
- [ ] `session['user_id']` is set to the user's integer id after login
- [ ] `session['user_name']` is set to the user's name after login
- [ ] Submitting a wrong password re-renders the form with a generic error message
- [ ] Submitting an email that does not exist re-renders the form with the same
      generic error message (no distinction between bad email vs bad password)
- [ ] Submitting with any blank field re-renders the form with an error
- [ ] `GET /logout` clears the session and redirects to `/`
- [ ] Visiting `/logout` while already logged out redirects safely without crashing
- [ ] `GET /login` still renders the empty form (regression check)
- [ ] No DB logic lives directly in `app.py` — it all belongs in `database/db.py`
- [ ] The demo user (`demo@spendly.com` / `demo123`) can log in successfully
