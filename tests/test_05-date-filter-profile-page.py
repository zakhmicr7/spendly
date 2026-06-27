"""
tests/test_05-date-filter-profile-page.py

Pytest tests for the Spendly date filter feature on GET /profile.

Covers
------
- Auth guard (unauthenticated → redirect, authenticated → 200)
- Unfiltered summary (no query params)
- Date-range filter: both dates, only start_date, only end_date
- Edge cases: invalid date strings, blank params, start_date > end_date
- Template UI: filter-active-bar, Clear link, input pre-fill, form method,
  type="date" attributes
- DB-layer unit tests for get_expense_summary (parameterised queries,
  boundary inclusivity, user isolation, ordering)

Isolation strategy
------------------
Each test receives a fresh temporary SQLite file.  `monkeypatch` redirects
database.db._DB_PATH to that file before init_db() is called, so the real
spendly.db is never touched and tests never share state.
"""

import pytest
import database.db as db_module
from app import app as flask_app
from database.db import init_db, create_user, get_db, get_expense_summary


# ---------------------------------------------------------------------------
# Seed constants — five expenses spanning May, June, and July 2026
# ---------------------------------------------------------------------------

TEST_USER_NAME = 'Filter Tester'
TEST_USER_EMAIL = 'filter@spendly.test'
TEST_USER_PASSWORD = 'testpassword99'

# (amount, category, date YYYY-MM-DD, description)
TEST_EXPENSES = [
    (500.00,  'Food',      '2026-05-15', 'May food expense'),
    (200.00,  'Transport', '2026-06-01', 'Metro card recharge'),
    (300.00,  'Food',      '2026-06-10', 'Weekly groceries'),
    (1000.00, 'Bills',     '2026-06-20', 'Electricity bill'),
    (800.00,  'Shopping',  '2026-07-05', 'Seasonal shopping'),
]

# Pre-computed expected totals for each filter scenario
TOTAL_ALL           = 2800.00   # no filter:  500+200+300+1000+800
COUNT_ALL           = 5

TOTAL_JUN1_JUN15    = 500.00    # start=2026-06-01 end=2026-06-15: 200+300
COUNT_JUN1_JUN15    = 2

TOTAL_FROM_JUN10    = 2100.00   # start=2026-06-10 only:          300+1000+800
COUNT_FROM_JUN10    = 3

TOTAL_UNTIL_JUN10   = 1000.00   # end=2026-06-10 only:            500+200+300
COUNT_UNTIL_JUN10   = 3

TOTAL_JUN1_JUN20    = 1500.00   # after auto-swap 2026-06-20/2026-06-01: 200+300+1000
COUNT_JUN1_JUN20    = 3


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    """
    Flask test app backed by an isolated temporary SQLite file.

    monkeypatch redirects database.db._DB_PATH to tmp_path/test_spendly.db
    before init_db() runs, so all get_db() calls in that test use the
    temporary file.  The original path is restored after each test.
    """
    db_path = str(tmp_path / 'test_spendly.db')
    monkeypatch.setattr(db_module, '_DB_PATH', db_path)

    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key-spendly',
        'WTF_CSRF_ENABLED': False,
    })
    with flask_app.app_context():
        init_db()
        yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded_user_id(app):
    """
    Insert TEST_USER into the isolated DB and seed TEST_EXPENSES for that user.
    Returns the integer user_id so DB-layer tests can call helpers directly.
    """
    user_id = create_user(TEST_USER_NAME, TEST_USER_EMAIL, TEST_USER_PASSWORD)
    conn = get_db()
    try:
        conn.executemany(
            'INSERT INTO expenses (user_id, amount, category, date, description)'
            ' VALUES (?, ?, ?, ?, ?)',
            [(user_id, amount, category, date, desc)
             for amount, category, date, desc in TEST_EXPENSES],
        )
        conn.commit()
    finally:
        conn.close()
    return user_id


@pytest.fixture
def auth_client(client, seeded_user_id):
    """
    Test client already logged in as TEST_USER with all seeded expenses present.
    seeded_user_id is declared as a dependency so expenses are created before
    the client hits any route.
    """
    resp = client.post('/login', data={
        'email': TEST_USER_EMAIL,
        'password': TEST_USER_PASSWORD,
    })
    assert resp.status_code == 302, (
        'Login POST must return 302; check register/login routes are functional'
    )
    return client


# ---------------------------------------------------------------------------
# 1. Auth guard
# ---------------------------------------------------------------------------

class TestProfileAuthGuard:

    def test_unauthenticated_request_redirects_to_login(self, client):
        """GET /profile without a session must 302 to /login."""
        response = client.get('/profile')
        assert response.status_code == 302, \
            'Expected 302 redirect for unauthenticated /profile'
        assert '/login' in response.headers['Location'], \
            'Redirect must target /login'

    def test_unauthenticated_does_not_return_200(self, client):
        """Unauthenticated /profile must never serve the profile page."""
        response = client.get('/profile')
        assert response.status_code != 200, \
            'Unauthenticated access must not return 200'

    def test_authenticated_user_receives_200(self, auth_client):
        """Logged-in user must receive 200 from GET /profile."""
        response = auth_client.get('/profile')
        assert response.status_code == 200, \
            'Logged-in user must get 200 from /profile'


# ---------------------------------------------------------------------------
# 2. Unfiltered profile (no query params)
# ---------------------------------------------------------------------------

class TestProfileUnfiltered:

    def test_no_params_returns_200(self, auth_client):
        response = auth_client.get('/profile')
        assert response.status_code == 200, \
            '/profile with no params must return 200'

    def test_no_params_shows_full_total_amount(self, auth_client):
        """Total amount rendered must be ₹2800.00 (all 5 seeded expenses)."""
        response = auth_client.get('/profile')
        data = response.data.decode('utf-8')
        assert '2800.00' in data, \
            'Expected ₹2800.00 in unfiltered summary; got: ' + data[:500]

    def test_no_params_shows_full_expense_count(self, auth_client):
        """Summary count must reflect all 5 seeded expenses."""
        response = auth_client.get('/profile')
        data = response.data.decode('utf-8')
        assert str(COUNT_ALL) in data, \
            f'Expected total count {COUNT_ALL} in unfiltered summary'

    def test_no_params_all_categories_visible(self, auth_client):
        """All four distinct categories must appear in the by-category list."""
        response = auth_client.get('/profile')
        data = response.data.decode('utf-8')
        for category in ('Food', 'Transport', 'Bills', 'Shopping'):
            assert category in data, \
                f'Expected category "{category}" in unfiltered profile page'

    def test_no_params_filter_active_bar_absent(self, auth_client):
        """
        The filter-active-bar element must NOT be rendered when no
        date filter is in effect (Jinja2 conditional block).
        """
        response = auth_client.get('/profile')
        data = response.data.decode('utf-8')
        assert 'filter-active-bar' not in data, \
            'filter-active-bar must not render without an active filter'
        assert 'Filtered:' not in data, \
            '"Filtered:" text must not appear when no filter is active'

    def test_no_params_clear_link_absent(self, auth_client):
        """Clear link must not appear when no filter is active."""
        response = auth_client.get('/profile')
        data = response.data.decode('utf-8')
        assert 'filter-clear-link' not in data, \
            'filter-clear-link element must not render without an active filter'

    def test_no_params_date_inputs_have_empty_values(self, auth_client):
        """
        Both date inputs must render with value="" when no filter is set —
        confirming that template variables start_date and end_date are falsy.
        """
        response = auth_client.get('/profile')
        data = response.data.decode('utf-8')
        assert 'value="2026-' not in data, \
            'Date inputs must not contain pre-filled 2026-* values when no filter is active'


# ---------------------------------------------------------------------------
# 3. Date filter — happy paths
# ---------------------------------------------------------------------------

class TestProfileDateFilterHappyPath:

    def test_both_dates_returns_200(self, auth_client):
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        assert response.status_code == 200, \
            '/profile with both date params must return 200'

    def test_both_dates_correct_total_amount(self, auth_client):
        """
        start=2026-06-01, end=2026-06-15 must sum only
        Transport(200) + Food(300) = ₹500.00.
        """
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        data = response.data.decode('utf-8')
        assert '500.00' in data, \
            f'Expected ₹500.00 for Jun 1–Jun 15 filter, got: {data[:500]}'

    def test_both_dates_correct_expense_count(self, auth_client):
        """Jun 1–Jun 15 filter must show count=2."""
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        data = response.data.decode('utf-8')
        assert str(COUNT_JUN1_JUN15) in data, \
            f'Expected count {COUNT_JUN1_JUN15} for Jun 1–Jun 15 filter'

    def test_both_dates_excludes_bills_category(self, auth_client):
        """Bills (Jun 20) must be absent from the Jun 1–Jun 15 result."""
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        data = response.data.decode('utf-8')
        assert 'Bills' not in data, \
            'Bills (Jun 20) must be excluded by end_date=2026-06-15'

    def test_both_dates_excludes_shopping_category(self, auth_client):
        """Shopping (Jul 5) must be absent from the Jun 1–Jun 15 result."""
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        data = response.data.decode('utf-8')
        assert 'Shopping' not in data, \
            'Shopping (Jul 5) must be excluded by end_date=2026-06-15'

    def test_only_start_date_correct_total(self, auth_client):
        """
        start_date=2026-06-10 (no end_date) must include expenses on or
        after Jun 10: Food(300) + Bills(1000) + Shopping(800) = ₹2100.00.
        """
        response = auth_client.get('/profile?start_date=2026-06-10')
        assert response.status_code == 200
        data = response.data.decode('utf-8')
        assert '2100.00' in data, \
            'Expected ₹2100.00 for start_date=2026-06-10 only'

    def test_only_start_date_correct_count(self, auth_client):
        response = auth_client.get('/profile?start_date=2026-06-10')
        data = response.data.decode('utf-8')
        assert str(COUNT_FROM_JUN10) in data, \
            f'Expected count {COUNT_FROM_JUN10} for start_date=2026-06-10 only'

    def test_only_start_date_excludes_transport(self, auth_client):
        """Transport (Jun 1) must be excluded when start_date=2026-06-10."""
        response = auth_client.get('/profile?start_date=2026-06-10')
        data = response.data.decode('utf-8')
        assert 'Transport' not in data, \
            'Transport (Jun 1) must be excluded when start_date=2026-06-10'

    def test_only_end_date_correct_total(self, auth_client):
        """
        end_date=2026-06-10 (no start_date) must include expenses on or
        before Jun 10: Food(500) + Transport(200) + Food(300) = ₹1000.00.
        """
        response = auth_client.get('/profile?end_date=2026-06-10')
        assert response.status_code == 200
        data = response.data.decode('utf-8')
        assert '1000.00' in data, \
            'Expected ₹1000.00 for end_date=2026-06-10 only'

    def test_only_end_date_correct_count(self, auth_client):
        response = auth_client.get('/profile?end_date=2026-06-10')
        data = response.data.decode('utf-8')
        assert str(COUNT_UNTIL_JUN10) in data, \
            f'Expected count {COUNT_UNTIL_JUN10} for end_date=2026-06-10 only'

    def test_only_end_date_excludes_bills(self, auth_client):
        """Bills (Jun 20) must be excluded when end_date=2026-06-10."""
        response = auth_client.get('/profile?end_date=2026-06-10')
        data = response.data.decode('utf-8')
        assert 'Bills' not in data, \
            'Bills (Jun 20) must be excluded when end_date=2026-06-10'

    def test_only_end_date_excludes_shopping(self, auth_client):
        """Shopping (Jul 5) must be excluded when end_date=2026-06-10."""
        response = auth_client.get('/profile?end_date=2026-06-10')
        data = response.data.decode('utf-8')
        assert 'Shopping' not in data, \
            'Shopping (Jul 5) must be excluded when end_date=2026-06-10'


# ---------------------------------------------------------------------------
# 4. Edge cases — invalid and boundary date inputs
# ---------------------------------------------------------------------------

class TestProfileDateEdgeCases:

    def test_invalid_start_date_ignored_shows_full_summary(self, auth_client):
        """
        An alphabetic start_date (e.g. 'abc') must be silently ignored;
        the full unfiltered summary (₹2800.00) must be shown.
        """
        response = auth_client.get('/profile?start_date=abc')
        assert response.status_code == 200, \
            'Invalid start_date must not cause a non-200 response'
        data = response.data.decode('utf-8')
        assert '2800.00' in data, \
            'Invalid start_date must be ignored; expect full ₹2800.00 total'

    def test_invalid_end_date_ignored_shows_full_summary(self, auth_client):
        """An invalid end_date must be silently ignored."""
        response = auth_client.get('/profile?end_date=not-a-date')
        assert response.status_code == 200
        data = response.data.decode('utf-8')
        assert '2800.00' in data, \
            'Invalid end_date must be ignored; expect full ₹2800.00 total'

    def test_invalid_dates_no_filter_indicator(self, auth_client):
        """
        Invalid date params must not trigger the active-filter indicator —
        the page must look identical to the unfiltered case.
        """
        response = auth_client.get('/profile?start_date=abc&end_date=xyz')
        data = response.data.decode('utf-8')
        assert 'Filtered:' not in data, \
            '"Filtered:" must not appear when both date params are invalid'
        assert 'filter-active-bar' not in data, \
            'filter-active-bar must not render for invalid date params'

    @pytest.mark.parametrize('qs', [
        'start_date=',
        'end_date=',
        'start_date=&end_date=',
    ])
    def test_blank_date_params_return_full_summary(self, auth_client, qs):
        """Blank (empty-string) date params must behave like absent params."""
        response = auth_client.get(f'/profile?{qs}')
        assert response.status_code == 200, \
            f'Blank date param "{qs}" must not cause an error'
        data = response.data.decode('utf-8')
        assert '2800.00' in data, \
            f'Blank date param "{qs}" must not filter; expect full ₹2800.00'

    def test_swapped_dates_no_error(self, auth_client):
        """
        start_date > end_date (2026-06-20 / 2026-06-01) must be handled
        gracefully — the route must auto-swap them and return 200.
        """
        response = auth_client.get(
            '/profile?start_date=2026-06-20&end_date=2026-06-01'
        )
        assert response.status_code == 200, \
            'Swapped dates must not cause an error response'

    def test_swapped_dates_correct_total(self, auth_client):
        """
        After auto-swap (start=2026-06-01, end=2026-06-20) the total must
        be Transport(200) + Food(300) + Bills(1000) = ₹1500.00.
        """
        response = auth_client.get(
            '/profile?start_date=2026-06-20&end_date=2026-06-01'
        )
        data = response.data.decode('utf-8')
        assert '1500.00' in data, \
            'Auto-swapped dates must yield ₹1500.00 (Jun 1–Jun 20)'

    def test_swapped_dates_correct_count(self, auth_client):
        """Auto-swap of Jun 20 / Jun 1 must yield count=3."""
        response = auth_client.get(
            '/profile?start_date=2026-06-20&end_date=2026-06-01'
        )
        data = response.data.decode('utf-8')
        assert str(COUNT_JUN1_JUN20) in data, \
            f'Expected count {COUNT_JUN1_JUN20} after date auto-swap'

    def test_filter_with_no_matching_expenses_returns_200(self, auth_client):
        """
        A valid date range that matches no expenses must still return 200
        (not a 404 or 500) and show a zero or empty state.
        """
        response = auth_client.get(
            '/profile?start_date=2020-01-01&end_date=2020-01-31'
        )
        assert response.status_code == 200, \
            'Filter with no matching expenses must return 200'
        data = response.data.decode('utf-8')
        assert '0.00' in data or 'No expenses' in data, \
            'Must show zero total or empty-state message when filter matches nothing'


# ---------------------------------------------------------------------------
# 5. Template UI — active filter elements and form semantics
# ---------------------------------------------------------------------------

class TestProfileFilterUI:

    def test_filter_form_uses_get_method(self, auth_client):
        """Date filter form must submit via GET — filters are read-only."""
        response = auth_client.get('/profile')
        data = response.data.decode('utf-8')
        assert 'method="GET"' in data, \
            'Filter form must declare method="GET"'

    def test_date_inputs_have_type_date(self, auth_client):
        """Both filter inputs must use type="date" (HTML5 native date picker)."""
        response = auth_client.get('/profile')
        data = response.data.decode('utf-8')
        assert data.count('type="date"') >= 2, \
            'Expected at least two type="date" inputs on the profile page'

    def test_active_filter_bar_appears_with_both_dates(self, auth_client):
        """filter-active-bar must render when both date params are valid."""
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        data = response.data.decode('utf-8')
        assert 'filter-active-bar' in data, \
            'filter-active-bar must render when both date params are provided'

    def test_filtered_text_appears_with_both_dates(self, auth_client):
        """"Filtered:" text must appear when both date params are valid."""
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        data = response.data.decode('utf-8')
        assert 'Filtered:' in data, \
            '"Filtered:" label must appear in active-filter bar'

    def test_both_filter_dates_shown_in_indicator_text(self, auth_client):
        """Active-filter indicator must display both the start and end date values."""
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        data = response.data.decode('utf-8')
        assert '2026-06-01' in data, \
            'start_date (2026-06-01) must appear in the active-filter indicator'
        assert '2026-06-15' in data, \
            'end_date (2026-06-15) must appear in the active-filter indicator'

    def test_active_filter_bar_appears_with_only_start_date(self, auth_client):
        """filter-active-bar must render when only start_date is provided."""
        response = auth_client.get('/profile?start_date=2026-06-10')
        data = response.data.decode('utf-8')
        assert 'Filtered:' in data, \
            '"Filtered:" must appear when only start_date is active'
        assert '2026-06-10' in data, \
            'Active start_date must appear in the indicator text'

    def test_active_filter_bar_appears_with_only_end_date(self, auth_client):
        """filter-active-bar must render when only end_date is provided."""
        response = auth_client.get('/profile?end_date=2026-06-20')
        data = response.data.decode('utf-8')
        assert 'Filtered:' in data, \
            '"Filtered:" must appear when only end_date is active'
        assert '2026-06-20' in data, \
            'Active end_date must appear in the indicator text'

    def test_clear_link_present_when_filter_active(self, auth_client):
        """A "Clear" link must appear alongside the active-filter indicator."""
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        data = response.data.decode('utf-8')
        assert 'filter-clear-link' in data, \
            'filter-clear-link element must render when filter is active'
        assert 'Clear' in data, \
            '"Clear" link text must be present when filter is active'

    def test_clear_link_absent_when_no_filter(self, auth_client):
        """Clear link must NOT appear when no date filter is applied."""
        response = auth_client.get('/profile')
        data = response.data.decode('utf-8')
        assert 'filter-clear-link' not in data, \
            'filter-clear-link must not render when no filter is in effect'

    def test_start_date_input_prefilled(self, auth_client):
        """start_date input must carry value="2026-06-01" when that filter is active."""
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        data = response.data.decode('utf-8')
        assert 'value="2026-06-01"' in data, \
            'start_date input must be pre-filled with the active filter value'

    def test_end_date_input_prefilled(self, auth_client):
        """end_date input must carry value="2026-06-15" when that filter is active."""
        response = auth_client.get(
            '/profile?start_date=2026-06-01&end_date=2026-06-15'
        )
        data = response.data.decode('utf-8')
        assert 'value="2026-06-15"' in data, \
            'end_date input must be pre-filled with the active filter value'

    def test_only_start_date_input_prefilled_end_empty(self, auth_client):
        """
        When only start_date is provided, start input is pre-filled and
        end input must still render with an empty value.
        """
        response = auth_client.get('/profile?start_date=2026-06-10')
        data = response.data.decode('utf-8')
        assert 'value="2026-06-10"' in data, \
            'start_date input must be pre-filled when only start_date is active'
        # end_date input should have an empty value
        assert 'value=""' in data, \
            'end_date input must have empty value when end_date param is absent'

    def test_only_end_date_input_prefilled_start_empty(self, auth_client):
        """
        When only end_date is provided, end input is pre-filled and
        start input must still render with an empty value.
        """
        response = auth_client.get('/profile?end_date=2026-06-20')
        data = response.data.decode('utf-8')
        assert 'value="2026-06-20"' in data, \
            'end_date input must be pre-filled when only end_date is active'
        assert 'value=""' in data, \
            'start_date input must have empty value when start_date param is absent'


# ---------------------------------------------------------------------------
# 6. DB-layer unit tests — get_expense_summary
# ---------------------------------------------------------------------------

class TestGetExpenseSummaryUnit:
    """
    Call get_expense_summary directly, bypassing the HTTP layer.
    The `app` fixture is not required here; `seeded_user_id` brings in `app`
    transitively (so _DB_PATH is already monkeypatched and init_db has run).
    """

    # --- Return contract -------------------------------------------------- #

    def test_returns_required_keys(self, seeded_user_id):
        """Result dict must always contain total_count, total_amount, by_category."""
        result = get_expense_summary(seeded_user_id)
        assert 'total_count' in result, 'Result must contain total_count'
        assert 'total_amount' in result, 'Result must contain total_amount'
        assert 'by_category' in result, 'Result must contain by_category'

    # --- No filter -------------------------------------------------------- #

    def test_no_filter_total_count(self, seeded_user_id):
        """Without date params all 5 expenses must be counted."""
        result = get_expense_summary(seeded_user_id)
        assert result['total_count'] == COUNT_ALL, \
            f'Expected total_count={COUNT_ALL}, got {result["total_count"]}'

    def test_no_filter_total_amount(self, seeded_user_id):
        """Without date params total amount must be ₹2800.00."""
        result = get_expense_summary(seeded_user_id)
        assert result['total_amount'] == pytest.approx(TOTAL_ALL), \
            f'Expected total_amount={TOTAL_ALL}, got {result["total_amount"]}'

    def test_no_filter_by_category_includes_all_categories(self, seeded_user_id):
        """All four distinct categories must appear in by_category."""
        result = get_expense_summary(seeded_user_id)
        categories = {row['category'] for row in result['by_category']}
        expected = {'Food', 'Transport', 'Bills', 'Shopping'}
        assert categories == expected, \
            f'Expected categories {expected}, got {categories}'

    def test_by_category_ordered_total_descending(self, seeded_user_id):
        """by_category rows must be sorted by total DESC."""
        result = get_expense_summary(seeded_user_id)
        totals = [row['total'] for row in result['by_category']]
        assert totals == sorted(totals, reverse=True), \
            'by_category must be ordered by total DESC'

    # --- Both date params ------------------------------------------------- #

    def test_both_dates_total_count(self, seeded_user_id):
        """start=2026-06-01, end=2026-06-15 must return count=2."""
        result = get_expense_summary(
            seeded_user_id, start_date='2026-06-01', end_date='2026-06-15'
        )
        assert result['total_count'] == COUNT_JUN1_JUN15, \
            f'Expected count {COUNT_JUN1_JUN15}, got {result["total_count"]}'

    def test_both_dates_total_amount(self, seeded_user_id):
        """start=2026-06-01, end=2026-06-15 must sum to ₹500.00."""
        result = get_expense_summary(
            seeded_user_id, start_date='2026-06-01', end_date='2026-06-15'
        )
        assert result['total_amount'] == pytest.approx(TOTAL_JUN1_JUN15), \
            f'Expected total {TOTAL_JUN1_JUN15}, got {result["total_amount"]}'

    def test_both_dates_by_category_contains_only_included_categories(self, seeded_user_id):
        """Jun 1–15 filter must yield only Transport and Food categories."""
        result = get_expense_summary(
            seeded_user_id, start_date='2026-06-01', end_date='2026-06-15'
        )
        categories = {row['category'] for row in result['by_category']}
        assert categories == {'Food', 'Transport'}, \
            f'Expected {{Food, Transport}} for Jun 1–15, got {categories}'

    # --- Only start_date -------------------------------------------------- #

    def test_only_start_date_total_count(self, seeded_user_id):
        """start=2026-06-10 (no end) must return count=3."""
        result = get_expense_summary(seeded_user_id, start_date='2026-06-10')
        assert result['total_count'] == COUNT_FROM_JUN10, \
            f'Expected count {COUNT_FROM_JUN10}, got {result["total_count"]}'

    def test_only_start_date_total_amount(self, seeded_user_id):
        """start=2026-06-10 must sum Food+Bills+Shopping = ₹2100.00."""
        result = get_expense_summary(seeded_user_id, start_date='2026-06-10')
        assert result['total_amount'] == pytest.approx(TOTAL_FROM_JUN10), \
            f'Expected total {TOTAL_FROM_JUN10}, got {result["total_amount"]}'

    def test_only_start_date_excludes_earlier_entries(self, seeded_user_id):
        """start=2026-06-10 must exclude Transport (Jun 1) and May Food."""
        result = get_expense_summary(seeded_user_id, start_date='2026-06-10')
        categories = {row['category'] for row in result['by_category']}
        assert 'Transport' not in categories, \
            'Transport (Jun 1) must be excluded when start_date=2026-06-10'

    # --- Only end_date ---------------------------------------------------- #

    def test_only_end_date_total_count(self, seeded_user_id):
        """end=2026-06-10 (no start) must return count=3."""
        result = get_expense_summary(seeded_user_id, end_date='2026-06-10')
        assert result['total_count'] == COUNT_UNTIL_JUN10, \
            f'Expected count {COUNT_UNTIL_JUN10}, got {result["total_count"]}'

    def test_only_end_date_total_amount(self, seeded_user_id):
        """end=2026-06-10 must sum Food+Transport+Food = ₹1000.00."""
        result = get_expense_summary(seeded_user_id, end_date='2026-06-10')
        assert result['total_amount'] == pytest.approx(TOTAL_UNTIL_JUN10), \
            f'Expected total {TOTAL_UNTIL_JUN10}, got {result["total_amount"]}'

    def test_only_end_date_excludes_later_entries(self, seeded_user_id):
        """end=2026-06-10 must exclude Bills (Jun 20) and Shopping (Jul 5)."""
        result = get_expense_summary(seeded_user_id, end_date='2026-06-10')
        categories = {row['category'] for row in result['by_category']}
        assert 'Bills' not in categories, \
            'Bills (Jun 20) must be excluded when end_date=2026-06-10'
        assert 'Shopping' not in categories, \
            'Shopping (Jul 5) must be excluded when end_date=2026-06-10'

    # --- Boundary inclusivity --------------------------------------------- #

    def test_start_date_boundary_is_inclusive(self, seeded_user_id):
        """
        Filtering on exactly the date of an expense must INCLUDE that expense
        (WHERE date >= ? is inclusive on the lower bound).
        """
        # 2026-06-01 is the date of exactly one expense (Transport, ₹200).
        result = get_expense_summary(
            seeded_user_id,
            start_date='2026-06-01',
            end_date='2026-06-01',
        )
        assert result['total_count'] == 1, \
            'Exact single-day filter must return 1 expense (boundary inclusive)'
        assert result['total_amount'] == pytest.approx(200.00), \
            'Single-day 2026-06-01 must return ₹200.00 (Transport only)'

    def test_end_date_boundary_is_inclusive(self, seeded_user_id):
        """end_date boundary must be inclusive (WHERE date <= ?)."""
        # 2026-06-20 is exactly one expense (Bills, ₹1000).
        result = get_expense_summary(
            seeded_user_id,
            start_date='2026-06-20',
            end_date='2026-06-20',
        )
        assert result['total_count'] == 1, \
            'Exact single-day end filter must return 1 expense'
        assert result['total_amount'] == pytest.approx(1000.00), \
            'Single-day 2026-06-20 must return ₹1000.00 (Bills only)'

    # --- No matching expenses --------------------------------------------- #

    def test_no_matching_expenses_total_count_is_zero(self, seeded_user_id):
        """A range with no expenses must return total_count=0."""
        result = get_expense_summary(
            seeded_user_id,
            start_date='2020-01-01',
            end_date='2020-12-31',
        )
        assert result['total_count'] == 0, \
            'Expected total_count=0 for a range with no expenses'

    def test_no_matching_expenses_total_amount_is_zero(self, seeded_user_id):
        """A range with no expenses must return total_amount=0.0."""
        result = get_expense_summary(
            seeded_user_id,
            start_date='2020-01-01',
            end_date='2020-12-31',
        )
        assert result['total_amount'] == pytest.approx(0.0), \
            'Expected total_amount=0.0 for a range with no expenses'

    def test_no_matching_expenses_by_category_is_empty(self, seeded_user_id):
        """A range with no expenses must return an empty by_category list."""
        result = get_expense_summary(
            seeded_user_id,
            start_date='2020-01-01',
            end_date='2020-12-31',
        )
        assert result['by_category'] == [], \
            'Expected empty by_category list when no expenses match the filter'

    # --- User isolation --------------------------------------------------- #

    def test_wrong_user_id_returns_zero_totals(self, seeded_user_id):
        """
        Querying with a user_id that owns no expenses must return zeros,
        confirming the WHERE user_id = ? clause is strictly enforced.
        """
        other_user_id = seeded_user_id + 9999
        result = get_expense_summary(other_user_id)
        assert result['total_count'] == 0, \
            'Unowned user_id must return total_count=0'
        assert result['total_amount'] == pytest.approx(0.0), \
            'Unowned user_id must return total_amount=0.0'
        assert result['by_category'] == [], \
            'Unowned user_id must return empty by_category'
