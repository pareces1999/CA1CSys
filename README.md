# CA1C System (Streamlit)

Professional Streamlit-based management system for CA1C (carnes y productos cárnicos).

## Features

- **Clients** — Full CRUD for client records
- **Orders** — Powerful order builder with live kg calculations + management (status, notes, clone for corrections)
- **Prices** — Catalog pricing with business rules enforcement (kg/unit/box/combo)
- Clean unified UI across all modules (toolbar + metrics + table + selection-driven actions + contextual editor)
- Repository + clean architecture layer on top of SQLite (local or Turso cloud)

## Project Structure

```
.
├── streamlit_app.py          # Main entry point
├── views/
│   ├── 1_home.py
│   ├── 2_clients.py
│   ├── 3_orders.py
│   └── 4_prices.py
├── core/
│   ├── db/connection.py
│   └── repositories/         # Clients, Orders, Prices
├── kg_per_order.py
├── kg_per_product.py         # Original kg calculation engines (called via runpy)
├── DBca1c.db
├── requirements.txt
└── archive/legacy_gui/       # Old desktop GUI code (preserved for reference)
```

## Running Locally

```powershell
cd $env:USERPROFILE\home\workdir\CA1CSys
. .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Notes

- The order module uses the original `kg_per_*.py` scripts via `runpy` for business-critical kilogram calculations.
- Cancelled orders are visible in history but excluded from cloning/editing actions.
- All interactive widgets use explicit `key=` parameters to prevent Streamlit duplicate element ID errors.

## License

Private / Internal use.
