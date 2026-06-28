"""
tests/test_06-add-expense.py

Pytest tests for the Spendly "Add Expense" feature.

Covers
------
- Auth guard: unauthenticated GET → 302 /login, unauthenticated POST → 403
- Authenticated GET: 200, form fields present, all valid categories visible, no $ sign
- POST happy path: valid data → 302 to /profile, flash success, record in DB
- POST happy path: blank description → succeeds, stored as None
- POST happy path: each of the 7 valid categories is accepted
- POST validation — amount: empty, non-numeric, zero, negative → 200 flash error, no DB write
- POST validation — category: empty, invalid string → 200 flash error, no DB write
- POST validation — date: empty, wrong format → 200 flash error, no DB write
- DB side effects: user_id, amount, category, date, description all verified in DB
- Edge cases: decimal amounts, large amounts, SQL injection in description, form data preserved

Isolation strategy
------------------
Each test receives a fresh temporary SQLite file. `monkeypatch` redirects
database.db._DB_PATH to that file before init_db() runs, so the real
spendly.db is never touched and tests never share state.
"""

import sys
import os

# Ensure the project root is on the Python path so `import app` and
# `import database.db` resolve correctly regardless of how pytest is invoked.
sys.path.insert(0, '/Users/abhitzakhmi/Desktop/expense-tracker')

import pytest
import database.db as db_module
from app import app as flask_app
from database.db import init_db, create_user, get_db


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_USER_NAME = 'Expense Tester'
TEST_USER_EMAIL = 'expense@spendly.test'
TEST_USER_PASSWORD = 'securepass99'

VALID_CATEGORIES = ['Food', 'Transport', 'Bills', 'Health', 'Entertainment', 'Shopping', 'Other']

VALID_EXPENSE = {
    'amount': '250.00',
    'category': 'Food',
    'date': '2026-06-15',
    'description': 'Lunch at work',
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    """
    Flask test app backed by an isolated temporary SQLite file.

    monkeypatch redirects database.db._DB_PATH to tmp_path/test_spendly.db
    before init_db() runs, so all get_db() calls during that test use the
    temporary file. The original path is restored automatically after each test.
    """
    db_path = str(tmp_path / 'test_spendly.db')
    monkeypatch.setattr(db_module, '_DB_PATH', db_path)

    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key-add-expense',
        'WTF_CSRF_ENABLED': False,
    })
    with flask_app.app_context():
        init_db()
        yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def registered_user(app):
    """
    Insert TEST_USER into the isolated DB using the DB helper directly.
    Returns (user_id, email, password) so tests can reference the user_id
    for direct DB queries and the credentials for logging in.
    """
    user_id = create_user(TEST_USER_NAME, TEST_USER_EMAIL, TEST_USER_PASSWORD)
    return user_id, TEST_USER_EMAIL, TEST_USER_PASSWORD


@pytest.fixture
def auth_client(client, registered_user):
    """
    Test client already logged in as TEST_USER.
    Depends on registered_user so the user exists before the login POST.
    """
    _, email, password = registered_user
    resp = client.post('/login', data={'email': email, 'password': password})
    assert resp.status_code == 302, (
        'Login POST must return 302; check that register/login routes are functional'
    )
    return client


# ---------------------------------------------------------------------------
# 1. Auth guard — GET /expenses/add
# ---------------------------------------------------------------------------

class TestAddExpenseGetAuthGuard:

    def test_unauthenticated_get_returns_302(self, client):
        """GET /expenses/add without a session must return 302."""
        response = client.get('/expenses/add')
        assert response.status_code == 302, \
            'Expected 302 redirect for unauthenticated GET /expenses/add'

    def test_unauthenticated_get_redirects_to_login(self, client):
        """Unauthenticated GET must redirect to /login."""
        response = client.get('/expenses/add')
        assert '/login' in response.headers.get('Location', ''), \
            'Unauthenticated GET /expenses/add must redirect to /login'

    def test_unauthenticated_get_does_not_return_200(self, client):
        """Unauthenticated access must never serve the add-expense form."""
        response = client.get('/expenses/add')
        assert response.status_code != 200, \
            'Unauthenticated GET /expenses/add must not return 200'

    def test_authenticated_get_returns_200(self, auth_client):
        """Logged-in user must receive 200 from GET /expenses/add."""
        response = auth_client.get('/expenses/add')
        assert response.status_code == 200, \
            'Authenticated GET /expenses/add must return 200'


# ---------------------------------------------------------------------------
# 2. Auth guard — POST /expenses/add
# ---------------------------------------------------------------------------

class TestAddExpensePostAuthGuard:

    def test_unauthenticated_post_returns_403(self, client):
        """Direct unauthenticated POST must return 403 (not a redirect)."""
        response = client.post('/expenses/add', data=VALID_EXPENSE)
        assert response.status_code == 403, \
            'Unauthenticated POST /expenses/add must return 403'

    def test_unauthenticated_post_does_not_return_302(self, client):
        """Unauthenticated POST must not redirect — it must be rejected with 403."""
        response = client.post('/expenses/add', data=VALID_EXPENSE)
        assert response.status_code != 302, \
            'Unauthenticated POST must not produce a redirect'


# ---------------------------------------------------------------------------
# 3. Form rendering — authenticated GET
# ---------------------------------------------------------------------------

class TestAddExpenseFormRendering:

    def test_form_contains_amount_field(self, auth_client):
        """Add-expense form must include an input with name="amount"."""
        response = auth_client.get('/expenses/add')
        assert b'name="amount"' in response.data, \
            'Form must contain an amount input field (name="amount")'

    def test_form_contains_category_field(self, auth_client):
        """Add-expense form must include a field with name="category"."""
        response = auth_client.get('/expenses/add')
        assert b'name="category"' in response.data, \
            'Form must contain a category field (name="category")'

    def test_form_contains_date_field(self, auth_client):
        """Add-expense form must include an input with name="date"."""
        response = auth_client.get('/expenses/add')
        assert b'name="date"' in response.data, \
            'Form must contain a date input field (name="date")'

    def test_form_contains_description_field(self, auth_client):
        """Add-expense form must include a field with name="description"."""
        response = auth_client.get('/expenses/add')
        assert b'name="description"' in response.data, \
            'Form must contain a description field (name="description")'

    @pytest.mark.parametrize('category', VALID_CATEGORIES)
    def test_form_shows_each_valid_category(self, auth_client, category):
        """All seven valid categories must appear in the rendered form."""
        response = auth_client.get('/expenses/add')
        assert category.encode() in response.data, \
            f'Category "{category}" must appear in the add-expense form'

    def test_no_dollar_signs_on_page(self, auth_client):
        """Currency must be ₹ (INR) — no $ signs must appear anywhere on the page."""
        response = auth_client.get('/expenses/add')
        assert b'$' not in response.data, \
            'No dollar signs must appear; currency is ₹ (INR)'

    def test_page_renders_html(self, auth_client):
        """GET /expenses/add must return an HTML page (not a plain text stub)."""
        response = auth_client.get('/expenses/add')
        data = response.data.decode('utf-8')
        assert '<html' in data or '<!DOCTYPE' in data, \
            'Response must be an HTML page, not a plain string stub'


# ---------------------------------------------------------------------------
# 4. POST happy path
# ---------------------------------------------------------------------------

class TestAddExpensePostHappyPath:

    def test_valid_post_redirects(self, auth_client):
        """Valid POST must return a 302 redirect."""
        response = auth_client.post('/expenses/add', data=VALID_EXPENSE)
        assert response.status_code == 302, \
            'Valid POST /expenses/add must return 302 redirect'

    def test_valid_post_redirects_to_profile(self, auth_client):
        """Valid POST must redirect to /profile."""
        response = auth_client.post('/expenses/add', data=VALID_EXPENSE)
        assert '/profile' in response.headers.get('Location', ''), \
            'Valid POST must redirect to /profile'

    def test_valid_post_flash_success_message(self, auth_client):
        """Valid POST must flash a success message visible on the profile page."""
        response = auth_client.post(
            '/expenses/add', data=VALID_EXPENSE, follow_redirects=True
        )
        data = response.data.decode('utf-8')
        assert 'Expense added successfully' in data, \
            'Success flash message "Expense added successfully" must appear after redirect'

    def test_valid_post_creates_db_record(self, auth_client, registered_user):
        """Valid POST must insert a new row into the expenses table."""
        user_id, _, _ = registered_user
        auth_client.post('/expenses/add', data=VALID_EXPENSE)

        conn = get_db()
        try:
            rows = conn.execute(
                'SELECT * FROM expenses WHERE user_id = ?', (user_id,)
            ).fetchall()
        finally:
            conn.close()

        assert len(rows) == 1, \
            f'Expected 1 expense in DB after valid POST, found {len(rows)}'

    def test_valid_post_blank_description_succeeds(self, auth_client):
        """Blank description must not block submission — it is an optional field."""
        data = {**VALID_EXPENSE, 'description': ''}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 302, \
            'POST with blank description must succeed and return 302'

    def test_valid_post_blank_description_stored_as_none(self, auth_client, registered_user):
        """A blank description must be stored as NULL (None) in the DB."""
        user_id, _, _ = registered_user
        data = {**VALID_EXPENSE, 'description': ''}
        auth_client.post('/expenses/add', data=data)

        conn = get_db()
        try:
            row = conn.execute(
                'SELECT description FROM expenses WHERE user_id = ?', (user_id,)
            ).fetchone()
        finally:
            conn.close()

        assert row is not None, 'Expected an expense record in DB'
        assert row['description'] is None, \
            f'Blank description must be stored as NULL, got: {row["description"]!r}'

    @pytest.mark.parametrize('category', VALID_CATEGORIES)
    def test_each_valid_category_is_accepted(self, auth_client, category):
        """Each of the 7 valid categories must result in a 302 (acceptance)."""
        data = {**VALID_EXPENSE, 'category': category}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 302, \
            f'Category "{category}" must be accepted; expected 302, got {response.status_code}'

    def test_decimal_amount_is_accepted(self, auth_client):
        """An amount with decimal places (e.g. 99.50) must be accepted."""
        data = {**VALID_EXPENSE, 'amount': '99.50'}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 302, \
            'Decimal amount 99.50 must be accepted and produce a 302'

    def test_large_amount_is_accepted(self, auth_client):
        """A large positive amount (e.g. 1000000) must be accepted."""
        data = {**VALID_EXPENSE, 'amount': '1000000'}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 302, \
            'Large amount 1000000 must be accepted and produce a 302'


# ---------------------------------------------------------------------------
# 5. POST validation — amount
# ---------------------------------------------------------------------------

class TestAddExpenseAmountValidation:

    @pytest.mark.parametrize('bad_amount', ['', 'abc', '0', '-10', '0.0', '-0.01'])
    def test_invalid_amount_returns_200(self, auth_client, bad_amount):
        """Invalid or non-positive amounts must cause re-render (200), not redirect."""
        data = {**VALID_EXPENSE, 'amount': bad_amount}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 200, \
            f'Amount "{bad_amount}" must trigger re-render (200), got {response.status_code}'

    @pytest.mark.parametrize('bad_amount', ['', 'abc', '0', '-10', '0.0', '-0.01'])
    def test_invalid_amount_flashes_error(self, auth_client, bad_amount):
        """Invalid amount must flash an appropriate error message."""
        data = {**VALID_EXPENSE, 'amount': bad_amount}
        response = auth_client.post('/expenses/add', data=data)
        assert b'Amount must be a positive number' in response.data, \
            f'Expected flash error for amount "{bad_amount}"; got: {response.data[:300]}'

    @pytest.mark.parametrize('bad_amount', ['', 'abc', '0', '-10'])
    def test_invalid_amount_does_not_create_db_record(self, auth_client, registered_user, bad_amount):
        """Invalid amount must not write any record to the expenses table."""
        user_id, _, _ = registered_user
        data = {**VALID_EXPENSE, 'amount': bad_amount}
        auth_client.post('/expenses/add', data=data)

        conn = get_db()
        try:
            count = conn.execute(
                'SELECT COUNT(*) FROM expenses WHERE user_id = ?', (user_id,)
            ).fetchone()[0]
        finally:
            conn.close()

        assert count == 0, \
            f'Invalid amount "{bad_amount}" must not create a DB record; found {count}'

    def test_missing_amount_key_returns_200(self, auth_client):
        """Omitting the amount key entirely must trigger re-render (200)."""
        data = {k: v for k, v in VALID_EXPENSE.items() if k != 'amount'}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 200, \
            'Missing amount key must cause re-render (200)'

    def test_whitespace_only_amount_flashes_error(self, auth_client):
        """Whitespace-only amount must be treated as invalid."""
        data = {**VALID_EXPENSE, 'amount': '   '}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 200, \
            'Whitespace-only amount must cause re-render (200)'
        assert b'Amount must be a positive number' in response.data, \
            'Whitespace-only amount must flash error'


# ---------------------------------------------------------------------------
# 6. POST validation — category
# ---------------------------------------------------------------------------

class TestAddExpenseCategoryValidation:

    def test_empty_category_returns_200(self, auth_client):
        """Empty category string must cause re-render (200)."""
        data = {**VALID_EXPENSE, 'category': ''}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 200, \
            'Empty category must trigger re-render (200)'

    def test_empty_category_flashes_error(self, auth_client):
        """Empty category must flash a category error message."""
        data = {**VALID_EXPENSE, 'category': ''}
        response = auth_client.post('/expenses/add', data=data)
        assert b'valid category' in response.data, \
            'Empty category must flash a "valid category" error'

    @pytest.mark.parametrize('bad_category', ['Groceries', 'travel', 'FOOD', 'random', '123'])
    def test_invalid_category_string_returns_200(self, auth_client, bad_category):
        """Unrecognized category values must cause re-render (200)."""
        data = {**VALID_EXPENSE, 'category': bad_category}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 200, \
            f'Invalid category "{bad_category}" must trigger re-render (200)'

    @pytest.mark.parametrize('bad_category', ['Groceries', 'travel', 'FOOD'])
    def test_invalid_category_flashes_error(self, auth_client, bad_category):
        """Unrecognized category must flash an error message."""
        data = {**VALID_EXPENSE, 'category': bad_category}
        response = auth_client.post('/expenses/add', data=data)
        assert b'valid category' in response.data, \
            f'Invalid category "{bad_category}" must flash a "valid category" error'

    @pytest.mark.parametrize('bad_category', ['Groceries', '', 'travel'])
    def test_invalid_category_does_not_create_db_record(self, auth_client, registered_user, bad_category):
        """Invalid category must not write any record to the expenses table."""
        user_id, _, _ = registered_user
        data = {**VALID_EXPENSE, 'category': bad_category}
        auth_client.post('/expenses/add', data=data)

        conn = get_db()
        try:
            count = conn.execute(
                'SELECT COUNT(*) FROM expenses WHERE user_id = ?', (user_id,)
            ).fetchone()[0]
        finally:
            conn.close()

        assert count == 0, \
            f'Invalid category "{bad_category}" must not create a DB record; found {count}'


# ---------------------------------------------------------------------------
# 7. POST validation — date
# ---------------------------------------------------------------------------

class TestAddExpenseDateValidation:

    def test_empty_date_returns_200(self, auth_client):
        """Empty date must cause re-render (200)."""
        data = {**VALID_EXPENSE, 'date': ''}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 200, \
            'Empty date must trigger re-render (200)'

    def test_empty_date_flashes_error(self, auth_client):
        """Empty date must flash a date error message."""
        data = {**VALID_EXPENSE, 'date': ''}
        response = auth_client.post('/expenses/add', data=data)
        assert b'valid date' in response.data, \
            'Empty date must flash a "valid date" error'

    @pytest.mark.parametrize('bad_date', [
        'not-a-date',
        '28/06/2026',     # DD/MM/YYYY — wrong separator and order
        '06-28-2026',     # MM-DD-YYYY — wrong order
        '2026/06/28',     # YYYY/MM/DD — wrong separator
        '2026-13-01',     # month 13 does not exist
        '2026-06-32',     # day 32 does not exist
        '20260628',       # no separators
        'June 28 2026',   # human-readable format
    ])
    def test_invalid_date_format_returns_200(self, auth_client, bad_date):
        """Dates not in YYYY-MM-DD format must cause re-render (200)."""
        data = {**VALID_EXPENSE, 'date': bad_date}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 200, \
            f'Invalid date "{bad_date}" must trigger re-render (200)'

    @pytest.mark.parametrize('bad_date', ['not-a-date', '06/28/2026', '28-06-2026'])
    def test_invalid_date_flashes_error(self, auth_client, bad_date):
        """Invalid date must flash a date error message."""
        data = {**VALID_EXPENSE, 'date': bad_date}
        response = auth_client.post('/expenses/add', data=data)
        assert b'valid date' in response.data, \
            f'Invalid date "{bad_date}" must flash a "valid date" error'

    @pytest.mark.parametrize('bad_date', ['not-a-date', '', '06/28/2026'])
    def test_invalid_date_does_not_create_db_record(self, auth_client, registered_user, bad_date):
        """Invalid date must not write any record to the expenses table."""
        user_id, _, _ = registered_user
        data = {**VALID_EXPENSE, 'date': bad_date}
        auth_client.post('/expenses/add', data=data)

        conn = get_db()
        try:
            count = conn.execute(
                'SELECT COUNT(*) FROM expenses WHERE user_id = ?', (user_id,)
            ).fetchone()[0]
        finally:
            conn.close()

        assert count == 0, \
            f'Invalid date "{bad_date}" must not create a DB record; found {count}'


# ---------------------------------------------------------------------------
# 8. DB side effects — verify record contents after valid POST
# ---------------------------------------------------------------------------

class TestAddExpenseDbSideEffects:

    def _post_and_fetch(self, auth_client, registered_user, data):
        """Helper: POST expense and return the resulting DB row."""
        user_id, _, _ = registered_user
        auth_client.post('/expenses/add', data=data)

        conn = get_db()
        try:
            row = conn.execute(
                'SELECT * FROM expenses WHERE user_id = ?', (user_id,)
            ).fetchone()
        finally:
            conn.close()
        return row

    def test_db_record_has_correct_user_id(self, auth_client, registered_user):
        """Stored expense must reference the logged-in user's ID."""
        user_id, _, _ = registered_user
        row = self._post_and_fetch(auth_client, registered_user, VALID_EXPENSE)

        assert row is not None, 'No expense record found in DB after valid POST'
        assert row['user_id'] == user_id, \
            f'Expected user_id={user_id} in DB, got {row["user_id"]}'

    def test_db_record_has_correct_amount(self, auth_client, registered_user):
        """Stored expense must have the submitted amount."""
        row = self._post_and_fetch(auth_client, registered_user, VALID_EXPENSE)

        assert row is not None, 'No expense record found in DB after valid POST'
        assert row['amount'] == pytest.approx(float(VALID_EXPENSE['amount'])), \
            f'Expected amount {VALID_EXPENSE["amount"]} in DB, got {row["amount"]}'

    def test_db_record_has_correct_category(self, auth_client, registered_user):
        """Stored expense must have the submitted category."""
        row = self._post_and_fetch(auth_client, registered_user, VALID_EXPENSE)

        assert row is not None, 'No expense record found in DB after valid POST'
        assert row['category'] == VALID_EXPENSE['category'], \
            f'Expected category "{VALID_EXPENSE["category"]}" in DB, got "{row["category"]}"'

    def test_db_record_has_correct_date(self, auth_client, registered_user):
        """Stored expense must have the submitted date in YYYY-MM-DD format."""
        row = self._post_and_fetch(auth_client, registered_user, VALID_EXPENSE)

        assert row is not None, 'No expense record found in DB after valid POST'
        assert row['date'] == VALID_EXPENSE['date'], \
            f'Expected date "{VALID_EXPENSE["date"]}" in DB, got "{row["date"]}"'

    def test_db_record_has_correct_description(self, auth_client, registered_user):
        """Stored expense must have the submitted description text."""
        row = self._post_and_fetch(auth_client, registered_user, VALID_EXPENSE)

        assert row is not None, 'No expense record found in DB after valid POST'
        assert row['description'] == VALID_EXPENSE['description'], \
            f'Expected description "{VALID_EXPENSE["description"]}" in DB, got "{row["description"]}"'

    def test_db_record_blank_description_is_null(self, auth_client, registered_user):
        """Blank description must be stored as NULL, not as an empty string."""
        data = {**VALID_EXPENSE, 'description': ''}
        row = self._post_and_fetch(auth_client, registered_user, data)

        assert row is not None, 'No expense record found in DB after valid POST'
        assert row['description'] is None, \
            f'Blank description must be NULL in DB, got: {row["description"]!r}'

    def test_db_record_decimal_amount_stored_correctly(self, auth_client, registered_user):
        """Decimal amount must be stored with full precision."""
        data = {**VALID_EXPENSE, 'amount': '99.75'}
        row = self._post_and_fetch(auth_client, registered_user, data)

        assert row is not None, 'No expense record found in DB after valid POST'
        assert row['amount'] == pytest.approx(99.75), \
            f'Expected amount 99.75 in DB, got {row["amount"]}'

    def test_multiple_expenses_stored_independently(self, auth_client, registered_user):
        """Submitting two valid expenses must produce two separate DB records."""
        user_id, _, _ = registered_user

        first = {**VALID_EXPENSE, 'amount': '100.00', 'description': 'First'}
        second = {**VALID_EXPENSE, 'amount': '200.00', 'category': 'Transport', 'description': 'Second'}

        auth_client.post('/expenses/add', data=first)
        auth_client.post('/expenses/add', data=second)

        conn = get_db()
        try:
            rows = conn.execute(
                'SELECT * FROM expenses WHERE user_id = ? ORDER BY id', (user_id,)
            ).fetchall()
        finally:
            conn.close()

        assert len(rows) == 2, \
            f'Expected 2 expense records after two valid POSTs, found {len(rows)}'
        assert rows[0]['amount'] == pytest.approx(100.00), \
            f'First expense amount must be 100.00, got {rows[0]["amount"]}'
        assert rows[1]['amount'] == pytest.approx(200.00), \
            f'Second expense amount must be 200.00, got {rows[1]["amount"]}'


# ---------------------------------------------------------------------------
# 9. Edge cases
# ---------------------------------------------------------------------------

class TestAddExpenseEdgeCases:

    def test_sql_injection_in_description_does_not_break(self, auth_client, registered_user):
        """
        SQL injection attempts in description must be stored safely (parameterised
        queries prevent injection) and must not raise an error or corrupt the DB.
        """
        user_id, _, _ = registered_user
        injection = "'; DROP TABLE expenses; --"
        data = {**VALID_EXPENSE, 'description': injection}
        response = auth_client.post('/expenses/add', data=data)

        # Must redirect (302) — not crash
        assert response.status_code == 302, \
            'SQL injection in description must not cause a server error'

        # expenses table must still exist and have the row
        conn = get_db()
        try:
            row = conn.execute(
                'SELECT description FROM expenses WHERE user_id = ?', (user_id,)
            ).fetchone()
        finally:
            conn.close()

        assert row is not None, \
            'expenses table must still exist and contain the record after injection attempt'
        assert row['description'] == injection, \
            'Injected description must be stored literally, not interpreted as SQL'

    def test_form_data_preserved_on_amount_error(self, auth_client):
        """
        On amount validation failure, the previously entered amount value must
        appear in the re-rendered form so the user does not lose their input.
        """
        data = {**VALID_EXPENSE, 'amount': 'bad-value'}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 200, \
            'Validation failure must re-render the form (200)'
        # The submitted (invalid) amount should appear in the form response
        assert b'bad-value' in response.data, \
            'Invalid amount value must be preserved in the re-rendered form'

    def test_form_data_preserved_on_category_error(self, auth_client):
        """
        On category validation failure, the submitted date must appear in the
        re-rendered form so the user does not lose their input.
        """
        data = {**VALID_EXPENSE, 'category': 'InvalidCat'}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 200, \
            'Category validation failure must re-render the form (200)'
        # The submitted date (a valid field) should be preserved
        assert VALID_EXPENSE['date'].encode() in response.data, \
            'Valid date must be preserved in the form when category fails validation'

    def test_very_long_description_is_accepted(self, auth_client):
        """An unusually long description (500 chars) must not cause a server error."""
        long_desc = 'A' * 500
        data = {**VALID_EXPENSE, 'description': long_desc}
        response = auth_client.post('/expenses/add', data=data)
        assert response.status_code == 302, \
            '500-character description must be accepted (302), not rejected'

    def test_whitespace_description_stored_as_none(self, auth_client, registered_user):
        """
        A description containing only whitespace must be treated as blank and
        stored as NULL, not as a whitespace string.
        """
        user_id, _, _ = registered_user
        data = {**VALID_EXPENSE, 'description': '   '}
        auth_client.post('/expenses/add', data=data)

        conn = get_db()
        try:
            row = conn.execute(
                'SELECT description FROM expenses WHERE user_id = ?', (user_id,)
            ).fetchone()
        finally:
            conn.close()

        assert row is not None, 'Expected a DB record after POST'
        assert row['description'] is None, \
            f'Whitespace description must be stored as NULL, got: {row["description"]!r}'

    def test_no_dollar_signs_on_validation_error_page(self, auth_client):
        """Re-rendered form on validation error must also not contain $ signs."""
        data = {**VALID_EXPENSE, 'amount': '-5'}
        response = auth_client.post('/expenses/add', data=data)
        assert b'$' not in response.data, \
            'Re-rendered form must not contain $ signs; currency is ₹ (INR)'

    def test_expense_appears_on_profile_page_after_add(self, auth_client):
        """
        After a successful POST, the new expense must be visible on the profile
        page — confirming the DB write and the profile query are both working.
        """
        data = {
            'amount': '375.00',
            'category': 'Health',
            'date': '2026-06-20',
            'description': 'Pharmacy visit',
        }
        auth_client.post('/expenses/add', data=data)
        profile_response = auth_client.get('/profile')
        assert profile_response.status_code == 200, \
            'Profile page must return 200 after adding expense'
        profile_data = profile_response.data.decode('utf-8')
        assert '375.00' in profile_data, \
            'Newly added expense amount (375.00) must appear on the profile page'
        assert 'Health' in profile_data, \
            'Newly added expense category (Health) must appear on the profile page'
