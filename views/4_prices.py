from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.repositories.prices_repository import PricesRepository


ROOT_DIR = Path(__file__).resolve().parent.parent
prices_repo = PricesRepository(show_errors=True)


# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTS & SESSION STATE
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_FORM_VALUES: dict[str, Any] = {
    "id": None,
    "product_name": "",
    "description": "",
    "price_per_kg": 0.0,
    "price_per_unit": 0.0,
    "weight_per_unit": 0.0,
    "unit": "kg",
    "category": "General",
    "notes": "",
    "active": True,
}

UNIT_OPTIONS = ["kg", "unit", "box", "combo"]
CATEGORY_OPTIONS = ["General", "Beef", "Chicken", "Pork", "Combo", "Special"]

PRICE_LIST_OPTIONS = [
    "Main Catalog (Active Draft)",
    "Future Price List 2026 (Planned)",
]


def ensure_session_state() -> None:
    """Initialize all required session state keys for the Prices page."""
    if "price_form_mode" not in st.session_state:
        st.session_state.price_form_mode = "add"
    if "price_form_data" not in st.session_state:
        st.session_state.price_form_data = DEFAULT_FORM_VALUES.copy()
    if "selected_price_id" not in st.session_state:
        st.session_state.selected_price_id = None
    if "show_editor" not in st.session_state:
        st.session_state.show_editor = False
    if "current_price_list" not in st.session_state:
        st.session_state.current_price_list = PRICE_LIST_OPTIONS[0]
    if "editor_unit" not in st.session_state:
        st.session_state.editor_unit = "kg"


def reset_form() -> None:
    """Reset the editor form to 'New Product' mode."""
    st.session_state.price_form_mode = "add"
    st.session_state.price_form_data = DEFAULT_FORM_VALUES.copy()
    st.session_state.editor_unit = "kg"
    st.session_state.show_editor = True


def load_price_into_form(price_id: int) -> None:
    """Load an existing price record into the editor form.
    Auto-adjusts values to comply with current pricing business rules.
    """
    price = prices_repo.get_price_by_id(price_id)
    if not price:
        st.error(f"Could not load price entry #{price_id}.")
        return

    form_data = DEFAULT_FORM_VALUES.copy()
    form_data.update(price)
    form_data["active"] = bool(form_data.get("active", 1))

    # Apply business rules for consistency (especially for legacy records)
    unit = str(form_data.get("unit", "kg"))
    price_kg = float(form_data.get("price_per_kg", 0) or 0)
    weight = float(form_data.get("weight_per_unit", 0) or 0)

    if unit == "kg":
        weight = 1.0
    price_unit = weight * price_kg

    form_data["unit"] = unit
    form_data["weight_per_unit"] = weight
    form_data["price_per_unit"] = price_unit

    st.session_state.price_form_mode = "edit"
    st.session_state.price_form_data = form_data
    st.session_state.editor_unit = unit
    st.session_state.selected_price_id = price_id
    st.session_state.show_editor = True


def clear_selection() -> None:
    st.session_state.selected_price_id = None


# ──────────────────────────────────────────────────────────────────────────────
# VALIDATION & PAYLOAD HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def validate_price_data(payload: dict[str, Any]) -> list[str]:
    """Validation respecting the new pricing business rules."""
    errors: list[str] = []
    unit = str(payload.get("unit", ""))

    if not str(payload.get("product_name", "")).strip():
        errors.append("Product name is required.")

    if float(payload.get("price_per_kg", 0) or 0) <= 0:
        errors.append("Price per kg must be greater than zero.")

    # Weight is only mandatory for unit/box/combo (kg forces it to 1)
    if unit in ("unit", "box", "combo"):
        if float(payload.get("weight_per_unit", 0) or 0) <= 0:
            errors.append("Weight per unit must be greater than zero for Unit, Box or Combo.")

    if not unit:
        errors.append("Unit is required.")

    if not str(payload.get("category", "")).strip():
        errors.append("Category is required.")

    return errors


def build_payload(form_values: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_name": str(form_values.get("product_name", "")).strip(),
        "description": str(form_values.get("description", "")).strip(),
        "price_per_kg": float(form_values.get("price_per_kg", 0) or 0),
        "price_per_unit": float(form_values.get("price_per_unit", 0) or 0),
        "weight_per_unit": float(form_values.get("weight_per_unit", 0) or 0),
        "unit": str(form_values.get("unit", "kg")),
        "category": str(form_values.get("category", "General")),
        "notes": str(form_values.get("notes", "")).strip(),
        "active": bool(form_values.get("active", True)),
    }


def apply_pricing_rules(unit: str, price_per_kg: float, weight_per_unit: float) -> tuple[float, float]:
    """Apply the core business rules and return the final (weight_per_unit, price_per_unit).

    Rules:
    - kg     → weight = 1.0, price_unit = 1 * price_per_kg
    - unit/box/combo → weight as provided, price_unit = weight * price_per_kg
    """
    if unit == "kg":
        weight = 1.0
    else:
        weight = float(weight_per_unit or 0)

    price_unit = weight * float(price_per_kg or 0)
    return weight, price_unit


# ──────────────────────────────────────────────────────────────────────────────
# DATA PREPARATION
# ──────────────────────────────────────────────────────────────────────────────

def prepare_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a clean, nicely formatted dataframe for display."""
    if df.empty:
        return pd.DataFrame(
            columns=["ID", "Product", "Category", "Unit", "Weight/Unit", "Price/KG", "Price/Unit", "Active"]
        )

    display = df[
        ["id", "product_name", "category", "unit", "weight_per_unit", "price_per_kg", "price_per_unit", "active"]
    ].copy()

    display["Active"] = display["active"].apply(lambda x: "✅ Active" if int(x) == 1 else "⏸️ Inactive")
    display = display.drop(columns=["active"])

    display = display.rename(
        columns={
            "id": "ID",
            "product_name": "Product",
            "category": "Category",
            "unit": "Unit",
            "weight_per_unit": "Weight/Unit",
            "price_per_kg": "Price/KG",
            "price_per_unit": "Price/Unit",
        }
    )

    # Format currency columns
    for col in ["Price/KG", "Price/Unit"]:
        display[col] = display[col].apply(lambda v: f"${float(v):,.0f}")

    display["Weight/Unit"] = display["Weight/Unit"].apply(lambda v: f"{float(v):.2f} kg")

    return display[["ID", "Product", "Category", "Unit", "Weight/Unit", "Price/KG", "Price/Unit", "Active"]]


def get_selected_price_record(price_id: int | None) -> dict | None:
    if not price_id:
        return None
    return prices_repo.get_price_by_id(price_id)


# ──────────────────────────────────────────────────────────────────────────────
# UI COMPONENTS
# ──────────────────────────────────────────────────────────────────────────────

def inject_page_styles() -> None:
    st.markdown(
        """
        <style>
            .prices-shell {
                background: linear-gradient(135deg, #fff8ed 0%, #f2dfca 100%);
                border: 1px solid rgba(166, 16, 41, 0.12);
                border-radius: 20px;
                padding: 1.1rem 1.3rem;
                margin-bottom: 1rem;
            }
            .prices-shell h3 {
                color: #34141b;
                margin: 0 0 0.25rem 0;
                font-size: 1.35rem;
            }
            .prices-shell p {
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.title("💰 Price Manager")
    st.caption("Manage the product catalog, maintain active prices, and prepare clean pricing for orders.")


def render_toolbar() -> None:
    """Clean top bar with Price List selector and primary actions."""
    with st.container(border=True):
        cols = st.columns([2.8, 1.1, 1.1, 1.1, 1.1])

        with cols[0]:
            selected_list = st.selectbox(
                "Price List",
                options=PRICE_LIST_OPTIONS,
                index=PRICE_LIST_OPTIONS.index(st.session_state.current_price_list),
                key="price_list_selector",
                label_visibility="collapsed",
            )
            if selected_list != st.session_state.current_price_list:
                st.session_state.current_price_list = selected_list
                st.rerun()

        with cols[1]:
            if st.button("➕ New Price List", use_container_width=True, disabled=True, help="Multi price list support coming soon", key="prices_toolbar_new_price_list_btn"):
                pass

        with cols[2]:
            if st.button("🚀 Activate Draft", use_container_width=True, disabled=True, help="Will publish the current draft as the live price list", key="prices_toolbar_activate_btn"):
                pass

        with cols[3]:
            if st.button("⟳ Refresh", use_container_width=True, type="secondary", key="prices_toolbar_refresh_btn"):
                # Clear any transient selection when refreshing
                clear_selection()
                st.rerun()

        with cols[4]:
            if st.button("📋 Export CSV", use_container_width=True, disabled=True, help="Export current price list (future)", key="prices_toolbar_export_btn"):
                pass


def render_metrics(df: pd.DataFrame) -> None:
    """Four clean metric cards."""
    total = len(df)
    active = int(df[df["active"] == 1].shape[0]) if not df.empty else 0
    inactive = total - active
    categories = df["category"].nunique() if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Total Products</div>'
            f'<div class="metric-value">{total}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Active Prices</div>'
            f'<div class="metric-value">{active}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Inactive</div>'
            f'<div class="metric-value">{inactive}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Categories</div>'
            f'<div class="metric-value">{categories}</div></div>',
            unsafe_allow_html=True,
        )


def render_main_table(df: pd.DataFrame) -> pd.DataFrame:
    """Render the single clean main table."""
    st.subheader("Current Price Catalog")

    display_df = prepare_display_dataframe(df)

    if display_df.empty:
        st.info("No prices in the catalog yet. Click **New Product** below to get started.")
        return df

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=380,
        column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "Product": st.column_config.TextColumn(width="medium"),
            "Price/KG": st.column_config.TextColumn(width="small"),
            "Price/Unit": st.column_config.TextColumn(width="small"),
            "Active": st.column_config.TextColumn(width="small"),
        },
    )

    return df


def render_selection_and_actions(df: pd.DataFrame) -> int | None:
    """Selection control + action buttons row. Returns the currently selected ID."""
    if df.empty:
        return None

    # Build nice options for the selector
    options = ["— Select a product —"]
    id_map = {}

    for _, row in df.iterrows():
        label = f"#{int(row['id'])} — {row['product_name']} ({row['category']})"
        options.append(label)
        id_map[label] = int(row["id"])

    # Pre-select if we have something in state
    current_id = st.session_state.selected_price_id
    current_label = next((k for k, v in id_map.items() if v == current_id), options[0])

    selected_label = st.selectbox(
        "Selected Product for Actions",
        options=options,
        index=options.index(current_label) if current_label in options else 0,
        key="prices_selection_selectbox",
    )

    selected_id = id_map.get(selected_label)

    if selected_id != st.session_state.selected_price_id:
        st.session_state.selected_price_id = selected_id

    # Action buttons
    st.markdown("**Actions**")
    btn_cols = st.columns([1.2, 1.2, 1.2, 1.2, 2])

    with btn_cols[0]:
        if st.button("➕ New Product", use_container_width=True, type="primary", key="prices_actions_new_btn"):
            reset_form()
            st.rerun()

    with btn_cols[1]:
        disabled = selected_id is None
        if st.button("✏️ Edit Selected", use_container_width=True, disabled=disabled, key="prices_actions_edit_btn"):
            if selected_id:
                load_price_into_form(selected_id)
                st.rerun()

    with btn_cols[2]:
        disabled = selected_id is None
        if st.button("🗑️ Delete Selected", use_container_width=True, disabled=disabled, key="prices_actions_delete_btn"):
            if selected_id:
                product_name = df[df["id"] == selected_id]["product_name"].iloc[0]
                confirm_delete_dialog(selected_id, product_name)

    with btn_cols[3]:
        if st.button("⟳ Refresh Table", use_container_width=True, key="prices_actions_refresh_btn"):
            st.rerun()

    with btn_cols[4]:
        st.caption("Tip: Select a row above, then use Edit or Delete.")

    return selected_id


@st.dialog("Confirm Delete")
def confirm_delete_dialog(price_id: int, product_name: str) -> None:
    st.write(f"Are you sure you want to permanently delete **{product_name}**?")
    st.caption("This action cannot be undone.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ Yes, Delete", type="primary", use_container_width=True, key="prices_delete_confirm_yes"):
            result = prices_repo.delete_price(price_id)
            if result["success"]:
                st.toast(result["message"])
                clear_selection()
                st.rerun()
            else:
                st.error(result["message"])
    with c2:
        if st.button("Cancel", use_container_width=True, key="prices_delete_confirm_cancel"):
            st.rerun()


def render_product_editor() -> None:
    """Contextual form for adding or editing a product.

    Implements the pricing business rules:
    - "kg"     → Weight locked at 1.0, Price/Unit = Price/Kg (calculated on save)
    - "unit/box/combo" → User enters Weight, Price/Unit is calculated on save
    - Price per Unit is always read-only (calculated field)
    """
    is_editing = st.session_state.price_form_mode == "edit"
    form_data = st.session_state.price_form_data

    # Only show the editor when user has triggered New or Edit
    if not st.session_state.show_editor:
        with st.expander("📝 Product Editor", expanded=False):
            st.info("Click **New Product** or **Edit Selected** above to open the editor.")
        return

    title = "Edit Product" if is_editing else "Add New Product"

    with st.expander(f"📝 {title}", expanded=True):

        # ============================================================
        # UNIT SELECTOR - Placed OUTSIDE the form for instant reactivity.
        # This solves the edit flow: when you change from "kg" to "unit",
        # the Weight field immediately becomes editable.
        # ============================================================
        with st.container(border=True):
            st.markdown("**Unit Type**")
            unit = st.selectbox(
                "Unit *",
                options=UNIT_OPTIONS,
                index=UNIT_OPTIONS.index(st.session_state.editor_unit) if st.session_state.editor_unit in UNIT_OPTIONS else 0,
                key="prices_editor_unit_selectbox",
                label_visibility="collapsed",
                help="kg = sold by the kilo (weight locked at 1). Unit/Box/Combo = sold by piece — you must enter the real weight of one item."
            )

        # React immediately when user changes the unit (critical for Edit mode)
        if unit != st.session_state.editor_unit:
            st.session_state.editor_unit = unit
            st.rerun()

        with st.form("price_editor_form", clear_on_submit=False):
            st.markdown(f"**{title}**")

            col1, col2 = st.columns(2)

            with col1:
                product_name = st.text_input(
                    "Product Name *",
                    value=form_data.get("product_name", ""),
                    placeholder="e.g. Asado, Lomo, Ojo de Bife",
                    key="prices_editor_product_name",
                )
                price_per_kg = st.number_input(
                    "Price per KG (ARS) *",
                    min_value=0.0,
                    value=float(form_data.get("price_per_kg", 0) or 0),
                    step=500.0,
                    format="%.0f",
                    key="prices_editor_price_kg",
                )

                # Weight field is controlled by the Unit selector above the form
                is_kg = (unit == "kg")
                weight_per_unit = st.number_input(
                    "Weight per Unit (kg) *",
                    min_value=0.0,
                    value=1.0 if is_kg else float(form_data.get("weight_per_unit", 0) or 0),
                    step=0.1,
                    disabled=is_kg,
                    help="For 'kg' items this is always 1. For Unit/Box/Combo enter the real weight of one piece.",
                    key="prices_editor_weight",
                )

            with col2:
                # Price per Unit is ALWAYS read-only / calculated
                current_weight = 1.0 if (unit == "kg") else float(form_data.get("weight_per_unit", 0) or 0)
                calculated_price_unit = current_weight * float(price_per_kg or 0)

                st.number_input(
                    "Price per Unit (ARS)",
                    min_value=0.0,
                    value=round(calculated_price_unit, 0),
                    step=500.0,
                    format="%.0f",
                    disabled=True,
                    help="This is a calculated field: Weight per Unit × Price per Kg",
                    key="prices_editor_price_unit_disabled",
                )
                category = st.selectbox(
                    "Category *",
                    options=CATEGORY_OPTIONS,
                    index=CATEGORY_OPTIONS.index(form_data.get("category", "General")) if form_data.get("category") in CATEGORY_OPTIONS else 0,
                    key="prices_editor_category",
                )
                active = st.checkbox("Active in current price list", value=bool(form_data.get("active", True)), key="prices_editor_active")

            description = st.text_input("Description", value=form_data.get("description", ""), key="prices_editor_description")
            notes = st.text_area(
                "Notes / Internal Comments",
                value=form_data.get("notes", ""),
                height=80,
                placeholder="Optional notes for the team (supplier, cuts, packaging, etc.)",
                key="prices_editor_notes",
            )

            # Clear explanation of the rules
            if unit == "kg":
                st.caption("**kg mode**: Weight is locked at 1 kg. Price per Unit will be set equal to Price per Kg on save.")
            else:
                st.caption("**Price per Unit** is calculated automatically as: Weight per Unit × Price per Kg (on save).")

            st.caption("Fields marked with * are required.")

            # Submit row
            submitted = st.form_submit_button(
                "💾 Save Changes" if is_editing else "➕ Add Product",
                use_container_width=True,
                type="primary",
                key="prices_editor_save_submit",
            )

            if submitted:
                # Remember the unit chosen by the user for next time the editor opens
                st.session_state.editor_unit = unit

                # === Apply business rules forcefully before saving ===
                final_weight, final_price_unit = apply_pricing_rules(
                    unit, price_per_kg, weight_per_unit
                )

                payload = build_payload(
                    {
                        "product_name": product_name,
                        "description": description,
                        "price_per_kg": price_per_kg,
                        "price_per_unit": final_price_unit,
                        "weight_per_unit": final_weight,
                        "unit": unit,
                        "category": category,
                        "notes": notes,
                        "active": active,
                    }
                )
                errors = validate_price_data(payload)

                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    if is_editing and form_data.get("id"):
                        result = prices_repo.update_price(int(form_data["id"]), payload)
                    else:
                        result = prices_repo.add_price(payload)

                    if result["success"]:
                        st.toast(result["message"])
                        st.success(result["message"])
                        reset_form()
                        st.session_state.show_editor = False
                        clear_selection()
                        st.rerun()
                    else:
                        st.error(result["message"])

        # Bottom controls inside expander
        ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 2])
        with ctrl1:
            if st.button("Clear Form", use_container_width=True, key="prices_editor_clear_btn"):
                reset_form()
                st.rerun()
        with ctrl2:
            if st.button("Close Editor", use_container_width=True, key="prices_editor_close_btn"):
                st.session_state.show_editor = False
                st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# MAIN PAGE RENDERING
# ──────────────────────────────────────────────────────────────────────────────

inject_page_styles()
ensure_session_state()
prices_repo.ensure_tables_exist()

render_header()
render_toolbar()

# Load data (respecting future price list filtering — currently all)
raw_df = prices_repo.get_all_prices()

render_metrics(raw_df)
st.divider()

raw_df = render_main_table(raw_df)
st.write("")  # small spacing

selected_id = render_selection_and_actions(raw_df)

st.divider()
render_product_editor()

# Footer
st.page_link("views/1_home.py", label="← Back to Home", icon="🏠")
