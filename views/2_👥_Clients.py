import math
import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.repositories.clients_repository import ClientsRepository


ROOT_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT_DIR / "Logo_CA1C_COM.png"
repo = ClientsRepository(show_errors=True)
CLIENTS_PAGE_SIZE = 10
EMAIL_REGEX = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
DNI_REGEX = r"(^\d{7}$)|(^\d{8}$)"
PHONE_REGEX = r"^[0-9+()\-\s]{6,20}$"


DEFAULT_FORM_VALUES = {
    "id": None,
    "first_name": "",
    "last_name": "",
    "dni_cuil": "",
    "phone": "",
    "email": "",
    "street": "",
    "street_number": "",
    "floor_apt": "",
    "neighborhood": "",
    "city": "",
    "province": "",
    "country": "Argentina",
    "zip_code": "",
}


DISPLAY_COLUMNS = {
    "id": "ID",
    "full_name": "Name",
    "dni_cuil": "DNI/CUIL",
    "phone": "Phone",
    "email": "Email",
    "full_address": "Address",
    "city": "City",
    "province": "Province",
}


st.title("👥 Clients Management")
st.caption("Search, review, add, update, and remove clients from the CA1C system.")


def inject_page_styles() -> None:
    """Keep the page styling aligned with the dashboard palette."""
    st.markdown(
        """
        <style>
            .clients-shell {
                background: linear-gradient(135deg, #fff8ed 0%, #f2dfca 100%);
                border: 1px solid rgba(166, 16, 41, 0.12);
                border-radius: 24px;
                padding: 1.25rem 1.35rem;
                margin-bottom: 1rem;
            }

            .clients-shell h3 {
                color: #34141b;
                margin-bottom: 0.25rem;
            }

            .clients-shell p {
                color: #5f2c34;
                margin-bottom: 0;
            }

            .mini-stat {
                background: #fffdf8;
                border: 1px solid rgba(166, 16, 41, 0.12);
                border-radius: 18px;
                padding: 1rem;
                margin-bottom: 0.9rem;
            }

            .mini-stat-label {
                color: #7f4c54;
                font-size: 0.82rem;
                font-weight: 700;
                letter-spacing: 0.06em;
                text-transform: uppercase;
            }

            .mini-stat-value {
                color: #a61029;
                font-size: 1.6rem;
                font-weight: 800;
                margin-top: 0.3rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_session_state() -> None:
    if "client_form_mode" not in st.session_state:
        st.session_state.client_form_mode = "add"
    if "client_form_data" not in st.session_state:
        st.session_state.client_form_data = DEFAULT_FORM_VALUES.copy()
    if "clients_current_page" not in st.session_state:
        st.session_state.clients_current_page = 1


def reset_form() -> None:
    st.session_state.client_form_mode = "add"
    st.session_state.client_form_data = DEFAULT_FORM_VALUES.copy()


def load_client_into_form(client_id: int) -> None:
    client = repo.get_client_by_id(client_id)
    if not client:
        st.error(f"Client {client_id} could not be loaded.")
        return

    form_data = DEFAULT_FORM_VALUES.copy()
    form_data.update(client)
    for key, value in form_data.items():
        if value is None:
            form_data[key] = ""
    st.session_state.client_form_mode = "edit"
    st.session_state.client_form_data = form_data


@st.dialog("Confirm Delete")
def confirm_delete_dialog(client_id: int, client_name: str) -> None:
    st.write(f"Delete client **{client_name}** (ID {client_id})?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Delete", key=f"confirm_delete_{client_id}", use_container_width=True):
            result = repo.delete_client(client_id)
            if result["success"]:
                st.toast(result["message"])
                st.success(result["message"])
                reset_form()
                st.rerun()
            st.error(result["message"])
    with col2:
        if st.button("Cancel", key=f"cancel_delete_{client_id}", use_container_width=True):
            st.rerun()


def validate_client_data(client_data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    first_name = str(client_data.get("first_name", "")).strip()
    last_name = str(client_data.get("last_name", "")).strip()
    dni_cuil = str(client_data.get("dni_cuil", "")).strip()
    email = str(client_data.get("email", "")).strip()
    phone = str(client_data.get("phone", "")).strip()
    city = str(client_data.get("city", "")).strip()
    province = str(client_data.get("province", "")).strip()

    if not first_name:
        errors.append("First name is required.")
    if not last_name:
        errors.append("Last name is required.")
    if dni_cuil and not re.fullmatch(DNI_REGEX, dni_cuil):
        errors.append("DNI/CUIL must contain 7 or 8 digits.")
    if email and not re.fullmatch(EMAIL_REGEX, email):
        errors.append("Email format is not valid.")
    if phone and not re.fullmatch(PHONE_REGEX, phone):
        errors.append("Phone contains invalid characters or length.")
    if not city:
        errors.append("City is required.")
    if not province:
        errors.append("Province is required.")

    return errors


def build_client_payload(form_values: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in DEFAULT_FORM_VALUES:
        if key == "id":
            continue
        value = form_values.get(key, "")
        payload[key] = value.strip() if isinstance(value, str) else value
    return payload


def prepare_clients_frame(clients_df: pd.DataFrame) -> pd.DataFrame:
    if clients_df.empty:
        return pd.DataFrame(columns=DISPLAY_COLUMNS.values())

    display_df = clients_df.copy()
    display_df["full_name"] = (
        display_df["first_name"].fillna("").astype(str).str.strip()
        + " "
        + display_df["last_name"].fillna("").astype(str).str.strip()
    ).str.strip()

    display_df["full_address"] = (
        display_df["street"].fillna("").astype(str).str.strip()
        + " "
        + display_df["street_number"].fillna("").astype(str).str.strip()
        + " "
        + display_df["floor_apt"].fillna("").astype(str).str.strip()
    ).str.replace(r"\s+", " ", regex=True).str.strip()

    display_df = display_df[list(DISPLAY_COLUMNS.keys())]
    return display_df.rename(columns=DISPLAY_COLUMNS)


def get_clients_data(search_term: str) -> pd.DataFrame:
    if search_term.strip():
        return repo.search_clients(search_term)
    return repo.get_all_clients()


def render_clients_table(clients_df: pd.DataFrame) -> None:
    total_rows = len(clients_df)
    total_pages = max(1, math.ceil(total_rows / CLIENTS_PAGE_SIZE))
    current_page = min(st.session_state.clients_current_page, total_pages)
    current_page = max(1, current_page)
    st.session_state.clients_current_page = current_page

    start = (current_page - 1) * CLIENTS_PAGE_SIZE
    end = start + CLIENTS_PAGE_SIZE
    page_df = clients_df.iloc[start:end].copy()
    display_df = prepare_clients_frame(page_df)

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=420)

    nav_col1, nav_col2, nav_col3 = st.columns([1, 1.6, 1])
    with nav_col1:
        if st.button("Previous", disabled=current_page == 1, use_container_width=True):
            st.session_state.clients_current_page = current_page - 1
            st.rerun()
    with nav_col2:
        st.caption(f"Page {current_page} of {total_pages} | Showing {len(page_df)} of {total_rows} client(s)")
    with nav_col3:
        if st.button("Next", disabled=current_page >= total_pages, use_container_width=True):
            st.session_state.clients_current_page = current_page + 1
            st.rerun()

    st.subheader("Row Actions")
    if page_df.empty:
        st.info("No clients to display yet.")
        return

    for row in page_df.to_dict(orient="records"):
        client_id = row.get("id")
        client_name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or f"Client {client_id}"
        summary_col, edit_col, delete_col = st.columns([5, 1, 1])
        with summary_col:
            st.write(f"**{client_name}**")
            st.caption(f"ID {client_id} | {row.get('email', '') or 'No email'} | {row.get('phone', '') or 'No phone'}")
        with edit_col:
            if st.button("Edit", key=f"edit_client_{client_id}", use_container_width=True):
                load_client_into_form(int(client_id))
                st.rerun()
        with delete_col:
            if st.button("Delete", key=f"delete_client_{client_id}", use_container_width=True):
                confirm_delete_dialog(int(client_id), client_name)


def render_client_form() -> None:
    form_mode = st.session_state.client_form_mode
    form_data = st.session_state.client_form_data
    is_editing = form_mode == "edit"

    st.markdown(
        f"""
        <div class="mini-stat">
            <div class="mini-stat-label">Form Mode</div>
            <div class="mini-stat-value">{'Edit' if is_editing else 'Add'}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("client_form", clear_on_submit=False):
        st.subheader("Add New Client" if not is_editing else "Edit Client")

        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First Name", value=str(form_data.get("first_name", "")))
            dni_cuil = st.text_input("DNI/CUIL", value=str(form_data.get("dni_cuil", "")))
            email = st.text_input("Email", value=str(form_data.get("email", "")))
            street = st.text_input("Street", value=str(form_data.get("street", "")))
            floor_apt = st.text_input("Floor / Apt", value=str(form_data.get("floor_apt", "")))
            city = st.text_input("City", value=str(form_data.get("city", "")))
            zip_code = st.text_input("ZIP Code", value=str(form_data.get("zip_code", "")))
        with col2:
            last_name = st.text_input("Last Name", value=str(form_data.get("last_name", "")))
            phone = st.text_input("Phone", value=str(form_data.get("phone", "")))
            street_number = st.text_input("Street Number", value=str(form_data.get("street_number", "")))
            neighborhood = st.text_input("Neighborhood", value=str(form_data.get("neighborhood", "")))
            province = st.text_input("Province", value=str(form_data.get("province", "")))
            country = st.text_input("Country", value=str(form_data.get("country", "")))

        submitted = st.form_submit_button(
            "Update Client" if is_editing else "Add Client",
            use_container_width=True,
            type="primary",
        )

        if submitted:
            payload = build_client_payload(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "dni_cuil": dni_cuil,
                    "phone": phone,
                    "email": email,
                    "street": street,
                    "street_number": street_number,
                    "floor_apt": floor_apt,
                    "neighborhood": neighborhood,
                    "city": city,
                    "province": province,
                    "country": country,
                    "zip_code": zip_code,
                }
            )
            validation_errors = validate_client_data(payload)
            if validation_errors:
                for error in validation_errors:
                    st.error(error)
            else:
                if is_editing:
                    result = repo.update_client(int(form_data["id"]), payload)
                else:
                    result = repo.add_client(payload)

                if result["success"]:
                    st.toast(result["message"])
                    st.success(result["message"])
                    reset_form()
                    st.rerun()
                else:
                    st.error(result["message"])

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("New Blank Form", use_container_width=True):
            reset_form()
            st.rerun()
    with action_col2:
        if st.button("Refresh Data", use_container_width=True):
            st.rerun()


inject_page_styles()
ensure_session_state()

st.markdown(
    """
    <div class="clients-shell">
        <h3>Client Directory</h3>
        <p>Use the search box to filter records, then edit or delete directly from the current page.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

search_col, stats_col = st.columns([2.2, 1])
with search_col:
    search_term = st.text_input(
        "Search clients",
        placeholder="Search by name, DNI/CUIL, email, phone, city, or province...",
    )
with stats_col:
    st.markdown(
        f"""
        <div class="mini-stat">
            <div class="mini-stat-label">Total Clients</div>
            <div class="mini-stat-value">{repo.get_client_count()}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

clients_df = get_clients_data(search_term)

main_col, form_col = st.columns([1.7, 1], gap="large")

with main_col:
    render_clients_table(clients_df)

with form_col:
    render_client_form()

st.page_link("views/1_🏠_Home.py", label="Back to Home", icon="🏠")
