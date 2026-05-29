import re
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.repositories.clients_repository import ClientsRepository


ROOT_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT_DIR / "Logo_CA1C_COM.png"
repo = ClientsRepository(show_errors=True)
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


def inject_page_styles() -> None:
    """Unified styling aligned with the Prices module for consistent look & feel."""
    st.markdown(
        """
        <style>
            .clients-shell {
                background: linear-gradient(135deg, #fff8ed 0%, #f2dfca 100%);
                border: 1px solid rgba(166, 16, 41, 0.12);
                border-radius: 20px;
                padding: 1.1rem 1.3rem;
                margin-bottom: 1rem;
            }
            .clients-shell h3 {
                color: #34141b;
                margin: 0 0 0.25rem 0;
                font-size: 1.35rem;
            }
            .clients-shell p {
                color: #5f2c34;
                margin: 0;
                font-size: 0.92rem;
            }
            .metric-card {
                background: #fffdf8;
                border: 1px solid rgba(166, 16, 41, 0.12);
                border-radius: 16px;
                padding: 0.85rem 1rem;
                text-align: center;
            }
            .metric-label {
                color: #7f4c54;
                font-size: 0.72rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }
            .metric-value {
                color: #a61029;
                font-size: 1.65rem;
                font-weight: 800;
                line-height: 1.1;
                margin-top: 0.15rem;
            }
            .toolbar {
                background: #fffdf8;
                border: 1px solid rgba(166, 16, 41, 0.1);
                border-radius: 14px;
                padding: 0.6rem 0.9rem;
                margin-bottom: 0.75rem;
            }
            .stDataFrame { border-radius: 12px; overflow: hidden; }
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
    """Initialize all required session state keys for the Clients page (aligned with Prices pattern)."""
    if "client_form_mode" not in st.session_state:
        st.session_state.client_form_mode = "add"
    if "client_form_data" not in st.session_state:
        st.session_state.client_form_data = DEFAULT_FORM_VALUES.copy()
    if "selected_client_id" not in st.session_state:
        st.session_state.selected_client_id = None
    if "show_editor" not in st.session_state:
        st.session_state.show_editor = False
    # Legacy pagination key kept for safety but no longer used in new layout
    if "clients_current_page" not in st.session_state:
        st.session_state.clients_current_page = 1


def reset_form() -> None:
    """Reset the editor form to 'New Client' mode (Prices-style)."""
    st.session_state.client_form_mode = "add"
    st.session_state.client_form_data = DEFAULT_FORM_VALUES.copy()
    st.session_state.show_editor = True


def load_client_into_form(client_id: int) -> None:
    """Load existing client into the contextual editor."""
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
    st.session_state.selected_client_id = client_id
    st.session_state.show_editor = True


def clear_selection() -> None:
    st.session_state.selected_client_id = None


@st.dialog("Confirm Delete")
def confirm_delete_dialog(client_id: int, client_name: str) -> None:
    st.write(f"Are you sure you want to permanently delete **{client_name}** (ID {client_id})?")
    st.caption("This action cannot be undone.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ Yes, Delete", type="primary", use_container_width=True, key="clients_delete_confirm_yes"):
            result = repo.delete_client(client_id)
            if result["success"]:
                st.toast(result["message"])
                clear_selection()
                reset_form()
                st.session_state.show_editor = False
                st.rerun()
            else:
                st.error(result["message"])
    with c2:
        if st.button("Cancel", use_container_width=True, key="clients_delete_confirm_cancel"):
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
    """Legacy helper kept for compatibility during transition."""
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


def prepare_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean, formatted dataframe for the unified main table (Prices-style)."""
    if df.empty:
        return pd.DataFrame(columns=["ID", "Name", "DNI/CUIL", "Phone", "Email", "City", "Province"])

    display = df.copy()
    display["full_name"] = (
        display["first_name"].fillna("").astype(str).str.strip()
        + " "
        + display["last_name"].fillna("").astype(str).str.strip()
    ).str.strip()

    display = display[["id", "full_name", "dni_cuil", "phone", "email", "city", "province"]].copy()
    display = display.rename(
        columns={
            "id": "ID",
            "full_name": "Name",
            "dni_cuil": "DNI/CUIL",
            "phone": "Phone",
            "email": "Email",
            "city": "City",
            "province": "Province",
        }
    )
    # Clean empties for display
    for col in ["Phone", "Email", "DNI/CUIL"]:
        display[col] = display[col].fillna("").astype(str).replace({"": "—"})
    return display[["ID", "Name", "DNI/CUIL", "Phone", "Email", "City", "Province"]]


def get_selected_client_record(client_id: int | None) -> dict | None:
    if not client_id:
        return None
    return repo.get_client_by_id(client_id)


def get_clients_data(search_term: str) -> pd.DataFrame:
    if search_term.strip():
        return repo.search_clients(search_term)
    return repo.get_all_clients()


def render_header() -> None:
    st.title("👥 Clients Management")
    st.caption("Search, review, add, update, and remove clients from the CA1C system.")


def render_toolbar(search_term: str) -> str:
    """Clean top bar with search + primary actions (unified Prices pattern)."""
    with st.container(border=True):
        cols = st.columns([3.2, 1.1, 1.1, 1.1])

        with cols[0]:
            new_search = st.text_input(
                "Search clients",
                value=search_term,
                placeholder="Search by name, DNI/CUIL, email, phone, city...",
                key="client_search_input",
                label_visibility="collapsed",
            )

        with cols[1]:
            if st.button("➕ New Client", use_container_width=True, type="primary", key="clients_toolbar_new_btn"):
                reset_form()
                st.rerun()

        with cols[2]:
            if st.button("⟳ Refresh", use_container_width=True, type="secondary", key="clients_toolbar_refresh_btn"):
                clear_selection()
                st.rerun()

        with cols[3]:
            if st.button("📋 Export CSV", use_container_width=True, disabled=True, help="Coming soon", key="clients_toolbar_export_btn"):
                pass

    return new_search


def render_metrics(df: pd.DataFrame) -> None:
    """Four clean metric cards (unified style)."""
    total = len(df)
    with_email = int(df[df["email"].notna() & (df["email"] != "")].shape[0]) if not df.empty else 0
    with_phone = int(df[df["phone"].notna() & (df["phone"] != "")].shape[0]) if not df.empty else 0
    provinces = df["province"].nunique() if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Total Clients</div>'
            f'<div class="metric-value">{total}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">With Email</div>'
            f'<div class="metric-value">{with_email}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">With Phone</div>'
            f'<div class="metric-value">{with_phone}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Provinces</div>'
            f'<div class="metric-value">{provinces}</div></div>',
            unsafe_allow_html=True,
        )


def render_main_table(df: pd.DataFrame) -> pd.DataFrame:
    """Render the single clean main table (Prices-style)."""
    st.subheader("Client Directory")

    display_df = prepare_display_dataframe(df)

    if display_df.empty:
        st.info("No clients yet. Click **New Client** above to get started.")
        return df

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=380,
        column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "Name": st.column_config.TextColumn(width="medium"),
            "DNI/CUIL": st.column_config.TextColumn(width="small"),
            "Phone": st.column_config.TextColumn(width="small"),
            "Email": st.column_config.TextColumn(width="medium"),
        },
    )

    return df


def render_selection_and_actions(df: pd.DataFrame) -> int | None:
    """Selection control + action buttons row. Returns the currently selected ID."""
    if df.empty:
        return None

    # Build nice options for the selector
    options = ["— Select a client —"]
    id_map = {}

    for _, row in df.iterrows():
        name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip() or "Unnamed"
        label = f"#{int(row['id'])} — {name} ({row.get('city', '') or '—'})"
        options.append(label)
        id_map[label] = int(row["id"])

    # Pre-select if we have something in state
    current_id = st.session_state.selected_client_id
    current_label = next((k for k, v in id_map.items() if v == current_id), options[0])

    selected_label = st.selectbox(
        "Selected Client for Actions",
        options=options,
        index=options.index(current_label) if current_label in options else 0,
        key="clients_selection_selectbox",
    )

    selected_id = id_map.get(selected_label)

    if selected_id != st.session_state.selected_client_id:
        st.session_state.selected_client_id = selected_id

    # Action buttons (exact same pattern as Prices)
    st.markdown("**Actions**")
    btn_cols = st.columns([1.2, 1.2, 1.2, 1.2, 2])

    with btn_cols[0]:
        if st.button("➕ New Client", use_container_width=True, type="primary", key="clients_actions_new_btn"):
            reset_form()
            st.rerun()

    with btn_cols[1]:
        disabled = selected_id is None
        if st.button("✏️ Edit Selected", use_container_width=True, disabled=disabled, key="clients_actions_edit_btn"):
            if selected_id:
                load_client_into_form(selected_id)
                st.rerun()

    with btn_cols[2]:
        disabled = selected_id is None
        if st.button("🗑️ Delete Selected", use_container_width=True, disabled=disabled, key="clients_actions_delete_btn"):
            if selected_id:
                client_row = df[df["id"] == selected_id].iloc[0]
                client_name = f"{client_row.get('first_name', '')} {client_row.get('last_name', '')}".strip() or f"Client #{selected_id}"
                confirm_delete_dialog(selected_id, client_name)

    with btn_cols[3]:
        if st.button("⟳ Refresh Table", use_container_width=True, key="clients_actions_refresh_btn"):
            st.rerun()

    with btn_cols[4]:
        st.caption("Tip: Select a client above, then use Edit or Delete. Use the search box in the toolbar.")

    return selected_id


def render_client_editor() -> None:
    """Contextual editor in expander (Prices-style unified pattern)."""
    is_editing = st.session_state.client_form_mode == "edit"
    form_data = st.session_state.client_form_data

    if not st.session_state.show_editor:
        with st.expander("📝 Client Editor", expanded=False):
            st.info("Click **New Client** or **Edit Selected** above to open the editor.")
        return

    title = "Edit Client" if is_editing else "Add New Client"

    with st.expander(f"📝 {title}", expanded=True):
        with st.form("client_editor_form", clear_on_submit=False):
            st.markdown(f"**{title}**")

            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input("First Name *", value=str(form_data.get("first_name", "")), key="clients_editor_first_name")
                last_name = st.text_input("Last Name *", value=str(form_data.get("last_name", "")), key="clients_editor_last_name")
                dni_cuil = st.text_input("DNI/CUIL", value=str(form_data.get("dni_cuil", "")), key="clients_editor_dni")
                phone = st.text_input("Phone", value=str(form_data.get("phone", "")), key="clients_editor_phone")
                email = st.text_input("Email", value=str(form_data.get("email", "")), key="clients_editor_email")
            with col2:
                street = st.text_input("Street", value=str(form_data.get("street", "")), key="clients_editor_street")
                street_number = st.text_input("Street Number", value=str(form_data.get("street_number", "")), key="clients_editor_street_number")
                floor_apt = st.text_input("Floor / Apt", value=str(form_data.get("floor_apt", "")), key="clients_editor_floor")
                neighborhood = st.text_input("Neighborhood", value=str(form_data.get("neighborhood", "")), key="clients_editor_neighborhood")
                city = st.text_input("City *", value=str(form_data.get("city", "")), key="clients_editor_city")
                province = st.text_input("Province *", value=str(form_data.get("province", "")), key="clients_editor_province")
                country = st.text_input("Country", value=str(form_data.get("country", "Argentina")), key="clients_editor_country")
                zip_code = st.text_input("ZIP Code", value=str(form_data.get("zip_code", "")), key="clients_editor_zip")

            st.caption("Fields marked with * are required.")

            submitted = st.form_submit_button(
                "💾 Save Changes" if is_editing else "➕ Add Client",
                use_container_width=True,
                type="primary",
                key="clients_editor_save_submit",
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
                    if is_editing and form_data.get("id"):
                        result = repo.update_client(int(form_data["id"]), payload)
                    else:
                        result = repo.add_client(payload)

                    if result["success"]:
                        st.toast(result["message"])
                        st.success(result["message"])
                        reset_form()
                        st.session_state.show_editor = False
                        clear_selection()
                        st.rerun()
                    else:
                        st.error(result["message"])

        # Bottom controls inside expander (consistent with Prices)
        ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 2])
        with ctrl1:
            if st.button("Clear Form", use_container_width=True, key="clients_editor_clear_btn"):
                reset_form()
                st.rerun()
        with ctrl2:
            if st.button("Close Editor", use_container_width=True, key="clients_editor_close_btn"):
                st.session_state.show_editor = False
                st.rerun()


inject_page_styles()
ensure_session_state()
repo.ensure_tables_exist()

render_header()

# Initial load (search will be read from the toolbar widget via its key)
clients_df = get_clients_data("")

render_toolbar("")  # The text_input inside manages its own key="client_search_input"

# Read live search value from session_state (set by the widget)
current_search = st.session_state.get("client_search_input", "")
if current_search:
    clients_df = get_clients_data(current_search)

render_metrics(clients_df)
st.divider()

clients_df = render_main_table(clients_df)
st.write("")

selected_id = render_selection_and_actions(clients_df)

st.divider()
render_client_editor()

# Footer
st.page_link("views/1_home.py", label="← Back to Home", icon="🏠")
