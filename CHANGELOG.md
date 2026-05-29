# Changelog

All notable changes to the CA1C System.

## [2026-04] - Streamlit Refactor (Major Release)

This release delivers a complete professional redesign and unification of the Streamlit application, moving from inconsistent module UIs and legacy desktop code to a single, clean, maintainable architecture.

### Highlights

- **Unified Professional GUI** across Prices, Clients, and Orders modules:
  - Consistent top toolbar (search + New / Refresh / Export buttons)
  - Four bordered metric summary cards
  - Single selectable `st.dataframe` with rich `ColumnConfig` (badges, currency, progress bars, weight formatting)
  - Selection-driven horizontal action button row (Edit / Delete / Clone / etc. with emoji icons for clarity)
  - Contextual `st.expander` editor using `st.form` + reactive widgets outside the form where needed (e.g., Unit type selector)
- **Prices Module** — canonical implementation of the new pattern plus 4 enforced business rules:
  - Weight mandatory except when Unit = Kg (locked at 1.0)
  - Price/Unit is always calculated and disabled
  - Option A pricing: `Price/Unit = weight × price_kg`
  - Box/Combo treated identically to Unit for calculations
  - Legacy data auto-adjusted on edit load
- **Orders Module** — preserved the powerful "New Order Workspace" builder (dynamic lines, live kg preview via `kg_per_order.py` / `kg_per_product.py`) while adding the unified management section (status/notes editor + **Clone this order** for safe corrections).
- **Clients Module** — fully rewritten to the unified pattern (was previously a repetitive grid + per-row edit buttons).

### Key Features Added

- **"Clone this order"** safe mutation workflow:
  - Cancelled orders are excluded from clone actions (historical/audit only).
  - Original order is set to "cancelled" with audit note.
  - Full deep copy (including all line items) is loaded into the editable New Order Workspace.
  - Uses `_pending_load_order_id` + early-render hook before any builder widgets are instantiated to avoid Streamlit "widget already instantiated" errors.
- Exhaustive **widget key hygiene**:
  - Every interactive element (`st.button`, `st.selectbox`, `st.text_input`, `st.number_input`, `st.dataframe`, `st.page_link` where supported, etc.) now carries a deterministic, namespaced `key=` (e.g. `orders_management_clone_btn`, `clients_editor_first_name`, `prices_unit_type_select`).
  - Eliminates all `StreamlitDuplicateElementId` errors permanently.
- **File hygiene & professionalization**:
  - All emoji characters removed from filenames (`1_🏠_Home.py` → `1_home.py`, etc.).
  - Legacy pre-Streamlit desktop GUI (14+ files: old `main.py`, `gui_*.py`, insertion scripts, old database helpers) moved to `archive/legacy_gui/` with its own README explaining they are dead code.
  - `archive/` explicitly gitignored going forward.
- Centralized repository layer (`core/repositories/*.py`) on top of the global DB connection.
- Improved session_state discipline: explicit state machine with `clear_*` helpers and pending-flag pattern for cross-section loads.

### Documentation & DX

- Complete rewrite of [README.md](README.md) with:
  - Project structure diagram
  - PowerShell run instructions
  - Architecture notes (kg scripts, cancelled order policy, widget key contract, clone workflow)
- New [CHANGELOG.md](CHANGELOG.md) (this file).
- All Python files pass `py_compile` / AST validation before any Streamlit restart recommendations.

### Bug Fixes Addressed During Refactor

- Edit form not clearing after successful save in Orders management → now uses enhanced `clear_order_selection()` + `st.rerun()`.
- Unit type reactivity broken for Kg → Unit transitions (Weight field locking) → Unit selector kept outside form with `on_change=st.rerun` + conditional `disabled`.
- Clone operation loaded the new order into the read-only status editor instead of the editable builder → fixed to target `load_order_into_builder`.
- Cancelled orders were incorrectly offered for cloning.
- `TypeError: ButtonMixin.page_link() got an unexpected keyword argument 'key'` on Home page (st.page_link does not support key= in current Streamlit) → keys removed only from page_link calls.
- Duplicate page title/caption in Clients module (module-level + inside `render_header`) → removed duplication.
- Various state timing issues during order clone fixed via the pending-flag early hook.

### Files Changed (Summary)

- `streamlit_app.py` — navigation registration, page config, imports updated for clean view names.
- `views/1_home.py`, `views/2_clients.py`, `views/3_orders.py`, `views/4_prices.py` — full unification + key hygiene + clone logic.
- `core/repositories/orders_repository.py` (and siblings) — repository methods for clone support.
- `core/db/connection.py`, `kg_per_*.py` — untouched (core calculation engines preserved).
- `.gitignore` — cleaned and extended with `archive/` rule.
- `README.md` — major rewrite.
- `CHANGELOG.md` — added.
- `archive/legacy_gui/` — added locally (deliberately untracked by git).

### Upgrade Notes

- Run with Python 3.11+ and the pinned `requirements.txt`.
- Existing `DBca1c.db` continues to work; the schema is stable.
- No breaking changes to the order calculation engines or pricing rules.

---

**Branch**: `streamlit-refactor`  
**Target remote**: `https://github.com/pareces1999/CA1CSys/tree/streamlit-refactor`

Previous history on the branch contains incremental steps of the migration. This release commit represents the final, production-ready state of the refactored application.
