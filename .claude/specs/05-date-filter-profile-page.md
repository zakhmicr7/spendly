# Spec: Date Filter for Profile Page

## Overview
This feature adds a date range filter to the profile page so users can narrow the expense
summary to a specific time window. When a `start_date` and/or `end_date` are provided as
query parameters, the totals and by-category breakdown on the profile page reflect only
expenses that fall within that window. This is the natural next step after the profile page
(step 04) because it makes the summary actionable — users can now answer "how much did I
spend this month?" without seeing all-time totals.

## Depends on
- Step 01 — Database Setup (`get_db`, `init_db`, expenses table)
- Step 04 — Profile Page (`get_expense_summary`, `profile.html`)

## Routes
- `GET /profile?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` — existing profile route,
  extended to accept optional date filter query params — logged-in only

No new routes.

## Database changes
No new tables or columns.

`get_expense_summary` in `database/db.py` must be extended to accept optional
`start_date` and `end_date` parameters and filter with `WHERE date >= ? AND date <= ?`
when provided. Both parameters are optional and independent.

## Templates
- **Modify:** `templates/profile.html` — add a date filter form above the summary card
  with two `<input type="date">` fields (Start Date, End Date) and a Filter button.
  The form submits via `GET` to `/profile`. Active filter values must be pre-filled
  into the inputs on page load. An active filter indicator (e.g. "Filtered: Jun 1 – Jun 30")
  must appear when a filter is in effect, with a "Clear" link that strips the query params.

## Files to change
- `database/db.py` — extend `get_expense_summary` signature and SQL
- `app.py` — read `start_date`/`end_date` from `request.args`, pass to `get_expense_summary`,
  pass values back to template for form pre-fill
- `templates/profile.html` — add date filter form and active-filter indicator
- `static/css/profile.css` — add styles for the filter form and active-filter badge

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Date inputs must use `type="date"` (HTML5 native picker)
- Filter form must use `method="GET"` — never POST for a read-only filter
- `start_date` and `end_date` must be validated: if present they must match `YYYY-MM-DD`
  format; invalid values are silently ignored (treat as if not provided)
- If `start_date > end_date`, swap them before querying so results are always correct
- The route must remain idempotent — no side effects from visiting the filtered URL
- The filter inputs and Clear link must only appear when the user is logged in (already guaranteed by the auth guard)

## Definition of done
- [ ] Visiting `/profile` with no query params shows the same unfiltered summary as before
- [ ] Visiting `/profile?start_date=2026-06-01&end_date=2026-06-15` shows only expenses
      in that range (totals and by-category)
- [ ] The date inputs on the profile page are pre-filled with the active filter values
- [ ] A "Clear" link appears when a filter is active and removes the filter when clicked
- [ ] Providing only `start_date` (no `end_date`) filters to expenses on or after that date
- [ ] Providing only `end_date` (no `start_date`) filters to expenses on or before that date
- [ ] An invalid date string (e.g. `start_date=abc`) is ignored and the page loads normally
- [ ] `start_date` > `end_date` is handled gracefully (results still shown, not an error)
- [ ] No raw SQL strings built with f-strings or string concatenation
- [ ] All existing profile page tests still pass
