# SecureView 🔐

**Business Intelligence & Cloud Data Security using Google BigQuery and Streamlit**

## Overview
SecureView is a dashboard that combines sales analytics with cloud data access security. It uses Google BigQuery for data storage and analysis and Streamlit for the interactive interface.

## Features

### Sales Intelligence
- Revenue, profit, and profit margin KPIs
- Sales analysis by date range
- Product performance and units sold
- Sales trends and comparisons with the previous period
- Category and regional analysis where available

### Employee Analytics
- Department-wise employee statistics
- Employee records through BigQuery authorized views
- Selected-column queries that omit salary

### Security Analysis
- Tests access to authorized department views
- Tests direct access to the private employee source table
- Demonstrates least-privilege access using Google Cloud IAM

## Technology Stack
- Python
- Streamlit
- Google BigQuery
- Google Cloud IAM
- Pandas
- Google Cloud authentication libraries

## Architecture
1. Sales data is stored in the `sales_analytics.sales` BigQuery table.
2. Employee records are exposed through department-specific authorized views.
3. The Streamlit dashboard queries BigQuery using a configured service account.
4. BigQuery IAM permissions control which tables and views that identity can access.

## Demo
[Open the SecureView dashboard](https://secureview-j7xmsbdw43bepnufpxn99k.streamlit.app/)

## Data Disclaimer
The sales dataset contains **synthetic demonstration data**. It does not represent actual business transactions.

## Security Notes
- Never commit service-account keys or `.streamlit/secrets.toml` to GitHub.
- Configure credentials using Streamlit Secrets.
- The current permission checks test the application's service-account identity, not individual signed-in employees.
- Production deployment requires verified user authentication, appropriate authorization rules, and audit monitoring.

## Run Locally
Install the dependencies:

```bash
pip install -r requirements.txt
```

Configure `.streamlit/secrets.toml` with your authorized Google Cloud service-account credentials, then run:

```bash
streamlit run app.py
```
