from pathlib import Path

import pandas as pd
import streamlit as st

from core.repositories.clients_repository import ClientsRepository
from core.repositories.orders_repository import OrdersRepository
from core.repositories.prices_repository import PricesRepository

try:
    from functions import kg_per_order, kg_per_product
except ModuleNotFoundError:
    def kg_per_order(order_df: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
        temp_merged = pd.merge(order_df, price_df, on=["codigo_lista", "sku"], how="left")
        order_df_merged = temp_merged[["orden", "cantidad_producto", "peso_en_kg", "combo"]].copy()
        order_df_merged["peso_de_orden"] = order_df_merged["cantidad_producto"] * order_df_merged["peso_en_kg"]
        return order_df_merged.groupby(["orden"])["peso_de_orden"].sum().reset_index()

    def kg_per_product(order_df: pd.DataFrame, price_df: pd.DataFrame, combo_df: pd.DataFrame) -> pd.DataFrame:
        temp_merged1 = pd.merge(order_df, price_df, on=["codigo_lista", "sku"], how="left")
        temp_merged_combo = temp_merged1.loc[temp_merged1["combo"]]
        temp_merged_nocombo = temp_merged1.loc[temp_merged1["combo"] != True].copy()
        temp_merged_nocombo["peso_total"] = temp_merged_nocombo["cantidad_producto"] * temp_merged_nocombo["peso_en_kg"]

        if temp_merged_combo.empty:
            output_totals = temp_merged_nocombo.groupby(["sku", "nombre_producto", "peso_en_kg"])["peso_total"].sum().reset_index()
        else:
            temp_merged2 = pd.merge(
                temp_merged_combo,
                combo_df,
                left_on=["codigo_lista", "sku"],
                right_on=["codigo_lista", "codigo_combo"],
                how="left",
            )
            temp_merged2["peso_total"] = temp_merged2["cantidad_producto"] * temp_merged2["cantidad_en_kg"]
            for row_ix, row_values in temp_merged2.iterrows():
                temp_merged2.iloc[row_ix, 8] = price_df.loc[
                    ((price_df["codigo_lista"] == row_values[1]) & (price_df["sku"] == row_values[11])),
                    "peso_en_kg",
                ].values[0]

            cols_dict = {"sku_y": "sku", "nombre_producto_y": "nombre_producto"}
            temp_append1 = temp_merged_nocombo[["codigo_lista", "sku", "nombre_producto", "peso_en_kg", "peso_total"]]
            temp_append2 = temp_merged2[["codigo_lista", "sku_y", "nombre_producto_y", "peso_en_kg", "peso_total"]]
            temp_append3 = temp_append2.rename(columns=cols_dict)
            cut_lst_merged = pd.concat([temp_append1, temp_append3], ignore_index=True)
            output_totals = cut_lst_merged.groupby(["sku", "nombre_producto", "peso_en_kg"])["peso_total"].sum().reset_index()

        output_totals["cantidad_unidades"] = 0.0
        for row_ix, row_values in output_totals.iterrows():
            peso_unit = output_totals.iloc[row_ix, 2]
            peso_total = output_totals.iloc[row_ix, 3]
            output_totals.iloc[row_ix, 4] = round(peso_total / peso_unit, 2) if peso_unit != 1 else 0
        return output_totals


ROOT_DIR = Path(__file__).resolve().parent.parent
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


def ensure_session_state() -> None:
    if "order_line_items" not in st.session_state:
        st.session_state.order_line_items = [{
            "product_id": None,
            "product_name": "",
            "quantity": 1.0,
            "unit_kg": 1.0,
            "estimated_unit_price": 0.0,
            "line_total": 0.0,
        }]
    if "selected_client_id" not in st.session_state:
        st.session_state.selected_client_id = None
    if "order_notes" not in st.session_state:
        st.session_state.order_notes = ""


def reset_order_form() -> None:
    st.session_state.order_line_items = [{
        "product_id": None,
        "product_name": "",
        "quantity": 1.0,
        "unit_kg": 1.0,
        "estimated_unit_price": 0.0,
        "line_total": 0.0,
    }]
    st.session_state.selected_client_id = None
    st.session_state.order_notes = ""


def load_client_options() -> tuple[list[dict], dict[str, int]]:
    clients_df = clients_repo.get_all_clients()
    if clients_df.empty:
        return [], {}

    options: list[dict] = []
    lookup: dict[str, int] = {}
    for row in clients_df.to_dict(orient="records"):
        full_name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
        dni = row.get("dni_cuil") or "No DNI"
        label = f"{full_name or 'Unnamed Client'} - {dni}"
        options.append({"label": label, "id": int(row["id"]), "raw": row})
        lookup[label] = int(row["id"])
    return options, lookup


def load_catalog_options() -> tuple[pd.DataFrame, list[dict], dict[str, dict]]:
    prices_df = prices_repo.get_all_prices()
    if prices_df.empty:
        return prices_df, [], {}

    catalog_df = prices_df.loc[prices_df["active"] == 1].copy()
    catalog_df = catalog_df.sort_values(["product_name", "category", "id"]).reset_index(drop=True)
    if catalog_df.empty:
        return catalog_df, [], {}

    options: list[dict] = []
    lookup: dict[str, dict] = {}
    for row in catalog_df.to_dict(orient="records"):
        unit = row.get("unit") or "unit"
        unit_price = float(row.get("price_per_unit", 0) or 0)
        if unit == "kg" and float(row.get("price_per_kg", 0) or 0) > 0:
            unit_price = float(row.get("price_per_kg", 0) or 0)
        label = f"{row.get('product_name', 'Unnamed Product')} | {row.get('category') or 'General'} | {unit.upper()}"
        option = {
            "label": label,
            "id": int(row["id"]),
            "product_name": row.get("product_name", ""),
            "unit": unit,
            "unit_price": unit_price,
            "raw": row,
        }
        options.append(option)
        lookup[label] = option
    return catalog_df, options, lookup


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


def build_order_frames(line_items: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    order_rows: list[dict] = []
    price_rows: list[dict] = []

    for index, item in enumerate(line_items, start=1):
        product_name = str(item.get("product_name", "")).strip() or f"Product {index}"
        quantity = float(item.get("quantity", 0) or 0)
        unit_kg = float(item.get("unit_kg", 0) or 0)
        estimated_unit_price = float(item.get("estimated_unit_price", 0) or 0)
        sku = index

        order_rows.append({"orden": DEFAULT_ORDER_ID, "codigo_lista": DEFAULT_LIST_CODE, "cantidad_producto": quantity, "sku": sku})
        price_rows.append(
            {
                "codigo_lista": DEFAULT_LIST_CODE,
                "sku": sku,
                "codigo_producto": f"SIM-{sku:03d}",
                "nombre_producto": product_name,
                "precio_frigorifico": 0.0,
                "precio_carneaunclick": estimated_unit_price,
                "peso_en_kg": unit_kg,
                "combo": False,
            }
        )

    order_df = pd.DataFrame(order_rows)
    price_df = pd.DataFrame(price_rows)
    combo_df = pd.DataFrame(columns=["codigo_lista", "codigo_combo", "sku", "nombre_producto", "cantidad_en_kg", "frigorifico_sin_iva", "frigorifico_con_iva", "ca1c_sin_iva", "ca1c_con_iva"])
    return order_df, price_df, combo_df


def calculate_preview(line_items: list[dict]) -> dict[str, object]:
    valid_items = []
    for item in line_items:
        product_name = str(item.get("product_name", "")).strip()
        quantity = float(item.get("quantity", 0) or 0)
        unit_kg = float(item.get("unit_kg", 0) or 0)
        estimated_unit_price = float(item.get("estimated_unit_price", 0) or 0)
        if product_name and quantity > 0 and unit_kg >= 0:
            valid_items.append({
                "product_id": item.get("product_id"),
                "product_name": product_name,
                "quantity": quantity,
                "unit_kg": unit_kg,
                "estimated_unit_price": estimated_unit_price,
                "line_total": quantity * estimated_unit_price,
            })

    if not valid_items:
        return {"valid_items": [], "order_total_kg": 0.0, "line_breakdown": pd.DataFrame(), "estimated_total_value": 0.0}

    order_df, price_df, combo_df = build_order_frames(valid_items)
    kg_order_df = kg_per_order(order_df, price_df)
    kg_product_df = kg_per_product(order_df, price_df, combo_df)

    line_breakdown = pd.DataFrame(valid_items)
    line_breakdown["line_total_kg"] = line_breakdown["quantity"] * line_breakdown["unit_kg"]
    line_breakdown["estimated_line_value"] = line_breakdown["line_total"]

    order_total_kg = float(kg_order_df["peso_de_orden"].sum()) if not kg_order_df.empty else 0.0
    estimated_total_value = float(line_breakdown["estimated_line_value"].sum())

    if not kg_product_df.empty:
        kg_product_df = kg_product_df.rename(columns={"nombre_producto": "product_name", "peso_total": "aggregated_kg", "cantidad_unidades": "estimated_units"})
        line_breakdown = line_breakdown.merge(kg_product_df[["product_name", "aggregated_kg", "estimated_units"]], on="product_name", how="left")

    return {"valid_items": valid_items, "order_total_kg": order_total_kg, "line_breakdown": line_breakdown, "estimated_total_value": estimated_total_value}


def render_order_lines() -> None:
    st.subheader("Line Items")
    st.caption("Add one or more products from the active catalog. Unit price is pulled automatically from Price Manager.")

    catalog_df, product_options, product_lookup = load_catalog_options()
    if catalog_df.empty:
        st.warning("No active products are available yet. Add products in Price Manager before creating orders.")

    for index, line_item in enumerate(st.session_state.order_line_items):
        with st.container(border=True):
            st.markdown(f"**Item {index + 1}**")
            col1, col2 = st.columns([2.3, 1])
            with col1:
                labels = [option["label"] for option in product_options]
                selected_index = None
                if line_item.get("product_id") is not None:
                    matches = [idx for idx, option in enumerate(product_options) if option["id"] == line_item["product_id"]]
                    if matches:
                        selected_index = matches[0]

                if labels:
                    selected_label = st.selectbox(
                        "Product",
                        options=labels,
                        index=selected_index if selected_index is not None else 0,
                        key=f"product_name_{index}",
                        help="Products are loaded from the same Prices repository used by Price Manager.",
                    )
                    selected_product = product_lookup[selected_label]
                else:
                    st.selectbox(
                        "Product",
                        options=["No active products available"],
                        index=0,
                        key=f"product_name_{index}",
                        disabled=True,
                    )
                    selected_product = {
                        "id": None,
                        "product_name": "",
                        "unit_price": 0.0,
                        "unit": "unit",
                    }
            with col2:
                remove_disabled = len(st.session_state.order_line_items) == 1
                if st.button("Remove", key=f"remove_line_{index}", use_container_width=True, disabled=remove_disabled):
                    st.session_state.order_line_items.pop(index)
                    st.rerun()

            col3, col4, col5 = st.columns(3)
            with col3:
                quantity = st.number_input("Quantity", min_value=0.0, value=float(line_item["quantity"]), step=1.0, key=f"quantity_{index}")
            with col4:
                catalog_weight_per_unit = get_catalog_weight_per_unit(
                    selected_product,
                    float(line_item["unit_kg"]),
                )
                unit_kg = st.number_input(
                    "Weight per Unit (kg)",
                    min_value=0.0,
                    value=float(catalog_weight_per_unit),
                    step=0.1,
                    key=f"unit_kg_{index}",
                    disabled=True,
                    help="Auto-populated from the selected catalog item.",
                )
            with col5:
                estimated_unit_price = st.number_input(
                    "Unit Value",
                    min_value=0.0,
                    value=float(selected_product["unit_price"]) if selected_product["id"] is not None else 0.0,
                    step=100.0,
                    key=f"unit_price_{index}",
                    disabled=True,
                    help="Auto-populated from the active price catalog.",
                )

            line_total = quantity * estimated_unit_price
            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.caption(f"Catalog unit: {selected_product['unit']}")
            with info_col2:
                st.caption(f"Line total: ARS {line_total:,.2f}")

            st.session_state.order_line_items[index] = {
                "product_id": selected_product["id"],
                "product_name": selected_product["product_name"],
                "quantity": quantity,
                "unit_kg": unit_kg,
                "estimated_unit_price": estimated_unit_price,
                "line_total": line_total,
            }


def validate_order(selected_client_id: int | None, valid_items: list[dict]) -> list[str]:
    errors: list[str] = []
    if selected_client_id is None:
        errors.append("Please select a client before saving the order.")
    if not valid_items:
        errors.append("Add at least one valid line item with product name, quantity, and weight.")
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
        default_index = 0
        if st.session_state.selected_client_id is not None:
            matches = [idx for idx, option in enumerate(client_options) if option["id"] == st.session_state.selected_client_id]
            if matches:
                default_index = matches[0]
        selected_label = st.selectbox("Client", options=labels, index=default_index, help="Clients are loaded from the Clients repository.")
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

    button_col1, button_col2, button_col3 = st.columns(3)
    with button_col1:
        if st.button("Add Line Item", use_container_width=True):
            st.session_state.order_line_items.append({
                "product_id": None,
                "product_name": "",
                "quantity": 1.0,
                "unit_kg": 1.0,
                "estimated_unit_price": 0.0,
                "line_total": 0.0,
            })
            st.rerun()
    with button_col2:
        if st.button("Clear Form", use_container_width=True):
            reset_order_form()
            st.toast("Order form cleared.")
            st.rerun()
    with button_col3:
        if st.button("Save Order", use_container_width=True, type="primary"):
            errors = validate_order(selected_client_id, preview["valid_items"])
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
        breakdown_df = preview["line_breakdown"].rename(columns={"product_name": "Product", "quantity": "Qty", "unit_kg": "Unit KG", "estimated_unit_price": "Unit Value", "line_total": "Line Total", "line_total_kg": "Line KG", "estimated_line_value": "Estimated Value", "aggregated_kg": "Aggregated KG", "estimated_units": "Estimated Units"})
        st.dataframe(breakdown_df, use_container_width=True, hide_index=True, height=320)

st.page_link("views/1_🏠_Home.py", label="Back to Home", icon="🏠")
