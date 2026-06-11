"""
SmartSpend AI – Personal Expense Tracker & Analytics
=====================================================
A full-stack Flask web application for tracking expenses with AI-powered insights.
"""

import os
import json
import random
from datetime import datetime, timedelta, date
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, send_file)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import cm
from dateutil.relativedelta import relativedelta
import io

# ─── App Configuration ──────────────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'smartspend-dev-key-change-me')
# Use PostgreSQL in production (Render sets DATABASE_URL), SQLite locally
database_url = os.environ.get('DATABASE_URL', 'sqlite:///smartspend.db')
# Render gives postgres:// but SQLAlchemy needs postgresql://
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access SmartSpend AI.'

# ─── Database Models ─────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    """User account model"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    currency = db.Column(db.String(10), default='INR')
    theme = db.Column(db.String(10), default='dark')
    avatar = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    monthly_budget = db.Column(db.Float, default=0.0)
    savings_goal = db.Column(db.Float, default=0.0)

    expenses = db.relationship('Expense', backref='user', lazy=True, cascade='all, delete-orphan')
    incomes = db.relationship('Income', backref='user', lazy=True, cascade='all, delete-orphan')
    budgets = db.relationship('Budget', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Expense(db.Model):
    """Expense transaction model"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text, default='')
    receipt = db.Column(db.String(200), default='')
    is_recurring = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Income(db.Model):
    """Income transaction model"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text, default='')
    is_recurring = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Budget(db.Model):
    """Monthly category budget model"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─── Helper Functions ────────────────────────────────────────────────────────

CATEGORIES = ['Food', 'Shopping', 'Bills', 'Travel', 'Entertainment',
              'Education', 'Health', 'Others']
INCOME_SOURCES = ['Salary', 'Freelance', 'Business', 'Investment',
                  'Rental', 'Gift', 'Others']
CURRENCY_SYMBOLS = {
    'INR': '₹', 'USD': '$', 'EUR': '€', 'GBP': '£',
    'JPY': '¥', 'CAD': 'CA$', 'AUD': 'A$'
}

def get_currency_symbol(user):
    return CURRENCY_SYMBOLS.get(user.currency, '₹')

def get_monthly_data(user_id, months=6):
    """Get expense/income data for last N months"""
    result = []
    today = date.today()
    for i in range(months - 1, -1, -1):
        target = today - relativedelta(months=i)
        expenses = db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            db.extract('month', Expense.date) == target.month,
            db.extract('year', Expense.date) == target.year
        ).scalar() or 0
        income = db.session.query(db.func.sum(Income.amount)).filter(
            Income.user_id == user_id,
            db.extract('month', Income.date) == target.month,
            db.extract('year', Income.date) == target.year
        ).scalar() or 0
        result.append({
            'month': target.strftime('%b %Y'),
            'expenses': round(expenses, 2),
            'income': round(income, 2)
        })
    return result

def get_category_totals(user_id, month=None, year=None):
    """Get expense totals by category"""
    query = db.session.query(
        Expense.category, db.func.sum(Expense.amount)
    ).filter(Expense.user_id == user_id)
    if month and year:
        query = query.filter(
            db.extract('month', Expense.date) == month,
            db.extract('year', Expense.date) == year
        )
    rows = query.group_by(Expense.category).all()
    return {cat: round(amt, 2) for cat, amt in rows}

def ai_analysis(user_id):
    """AI-powered spending analysis and recommendations"""
    today = date.today()
    month_expenses = get_category_totals(user_id, today.month, today.year)
    total_expense = sum(month_expenses.values())

    total_income = db.session.query(db.func.sum(Income.amount)).filter(
        Income.user_id == user_id,
        db.extract('month', Income.date) == today.month,
        db.extract('year', Income.date) == today.year
    ).scalar() or 0

    tips = []
    alerts = []
    health_score = 100

    # Savings rate
    if total_income > 0:
        savings_rate = ((total_income - total_expense) / total_income) * 100
        if savings_rate < 10:
            alerts.append({'type': 'danger', 'icon': '🚨', 'msg': f'Low savings rate ({savings_rate:.1f}%). Aim for at least 20%.'})
            health_score -= 25
        elif savings_rate < 20:
            alerts.append({'type': 'warning', 'icon': '⚠️', 'msg': f'Savings rate is {savings_rate:.1f}%. Try to reach 20%.'})
            health_score -= 10
        else:
            tips.append({'icon': '🎉', 'msg': f'Great job! You\'re saving {savings_rate:.1f}% of your income.'})
    else:
        alerts.append({'type': 'warning', 'icon': '💡', 'msg': 'No income recorded this month. Add your income sources.'})
        health_score -= 15

    # Category analysis
    if month_expenses:
        top_cat = max(month_expenses, key=month_expenses.get)
        tips.append({'icon': '📊', 'msg': f'Your highest spending category is {top_cat} (₹{month_expenses[top_cat]:,.0f}).'})

        if 'Food' in month_expenses and total_income > 0:
            food_pct = (month_expenses['Food'] / total_income) * 100
            if food_pct > 30:
                alerts.append({'type': 'warning', 'icon': '🍔', 'msg': f'Food spending is {food_pct:.1f}% of income. Consider meal planning.'})
                health_score -= 10

        if 'Entertainment' in month_expenses and total_income > 0:
            ent_pct = (month_expenses['Entertainment'] / total_income) * 100
            if ent_pct > 15:
                alerts.append({'type': 'warning', 'icon': '🎬', 'msg': f'Entertainment is {ent_pct:.1f}% of income. Consider cutting back.'})
                health_score -= 5

    # Generic smart tips
    generic_tips = [
        {'icon': '💰', 'msg': 'Try the 50/30/20 rule: 50% needs, 30% wants, 20% savings.'},
        {'icon': '📱', 'msg': 'Review your subscriptions monthly to eliminate unused ones.'},
        {'icon': '🛒', 'msg': 'Make a shopping list before going to the store to avoid impulse buys.'},
        {'icon': '☕', 'msg': 'Making coffee at home instead of buying can save ₹3,000+ monthly.'},
        {'icon': '🎯', 'msg': 'Set a specific savings goal to stay motivated.'},
    ]
    tips.extend(random.sample(generic_tips, min(2, len(generic_tips))))

    health_score = max(0, min(100, health_score))
    if health_score >= 80:
        health_label, health_color = 'Excellent', '#22c55e'
    elif health_score >= 60:
        health_label, health_color = 'Good', '#84cc16'
    elif health_score >= 40:
        health_label, health_color = 'Fair', '#f59e0b'
    else:
        health_label, health_color = 'Needs Attention', '#ef4444'

    # Predict next month expenses (simple moving average)
    monthly = get_monthly_data(user_id, 3)
    avg_expense = sum(m['expenses'] for m in monthly) / len(monthly) if monthly else 0
    prediction = round(avg_expense * random.uniform(0.95, 1.05), 2)

    return {
        'alerts': alerts,
        'tips': tips,
        'health_score': health_score,
        'health_label': health_label,
        'health_color': health_color,
        'prediction': prediction,
        'total_expense': total_expense,
        'total_income': total_income,
    }

# ─── Routes: Auth ────────────────────────────────────────────────────────────

@app.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('signup.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please login.', 'error')
            return render_template('signup.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return render_template('signup.html')
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f'Welcome to SmartSpend AI, {name}! 🎉', 'success')
        return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=request.form.get('remember'))
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('landing'))

# ─── Routes: Dashboard ───────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    sym = get_currency_symbol(current_user)

    # This month totals
    total_expense = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.user_id == current_user.id,
        db.extract('month', Expense.date) == today.month,
        db.extract('year', Expense.date) == today.year
    ).scalar() or 0

    total_income = db.session.query(db.func.sum(Income.amount)).filter(
        Income.user_id == current_user.id,
        db.extract('month', Income.date) == today.month,
        db.extract('year', Income.date) == today.year
    ).scalar() or 0

    balance = total_income - total_expense
    savings_pct = round((balance / total_income * 100), 1) if total_income > 0 else 0

    # Recent transactions
    recent_expenses = Expense.query.filter_by(user_id=current_user.id)\
        .order_by(Expense.date.desc(), Expense.created_at.desc()).limit(8).all()

    # Monthly chart data
    monthly_data = get_monthly_data(current_user.id, 6)
    category_data = get_category_totals(current_user.id, today.month, today.year)

    # AI analysis
    ai = ai_analysis(current_user.id)

    # Budget progress
    budgets = Budget.query.filter_by(
        user_id=current_user.id, month=today.month, year=today.year
    ).all()
    budget_progress = []
    for b in budgets:
        spent = category_data.get(b.category, 0)
        pct = min(round((spent / b.amount * 100), 1), 100) if b.amount > 0 else 0
        budget_progress.append({
            'category': b.category, 'budget': b.amount,
            'spent': spent, 'pct': pct,
            'status': 'danger' if pct >= 90 else 'warning' if pct >= 70 else 'success'
        })

    now_hour = datetime.utcnow().hour
    return render_template('dashboard.html',
        sym=sym, total_expense=total_expense, total_income=total_income,
        balance=balance, savings_pct=savings_pct,
        recent_expenses=recent_expenses, monthly_data=json.dumps(monthly_data),
        category_data=json.dumps(category_data), ai=ai,
        budget_progress=budget_progress, today=today,
        now_hour=now_hour, categories=CATEGORIES
    )

# ─── Routes: Expenses ────────────────────────────────────────────────────────

@app.route('/expenses')
@login_required
def expenses():
    sym = get_currency_symbol(current_user)
    q = request.args.get('q', '')
    cat = request.args.get('category', '')
    month = request.args.get('month', '')

    query = Expense.query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(Expense.title.ilike(f'%{q}%'))
    if cat:
        query = query.filter_by(category=cat)
    if month:
        try:
            yr, mo = month.split('-')
            query = query.filter(
                db.extract('year', Expense.date) == int(yr),
                db.extract('month', Expense.date) == int(mo)
            )
        except Exception:
            pass

    all_expenses = query.order_by(Expense.date.desc(), Expense.created_at.desc()).all()
    total = sum(e.amount for e in all_expenses)

    return render_template('expenses.html',
        expenses=all_expenses, categories=CATEGORIES,
        sym=sym, total=total, q=q, cat=cat, month=month
    )

@app.route('/expenses/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        amount = request.form.get('amount', 0)
        category = request.form.get('category', 'Others')
        exp_date = request.form.get('date', str(date.today()))
        notes = request.form.get('notes', '')
        is_recurring = bool(request.form.get('is_recurring'))

        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash('Please enter a valid amount.', 'error')
            return redirect(url_for('add_expense'))

        receipt_filename = ''
        if 'receipt' in request.files:
            file = request.files['receipt']
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext in ['jpg', 'jpeg', 'png', 'pdf']:
                    receipt_filename = f"receipt_{current_user.id}_{int(datetime.utcnow().timestamp())}.{ext}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], receipt_filename))

        exp = Expense(
            user_id=current_user.id, title=title, amount=amount,
            category=category, date=datetime.strptime(exp_date, '%Y-%m-%d').date(),
            notes=notes, receipt=receipt_filename, is_recurring=is_recurring
        )
        db.session.add(exp)
        db.session.commit()
        flash('Expense added successfully! 💸', 'success')
        return redirect(url_for('expenses'))

    return render_template('add_expense.html', categories=CATEGORIES, today=date.today())

@app.route('/expenses/edit/<int:exp_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(exp_id):
    exp = Expense.query.filter_by(id=exp_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        exp.title = request.form.get('title', exp.title).strip()
        exp.category = request.form.get('category', exp.category)
        exp.notes = request.form.get('notes', '')
        exp.is_recurring = bool(request.form.get('is_recurring'))
        try:
            exp.amount = float(request.form.get('amount', exp.amount))
            exp.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
        except Exception:
            flash('Invalid amount or date.', 'error')
            return redirect(url_for('edit_expense', exp_id=exp_id))
        db.session.commit()
        flash('Expense updated! ✅', 'success')
        return redirect(url_for('expenses'))
    return render_template('edit_expense.html', exp=exp, categories=CATEGORIES)

@app.route('/expenses/delete/<int:exp_id>', methods=['POST'])
@login_required
def delete_expense(exp_id):
    exp = Expense.query.filter_by(id=exp_id, user_id=current_user.id).first_or_404()
    db.session.delete(exp)
    db.session.commit()
    flash('Expense deleted.', 'info')
    return redirect(url_for('expenses'))

# ─── Routes: Income ──────────────────────────────────────────────────────────

@app.route('/income')
@login_required
def income():
    sym = get_currency_symbol(current_user)
    all_income = Income.query.filter_by(user_id=current_user.id)\
        .order_by(Income.date.desc()).all()
    total = sum(i.amount for i in all_income)
    return render_template('income.html', incomes=all_income,
                           sources=INCOME_SOURCES, sym=sym, total=total)

@app.route('/income/add', methods=['POST'])
@login_required
def add_income():
    try:
        inc = Income(
            user_id=current_user.id,
            title=request.form.get('title', '').strip(),
            amount=float(request.form.get('amount', 0)),
            source=request.form.get('source', 'Others'),
            date=datetime.strptime(request.form.get('date', str(date.today())), '%Y-%m-%d').date(),
            notes=request.form.get('notes', ''),
            is_recurring=bool(request.form.get('is_recurring'))
        )
        if inc.amount <= 0:
            raise ValueError
        db.session.add(inc)
        db.session.commit()
        flash('Income added! 💰', 'success')
    except Exception:
        flash('Invalid data. Please try again.', 'error')
    return redirect(url_for('income'))

@app.route('/income/delete/<int:inc_id>', methods=['POST'])
@login_required
def delete_income(inc_id):
    inc = Income.query.filter_by(id=inc_id, user_id=current_user.id).first_or_404()
    db.session.delete(inc)
    db.session.commit()
    flash('Income record deleted.', 'info')
    return redirect(url_for('income'))

# ─── Routes: Analytics ───────────────────────────────────────────────────────

@app.route('/analytics')
@login_required
def analytics():
    sym = get_currency_symbol(current_user)
    monthly_data = get_monthly_data(current_user.id, 12)
    today = date.today()
    category_data = get_category_totals(current_user.id, today.month, today.year)
    yearly_category = get_category_totals(current_user.id)
    ai = ai_analysis(current_user.id)
    return render_template('analytics.html',
        sym=sym, monthly_data=json.dumps(monthly_data),
        category_data=json.dumps(category_data),
        yearly_category=json.dumps(yearly_category),
        ai=ai, categories=CATEGORIES
    )

# ─── Routes: Budget ──────────────────────────────────────────────────────────

@app.route('/budget')
@login_required
def budget():
    sym = get_currency_symbol(current_user)
    today = date.today()
    category_data = get_category_totals(current_user.id, today.month, today.year)
    budgets = Budget.query.filter_by(
        user_id=current_user.id, month=today.month, year=today.year
    ).all()

    budget_list = []
    for cat in CATEGORIES:
        b = next((x for x in budgets if x.category == cat), None)
        spent = category_data.get(cat, 0)
        limit = b.amount if b else 0
        pct = min(round((spent / limit * 100), 1), 100) if limit > 0 else 0
        status = 'danger' if pct >= 90 else 'warning' if pct >= 70 else 'success'
        budget_list.append({
            'id': b.id if b else None, 'category': cat,
            'limit': limit, 'spent': spent, 'pct': pct, 'status': status
        })

    return render_template('budget.html', sym=sym, budget_list=budget_list,
                           categories=CATEGORIES, today=today)

@app.route('/budget/set', methods=['POST'])
@login_required
def set_budget():
    today = date.today()
    for cat in CATEGORIES:
        val = request.form.get(f'budget_{cat}', '')
        if val:
            try:
                amount = float(val)
                existing = Budget.query.filter_by(
                    user_id=current_user.id, category=cat,
                    month=today.month, year=today.year
                ).first()
                if existing:
                    existing.amount = amount
                else:
                    db.session.add(Budget(
                        user_id=current_user.id, category=cat,
                        amount=amount, month=today.month, year=today.year
                    ))
            except ValueError:
                pass
    db.session.commit()
    flash('Budgets updated! 🎯', 'success')
    return redirect(url_for('budget'))

# ─── Routes: Profile ─────────────────────────────────────────────────────────

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name).strip()
        current_user.currency = request.form.get('currency', current_user.currency)
        current_user.theme = request.form.get('theme', current_user.theme)
        try:
            current_user.monthly_budget = float(request.form.get('monthly_budget', 0))
            current_user.savings_goal = float(request.form.get('savings_goal', 0))
        except ValueError:
            pass
        new_pass = request.form.get('new_password', '')
        if new_pass:
            if len(new_pass) < 6:
                flash('Password must be at least 6 characters.', 'error')
                return redirect(url_for('profile'))
            current_user.set_password(new_pass)
        db.session.commit()
        flash('Profile updated! ✅', 'success')
        return redirect(url_for('profile'))

    currencies = list(CURRENCY_SYMBOLS.keys())
    return render_template('profile.html', currencies=currencies,
                           sym=get_currency_symbol(current_user))

# ─── Routes: Export ──────────────────────────────────────────────────────────

@app.route('/export/excel')
@login_required
def export_excel():
    expenses = Expense.query.filter_by(user_id=current_user.id)\
        .order_by(Expense.date.desc()).all()
    incomes = Income.query.filter_by(user_id=current_user.id)\
        .order_by(Income.date.desc()).all()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Expenses sheet
        exp_data = [{
            'Date': e.date, 'Title': e.title, 'Category': e.category,
            'Amount': e.amount, 'Notes': e.notes
        } for e in expenses]
        pd.DataFrame(exp_data).to_excel(writer, sheet_name='Expenses', index=False)

        # Income sheet
        inc_data = [{
            'Date': i.date, 'Title': i.title, 'Source': i.source,
            'Amount': i.amount, 'Notes': i.notes
        } for i in incomes]
        pd.DataFrame(inc_data).to_excel(writer, sheet_name='Income', index=False)

    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='smartspend_report.xlsx')

@app.route('/export/pdf')
@login_required
def export_pdf():
    today = date.today()
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Heading1'],
                                 textColor=colors.HexColor('#6366f1'), fontSize=20)
    elements = []

    elements.append(Paragraph('SmartSpend AI – Monthly Report', title_style))
    elements.append(Paragraph(f'Generated for {current_user.name} | {today.strftime("%B %Y")}', styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    # Summary
    sym = get_currency_symbol(current_user)
    cat_data = get_category_totals(current_user.id, today.month, today.year)
    total_exp = sum(cat_data.values())
    total_inc = db.session.query(db.func.sum(Income.amount)).filter(
        Income.user_id == current_user.id,
        db.extract('month', Income.date) == today.month,
        db.extract('year', Income.date) == today.year
    ).scalar() or 0

    summary_data = [
        ['Metric', 'Amount'],
        ['Total Income', f'{sym}{total_inc:,.2f}'],
        ['Total Expenses', f'{sym}{total_exp:,.2f}'],
        ['Net Savings', f'{sym}{total_inc - total_exp:,.2f}'],
    ]
    t = Table(summary_data, colWidths=[8*cm, 8*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROUNDEDCORNERS', [5]),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.5*cm))

    # Expenses table
    elements.append(Paragraph('Expense Breakdown', styles['Heading2']))
    expenses = Expense.query.filter_by(user_id=current_user.id).filter(
        db.extract('month', Expense.date) == today.month,
        db.extract('year', Expense.date) == today.year
    ).order_by(Expense.date.desc()).all()

    if expenses:
        exp_table_data = [['Date', 'Title', 'Category', 'Amount']]
        for e in expenses:
            exp_table_data.append([str(e.date), e.title, e.category, f'{sym}{e.amount:,.2f}'])
        t2 = Table(exp_table_data, colWidths=[3*cm, 6*cm, 4*cm, 3*cm])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366f1')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(t2)

    doc.build(elements)
    output.seek(0)
    return send_file(output, mimetype='application/pdf',
                     as_attachment=True, download_name='smartspend_report.pdf')

# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.route('/api/chart/monthly')
@login_required
def api_monthly():
    months = int(request.args.get('months', 6))
    return jsonify(get_monthly_data(current_user.id, months))

@app.route('/api/chart/categories')
@login_required
def api_categories():
    today = date.today()
    return jsonify(get_category_totals(current_user.id, today.month, today.year))

@app.route('/api/ai/chat', methods=['POST'])
@login_required
def ai_chat():
    """Simple AI finance chatbot"""
    msg = request.json.get('message', '').lower()
    ai = ai_analysis(current_user.id)
    sym = get_currency_symbol(current_user)

    # Keyword-based responses
    if any(w in msg for w in ['hello', 'hi', 'hey']):
        reply = f"Hello {current_user.name}! I'm your AI finance assistant. Ask me about your spending, savings, or budget! 😊"
    elif any(w in msg for w in ['spend', 'expense', 'spent']):
        reply = f"This month you've spent {sym}{ai['total_expense']:,.0f}. Your top spending areas are based on your category breakdown. Would you like tips to reduce spending?"
    elif any(w in msg for w in ['save', 'saving', 'savings']):
        balance = ai['total_income'] - ai['total_expense']
        reply = f"Your net savings this month is {sym}{balance:,.0f}. {ai['health_label']} financial health! 🎯"
    elif any(w in msg for w in ['budget', 'limit']):
        reply = "Set category budgets in the Budget Planner section to track your limits and get alerts when you're close to overspending!"
    elif any(w in msg for w in ['tip', 'advice', 'suggest']):
        tip = random.choice(ai['tips'])
        reply = f"{tip['icon']} {tip['msg']}"
    elif any(w in msg for w in ['predict', 'next month', 'forecast']):
        reply = f"Based on your spending patterns, I predict your expenses next month will be around {sym}{ai['prediction']:,.0f}. Plan accordingly!"
    elif any(w in msg for w in ['health', 'score']):
        reply = f"Your financial health score is {ai['health_score']}/100 – {ai['health_label']}! {'Keep it up! 🌟' if ai['health_score'] >= 70 else 'Let me help you improve it.'}"
    else:
        replies = [
            f"Great question! Your financial health score is {ai['health_score']}/100. {ai['health_label']}!",
            "Try setting budgets for each category to control your spending better.",
            f"You've recorded {sym}{ai['total_income']:,.0f} income and {sym}{ai['total_expense']:,.0f} in expenses this month.",
            "Use the Analytics section for detailed charts and trends!",
        ]
        reply = random.choice(replies)

    return jsonify({'reply': reply})

# ─── Sample Data Seeder ───────────────────────────────────────────────────────

def _seed_sample_data(user_id):
    """Seed disabled — users enter their own data."""
    pass


# ═══════════════════════════════════════════════════════════
# AJAX API ROUTES  (called by dashboard JS — no page reload)
# ═══════════════════════════════════════════════════════════

def _month_stats(user_id):
    """Return this-month summary used by all AJAX endpoints."""
    from datetime import date as _date
    today = _date.today()
    exp = db.session.query(db.func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        db.extract('month', Expense.date) == today.month,
        db.extract('year',  Expense.date) == today.year
    ).scalar() or 0
    inc = db.session.query(db.func.sum(Income.amount)).filter(
        Income.user_id == user_id,
        db.extract('month', Income.date) == today.month,
        db.extract('year',  Income.date) == today.year
    ).scalar() or 0
    bal = inc - exp
    pct = round(bal / inc * 100, 1) if inc > 0 else 0
    cats = get_category_totals(user_id, today.month, today.year)
    recent = Expense.query.filter_by(user_id=user_id)        .order_by(Expense.date.desc(), Expense.created_at.desc()).limit(8).all()
    return {
        'income': round(inc, 2), 'expense': round(exp, 2),
        'balance': round(bal, 2), 'savings_pct': pct,
        'category_data': cats,
        'recent': [{'id': e.id, 'title': e.title, 'amount': e.amount,
                    'category': e.category,
                    'date_display': e.date.strftime('%d %b %Y')} for e in recent]
    }


@app.route('/api/expense/add', methods=['POST'])
@login_required
def api_add_expense():
    try:
        data     = request.get_json(force=True) or {}
        title    = (data.get('title') or '').strip()
        amount   = float(data.get('amount', 0))
        category = data.get('category', 'Others')
        raw_date = data.get('date', str(date.today()))
        notes    = (data.get('notes') or '').strip()
        if not title:
            return jsonify({'success': False, 'error': 'Title is required.'})
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be > 0.'})
        exp = Expense(
            user_id=current_user.id, title=title, amount=amount,
            category=category,
            date=datetime.strptime(raw_date, '%Y-%m-%d').date(),
            notes=notes
        )
        db.session.add(exp)
        db.session.commit()
        return jsonify({
            'success': True,
            'expense': {
                'id': exp.id, 'title': exp.title,
                'amount': exp.amount, 'category': exp.category,
                'date_display': exp.date.strftime('%d %b %Y'),
            },
            'stats': _month_stats(current_user.id)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/expense/delete/<int:exp_id>', methods=['POST'])
@login_required
def api_delete_expense(exp_id):
    exp = Expense.query.filter_by(id=exp_id, user_id=current_user.id).first()
    if not exp:
        return jsonify({'success': False, 'error': 'Not found'})
    db.session.delete(exp)
    db.session.commit()
    return jsonify({'success': True, 'stats': _month_stats(current_user.id)})


@app.route('/api/income/add', methods=['POST'])
@login_required
def api_add_income():
    try:
        data     = request.get_json(force=True) or {}
        title    = (data.get('title') or '').strip()
        amount   = float(data.get('amount', 0))
        source   = data.get('source', 'Others')
        raw_date = data.get('date', str(date.today()))
        if not title:
            return jsonify({'success': False, 'error': 'Title is required.'})
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be > 0.'})
        inc = Income(
            user_id=current_user.id, title=title, amount=amount,
            source=source,
            date=datetime.strptime(raw_date, '%Y-%m-%d').date()
        )
        db.session.add(inc)
        db.session.commit()
        return jsonify({'success': True, 'stats': _month_stats(current_user.id)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/stats/summary')
@login_required
def api_stats_summary():
    return jsonify(_month_stats(current_user.id))


@app.route('/api/theme/set', methods=['POST'])
@login_required
def api_set_theme():
    """AJAX endpoint — saves theme preference instantly from toggle button."""
    data = request.get_json(force=True) or {}
    t = data.get('theme', 'dark')
    if t not in ('dark', 'light'):
        t = 'dark'
    current_user.theme = t
    db.session.commit()
    return jsonify({'success': True, 'theme': t})

# ─── Main Entry ───────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)