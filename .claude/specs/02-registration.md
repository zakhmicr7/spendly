# Spec: Registration

## Overview
Allow new users to create an account on Spendly by submitting their name,
email, and password. The POST handler validates the input server-side, hashes
the password with werkzeug, inserts the user into the database, and redirects
to the login page on success. Duplicate email addresses are caught and reported
as a user-facing error. This step is the entry point for all authenticated
features that follow.

## Depends on
Step 01 — Database Setup (users table must exist, `get_db()` must be working).

## Routes
- `GET /register` — render the registration form — public (already exists, no change)
- `POST /register` — validate input, create user, redirect to `/login` — public

## Database changes
No new tables or columns. The existing `users` table (id, name, email,
password_hash, created_at) is sufficient. The `UNIQUE` constraint on `email`
handles duplicate detection.

## Templates
- **Modify:** `templates/register.html` — already supports `{% if error %}` block;
  no structural changes needed. Ensure the form has `method="POST"` and
  `action="{{ url_for('register') }}"` (verify these are present).

## Files to change
- `database/db.py` — add `create_user(name, email, password)` helper
- `app.py` — add `POST` method to `/register` route; import `request`,
  `redirect`, `url_for`, `sqlite3`; import `create_user` from `database.db`

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.generate_password_hash` is already
imported in `database/db.py`.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`
- `create_user()` must live in `database/db.py`, not inline in the route
- The route must use `abort()` for unexpected server errors, not bare string returns
- Duplicate email → catch `sqlite3.IntegrityError` and re-render form with error
- Password must be at least 8 characters (server-side check, not just HTML5)
- All form fields (name, email, password) must be non-empty (strip whitespace)
- On success → `redirect(url_for('login'))`, never a raw string
- Use CSS variables — never hardcode hex values in any template changes
- All templates extend `base.html`

## Definition of done
- [ ] Submitting valid name/email/password creates a new row in `users`
- [ ] Password is stored as a werkzeug hash, never plaintext
- [ ] Submitting a duplicate email re-renders the form with a clear error message
- [ ] Submitting a password shorter than 8 characters re-renders the form with an error
- [ ] Submitting with any blank field re-renders the form with an error
- [ ] Successful registration redirects to `/login`
- [ ] The `GET /register` route still works and renders the empty form
- [ ] No DB logic lives directly in `app.py` — it is all in `database/db.py`
