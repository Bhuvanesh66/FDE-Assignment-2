# Workflow and data model

## 1. The business workflow (what actually happens to an order)

```mermaid
flowchart LR
    A[Customer places order<br/>ORDER_CREATED<br/>promised_eta shown] --> B[Dispatch assigns driver<br/>DRIVER_ASSIGNED<br/>estimated_pickup_at]
    B --> C{Restaurant prepares<br/>preparing → ready → handed_off}
    B --> D[Driver rides to restaurant<br/>GPS pings]
    C --> E[PICKED_UP]
    D -.no arrival event.-> E
    E --> F[Transit<br/>GPS pings]
    F --> G[DELIVERED<br/>actual_delivery_at]
    A -.-> X[CANCELLED<br/>no timestamp]
    subgraph Customer reacts
        H[APP_ETA_VIEWED / APP_SUPPORT_OPENED / APP_CANCEL_ATTEMPTED]
        I[SUPPORT_TICKET]
    end
    subgraph Ops intervenes
        J[DRIVER_REASSIGNMENT · RESTAURANT_CONTACT · PRIORITY_DISPATCH · CUSTOMER_CREDIT]
    end
    A --- H
    H --> I
    I --> J
    J --> E
    G --> K[(Outcome<br/>late_flag · delay_min · outcome_bucket)]
```

States of an order: `created → assigned → (at restaurant?) → picked_up → delivered | cancelled`. The dotted edge is the missing instrumentation: nothing records when the driver **arrived** at the restaurant.

## 2. Entities, events, interactions, interventions, outcomes

| Concept | Instances in this domain |
|---|---|
| **Entities** (things that persist) | customer, restaurant, driver, order, support ticket, intervention |
| **Events** (things that happen, timestamped) | ORDER_CREATED, DRIVER_ASSIGNED, DRIVER_REASSIGNED, PICKUP_ESTIMATED, RESTAURANT_PREPARING/READY/HANDED_OFF, PICKED_UP, DELIVERED, DRIVER_APP_* (incl. GPS pings), APP_*, SUPPORT_TICKET, INTERVENTION_* |
| **States** | `final_status` (delivered / cancelled), `dispatch_status`, restaurant status, derived `outcome_bucket` |
| **User actions / interactions** | ETA viewed, support opened, cancel attempted, ticket raised |
| **Interventions** | driver reassignment (dispatch), restaurant contact (support), priority dispatch (operations), customer credit (support) |
| **Outcomes** | delivered on time / delivered late / cancelled / unknown (missing timestamp) / excluded (chronology rule) |

## 3. Relational model (produced by `src/flasheats_pipeline/model.py`)

```mermaid
erDiagram
    dim_customer ||--o{ fact_order : places
    dim_restaurant ||--o{ fact_order : fulfils
    dim_driver ||--o{ fact_order : delivers
    fact_order ||--o{ fact_event : "has lifecycle events"
    fact_order ||--o{ fact_interaction : "customer interacts"
    fact_order ||--o{ fact_intervention : "ops intervenes"
    fact_order ||--|| order_journey : "one row per order"

    dim_customer { string customer_id PK  float lat  float lon }
    dim_restaurant { string restaurant_id PK  string cuisine  float lat  float lon  int manual_status_updates  bool coords_valid }
    dim_driver { string driver_id PK  float rating  string vehicle_type  int experience_months }
    fact_order { string order_id PK  string customer_id FK  string restaurant_id FK  string driver_id FK  string original_driver_id  datetime created_at  datetime promised_eta  datetime assigned_at  datetime estimated_pickup_at  datetime pickup_at  datetime actual_delivery_at  string final_status  bool kpi_population  float delay_min  float late_flag  string outcome_bucket  float pickup_overrun_min  float transit_overrun_min  string dq_flags }
    fact_event { string order_id FK  datetime event_time  string event_type  string actor_type  string actor_id  string source_system  string detail }
    fact_interaction { string interaction_id PK  string order_id FK  string interaction_type  datetime interaction_at  string channel  string detail  string source_system }
    fact_intervention { string intervention_id PK  string order_id FK  string intervention_type  datetime intervention_at  string initiated_by  string reason  bool before_promised_eta }
    order_journey { string order_id PK  int eta_view_count  bool support_opened  bool cancel_attempted  int ticket_count  int intervention_count  string intervention_types  bool support_contact  float late_flag  float delay_min  string outcome_bucket }
```

| Table | Grain | Primary key | Foreign keys | Built from |
|---|---|---|---|---|
| `dim_customer` | customer | `customer_id` | — | SQL `customers` (no PII columns retrieved) |
| `dim_restaurant` | restaurant | `restaurant_id` | — | SQL `restaurants` + rule RG-02 |
| `dim_driver` | driver | `driver_id` | — | SQL `drivers` |
| `fact_order` | order | `order_id` | customer, restaurant, driver (final, from Dispatch) | SQL `orders` ⟕ Dispatch API ⟕ aggregated driver events; rules → `kpi_population`, `dq_flags` |
| `fact_event` | event | (order_id, event_time, event_type, source) | `order_id` | union of all timestamped facts in every source |
| `fact_interaction` | interaction | `interaction_id` | `order_id` | app actions ∪ support tickets |
| `fact_intervention` | intervention | `intervention_id` | `order_id` | interventions log + timing vs promise/delivery |
| `order_journey` | order | `order_id` | as `fact_order` | `fact_order` ⟕ aggregated interactions ⟕ aggregated interventions |

**Cardinality rule:** every one-to-many table is aggregated to order grain *before* it is joined; each merge is checked to preserve the left row count (`data/processed/join_checks.json`). `fact_order` and `order_journey` are asserted unique on `order_id`.

## 4. Stage model used for "where does delay accumulate"

```
created_at ──dispatch_wait──► assigned_at ──pickup_wait (prep + ride to restaurant)──► pickup_at ──transit──► actual_delivery_at
                                                 estimated_pickup_at (plan)                          promised_eta (plan)
```

`delay = (pickup_at − estimated_pickup_at) + [(actual − pickup) − (promised − estimated_pickup)]`
`      =  pre-pickup overrun               +  transit overrun` — an exact identity (checked on every run).

## 5. Why not mirror the source tables?

The sources are organised by system and disagree on grain (1603 vs 1600 orders), spelling (`Delivered`/`delivered`, `handoff`/`handed_off`) and even on who the driver is. Re-organising them around the order lifecycle gives one auditable table per business question and makes the denominator of every metric explicit (`kpi_population`), which is what the KPI needs.

## 6. Pipeline architecture

The editable sources are in `docs/diagrams/`: `architecture.mmd`, `source-map.mmd` and `data-model.mmd`. GitHub renders the architecture below:

```mermaid
flowchart LR
    subgraph SRC["Client systems (source_systems/, read-only)"]
        DB[("Orders DB<br/>SQLite")]
        API["Dispatch REST API<br/>paginated · 429/500"]
        CSV["CSV exports<br/>tickets · restaurant feed<br/>app actions · interventions"]
        JSON["Driver app JSON<br/>nested events + GPS"]
    end
    EXT["Open-Meteo archive<br/>observed weather<br/>(independent source)"]
    POL["config/pipeline.yaml<br/>stakeholder-owned policy"]

    subgraph PIPE["python run_pipeline.py (10 logged stages)"]
        I["1 Ingest + raw preservation<br/>SHA-256 · raw API pages"] --> P["2 Profile"] --> C["3 Clean<br/>representation only"] --> V["4 Validate<br/>38 business rules"]
        V --> M["5 Model<br/>order-grain facts"] --> K["6 Metrics M1-M5<br/>+ independent checks + ledger"]
        K --> D["7 Decision layer<br/>trigger · ETA · fairness · weather · GPS"]
        D --> G{"8 Gate<br/>PASS / WARN / FAIL / UNKNOWN<br/>+ drift vs last run"}
        G --> MEMO["9 Decision memo"] --> O["10 Publish"]
    end

    DB --> I
    API --> I
    CSV --> I
    JSON --> I
    EXT --> I
    POL -. thresholds .-> PIPE

    O --> OUT["output/<br/>evidence table · metrics · insights<br/>data-quality report · gate · memo · charts"]
    O --> PROC["data/processed/<br/>fact tables + SQLite model"]
    OUT --> DASH["Streamlit dashboard<br/>app/dashboard.py"]
    PROC --> DASH
    G -- FAIL --> STOP["not published<br/>kept in output/runs/&lt;run_id&gt;"]
```
