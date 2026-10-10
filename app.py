
import streamlit as st
import pandas as pd

from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery
from google.oauth2 import service_account
from google.api_core.exceptions import Forbidden, GoogleAPICallError


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(
    page_title="SecureView | Analytics & Security",
    page_icon="🔐",
    layout="wide",
)

PROJECT_ID = "bigquery-row-access"
SOURCE_TABLE = f"{PROJECT_ID}.student_private.employees"

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
    """Count rows only in views the app identity can access."""
    results = []

    for department_name, view_name in VIEWS.items():
        try:
            query = f"SELECT COUNT(*) AS total FROM `{view_name}`"
            count_df = client.query(query).to_dataframe()

            results.append({
                "Department": department_name,
                "Employees": int(count_df.iloc[0]["total"]),
                "Status": "Accessible",
            })

        except Forbidden:
            results.append({
                "Department": department_name,
                "Employees": None,
                "Status": "Access denied",
            })

        except GoogleAPICallError:
            results.append({
                "Department": department_name,
                "Employees": None,
                "Status": "Query error",
            })

    return pd.DataFrame(results)


# --------------------------------------------------
# HEADER
# --------------------------------------------------
st.title("🔐 SecureView")
st.subheader("BigQuery Authorized Views & Department Access")
st.caption(
    "Hackathon project · Employee Analytics · Least-Privilege Security"
)

with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "Choose a dashboard",
        [
            "Employee Analytics",
            "Department Records",
            "Security Analysis",
        ],
    )

    st.divider()
    st.caption("Google Cloud BigQuery · Authorized Views")


# --------------------------------------------------
# CONNECT
# --------------------------------------------------
try:
    client = get_client()

except (DefaultCredentialsError, KeyError, ValueError):
    st.error(
        "Google Cloud credentials could not be loaded. "
        "Check the Streamlit Secrets configuration."
    )
    st.stop()

except Exception:
    st.error("Unable to initialize the BigQuery connection.")
    st.stop()


# --------------------------------------------------
# EMPLOYEE ANALYTICS
# --------------------------------------------------
if page == "Employee Analytics":
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
        chart_df = accessible_df.set_index("Department")[["Employees"]]
        st.bar_chart(chart_df)

        st.subheader("Department Distribution")

        # Use only counts from views the app could query.
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
        "These totals reflect views accessible to the app's service account. "
        "They do not establish which departments an individual user is "
        "authorized to access."
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
        "- The app queries employee_id, name, department, and email; "
        "it does not request salary."
    )
    st.write(
        "- Successful and denied query totals require actual audit-log "
        "data; this dashboard does not invent event counts."
    )

    st.caption(
        "For a production system, use verified user identities, "
        "server-side authorization, and appropriately configured "
        "Cloud Audit Logs."
    )
