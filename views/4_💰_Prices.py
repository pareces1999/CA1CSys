from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.repositories.prices_repository import PricesRepository


ROOT_DIR = Path(__file__).resolve().parent.parent
prices_repo = PricesRepository(show_errors=True)


DEFAULT_FORM_VALUES = {
    "id": None,
    "product_name": "",
    "description": "",
    "price_per_kg": 0.0,
    "price_per_unit": 0.0,
    "unit": "kg",
    "category": "General",
    "notes": "",
    "active": True,
}
UNIT_OPTIONS = ["kg", "unit", "box", "combo"]
CATEGORY_OPTIONS = ["General", "Beef", "Chicken", "Pork", "Combo", "Special"]


st.title("💰 Price Manager")
st.caption("Manage product prices, maintain active catalog entries, and prepare the next step for real order pricing.")


def inject_page_styles() -> None:
    st.markdown(
        """
        <style>
            .prices-shell {
                background: linear-gradient(135deg, #fff8ed 0%, #f2dfca 100%);
                border: 1px solid rgba(166, 16, 41, 0.12);
                border-radius: 24px;
                padding: 1.25rem 1.35rem;
                margin-bottom: 1rem;
            }

            .prices-shell h3 {
                color: #34141b;
                margin-bottom: 0.25rem;
            }

            .prices-shell p {
                color: #5f2c34;
                margin-bottom: 0;
            }

            .summary-card {
                background: #fffdf8;
                border: 1px solid rgba(166, 16, 41, 0.12);
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(52, 20, 27, 0.06);
                padding: 1rem 1.15rem;
                margin-bottom: 1rem;
            }

            .summary-label {
                color: #7f4c54;
                font-size: 0.82rem;
                font-weight: 700;
                letter-spacing: 0.06em;
                text-transform: uppercase;
            }

            .summary-value {
                color: #a61029;
                font-size: 1.55rem;
                font-weight: 800;
                margin-top: 0.3rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_session_state() -> None:
    if "price_form_mode" not in st.session_state:
        st.session_state.price_form_mode = "add"
    if "price_form_data" not in st.session_state:
        st.session_state.price_form_data = DEFAULT_FORM_VALUES.copy()


def reset_form() -> None:
    st.session_state.price_form_mode = "add"
    st.session_state.price_form_data = DEFAULT_FORM_VALUES.copy()


def load_price_into_form(price_id: int) -> None:
    price = prices_repo.get_price_by_id(price_id)
    if not price:
        st.error(f"Price entry {price_id} could not be loaded.")
        return

    form_data = DEFAULT_FORM_VALUES.copy()
    form_data.update(price)
    form_data["active"] = bool(form_data.get("active", 1))
    st.session_state.price_form_mode = "edit"
    st.session_state.price_form_data = form_data


@st.dialog("Confirm Delete")
def confirm_delete_dialog(price_id: int, product_name: str) -> None:
    st.write(f"Delete **{product_name}** from the price table?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Delete", key=f"confirm_delete_price_{price_id}", use_container_width=True):
            result = prices_repo.delete_price(price_id)
            if result["success"]:
                st.toast(result["message"])
                st.success(result["message"])
                reset_form()
                st.rerun()
            st.error(result["message"])
    with col2:
        if st.button("Cancel", key=f"cancel_delete_price_{price_id}", use_container_width=True):
            st.rerun()


def validate_price_data(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(payload.get("product_name", "")).strip():
        errors.append("Product name is required.")
    if float(payload.get("price_per_kg", 0) or 0) < 0:
        errors.append("Price per kg cannot be negative.")
    if float(payload.get("price_per_unit", 0) or 0) < 0:
        errors.append("Price per unit cannot be negative.")
    if not payload.get("unit"):
        errors.append("A unit must be selected.")
    return errors


def build_payload(form_values: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_name": str(form_values.get("product_name", "")).strip(),
        "description": str(form_values.get("description", "")).strip(),
        "price_per_kg": float(form_values.get("price_per_kg", 0) or 0),
        "price_per_unit": float(form_values.get("price_per_unit", 0) or 0),
        "unit": str(form_values.get("unit", "kg")),
        "category": str(form_values.get("category", "General")),
        "notes": str(form_values.get("notes", "")).strip(),
        "active": bool(form_values.get("active", True)),
    }


def prepare_prices_frame(prices_df: pd.DataFrame) -> pd.DataFrame:
    if prices_df.empty:
        return pd.DataFrame(columns=["ID", "Product", "Category", "Unit", "Price / KG", "Price / Unit", "Active", "Created"])

    display_df = prices_df[["id", "product_name", "category", "unit", "price_per_kg", "price_per_unit", "active", "created_at"]].copy()
    display_df["active"] = display_df["active"].apply(lambda value: "Yes" if int(value) == 1 else "No")
    return display_df.rename(
        columns={
            "id": "ID",
            "product_name": "Product",
            "category": "Category",
            "unit": "Unit",
            "price_per_kg": "Price / KG",
            "price_per_unit": "Price / Unit",
            "active": "Active",
            "created_at": "Created",
        }
    )


def render_summary_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="summary-card">
            <div class="summary-label">{label}</div>
            <div class="summary-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_form() -> None:
    form_data = st.session_state.price_form_data
    is_editing = st.session_state.price_form_mode == "edit"

    render_summary_card("Form Mode", "Edit" if is_editing else "Add")

    with st.form("price_form", clear_on_submit=False):
        st.subheader("Add / Edit Product")
        product_name = st.text_input("Product Name", value=str(form_data.get("product_name", "")))
        description = st.text_input("Description", value=str(form_data.get("description", "")))

        col1, col2 = st.columns(2)
        with col1:
            price_per_kg = st.number_input("Price per KG", min_value=0.0, value=float(form_data.get("price_per_kg", 0) or 0), step=100.0)
            unit_index = UNIT_OPTIONS.index(form_data.get("unit", "kg")) if form_data.get("unit", "kg") in UNIT_OPTIONS else 0
            unit = st.selectbox("Unit", options=UNIT_OPTIONS, index=unit_index)
            active = st.checkbox("Active", value=bool(form_data.get("active", True)))
        with col2:
            price_per_unit = st.number_input("Price per Unit", min_value=0.0, value=float(form_data.get("price_per_unit", 0) or 0), step=100.0)
            category_index = CATEGORY_OPTIONS.index(form_data.get("category", "General")) if form_data.get("category", "General") in CATEGORY_OPTIONS else 0
            category = st.selectbox("Category", options=CATEGORY_OPTIONS, index=category_index)

        notes = st.text_area("Notes", value=str(form_data.get("notes", "")), placeholder="Optional notes for promotions, supplier references, or packing details.")

        submitted = st.form_submit_button("Update Product" if is_editing else "Add Product", use_container_width=True, type="primary")
        if submitted:
            payload = build_payload(
                {
                    "product_name": product_name,
                    "description": description,
                    "price_per_kg": price_per_kg,
                    "price_per_unit": price_per_unit,
                    "unit": unit,
                    "category": category,
                    "notes": notes,
                    "active": active,
                }
            )
            errors = validate_price_data(payload)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                if is_editing:
                    result = prices_repo.update_price(int(form_data["id"]), payload)
                else:
                    result = prices_repo.add_price(payload)

                if result["success"]:
                    st.toast(result["message"])
                    st.success(result["message"])
                    reset_form()
                    st.rerun()
                st.error(result["message"])

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("New Blank Form", use_container_width=True):
            reset_form()
            st.rerun()
    with col_b:
        if st.button("Refresh Prices", use_container_width=True):
            st.rerun()


inject_page_styles()
ensure_session_state()
prices_repo.ensure_tables_exist()

st.markdown(
    """
    <div class="prices-shell">
        <h3>Product Pricing Workspace</h3>
        <p>Maintain the current catalog, update active prices, and prepare the next phase of real order valuation.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

search_col, summary_col = st.columns([2.3, 1])
with search_col:
    search_term = st.text_input(
        "Search products",
        placeholder="Search by product name, description, category, or notes...",
    )
with summary_col:
    render_summary_card("Active Prices", str(prices_repo.get_active_price_count()))

prices_df = prices_repo.search_prices(search_term) if search_term.strip() else prices_repo.get_all_prices()
active_count = int(prices_df[prices_df["active"] == 1].shape[0]) if not prices_df.empty else 0

price_tab, form_tab, combo_tab = st.tabs(["Price List", "Add / Edit Product", "Combos / Specials"])

with price_tab:
    st.subheader("Current Price List")
    st.caption("Use search to narrow the catalog, then edit or delete a product entry below.")
    st.dataframe(prepare_prices_frame(prices_df), use_container_width=True, hide_index=True, height=420)

    st.markdown("**Actions**")
    if prices_df.empty:
        st.info("No price entries yet. Add your first product from the form tab.")
    else:
        for row in prices_df.to_dict(orient="records"):
            product_name = row.get("product_name", "Unnamed Product")
            summary_col, edit_col, delete_col = st.columns([5, 1, 1])
            with summary_col:
                st.write(f"**{product_name}**")
                st.caption(
                    f"ID {row['id']} | {row.get('category') or 'No category'} | {row.get('unit') or 'unit'} | Active: {'Yes' if int(row.get('active', 1)) == 1 else 'No'}"
                )
            with edit_col:
                if st.button("Edit", key=f"edit_price_{row['id']}", use_container_width=True):
                    load_price_into_form(int(row["id"]))
                    st.rerun()
            with delete_col:
                if st.button("Delete", key=f"delete_price_{row['id']}", use_container_width=True):
                    confirm_delete_dialog(int(row["id"]), product_name)

with form_tab:
    render_form()

with combo_tab:
    st.subheader("Combos / Specials")
    st.info(
        "This section is reserved for the next phase, where combo pricing and special bundles will be migrated from the original combo logic."
    )
    placeholder_df = pd.DataFrame(
        [
            {
                "Combo": "Weekend Grill Box",
                "Status": "Planned",
                "Notes": "Future combo composition and special pricing workflow.",
            }
        ]
    )
    st.dataframe(placeholder_df, use_container_width=True, hide_index=True)
    st.caption(f"Current catalog entries: {len(prices_df)} | Active entries: {active_count}")

st.page_link("views/1_🏠_Home.py", label="Back to Home", icon="🏠")
