# Data Dictionary

All data is synthetic, generated in code (reproducible via a fixed random seed).
It simulates a warehouse supplying a production line: 20 parts over 30 days.

## Table: pfep (Plan for Every Part — one row per part)

| Column | Type | Description |
|--------|------|-------------|
| part_id | text | Unique part identifier (e.g. P-1001) |
| description | text | Part description |
| location | text | Storage location (WH-A, WH-B, Line-1, Line-2) |
| avg_daily_demand | integer | Average units consumed per day |
| lead_time_days | integer | Days for replenishment to arrive after ordering |
| reorder_point | integer | Stock level that triggers a reorder (demand x lead time + safety buffer) |
| max_stock | integer | Full-shelf / replenish-up-to level |

## Table: stock_daily (daily stock ledger — one row per part per day)

| Column | Type | Description |
|--------|------|-------------|
| part_id | text | Part identifier (links to pfep.part_id) |
| date | date | Calendar day |
| opening | integer | Stock at the start of the day |
| consumed | integer | Units consumed that day |
| received | integer | Units received (replenishment) that day |
| closing | integer | Stock at the end of the day (opening - consumed + received, floored at 0) |

## Relationship
`stock_daily.part_id` joins to `pfep.part_id`. Current stock (latest day's
`closing`) is compared against `pfep.reorder_point` to generate alerts.

## Derived metric
Days of coverage = current stock / avg_daily_demand — estimated days until a
part runs out at its average consumption rate.
