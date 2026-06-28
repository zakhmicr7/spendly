import math
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email, get_user_by_id, get_expense_summary, create_expense

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-production'


with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _parse_date(raw):
    if not raw:
        return None
    try:
        datetime.strptime(raw.strip(), '%Y-%m-%d')
        return raw.strip()
    except ValueError:
        return None


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get('user_id'):
        return redirect(url_for('profile'))
    if request.method == "POST":
        name             = request.form.get("name", "").strip()
        email            = request.form.get("email", "").strip()
        password         = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("register.html")

        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.")
            return render_template("register.html")

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get('user_id'):
        return redirect(url_for('profile'))
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Invalid email or password.")
            return render_template("login.html")

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user['password_hash'], password):
            flash("Invalid email or password.")
            return render_template("login.html")

        session['user_id']   = user['id']
        session['user_name'] = user['name']
        return redirect(url_for('profile'))

    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('landing'))


@app.route("/profile")
def profile():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    user = get_user_by_id(session['user_id'])

    start_date = _parse_date(request.args.get('start_date', ''))
    end_date = _parse_date(request.args.get('end_date', ''))

    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date

    summary = get_expense_summary(session['user_id'], start_date=start_date, end_date=end_date)
    return render_template("profile.html", user=user, summary=summary,
                           start_date=start_date, end_date=end_date)


VALID_CATEGORIES = {'Food', 'Transport', 'Bills', 'Health', 'Entertainment', 'Shopping', 'Other'}


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get('user_id'):
        if request.method == "POST":
            abort(403)
        return redirect(url_for('login'))

    if request.method == "POST":
        amount_raw  = request.form.get("amount", "").strip()
        category    = request.form.get("category", "").strip()
        date_raw    = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        try:
            amount = float(amount_raw)
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError
        except ValueError:
            flash("Amount must be a positive number.")
            return render_template("add_expense.html", form=request.form, categories=VALID_CATEGORIES)

        if category not in VALID_CATEGORIES:
            flash("Please select a valid category.")
            return render_template("add_expense.html", form=request.form, categories=VALID_CATEGORIES)

        date = _parse_date(date_raw)
        if not date:
            flash("Please enter a valid date (YYYY-MM-DD).")
            return render_template("add_expense.html", form=request.form, categories=VALID_CATEGORIES)

        try:
            create_expense(session['user_id'], amount, category, date, description or None)
        except sqlite3.IntegrityError:
            flash("Could not save expense. Please try again.")
            return render_template("add_expense.html", form=request.form, categories=VALID_CATEGORIES)
        flash("Expense added successfully.", "success")
        return redirect(url_for('profile'))

    return render_template("add_expense.html", form={}, categories=VALID_CATEGORIES)


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
