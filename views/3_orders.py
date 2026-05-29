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

    # New keys for the unified Order Management section (Prices-style)
    if "selected_order_id" not in st.session_state:
        st.session_state.selected_order_id = None
    if "show_order_editor" not in st.session_state:
        st.session_state.show_order_editor = False
    if "order_editor_status" not in st.session_state:
        st.session_state.order_editor_status = "draft"
    if "order_editor_notes" not in st.session_state:
        st.session_state.order_editor_notes = ""

    if "_clone_success_banner" not in st.session_state:
        st.session_state._clone_success_banner = None

    if "_pending_load_order_id" not in st.session_state:
        st.session_state._pending_load_order_id = None


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


# ──────────────────────────────────────────────────────────────────────────────
# ORDER MANAGEMENT HELPERS (unified Prices-style pattern for existing orders)
# ──────────────────────────────────────────────────────────────────────────────

def clear_order_selection() -> None:
    """Clear selection and fully exit the management editor (mirrors Prices/Clients pattern)."""
    st.session_state.selected_order_id = None
    st.session_state.show_order_editor = False
    st.session_state.order_editor_status = "draft"
    st.session_state.order_editor_notes = ""


def load_order_into_editor(order_id: int) -> None:
    """Load an existing order header into the simple management editor."""
    order = orders_repo.get_order_by_id(order_id)
    if not order:
        st.error(f"Could not load order #{order_id}.")
        return
    st.session_state.selected_order_id = order_id
    st.session_state.order_editor_status = order.get("status", "draft") or "draft"
    st.session_state.order_editor_notes = order.get("notes") or ""
    st.session_state.show_order_editor = True


def clone_order(source_order_id: int) -> dict[str, Any]:
    """Create a complete copy of an existing order (client + all line items) as a new 'draft' order.
    Used for error correction workflows: clone the order, then cancel the original.
    Returns the same shape as orders_repo.save_order result.
    """
    source = orders_repo.get_order_by_id(source_order_id)
    if not source:
        return {"success": False, "message": f"Source order #{source_order_id} not found."}

    order_payload = {
        "client_id": source.get("client_id"),
        "total_kg": float(source.get("total_kg", 0) or 0),
        "estimated_value": float(source.get("estimated_value", 0) or 0),
        "status": "draft",
        "notes": ((source.get("notes") or "").strip() + f"\n\n[Cloned from Order #{source_order_id}]").strip() or None,
    }

    items_payload = []
    for it in source.get("items", []):
        items_payload.append({
            "product_description": it.get("product_description", ""),
            "quantity": float(it.get("quantity", 0) or 0),
            "weight_per_unit": float(it.get("weight_per_unit", 0) or 0),
            "kg_contribution": float(it.get("kg_contribution", 0) or 0),
            "unit_value": float(it.get("unit_value", 0) or 0),
            "line_total": float(it.get("line_total", 0) or 0),
        })

    return orders_repo.save_order(order_payload, items_payload)


def load_order_into_builder(order_id: int) -> None:
    """Safely load a saved order into the builder state.

    IMPORTANT: This function must only be called *before* any widgets using
    the keys 'selected_client_label', 'selected_client_id', or the dynamic line widgets
    have been instantiated in the current render (i.e. very early after ensure_session_state).
    It is triggered via the _pending_load_order_id mechanism from action buttons.
    """
    order = orders_repo.get_order_by_id(order_id)
    if not order:
        st.error(f"Could not load order #{order_id}.")
        return

    # Client (both id and label)
    st.session_state.selected_client_id = order.get("client_id")
    client_options, _ = load_client_options()
    st.session_state.selected_client_label = None
    for opt in client_options:
        if opt["id"] == st.session_state.selected_client_id:
            st.session_state.selected_client_label = opt["label"]
            break

    # Notes
    st.session_state.order_notes = order.get("notes") or ""

    # Rebuild line items
    _, product_options, _, _ = load_catalog_options()
    new_lines: list[dict[str, Any]] = []
    for item in order.get("items", []):
        line = make_default_line_item()
        desc = str(item.get("product_description", "")).strip()
        line["product_name"] = desc
        line["quantity"] = int(float(item.get("quantity", 1) or 1))
        line["unit_kg"] = float(item.get("weight_per_unit", 1.0) or 1.0)
        line["estimated_unit_price"] = float(item.get("unit_value", 0.0) or 0.0)
        line["line_total"] = float(item.get("line_total", 0.0) or 0.0)

        for opt in product_options:
            if str(opt.get("product_name", "")).lower() == desc.lower():
                line["product_id"] = opt["id"]
                line["catalog_unit"] = opt.get("unit", "")
                break

        new_lines.append(line)

    if not new_lines:
        new_lines = [make_default_line_item()]

    st.session_state.order_line_items = new_lines
    st.session_state.order_form_nonce += 1

    # One-shot banner shown in builder area
    st.session_state._clone_success_banner = (
        f"📋 Cloned from Order #{order_id} — this draft is now loaded here for editing. "
        "Modify line items, quantities or client as needed, then Save Order."
    )


def prepare_orders_display_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean formatted dataframe for the Order Management table."""
    if df.empty:
        return pd.DataFrame(columns=["ID", "Date", "Client", "Lines", "Total KG", "Est. Value", "Status"])

    display = df[["id", "order_date", "client_label", "line_count", "total_kg", "estimated_value", "status"]].copy()
    display = display.rename(
        columns={
            "id": "ID",
            "order_date": "Date",
            "client_label": "Client",
            "line_count": "Lines",
            "total_kg": "Total KG",
            "estimated_value": "Est. Value",
            "status": "Status",
        }
    )
    # Format
    display["Total KG"] = display["Total KG"].apply(lambda v: f"{float(v or 0):.2f}")
    display["Est. Value"] = display["Est. Value"].apply(lambda v: f"ARS {float(v or 0):,.0f}")
    display["Date"] = pd.to_datetime(display["Date"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M").fillna("")
    return display[["ID", "Date", "Client", "Lines", "Total KG", "Est. Value", "Status"]]


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


# ──────────────────────────────────────────────────────────────────────────────
# ORDER MANAGEMENT UI (unified with Prices look & feel)
# ──────────────────────────────────────────────────────────────────────────────

@st.dialog("Confirm Delete Order")
def confirm_delete_order_dialog(order_id: int, client_label: str) -> None:
    st.write(f"Are you sure you want to permanently delete **Order #{order_id}** for **{client_label}**?")
    st.caption("This will also remove all line items. This action cannot be undone.")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🗑️ Yes, Delete Order", type="primary", use_container_width=True, key="orders_delete_confirm_yes"):
            result = orders_repo.delete_order(order_id)
            if result["success"]:
                st.toast(result["message"])
                clear_order_selection()
                st.rerun()
            else:
                st.error(result["message"])
    with c2:
        if st.button("Cancel", use_container_width=True, key="orders_delete_confirm_cancel"):
            st.rerun()


def render_order_management_header() -> None:
    st.subheader("Order Management")
    st.caption("View all orders (including cancelled). Use the selector below for actions on open/draft orders only — cancelled orders cannot be cloned or edited via this panel.")


def render_order_metrics(df: pd.DataFrame) -> None:
    """Metrics row for the Order Management section."""
    total = len(df)
    status_counts = orders_repo.get_order_status_counts()
    draft = status_counts.get("draft", 0)
    completed = status_counts.get("completed", 0) + status_counts.get("closed", 0)

    total_value = float(df["estimated_value"].sum()) if not df.empty else 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Total Orders</div>'
            f'<div class="metric-value">{total}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Draft / Open</div>'
            f'<div class="metric-value">{draft}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Completed</div>'
            f'<div class="metric-value">{completed}</div></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Total Value</div>'
            f'<div class="metric-value">ARS {total_value:,.0f}</div></div>',
            unsafe_allow_html=True,
        )


def render_order_table(df: pd.DataFrame) -> pd.DataFrame:
    """Single clean table for orders (Prices pattern)."""
    display_df = prepare_orders_display_dataframe(df)

    if display_df.empty:
        st.info("No orders have been saved yet. Create your first order using the builder above.")
        return df

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=260,
        column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "Lines": st.column_config.NumberColumn(width="small"),
            "Status": st.column_config.TextColumn(width="small"),
        },
    )
    return df


def render_order_selection_and_actions(df: pd.DataFrame) -> int | None:
    """Selection + actions bar for Order Management (exact Prices pattern)."""
    if df.empty:
        return None

    options = ["— Select an order —"]
    id_map = {}
    for _, row in df.iterrows():
        status = str(row.get("status", "")).lower()
        if status == "cancelled":
            continue  # Cancelled orders are visible in the table above but not available for cloning / actions
        label = f"#{int(row['id'])} — {row.get('client_label', 'Unknown')} | {row.get('status', '')}"
        options.append(label)
        id_map[label] = int(row["id"])

    current_id = st.session_state.selected_order_id
    current_label = next((k for k, v in id_map.items() if v == current_id), options[0])

    selected_label = st.selectbox(
        "Selected Order for Actions",
        options=options,
        index=options.index(current_label) if current_label in options else 0,
        key="orders_management_selection_selectbox",
    )
    selected_id = id_map.get(selected_label)

    if selected_id != st.session_state.selected_order_id:
        st.session_state.selected_order_id = selected_id

    st.markdown("**Actions**")
    btn_cols = st.columns([1.1, 1.3, 1.5, 1.3, 1.1, 1.7])

    with btn_cols[0]:
        if st.button("➕ New Order (above)", use_container_width=True, type="primary", key="orders_management_new_hint_btn"):
            # Just give visual hint — the builder is always at the top
            st.toast("Scroll up to the 'New Order Form' builder to create a fresh order.")
            clear_order_selection()

    with btn_cols[1]:
        # Extra safety: never allow cloning a cancelled order even if it somehow became selected
        is_cancelled = False
        if selected_id:
            sel_row = df[df["id"] == selected_id]
            if not sel_row.empty:
                is_cancelled = str(sel_row.iloc[0].get("status", "")).lower() == "cancelled"
        disabled = selected_id is None or is_cancelled
        if st.button("📋 Clone Order", use_container_width=True, disabled=disabled, key="orders_management_clone_btn"):
            if selected_id:
                source = orders_repo.get_order_by_id(selected_id)
                if not source:
                    st.error(f"Could not load source order #{selected_id}.")
                else:
                    result = clone_order(selected_id)
                    if result.get("success"):
                        new_id = result["data"]["order_id"]
                        # Mark the original as cancelled for error-correction workflow
                        orig_notes = (source.get("notes") or "").strip()
                        replacement_note = f"\n\n[Replaced by cloned Order #{new_id}]"
                        orders_repo.update_order(selected_id, {
                            "status": "cancelled",
                            "notes": (orig_notes + replacement_note).strip() or None,
                        })
                        st.toast(f"Order #{selected_id} cloned as #{new_id}")
                        st.success(
                            f"✅ Order #{selected_id} cloned as new draft Order #{new_id} (original cancelled). "
                            "The clone will be loaded into the New Order Workspace above on the next render."
                        )
                        # Do NOT call load_order_into_builder here — it would mutate widget keys after they are created.
                        # Instead, set a pending flag. The early guard right after ensure_session_state() will apply it safely.
                        st.session_state._pending_load_order_id = new_id
                        st.session_state._clone_success_banner = (
                            f"📋 Cloned from Order #{selected_id} as new draft #{new_id}. "
                            "Edit lines/quantities/client in the workspace above, then Save Order."
                        )
                        clear_order_selection()
                        st.rerun()
                    else:
                        st.error(result.get("message", "Clone failed."))

    with btn_cols[2]:
        disabled = selected_id is None
        if st.button("✏️ Edit Status/Notes", use_container_width=True, disabled=disabled, key="orders_management_edit_btn"):
            if selected_id:
                load_order_into_editor(selected_id)
                st.rerun()

    with btn_cols[3]:
        disabled = selected_id is None
        if st.button("🗑️ Delete Selected", use_container_width=True, disabled=disabled, key="orders_management_delete_btn"):
            if selected_id:
                row = df[df["id"] == selected_id].iloc[0]
                confirm_delete_order_dialog(selected_id, row.get("client_label", f"Order #{selected_id}"))

    with btn_cols[4]:
        if st.button("⟳ Refresh", use_container_width=True, type="secondary", key="orders_management_refresh_btn"):
            clear_order_selection()
            st.rerun()

    with btn_cols[5]:
        st.caption("Tip: Clone is only available for non-cancelled orders. Cancelled orders stay visible in the table for history.")

    return selected_id


def render_order_editor() -> None:
    """Contextual simple editor for order header (status + notes)."""
    if not st.session_state.show_order_editor or not st.session_state.selected_order_id:
        with st.expander("📝 Order Editor (Status & Notes)", expanded=False):
            st.info("Select an order above and click **Edit Status/Notes** to open the editor.")
        return

    order_id = st.session_state.selected_order_id
    order = orders_repo.get_order_by_id(order_id)
    if not order:
        st.warning("Selected order could not be found (it may have been deleted).")
        clear_order_selection()
        return

    with st.expander(f"📝 Order #{order_id} — {order.get('client_label') or order.get('client_name', 'Unknown')}", expanded=True):
        # Read-only summary
        st.markdown("**Order Summary (read-only)**")
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.metric("Total KG", f"{float(order.get('total_kg', 0)):.2f}")
        with s2:
            st.metric("Est. Value", f"ARS {float(order.get('estimated_value', 0)):,.0f}")
        with s3:
            st.metric("Lines", len(order.get("items", [])))
        with s4:
            st.metric("Current Status", str(order.get("status", "—")).upper())

        # Items preview (collapsed)
        with st.expander("Line Items (preview)", expanded=False):
            items = order.get("items", [])
            if items:
                items_df = pd.DataFrame(items)[["product_description", "quantity", "line_total"]]
                items_df.columns = ["Product", "Qty", "Line Total"]
                st.dataframe(items_df, hide_index=True, use_container_width=True, height=180)
            else:
                st.caption("No line items found.")

        st.divider()

        # Editable fields
        with st.form("order_management_form", clear_on_submit=False):
            st.markdown("**Update Status & Notes**")

            status_options = ["draft", "confirmed", "in_progress", "completed", "cancelled"]
            current_status = st.session_state.order_editor_status or order.get("status", "draft")
            new_status = st.selectbox(
                "Status",
                options=status_options,
                index=status_options.index(current_status) if current_status in status_options else 0,
                key="orders_editor_status_selectbox",
            )

            new_notes = st.text_area(
                "Notes",
                value=st.session_state.order_editor_notes or (order.get("notes") or ""),
                height=100,
                placeholder="Internal notes, delivery instructions, etc.",
                key="orders_editor_notes_textarea",
            )

            submitted = st.form_submit_button("💾 Save Status & Notes", use_container_width=True, type="primary", key="orders_editor_save_submit")

            if submitted:
                payload = {"status": new_status, "notes": new_notes.strip() or None}
                result = orders_repo.update_order(order_id, payload)
                if result["success"]:
                    st.toast(result["message"])
                    st.success(result["message"])
                    # Fully exit editor + clear selection so user can pick another order immediately (fixes stale editor frame)
                    clear_order_selection()
                    st.rerun()
                else:
                    st.error(result["message"])

        # Bottom controls
        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("Close Editor", use_container_width=True, key="orders_editor_close_btn"):
                clear_order_selection()
                st.rerun()


inject_page_styles()
ensure_session_state()
orders_repo.ensure_tables_exist()

# Apply any pending order load into the builder (must happen BEFORE any builder widgets are created)
if st.session_state.get("_pending_load_order_id"):
    pending_id = st.session_state._pending_load_order_id
    st.session_state._pending_load_order_id = None
    load_order_into_builder(pending_id)

st.markdown(
    """
    <div class="orders-shell">
        <h3>New Order Workspace</h3>
        <p>Select a client, compose the order with multiple lines, review live kilogram totals, and save the order to the database.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Show one-shot clone success banner (if present)
if st.session_state.get("_clone_success_banner"):
    st.info(st.session_state._clone_success_banner)
    st.session_state._clone_success_banner = None

client_options, client_lookup = load_client_options()

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
        key="orders_creation_notes_textarea",
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
        if st.button("Add Line Item", use_container_width=True, key="orders_creation_add_line_btn"):
            st.session_state.order_line_items.append(make_default_line_item())
            st.rerun()
    with button_col2:
        if st.button("Clear Form", use_container_width=True, key="orders_creation_clear_btn"):
            reset_order_form()
            st.toast("Order form cleared.")
            st.rerun()
    with button_col3:
        if st.button("Save Order", use_container_width=True, type="primary", key="orders_creation_save_btn"):
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

    # (Recent Orders table removed — now provided in the full "Order Management" section below for unified look & feel)

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

# ══════════════════════════════════════════════════════════════════════════════
# ORDER MANAGEMENT SECTION — unified GUI with Prices (below the creation workspace)
# The entire builder above remains 100% functional and untouched.
# ══════════════════════════════════════════════════════════════════════════════

st.divider()
orders_repo.ensure_tables_exist()

render_order_management_header()

# Load all orders for the management table (richer than the old "recent" list)
all_orders_df = orders_repo.get_all_orders()

render_order_metrics(all_orders_df)
st.write("")

all_orders_df = render_order_table(all_orders_df)
st.write("")

selected_order_id = render_order_selection_and_actions(all_orders_df)

st.divider()
render_order_editor()

st.page_link("views/1_home.py", label="← Back to Home", icon="🏠")
