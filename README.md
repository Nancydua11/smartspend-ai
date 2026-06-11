SmartSpend AI 💸


A full-stack personal finance tracker with AI-powered insights, real-time dashboard updates, budget planning and export reports — built with Python Flask.



Show Image
Show Image
Show Image
Show Image
Show Image


✨ Features

🔐 Authentication


Secure signup & login with password hashing (scrypt via Werkzeug)
Session management with Flask-Login
Per-user isolated data — no shared state between accounts


📊 Real-Time Dashboard


Live clock updating every second
Add Expense and Add Income via modal popups — no page reload
Stat cards (Income, Expenses, Balance, Savings Rate) update instantly via AJAX
Pie chart redraws automatically after every transaction
Delete transactions directly from the dashboard with slide animation
Onboarding banner for new users with step-by-step guidance


💸 Expense Management


Add, edit, delete expenses
8 categories: Food, Shopping, Bills, Travel, Entertainment, Education, Health, Others
Filter by category, month or keyword search
Upload receipt/bill images
Mark as recurring


💰 Income Management


7 income sources: Salary, Freelance, Business, Investment, Rental, Gift, Others
Add and delete income records
Monthly income tracking


📈 Analytics


Income vs Expenses bar chart (3 / 6 / 12 month range selector)
Category doughnut breakdown
12-month trend line chart
All-time yearly category chart
Category table with amount + percentage share


🤖 AI Financial Health


Financial health score out of 100
Overspending alerts per category
Personalised saving tips
Next-month expense prediction (3-month moving average)
AI chatbot — ask about spending, savings and budget


🎯 Budget Planner


Set monthly limits per category
Colour-coded progress bars (green → amber → red)
Over-limit warnings


👤 Profile & Settings


Update name, currency (INR, USD, EUR, GBP, JPY, CAD, AUD)
Visual dark / light mode toggle saved instantly to server
Change password
Monthly budget limit and savings goal


📤 Export


Excel (.xlsx) — all transactions (Expenses + Income sheets)
PDF report — styled monthly summary with tables



🛠️ Tech Stack

LayerTechnologyBackendPython 3.10+, Flask 3.0DatabaseSQLite (local) / PostgreSQL (production)ORMFlask-SQLAlchemyAuthFlask-Login, WerkzeugFrontendHTML5, CSS3, Vanilla JavaScriptChartsChart.js 4.4IconsFont Awesome 6.5FontsSyne + DM Sans (Google Fonts)Excel exportPandas + OpenPyXLPDF exportReportLabProduction serverGunicorn


🚀 Local Setup

Prerequisites


Python 3.10 or higher
pip


Steps

bash# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/smartspend-ai.git
cd smartspend-ai

# 2. Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py

Open http://127.0.0.1:5000 in your browser.

The SQLite database is created automatically on first run at instance/smartspend.db.


🌐 Free Deployment

Option 1 — Render.com (Recommended)


Push this repo to GitHub
Go to render.com → New Web Service
Connect your GitHub repo
Settings:

Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
Instance Type: Free



Add environment variable: SECRET_KEY → any long random string
Click Deploy


Live at: https://smartspend-ai.onrender.com


Add a free Render PostgreSQL database and set DATABASE_URL for persistent storage.



Option 2 — PythonAnywhere


Upload files via Files tab
Create Flask web app → point to your directory
Edit WSGI file to import app
Reload



📁 Project Structure

smartspend-ai/
│
├── app.py                   # Flask app — routes, models, AI logic, AJAX APIs
│
├── templates/
│   ├── base.html            # Sidebar, topbar, AI chat widget
│   ├── landing.html         # Public landing page
│   ├── login.html           # Login
│   ├── signup.html          # Signup
│   ├── dashboard.html       # Real-time dashboard
│   ├── expenses.html        # Expense list + search
│   ├── add_expense.html     # Add expense form
│   ├── edit_expense.html    # Edit expense form
│   ├── income.html          # Income management
│   ├── analytics.html       # Charts & analytics
│   ├── budget.html          # Budget planner
│   └── profile.html         # Settings & theme
│
├── static/
│   ├── css/main.css         # Dark/light themes, glassmorphism, responsive
│   ├── js/main.js           # AJAX, charts, theme sync, chat, animations
│   └── uploads/             # Receipt image uploads
│
├── Procfile                 # Render/Heroku start command
├── render.yaml              # Render auto-deploy config
├── requirements.txt         # Python dependencies
└── README.md


🔌 API Endpoints

MethodEndpointDescriptionPOST/api/expense/addAJAX add expensePOST/api/expense/delete/<id>AJAX delete expensePOST/api/income/addAJAX add incomeGET/api/stats/summaryThis-month statsGET/api/chart/monthlyMonthly chart dataGET/api/chart/categoriesCategory totalsPOST/api/theme/setSave theme preferencePOST/api/ai/chatAI chatbot response


🗄️ Database Models

User       id · name · email · password_hash · currency · theme · monthly_budget · savings_goal
Expense    id · user_id · title · amount · category · date · notes · receipt · is_recurring
Income     id · user_id · title · amount · source · date · notes · is_recurring
Budget     id · user_id · category · amount · month · year


⚠️ About UPI / Bank Auto-Sync

SmartSpend is a manual tracking app. Direct integration with UPI apps (PhonePe, GPay, Paytm) or bank accounts requires RBI Account Aggregator licensing — only available to regulated fintech companies.

Workaround: Use the quick-add button right after a payment, or download your bank statement as CSV and enter transactions manually.


📄 License

MIT License — free to use, modify and distribute.


👩‍💻 Author

Nancy Dua
B.Tech Computer Science Engineering · Chandigarh University · 2026
Specialisation: Data Analytics & Business Intelligence
Certifications: Oracle · IBM · Microsoft Power BI · Meta


Built as a portfolio project demonstrating full-stack Python development, REST API design, SQL database management, and responsive frontend development.
