
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery
from google.oauth2 import service_account
from google.api_core.exceptions import Forbidden, GoogleAPICallError


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(
    page_title="SecureView | Business Intelligence",
    page_icon="🔐",
    layout="wide",
)

PROJECT_ID = "bigquery-row-access"
SOURCE_TABLE = f"{PROJECT_ID}.student_private.employees"
SALES_TABLE = f"{PROJECT_ID}.sales_analytics.sales"

VIEWS = {
    "IT": f"{PROJECT_ID}.student_views.it_employees",
    "HR": f"{PROJECT_ID}.student_views.hr_employees",
    "Finance": f"{PROJECT_ID}.student_views.finance_employees",
}


# --------------------------------------------------
# BIGQUERY CONNECTION
# --------------------------------------------------
@st.cache_resource
def get_client():
    credentials_info = dict(st.secrets["gcp_service_account"])
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info
    )
    return bigquery.Client(
        project=PROJECT_ID,
        credentials=credentials,
    )


def load_employees(client, view_name):
    query = f"""
        SELECT employee_id, name, department, email
        FROM `{view_name}`
        ORDER BY employee_id
    """
    return client.query(query).to_dataframe()


def get_department_counts(client):
    results = []

    for department, view_name in VIEWS.items():
        try:
            query = f"SELECT COUNT(*) AS total FROM `{view_name}`"
            result = client.query(query).to_dataframe()
            results.append({
                "Department": department,
                "Employees": int(result.iloc[0]["total"]),
                "Status": "Accessible",
            })
        except Forbidden:
            results.append({
                "Department": department,
                "Employees": None,
                "Status": "Access denied",
            })
        except GoogleAPICallError:
            results.append({
                "Department": department,
                "Employees": None,
                "Status": "Query error",
            })

    return pd.DataFrame(results)


# --------------------------------------------------
# SALES DATA
# --------------------------------------------------
@st.cache_data(ttl=300)
def load_sales(start_date, end_date):
    client = get_client()

    query = f"""
        SELECT
            order_id,
            sale_date,
            product_id,
            product_name,
            category,
            quantity,
            unit_price,
            unit_cost,
            revenue,
            profit,
            region,
            customer_id,
            order_status
        FROM `{SALES_TABLE}`
        WHERE sale_date BETWEEN @start_date AND @end_date
        ORDER BY sale_date
    """

    config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "start_date", "DATE", start_date
            ),
            bigquery.ScalarQueryParameter(
                "end_date", "DATE", end_date
            ),
        ]
    )

    df = client.query(query, job_config=config).to_dataframe()

    if not df.empty:
        df["sale_date"] = pd.to_datetime(df["sale_date"]).dt.date

    return df


def get_period_dates(period):
    today = date.today()

    if period == "Today":
        return today, today

    if period == "This week":
        start = today - timedelta(days=today.weekday())
        return start, today

    if period == "This month":
        return today.replace(day=1), today

    if period == "Last 7 days":
        return today - timedelta(days=6), today

    if period == "Last 30 days":
        return today - timedelta(days=29), today

    if period == "Last 90 days":
        return today - timedelta(days=89), today

    if period == "Last 180 days":
        return today - timedelta(days=179), today

    return today - timedelta(days=6), today


def calculate_metrics(df):
    if df.empty:
        return {
            "revenue": 0.0,
            "profit": 0.0,
            "units": 0,
            "orders": 0,
            "customers": 0,
            "margin": 0.0,
        }

    completed = df[df["order_status"] == "Completed"]

    revenue = float(completed["revenue"].sum())
    profit = float(completed["profit"].sum())

    return {
        "revenue": revenue,
        "profit": profit,
        "units": int(completed["quantity"].sum()),
        "orders": int(completed["order_id"].nunique()),
        "customers": int(completed["customer_id"].nunique()),
        "margin": (profit / revenue * 100) if revenue else 0.0,
    }


def money(value):
    return f"₹{value:,.0f}"


def show_change(current, previous, suffix=""):
    if previous == 0:
        if current == 0:
            return "No change"
        return "New in this period"

    change = ((current - previous) / abs(previous)) * 100
    return f"{change:+.1f}%{suffix} vs previous period"


# --------------------------------------------------
# HEADER AND NAVIGATION
# --------------------------------------------------
st.title("🔐 SecureView")
st.subheader("Business Intelligence & Cloud Data Security")
st.caption(
    "BigQuery analytics · Authorized views · Access monitoring"
)

with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "Choose a dashboard",
        [
            "Sales Intelligence",
            "Employee Analytics",
            "Department Records",
            "Security Analysis",
        ],
    )

    st.divider()
    st.caption("Google Cloud BigQuery")
    st.caption("Sales figures use synthetic demo data.")


# --------------------------------------------------
# CONNECT TO BIGQUERY
# --------------------------------------------------
try:
    client = get_client()
except (DefaultCredentialsError, KeyError, ValueError):
    st.error(
        "Google Cloud credentials could not be loaded. "
        "Check the Streamlit Secrets configuration."
    )
    st.stop()
except Exception as exc:
    st.error("Unable to initialize the BigQuery connection.")
    st.exception(exc)
    st.stop()


# --------------------------------------------------
# SALES INTELLIGENCE
# --------------------------------------------------
if page == "Sales Intelligence":
    st.header("📈 Sales Intelligence")
    st.caption(
        "Explore revenue, profit, product performance and trends."
    )

    period = st.selectbox(
        "Analysis period",
        [
            "Today",
            "This week",
            "This month",
            "Last 7 days",
            "Last 30 days",
            "Last 90 days",
            "Last 180 days",
            "Custom range",
        ],
        index=4,
    )

    if period == "Custom range":
        col_a, col_b = st.columns(2)
        with col_a:
            start_date = st.date_input(
                "Start date",
                value=date.today() - timedelta(days=29),
            )
        with col_b:
            end_date = st.date_input(
                "End date",
                value=date.today(),
            )
    else:
        start_date, end_date = get_period_dates(period)

    if start_date > end_date:
        st.error("Start date must be on or before end date.")
        st.stop()

    st.caption(
        f"Showing {start_date:%d %b %Y} to {end_date:%d %b %Y}"
    )

    try:
        with st.spinner("Loading sales data from BigQuery..."):
            sales_df = load_sales(start_date, end_date)

            days = (end_date - start_date).days + 1
            previous_end = start_date - timedelta(days=1)
            previous_start = previous_end - timedelta(days=days - 1)

            previous_df = load_sales(previous_start, previous_end)

    except Forbidden:
        st.error(
            "Access denied. Grant the Streamlit service account "
            "BigQuery Data Viewer on the sales_analytics dataset."
        )
        st.stop()
    except GoogleAPICallError as exc:
        st.error(f"BigQuery could not load sales data: {exc}")
        st.stop()
    except Exception as exc:
        st.error(f"Unable to load sales data: {exc}")
        st.stop()

    current = calculate_metrics(sales_df)
    previous = calculate_metrics(previous_df)

    st.info(
        "DEMO DATA: These are generated sales records, not actual "
        "business transactions."
    )

    if sales_df.empty:
        st.warning(
            "No sales records exist in this date range. "
            "Try Last 180 days or choose another date range."
        )
    else:
        # KPI cards
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Completed Revenue",
            money(current["revenue"]),
            show_change(current["revenue"], previous["revenue"]),
        )
        c2.metric(
            "Completed Profit",
            money(current["profit"]),
            show_change(current["profit"], previous["profit"]),
        )
        c3.metric(
            "Profit Margin",
            f'{current["margin"]:.1f}%',
            show_change(current["margin"], previous["margin"], " pp"),
        )

        c4, c5, c6 = st.columns(3)
        c4.metric(
            "Units Sold",
            f'{current["units"]:,}',
            show_change(current["units"], previous["units"]),
        )
        c5.metric(
            "Completed Orders",
            f'{current["orders"]:,}',
            show_change(current["orders"], previous["orders"]),
        )
        c6.metric(
            "Unique Customers",
            f'{current["customers"]:,}',
            show_change(current["customers"], previous["customers"]),
        )

        st.divider()

        # Product performance
        st.subheader("🏆 Product Performance")

        completed = sales_df[
            sales_df["order_status"] == "Completed"
        ].copy()

        product_df = (
            completed.groupby(
                ["product_name", "category"], as_index=False
            )
            .agg(
                units_sold=("quantity", "sum"),
                revenue=("revenue", "sum"),
                profit=("profit", "sum"),
                orders=("order_id", "nunique"),
            )
            .sort_values("revenue", ascending=False)
        )

        product_df["profit_margin_pct"] = (
            product_df["profit"] / product_df["revenue"] * 100
        ).fillna(0)

        left, right = st.columns(2)

        with left:
            st.markdown("**Revenue by product**")
            st.bar_chart(
                product_df.set_index("product_name")[["revenue"]]
            )

        with right:
            st.markdown("**Units sold by product**")
            st.bar_chart(
                product_df.set_index("product_name")[["units_sold"]]
            )

        st.dataframe(
            product_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "revenue": st.column_config.NumberColumn(
                    "Revenue", format="₹%.0f"
                ),
                "profit": st.column_config.NumberColumn(
                    "Profit", format="₹%.0f"
                ),
                "profit_margin_pct": st.column_config.NumberColumn(
                    "Profit Margin (%)", format="%.1f%%"
                ),
            },
        )

        st.divider()

        # Daily revenue and profit trend
        st.subheader("📅 Daily Revenue and Profit Trend")

        trend = completed.groupby("sale_date", as_index=False).agg(
            revenue=("revenue", "sum"),
            profit=("profit", "sum"),
        )

        if not trend.empty:
            trend["sale_date"] = pd.to_datetime(trend["sale_date"])
            trend = trend.set_index("sale_date")
            st.line_chart(trend[["revenue", "profit"]])

        # Category analysis
        st.subheader("🧩 Category Analysis")

        category_df = (
            completed.groupby("category", as_index=False)
            .agg(
                revenue=("revenue", "sum"),
                profit=("profit", "sum"),
                units=("quantity", "sum"),
            )
            .sort_values("revenue", ascending=False)
        )

        cat1, cat2 = st.columns(2)

        with cat1:
            st.markdown("**Revenue by category**")
            st.bar_chart(
                category_df.set_index("category")[["revenue"]]
            )

        with cat2:
            st.markdown("**Profit by category**")
            st.bar_chart(
                category_df.set_index("category")[["profit"]]
            )

        # Regional analysis
        st.subheader("🌍 Regional Analysis")

        region_df = (
            completed.groupby("region", as_index=False)
            .agg(
                revenue=("revenue", "sum"),
                profit=("profit", "sum"),
                units=("quantity", "sum"),
            )
            .sort_values("revenue", ascending=False)
        )

        r1, r2 = st.columns(2)

        with r1:
            st.markdown("**Revenue by region**")
            st.bar_chart(
                region_df.set_index("region")[["revenue"]]
            )

        with r2:
            st.markdown("**Regional summary**")
            st.dataframe(
                region_df,
                use_container_width=True,
                hide_index=True,
            )

        # Order status
        st.subheader("📦 Order Status")

        status_df = (
            sales_df.groupby("order_status", as_index=False)
            .agg(
                records=("order_id", "count"),
                recorded_revenue=("revenue", "sum"),
            )
            .sort_values("records", ascending=False)
        )

        s1, s2 = st.columns(2)

        with s1:
            st.bar_chart(
                status_df.set_index("order_status")[["records"]]
            )

        with s2:
            st.dataframe(
                status_df,
                use_container_width=True,
                hide_index=True,
            )

        # Monthly analysis
        st.subheader("🗓️ Monthly Performance")

        monthly_source = completed.copy()
        monthly_source["month"] = pd.to_datetime(
            monthly_source["sale_date"]
        ).dt.to_period("M").astype(str)

        monthly_df = (
            monthly_source.groupby("month", as_index=False)
            .agg(
                revenue=("revenue", "sum"),
                profit=("profit", "sum"),
                units=("quantity", "sum"),
            )
            .sort_values("month")
        )

        st.line_chart(monthly_df.set_index("month")[["revenue", "profit"]])

        # Downloadable reports
        st.subheader("⬇️ Download Reports")

        d1, d2 = st.columns(2)

        with d1:
            st.download_button(
                "Download filtered sales CSV",
                data=sales_df.to_csv(index=False).encode("utf-8"),
                file_name="secureview_sales.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with d2:
            st.download_button(
                "Download product summary CSV",
                data=product_df.to_csv(index=False).encode("utf-8"),
                file_name="secureview_product_summary.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with st.expander("View filtered raw sales records"):
            st.dataframe(
                sales_df,
                use_container_width=True,
                hide_index=True,
            )


# --------------------------------------------------
# EMPLOYEE ANALYTICS
# --------------------------------------------------
elif page == "Employee Analytics":
    st.header("📊 Employee Analytics")
    st.write(
        "Compare employee counts using the department views "
        "available to the application's service account."
    )

    with st.spinner("Loading department statistics..."):
        counts_df = get_department_counts(client)

    accessible_df = counts_df[
        counts_df["Status"] == "Accessible"
    ].copy()

    total_employees = int(accessible_df["Employees"].sum())
    accessible_departments = len(accessible_df)
    inaccessible_departments = len(counts_df) - accessible_departments

    col1, col2, col3 = st.columns(3)
    col1.metric("Employees in accessible views", total_employees)
    col2.metric("Accessible departments", accessible_departments)
    col3.metric("Inaccessible departments", inaccessible_departments)

    st.divider()
    st.subheader("Department-wise Employee Count")

    if not accessible_df.empty:
        st.bar_chart(
            accessible_df.set_index("Department")[["Employees"]]
        )

        st.subheader("Department Distribution")
        pie_df = accessible_df[["Department", "Employees"]]

        st.vega_lite_chart(
            pie_df,
            {
                "mark": {"type": "arc", "outerRadius": 130},
                "encoding": {
                    "theta": {
                        "field": "Employees",
                        "type": "quantitative",
                    },
                    "color": {
                        "field": "Department",
                        "type": "nominal",
                    },
                    "tooltip": [
                        {"field": "Department", "type": "nominal"},
                        {"field": "Employees", "type": "quantitative"},
                    ],
                },
                "width": "container",
                "height": 300,
            },
            use_container_width=True,
        )
    else:
        st.warning("No department views could be queried.")

    st.subheader("Department Access Summary")
    st.dataframe(counts_df, use_container_width=True, hide_index=True)

    st.info(
        "These totals reflect views accessible to the app's service "
        "account. They do not establish which departments an individual "
        "user is authorized to access."
    )


# --------------------------------------------------
# DEPARTMENT RECORDS
# --------------------------------------------------
elif page == "Department Records":
    st.header("👥 Department Employee Records")

    department = st.selectbox(
        "Choose a department view",
        list(VIEWS.keys()),
    )

    st.info(
        "The selector chooses a view; it does not grant or restrict "
        "permissions for individual users."
    )

    try:
        with st.spinner(f"Loading {department} records..."):
            employees_df = load_employees(client, VIEWS[department])

        st.success(f"Query succeeded for the {department} view.")

        col1, col2 = st.columns(2)
        col1.metric("Selected department", department)
        col2.metric("Visible employees", len(employees_df))

        st.dataframe(
            employees_df,
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "Only the columns selected by this query are displayed."
        )

    except Forbidden:
        st.error(
            f"Access denied: the application's identity cannot query "
            f"the {department} view."
        )
    except GoogleAPICallError:
        st.error("BigQuery could not complete the employee query.")
    except Exception:
        st.error("Unable to load department records. Check the app logs.")


# --------------------------------------------------
# SECURITY ANALYSIS
# --------------------------------------------------
elif page == "Security Analysis":
    st.header("🛡️ Security Analysis")

    st.write(
        "Run permission checks using the application's actual "
        "Google Cloud service-account identity."
    )

    st.warning(
        "These checks test the app identity, not a signed-in employee. "
        "Individual-user authorization requires verified sign-in and "
        "server-side authorization rules."
    )

    st.subheader("1. Department View Access")

    with st.spinner("Checking department views..."):
        security_df = get_department_counts(client)

    st.dataframe(
        security_df[["Department", "Status"]],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("2. Private Source Table Access")

    if st.button("Test source table permissions"):
        try:
            source_query = f"""
                SELECT employee_id
                FROM `{SOURCE_TABLE}`
                LIMIT 1
            """
            client.query(source_query).result()

            st.error(
                "The source-table query succeeded. Review the service "
                "account permissions and dataset access configuration."
            )
        except Forbidden:
            st.success(
                "Access denied as expected: the app identity cannot "
                "query the private source table directly."
            )
        except GoogleAPICallError:
            st.warning(
                "The source-table test could not complete. Check the "
                "BigQuery error and permissions before drawing a conclusion."
            )
        except Exception:
            st.warning(
                "The source-table test failed. Check the application logs."
            )

    st.subheader("3. Security Findings")

    st.write(
        "- BigQuery evaluates IAM permissions when queries execute."
    )
    st.write(
        "- Authorized views can expose approved columns without granting "
        "direct access to the underlying source table."
    )
    st.write(
        "- The employee query selects employee_id, name, department, "
        "and email; it does not request salary."
    )
    st.write(
        "- Actual successful and denied query totals require audit-log "
        "data. This dashboard does not invent event counts."
    )

    st.caption(
        "For production, use verified user identities, server-side "
        "authorization, and appropriately configured Cloud Audit Logs."
    )
