# Spendly Page Layout Reference

Known pages from CLAUDE.md route table + typical expense tracker patterns.

---

## `/` — Landing Page (`landing.html`)

**Purpose:** Marketing/intro page for unauthenticated users.

**Layout:**
```
[Navbar: logo + Login + Register buttons]
[Hero: headline, subheadline, CTA button, hero illustration]
[Features: 3-column grid of feature cards with icons]
[Footer: minimal]
```

**Key UX:** Hero should communicate the core value prop in one line. CTA goes to `/register`.

---

## `/register` — Register Page (`register.html`)

**Layout:**
```
[Centered card, max-width 420px]
  [Logo at top]
  [Title: "Create your account"]
  [Form: Full name | Email | Password | Confirm password]
  [Submit button: full-width primary]
  [Footer link: "Already have an account? Login"]
```

**Key UX:** Show password strength indicator. Field labels above inputs, not placeholder-only.

---

## `/login` — Login Page (`login.html`)

**Layout:**
```
[Centered card, max-width 400px]
  [Logo at top]
  [Title: "Welcome back"]
  [Form: Email | Password | Remember me checkbox]
  [Submit button: full-width primary]
  [Footer link: "Don't have an account? Register"]
```

---

## `/profile` — Profile Page (`profile.html`) — Stub Step 4

**Layout:**
```
[Page header: "My Profile"]
[Two-column: left = avatar + basic info card | right = settings/edit form]
  Left card: avatar initials circle, name, email, member since
  Right card: editable form (name, email, current password, new password)
  [Save button]
```

---

## `/expenses/add` — Add Expense (`add_expense.html`) — Stub Step 7

**Layout:**
```
[Page header: "Add Expense" + back link]
[Centered form card, max-width 560px]
  [Amount input: large, prominent, with ₹ prefix]
  [Category select with icons]
  [Description textarea]
  [Date picker (defaults to today)]
  [Type toggle: Expense / Income]
  [Submit button: full-width]
```

**Key UX:** Amount field is the most important — make it big (36px font). Category icons help quick scanning.

**Categories + Lucide icons:**
- Food & Dining → `utensils`
- Transport → `car`
- Shopping → `shopping-bag`
- Entertainment → `film`
- Health → `heart-pulse`
- Bills & Utilities → `zap`
- Housing → `home`
- Education → `book-open`
- Travel → `plane`
- Other → `more-horizontal`

---

## `/expenses/<id>/edit` — Edit Expense — Stub Step 8

Same layout as Add Expense, but fields pre-filled. Title: "Edit Expense". Add a "Delete" danger button in the footer.

---

## Dashboard (hypothetical `/dashboard`)

**Layout:**
```
[Page header: "Good morning, {name}" + date]
[KPI row: 4 stat cards]
  Total Spent (month) | Total Income (month) | Balance | # Transactions
[Two-column below:]
  Left (60%): Recent Transactions table
  Right (40%): Spending by Category (pie/donut placeholder or CSS bars)
[FAB: "+ Add Expense" button fixed bottom-right]
```

**KPI card colors:**
- Spent: danger tint
- Income: success tint
- Balance: primary tint
- Transactions: warning tint

---

## Expense List (hypothetical `/expenses`)

**Layout:**
```
[Page header: "Expenses" + "Add Expense" button top-right]
[Filter bar: date range | category | type (expense/income) | search]
[Table card:]
  Columns: Date | Category (icon + name) | Description | Type | Amount
  Row hover: subtle bg tint
  Amount: red for expense, green for income
[Pagination at bottom]
[Empty state: illustration + "No expenses yet. Add your first one!" + CTA]
```