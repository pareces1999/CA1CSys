import os
import runpy
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.repositories.clients_repository import ClientsRepository
from core.repositories.orders_repository import OrdersRepository
from core.repositories.prices_repository import PricesRepository


ROOT_DIR = Path(__file__).resolve().parent.parent
KG_PER_ORDER_SCRIPT = ROOT_DIR / "kg_per_order.py"
KG_PER_PRODUCT_SCRIPT = ROOT_DIR / "kg_per_product.py"
clients_repo = ClientsRepository(show_errors=True)
orders_repo = OrdersRepository(show_errors=True)
prices_repo = PricesRepository(show_errors=True)
DEFAULT_LIST_CODE = 1
DEFAULT_ORDER_ID = 1


st.title("📦 Order Handler")
st.caption("Create a new order, preview total kilograms live, and save the order with line items.")


def inject_page_styles() -> None:
    st.markdown(
        """
        <style>
            .orders-shell {
                background: linear-gradient(135deg, #fff8ed 0%, #f2dfca 100%);
                border: 1px solid rgba(166, 16, 41, 0.12);
                border-radius: 24px;
                padding: 1.25rem 1.35rem;
                margin-bottom: 1rem;
            }

            .orders-shell h3 {
                color: #34141b;
                margin-bottom: 0.25rem;
            }

            .orders-shell p {
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


def make_default_combo_component() -> dict[str, Any]:
    return {
        "product_id": None,
        "product_name": "",
        "cantidad_en_kg": 0.0,
    }


def make_default_line_item() -> dict[str, Any]:
    return {
        "product_id": None,
        "product_name": "",
        "catalog_unit": "",
        "quantity": 1,
        "unit_kg": 1.0,
        "estimated_unit_price": 0.0,
        "line_total": 0.0,
        "is_combo": False,
        "combo_components": [],
    }


def ensure_session_state() -> None:
    if "order_line_items" not in st.session_state:
        st.session_state.order_line_items = [make_default_line_item()]
    if "selected_client_id" not in st.session_state:
        st.session_state.selected_client_id = None
    if "selected_client_label" not in st.session_state:
        st.session_state.selected_client_label = None
    if "order_notes" not in st.session_state:
        st.session_state.order_notes = ""
    if "order_form_nonce" not in st.session_state:
        st.session_state.order_form_nonce = 0


def clear_order_widget_state() -> None:
    dynamic_prefixes = (
        "product_name_",
        "quantity_",
        "unit_kg_",
        "unit_price_",
        "component_product_",
        "component_kg_",
    )
    dynamic_exact_keys = ("selected_client_label",)

    keys_to_remove = [
        key
        for key in list(st.session_state.keys())
        if key in dynamic_exact_keys or key.startswith(dynamic_prefixes)
    ]
    for key in keys_to_remove:
        st.session_state.pop(key, None)


def reset_order_form() -> None:
    clear_order_widget_state()
    st.session_state.order_line_items = [make_default_line_item()]
    st.session_state.selected_client_id = None
    st.session_state.selected_client_label = None
    st.session_state.order_notes = ""
    st.session_state.order_form_nonce += 1


def load_client_options() -> tuple[list[dict[str, Any]], dict[str, int]]:
    clients_df = clients_repo.get_all_clients()
    if clients_df.empty:
        return [], {}

    options: list[dict[str, Any]] = []
    lookup: dict[str, int] = {}
    for row in clients_df.to_dict(orient="records"):
        full_name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
        dni = row.get("dni_cuil") or "No DNI"
        label = f"{full_name or 'Unnamed Client'} - {dni}"
        options.append({"label": label, "id": int(row["id"]), "raw": row})
        lookup[label] = int(row["id"])
    return options, lookup


def get_catalog_unit_price(catalog_row: dict[str, Any]) -> float:
    unit = catalog_row.get("unit") or "unit"
    if unit == "kg" and float(catalog_row.get("price_per_kg", 0) or 0) > 0:
        return float(catalog_row.get("price_per_kg", 0) or 0)
    return float(catalog_row.get("price_per_unit", 0) or 0)


def is_combo_catalog_product(catalog_row: dict[str, Any]) -> bool:
    raw = catalog_row.get("raw", catalog_row)
    if bool(raw.get("combo", False)):
        return True
    return str(raw.get("unit", "")).lower() == "combo" or str(raw.get("category", "")).lower() == "combo"


def load_catalog_options() -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, dict[str, Any]], dict[int, dict[str, Any]]]:
    prices_df = prices_repo.get_all_prices()
    if prices_df.empty:
        return prices_df, [], {}, {}

    catalog_df = prices_df.loc[prices_df["active"] == 1].copy()
    catalog_df = catalog_df.sort_values(["product_name", "category", "id"]).reset_index(drop=True)
    if catalog_df.empty:
        return catalog_df, [], {}, {}

    options: list[dict[str, Any]] = []
    label_lookup: dict[str, dict[str, Any]] = {}
    id_lookup: dict[int, dict[str, Any]] = {}
    for row in catalog_df.to_dict(orient="records"):
        unit = row.get("unit") or "unit"
        label = f"{row.get('product_name', 'Unnamed Product')} | {row.get('category') or 'General'} | {unit.upper()}"
        option = {
            "label": label,
            "id": int(row["id"]),
            "product_name": row.get("product_name", ""),
            "unit": unit,
            "unit_price": get_catalog_unit_price(row),
            "raw": row,
            "is_combo": is_combo_catalog_product(row),
        }
        options.append(option)
        label_lookup[label] = option
        id_lookup[int(row["id"])] = option
    return catalog_df, options, label_lookup, id_lookup


def get_catalog_weight_per_unit(selected_product: dict[str, Any], current_weight: float) -> float:
    raw_product = selected_product.get("raw", {})
    explicit_weight = raw_product.get("weight_per_unit")
    if explicit_weight is None:
        explicit_weight = raw_product.get("weight_per_unit_kg")

    if explicit_weight not in (None, ""):
        return float(explicit_weight)

    if selected_product.get("unit") == "kg":
        return 1.0

    return float(current_weight or 1.0)


@contextmanager
def pushd(target_dir: Path):
    original_dir = Path.cwd()
    os.chdir(target_dir)
    try:
        yield
    finally:
        os.chdir(original_dir)


@contextmanager
def pandas_append_compat():
    original_append = getattr(pd.DataFrame, "append", None)

    if original_append is None:
        def _append_compat(self, other, ignore_index=False, verify_integrity=False, sort=False):
            if verify_integrity:
                raise NotImplementedError("verify_integrity is not supported by the compatibility shim.")
            return pd.concat([self, other], ignore_index=ignore_index, sort=sort)

        pd.DataFrame.append = _append_compat

    try:
        yield
    finally:
        if original_append is None:
            delattr(pd.DataFrame, "append")


def write_script_input_csv(target_path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(target_path, sep=";", encoding="utf-8", decimal=",", index=False)


def run_kg_script(
    script_path: Path,
    output_filename: str,
    combo_df: pd.DataFrame,
    price_df: pd.DataFrame,
    order_df: pd.DataFrame,
) -> pd.DataFrame:
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        write_script_input_csv(temp_dir / "lista_combos.csv", combo_df)
        write_script_input_csv(temp_dir / "lista_precios.csv", price_df)
        write_script_input_csv(temp_dir / "ordenes.csv", order_df)

        with pushd(temp_dir), pandas_append_compat():
            runpy.run_path(str(script_path), run_name="__main__")

        output_path = temp_dir / output_filename
        return pd.read_csv(output_path, delimiter=";", decimal=",", encoding="utf-8")


def build_script_frames(line_items: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    _, _, _, catalog_by_id = load_catalog_options()

    order_rows: list[dict[str, Any]] = []
    combo_rows: list[dict[str, Any]] = []
    involved_product_ids: set[int] = set()

    for item in line_items:
        product_id = int(item["product_id"])
        involved_product_ids.add(product_id)
        order_rows.append(
            {
                "codigo_lista": DEFAULT_LIST_CODE,
                "orden": DEFAULT_ORDER_ID,
                "cantidad_producto": int(item["quantity"]),
                "sku": product_id,
            }
        )

        if item["is_combo"]:
            for component in item["combo_components"]:
                component_id = int(component["product_id"])
                involved_product_ids.add(component_id)
                combo_rows.append(
                    {
                        "codigo_lista": DEFAULT_LIST_CODE,
                        "codigo_combo": product_id,
                        "sku": component_id,
                        "nombre_producto": component["product_name"],
                        "cantidad_en_kg": float(component["cantidad_en_kg"]),
                        "frigorifico_sin_iva": 0.0,
                        "frigorifico_con_iva": 0.0,
                        "ca1c_sin_iva": 0.0,
                        "ca1c_con_iva": 0.0,
                    }
                )

    price_rows: list[dict[str, Any]] = []
    for product_id in sorted(involved_product_ids):
        catalog_item = catalog_by_id.get(product_id)
        if not catalog_item:
            continue
        price_rows.append(
            {
                "codigo_lista": DEFAULT_LIST_CODE,
                "sku": product_id,
                "codigo_producto": str(product_id),
                "nombre_producto": catalog_item["product_name"],
                "precio_frigorifico": 0.0,
                "precio_carneaunclick": float(catalog_item["unit_price"]),
                "peso_en_kg": get_catalog_weight_per_unit(catalog_item, 1.0),
                "combo": bool(catalog_item["is_combo"]),
            }
        )

    order_df = pd.DataFrame(order_rows, columns=["codigo_lista", "orden", "cantidad_producto", "sku"])
    price_df = pd.DataFrame(
        price_rows,
        columns=[
            "codigo_lista",
            "sku",
            "codigo_producto",
            "nombre_producto",
            "precio_frigorifico",
            "precio_carneaunclick",
            "peso_en_kg",
            "combo",
        ],
    )
    combo_df = pd.DataFrame(
        combo_rows,
        columns=[
            "codigo_lista",
            "codigo_combo",
            "sku",
            "nombre_producto",
            "cantidad_en_kg",
            "frigorifico_sin_iva",
            "frigorifico_con_iva",
            "ca1c_sin_iva",
            "ca1c_con_iva",
        ],
    )
    return order_df, price_df, combo_df


def calculate_preview(line_items: list[dict[str, Any]]) -> dict[str, object]:
    valid_items: list[dict[str, Any]] = []
    validation_errors: list[str] = []

    for item_index, item in enumerate(line_items, start=1):
        product_name = str(item.get("product_name", "")).strip()
        catalog_unit = str(item.get("catalog_unit", "unit") or "unit").lower()
        quantity = int(item.get("quantity", 0) or 0)
        unit_kg = float(item.get("unit_kg", 0) or 0)
        estimated_unit_price = float(item.get("estimated_unit_price", 0) or 0)
        product_id = item.get("product_id")
        is_combo = bool(item.get("is_combo", False))

        if product_id is None or not product_name or quantity <= 0 or unit_kg < 0:
            continue

        combo_components: list[dict[str, Any]] = []
        if is_combo:
            raw_components = item.get("combo_components", [])
            for component in raw_components:
                component_id = component.get("product_id")
                component_name = str(component.get("product_name", "")).strip()
                cantidad_en_kg = float(component.get("cantidad_en_kg", 0) or 0)
                if component_id is None or not component_name or cantidad_en_kg <= 0:
                    continue
                combo_components.append(
                    {
                        "product_id": int(component_id),
                        "product_name": component_name,
                        "cantidad_en_kg": cantidad_en_kg,
                    }
                )

            if not combo_components:
                validation_errors.append(
                    f"Combo item {item_index} requires at least one component product with kilograms per combo unit."
                )

        # Monetary value follows the business rule directly:
        # - kg products treat quantity as kilograms entered by the user
        # - unit products treat quantity as pieces entered by the user
        total_kg = float(quantity) if catalog_unit == "kg" else float(quantity) * unit_kg
        line_total = float(quantity) * estimated_unit_price

        valid_items.append(
            {
                "product_id": int(product_id),
                "product_name": product_name,
                "catalog_unit": catalog_unit,
                "quantity": quantity,
                "unit_kg": unit_kg,
                "total_kg": total_kg,
                "estimated_unit_price": estimated_unit_price,
                "line_total": line_total,
                "is_combo": is_combo,
                "combo_components": combo_components,
            }
        )

    if not valid_items:
        return {
            "valid_items": [],
            "order_total_kg": 0.0,
            "line_breakdown": pd.DataFrame(),
            "estimated_total_value": 0.0,
            "validation_errors": validation_errors,
        }

    if validation_errors:
        return {
            "valid_items": valid_items,
            "order_total_kg": 0.0,
            "line_breakdown": pd.DataFrame(),
            "estimated_total_value": float(sum(item["line_total"] for item in valid_items)),
            "validation_errors": validation_errors,
        }

    try:
        order_df, price_df, combo_df = build_script_frames(valid_items)
        kg_order_df = run_kg_script(KG_PER_ORDER_SCRIPT, "kg_x_orden.csv", combo_df, price_df, order_df)
        kg_product_df = run_kg_script(KG_PER_PRODUCT_SCRIPT, "totals.csv", combo_df, price_df, order_df)
    except Exception as exc:
        return {
            "valid_items": valid_items,
            "order_total_kg": 0.0,
            "line_breakdown": pd.DataFrame(),
            "estimated_total_value": float(sum(item["line_total"] for item in valid_items)),
            "validation_errors": [f"KG calculation could not be completed with the original modules: {exc}"],
        }

    order_total_kg = float(kg_order_df["peso_de_orden"].sum()) if not kg_order_df.empty else 0.0
    estimated_total_value = float(sum(item["line_total"] for item in valid_items))

    if kg_product_df.empty:
        line_breakdown = pd.DataFrame()
    else:
        order_value_df = (
            pd.DataFrame(valid_items)
            .groupby(["product_id", "product_name", "catalog_unit", "unit_kg"], as_index=False)[
                ["quantity", "total_kg", "estimated_unit_price", "line_total"]
            ]
            .sum()
            .rename(
                columns={
                    "product_id": "sku",
                    "product_name": "Product",
                    "catalog_unit": "Catalog Unit",
                    "unit_kg": "Unit KG",
                    "quantity": "raw_quantity",
                    "total_kg": "Total KG",
                    "estimated_unit_price": "Unit Value",
                    "line_total": "Estimated Value",
                }
            )
        )

        # Keep the legacy kg modules as the source for kilogram preview, but
        # display monetary values from the direct business rule above.
        kg_totals_lookup = {
            int(row["sku"]): float(row["peso_total"])
            for row in kg_product_df.to_dict(orient="records")
        }
        order_value_df["Total KG"] = order_value_df["sku"].map(kg_totals_lookup).fillna(order_value_df["Total KG"])
        order_value_df["Units"] = order_value_df.apply(
            lambda row: "kg" if row["Catalog Unit"] == "kg" else int(row["raw_quantity"]),
            axis=1,
        )
        order_value_df["Line Total"] = order_value_df["Estimated Value"]
        line_breakdown = order_value_df[["Product", "Catalog Unit", "Units", "Unit KG", "Total KG", "Unit Value", "Estimated Value", "Line Total"]]

    return {
        "valid_items": valid_items,
        "order_total_kg": order_total_kg,
        "line_breakdown": line_breakdown,
        "estimated_total_value": estimated_total_value,
        "validation_errors": [],
    }


def render_combo_components(
    line_index: int,
    combo_components: list[dict[str, Any]],
    component_options: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    component_lookup = {option["label"]: option for option in component_options}
    component_labels = [option["label"] for option in component_options]
    updated_components = combo_components[:] if combo_components else [make_default_combo_component()]

    with st.expander("Combo Composition", expanded=True):
        st.caption("These component rows feed the original combo kilogram logic from the legacy module.")

        for component_index, component in enumerate(updated_components):
            component_col1, component_col2, component_col3 = st.columns([2.2, 1, 1])
            with component_col1:
                selected_component_index = 0
                if component.get("product_id") is not None:
                    matches = [idx for idx, option in enumerate(component_options) if option["id"] == component["product_id"]]
                    if matches:
                        selected_component_index = matches[0]

                if component_labels:
                    selected_component_label = st.selectbox(
                        "Component Product",
                        options=component_labels,
                        index=selected_component_index,
                        key=f"component_product_{line_index}_{component_index}",
                    )
                    selected_component = component_lookup[selected_component_label]
                else:
                    st.selectbox(
                        "Component Product",
                        options=["No component products available"],
                        index=0,
                        key=f"component_product_{line_index}_{component_index}",
                        disabled=True,
                    )
                    selected_component = {
                        "id": None,
                        "product_name": "",
                    }

            with component_col2:
                component_kg = st.number_input(
                    "KG per Combo Unit",
                    min_value=0.0,
                    value=float(component.get("cantidad_en_kg", 0) or 0),
                    step=0.1,
                    key=f"component_kg_{line_index}_{component_index}",
                )

            with component_col3:
                remove_disabled = len(updated_components) == 1
                if st.button(
                    "Remove Component",
                    key=f"remove_component_{line_index}_{component_index}",
                    use_container_width=True,
                    disabled=remove_disabled,
                ):
                    updated_components.pop(component_index)
                    st.session_state.order_line_items[line_index]["combo_components"] = updated_components
                    st.rerun()

            updated_components[component_index] = {
                "product_id": selected_component.get("id"),
                "product_name": selected_component.get("product_name", ""),
                "cantidad_en_kg": component_kg,
            }

        if st.button(f"Add Component", key=f"add_component_{line_index}", use_container_width=True):
            updated_components.append(make_default_combo_component())
            st.session_state.order_line_items[line_index]["combo_components"] = updated_components
            st.rerun()

    return updated_components


def render_order_lines() -> None:
    st.subheader("Line Items")
    st.caption("Add one or more products from the active catalog. The kilogram preview runs through the original kg modules.")

    catalog_df, product_options, product_lookup, _ = load_catalog_options()
    component_options = [option for option in product_options if not option["is_combo"]]
    if catalog_df.empty:
        st.warning("No active products are available yet. Add products in Price Manager before creating orders.")

    for index, line_item in enumerate(st.session_state.order_line_items):
        with st.container(border=True):
            st.markdown(f"**Item {index + 1}**")
            nonce = st.session_state.order_form_nonce
            col1, col2 = st.columns([2.3, 1])
            with col1:
                labels = [option["label"] for option in product_options]
                product_key = f"product_name_{nonce}_{index}"
                selected_option = None
                if line_item.get("product_id") is not None:
                    matches = [option["label"] for option in product_options if option["id"] == line_item["product_id"]]
                    if matches:
                        selected_option = matches[0]

                if labels:
                    selected_label = st.selectbox(
                        "Product",
                        options=[None, *labels],
                        index=0 if selected_option is None else [None, *labels].index(selected_option),
                        key=product_key,
                        format_func=lambda option: "Select a product from the catalog..." if option is None else option,
                        help="Products are loaded from the same Prices repository used by Price Manager.",
                    )
                    selected_product = product_lookup[selected_label] if selected_label else {
                        "id": None,
                        "product_name": "",
                        "unit_price": 0.0,
                        "unit": "",
                        "is_combo": False,
                        "raw": {},
                    }
                else:
                    st.selectbox(
                        "Product",
                        options=["No active products available"],
                        index=0,
                        key=product_key,
                        disabled=True,
                    )
                    selected_product = {
                        "id": None,
                        "product_name": "",
                        "unit_price": 0.0,
                        "unit": "unit",
                        "is_combo": False,
                    }
            with col2:
                remove_disabled = len(st.session_state.order_line_items) == 1
                if st.button("Remove", key=f"remove_line_{index}", use_container_width=True, disabled=remove_disabled):
                    st.session_state.order_line_items.pop(index)
                    st.rerun()

            col3, col4, col5 = st.columns(3)
            with col3:
                quantity_key = f"quantity_{nonce}_{index}"
                quantity = st.number_input(
                    "Quantity",
                    min_value=0,
                    value=int(line_item.get("quantity", 1) or 1),
                    step=1,
                    key=quantity_key,
                    help="The original kilogram modules expect whole ordered units.",
                )
            with col4:
                catalog_weight_per_unit = get_catalog_weight_per_unit(selected_product, float(line_item.get("unit_kg", 1.0) or 1.0))
                unit_kg_key = f"unit_kg_{nonce}_{index}"
                st.session_state[unit_kg_key] = float(catalog_weight_per_unit) if selected_product["id"] is not None else 0.0
                unit_kg = st.number_input(
                    "Weight per Unit (kg)",
                    min_value=0.0,
                    value=st.session_state[unit_kg_key],
                    step=0.1,
                    key=unit_kg_key,
                    disabled=True,
                    help="Auto-populated from the selected catalog item.",
                )
            with col5:
                unit_price_key = f"unit_price_{nonce}_{index}"
                st.session_state[unit_price_key] = float(selected_product["unit_price"]) if selected_product["id"] is not None else 0.0
                estimated_unit_price = st.number_input(
                    "Unit Value",
                    min_value=0.0,
                    value=st.session_state[unit_price_key],
                    step=100.0,
                    key=unit_price_key,
                    disabled=True,
                    help="Auto-populated from the active price catalog.",
                )

            combo_components: list[dict[str, Any]] = []
            is_combo = bool(selected_product.get("is_combo", False))
            if is_combo:
                combo_components = render_combo_components(
                    index,
                    line_item.get("combo_components", []),
                    component_options,
                )

            line_total = quantity * estimated_unit_price
            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.caption(f"Catalog unit: {selected_product['unit'] or 'No product selected'}")
                if is_combo:
                    st.caption("Combo item: component kilograms are required for the original combo logic.")
            with info_col2:
                st.caption(f"Line total: ARS {line_total:,.2f}")

            st.session_state.order_line_items[index] = {
                "product_id": selected_product["id"],
                "product_name": selected_product["product_name"],
                "catalog_unit": selected_product["unit"],
                "quantity": quantity,
                "unit_kg": unit_kg,
                "estimated_unit_price": estimated_unit_price,
                "line_total": line_total,
                "is_combo": is_combo,
                "combo_components": combo_components,
            }


def validate_order(selected_client_id: int | None, valid_items: list[dict[str, Any]], validation_errors: list[str]) -> list[str]:
    errors: list[str] = []
    if selected_client_id is None:
        errors.append("Please select a client before saving the order.")
    if not valid_items:
        errors.append("Add at least one valid line item with product, quantity, and catalog weight.")
    errors.extend(validation_errors)
    return errors


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


inject_page_styles()
ensure_session_state()
orders_repo.ensure_tables_exist()

st.markdown(
    """
    <div class="orders-shell">
        <h3>New Order Workspace</h3>
        <p>Select a client, compose the order with multiple lines, review live kilogram totals, and save the order to the database.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

client_options, client_lookup = load_client_options()
recent_orders_df = orders_repo.get_recent_orders(limit=10)

main_col, preview_col = st.columns([1.85, 1], gap="large")

with main_col:
    st.subheader("New Order Form")
    if not client_options:
        st.warning("No clients are available yet. Add at least one client before creating orders.")
        selected_label = None
        selected_client_id = None
    else:
        labels = [option["label"] for option in client_options]
        if st.session_state.selected_client_id is not None and st.session_state.selected_client_label is None:
            matches = [option["label"] for option in client_options if option["id"] == st.session_state.selected_client_id]
            if matches:
                st.session_state.selected_client_label = matches[0]
        selected_label = st.selectbox(
            "Client",
            options=[None, *labels],
            index=0 if st.session_state.selected_client_label is None else [None, *labels].index(st.session_state.selected_client_label),
            key="selected_client_label",
            format_func=lambda option: "Select a client..." if option is None else option,
            help="Clients are loaded from the Clients repository.",
        )
        selected_client_id = client_lookup.get(selected_label)
        st.session_state.selected_client_id = selected_client_id

    order_notes = st.text_area(
        "Notes",
        value=st.session_state.order_notes,
        placeholder="Optional delivery or order notes...",
        help="Stored in the orders table for future workflow use.",
    )
    st.session_state.order_notes = order_notes

    render_order_lines()
    preview = calculate_preview(st.session_state.order_line_items)
    if preview["valid_items"]:
        st.info(f"Running grand total: ARS {preview['estimated_total_value']:,.2f}")
    for validation_error in preview["validation_errors"]:
        st.warning(validation_error)

    button_col1, button_col2, button_col3 = st.columns(3)
    with button_col1:
        if st.button("Add Line Item", use_container_width=True):
            st.session_state.order_line_items.append(make_default_line_item())
            st.rerun()
    with button_col2:
        if st.button("Clear Form", use_container_width=True):
            reset_order_form()
            st.toast("Order form cleared.")
            st.rerun()
    with button_col3:
        if st.button("Save Order", use_container_width=True, type="primary"):
            errors = validate_order(selected_client_id, preview["valid_items"], preview["validation_errors"])
            if errors:
                for error in errors:
                    st.error(error)
            else:
                order_payload = {
                    "client_id": selected_client_id,
                    "total_kg": preview["order_total_kg"],
                    "estimated_value": preview["estimated_total_value"],
                    "status": "draft",
                    "notes": order_notes.strip() or None,
                }
                items_payload = [
                    {
                        "product_description": item["product_name"],
                        "quantity": item["quantity"],
                        "weight_per_unit": item["unit_kg"],
                        "kg_contribution": item["quantity"] * item["unit_kg"],
                        "unit_value": item["estimated_unit_price"],
                        "line_total": item["line_total"],
                    }
                    for item in preview["valid_items"]
                ]
                result = orders_repo.save_order(order_payload, items_payload)
                if result["success"]:
                    order_id = result["data"]["order_id"]
                    st.toast(f"Order {order_id} saved successfully.")
                    st.success(f"Order {order_id} saved successfully.")
                    reset_order_form()
                    st.rerun()
                else:
                    st.error(result["message"])

    st.divider()
    st.subheader("Recent Orders")
    if recent_orders_df.empty:
        st.info("No orders have been saved yet.")
    else:
        display_recent_df = recent_orders_df[["id", "order_date", "client_label", "line_count", "total_kg", "estimated_value", "status"]].rename(
            columns={
                "id": "Order ID",
                "order_date": "Date",
                "client_label": "Client",
                "line_count": "Lines",
                "total_kg": "Total KG",
                "estimated_value": "Estimated Value",
                "status": "Status",
            }
        )
        st.dataframe(display_recent_df, use_container_width=True, hide_index=True)

with preview_col:
    preview = calculate_preview(st.session_state.order_line_items)
    st.subheader("Live Order Preview")
    selected_client_name = selected_label if client_options and selected_label else "No client selected"
    render_summary_card("Client", selected_client_name)
    render_summary_card("Line Items", str(len(preview["valid_items"])))
    render_summary_card("Total KG", f"{preview['order_total_kg']:.2f}")
    render_summary_card("Estimated Value", f"ARS {preview['estimated_total_value']:,.2f}")

    st.markdown("**Order Summary**")
    st.write(f"Client: {selected_client_name}")
    st.write(f"Lines in preview: {len(preview['valid_items'])}")
    st.write(f"Estimated kilograms: {preview['order_total_kg']:.2f} kg")
    st.write(f"Grand total: ARS {preview['estimated_total_value']:,.2f}")

    st.markdown("**Line Breakdown**")
    if preview["line_breakdown"].empty:
        st.info("Start adding line items to see the live calculation preview.")
    else:
        st.dataframe(preview["line_breakdown"], use_container_width=True, hide_index=True, height=320)

st.page_link("views/1_🏠_Home.py", label="Back to Home", icon="🏠")
