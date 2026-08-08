# Financial Intelligence Research Platform

A Django-based personal finance, banking, and investment research platform.

Originally built as a personal finance tracker, the application has expanded into a financial research environment capable of importing banking transactions, analyzing spending habits, and researching publicly traded companies using SEC EDGAR filings.

---

# Features

## Personal Finance

- Import transactions from multiple financial institutions
- Duplicate transaction detection
- Automatic transaction categorization
- Category rules engine
- Import preview before committing
- Import history and audit log
- Dashboard with spending analytics
- Vehicle expense reporting
- Food spending analysis
- Subscription tracking
- Debt payoff dashboard

Supported import formats include:

- Generic CSV
- Canadian Tire Mastercard
- Capital One

---

## Investment Research

The Research application provides SEC EDGAR integration including:

- Company database
- SEC filing downloads
- Financial statement normalization
- Annual and quarterly metrics
- Financial ratios
- Historical financial trends
- Filing browser
- Company dashboard

Current metric support includes:

- Revenue
- Gross Profit
- Operating Income
- Net Income
- EPS
- Cash
- Assets
- Liabilities
- Shareholder Equity
- Operating Cash Flow
- Free Cash Flow

---

# Technology Stack

- Python 3.9+
- Django 4.2
- PostgreSQL
- Bootstrap 5
- SEC EDGAR API

---

# Installation

Clone the repository

```bash
git clone https://github.com/yourusername/bank-app.git
cd bank-app
```

Create a virtual environment

```bash
python -m venv venv
```

Activate

Mac/Linux

```bash
source venv/bin/activate
```

Windows

```bash
venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file.

Example:

```text
SECRET_KEY=your-secret-key
DEBUG=True

DB_NAME=bankdb
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

SEC_USER_AGENT=Your Name your@email.com
```

The SEC requires a valid User-Agent string.

---

# Database

Run migrations

```bash
python manage.py migrate
```

Create an administrator

```bash
python manage.py createsuperuser
```

Run the development server

```bash
python manage.py runserver
```

---

# Project Structure

```
bank-app/
│
├── banking/
│   ├── models.py
│   ├── views.py
│   ├── templates/
│   └── services/
│
├── research/
│   ├── models.py
│   ├── services/
│   ├── sec_client.py
│   ├── metric_normalizer.py
│   └── templates/
│
├── manage.py
└── requirements.txt
```

---

# Roadmap

## Banking

- Additional bank importers
- Recurring payment detection
- Cash flow forecasting
- Budget planning
- AI spending insights

## Research

- Insider trading
- Earnings calendar
- Dividend history
- Option strategy tools
- Calendar spread analyzer
- AI company analysis
- SEC filing summaries

---

# Contributing

Contributions are welcome.

Please open an issue before submitting significant changes.

---

# License

This project is released under the MIT License.

---

# Disclaimer

This project is intended for educational and personal financial analysis purposes.

Investment decisions should not be based solely on the information produced by this software.