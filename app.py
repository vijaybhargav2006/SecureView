
import streamlit as st
from google.cloud import bigquery
from google.auth.exceptions import DefaultCredentialsError
from google.api_core.exceptions import Forbidden, GoogleAPICallError

st.set_page_config(
    page_title="SecureView | BigQuery Access Control",
    page_icon="🔐",
    layout="wide",
)

st.title("🔐 SecureView")
st.subheader("BigQuery Authorized Views & Department Access")
st.caption("Hackathon project · Least-privilege data access")

PROJECT_ID = "bigquery-row-access"

VIEWS = {
    "IT": f"{PROJECT_ID}.student_views.it_employees",
    "HR": f"{PROJECT_ID}.student_views.hr_employees",
    "Finance": f"{PROJECT_ID}.student_views.finance_employees",
}

with st.sidebar:
    st.header("Access Dashboard")
    department = st.selectbox("Choose a department to request", list(VIEWS))
    st.info(
        "BigQuery IAM enforces access. Choosing a department here "
        "does not grant permission to its data."
    )

@st.cache_resource
def get_client():
    return bigquery.Client(project=PROJECT_ID)

try:
    client = get_client()
    view_name = VIEWS[department]

    query = f"""
        SELECT employee_id, name, department, email
        FROM `{view_name}`
        ORDER BY employee_id
    """

    df = client.query(query).to_dataframe()

    st.success(f"Access granted: {department}")
    col1, col2 = st.columns(2)
    col1.metric("Authorized department", department)
    col2.metric("Visible employees", len(df))

    st.subheader(f"{department} Employee Records")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Security Controls")
    st.write("✅ BigQuery IAM checks permissions when the query runs.")
    st.write("✅ The view exposes only approved columns.")
    st.write("✅ Unauthorized department queries are rejected by BigQuery.")

except DefaultCredentialsError:
    st.error("Google Cloud credentials are not configured.")
    st.code("gcloud auth application-default login", language="bash")

except Forbidden:
    st.error(f"Access denied: your Google Cloud identity cannot read the {department} view.")
    st.info("Ask your administrator for access if this department is part of your role.")

except GoogleAPICallError as exc:
    st.error("BigQuery could not complete the request.")
    st.caption(str(exc))

except Exception as exc:
    st.error("Could not load the department view.")
    st.caption(str(exc))
