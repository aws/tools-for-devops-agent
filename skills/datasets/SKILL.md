---
name: datasets
description: Dataset discovery and source-selection guidance for DataPrime system and user-defined datasets. Load when the user asks what datasets exist, how to use `list_datasets`, how to query `system/...` or `default/...` sources, or how to inspect a specific system dataset after discovery. The `dataprime` skill should be loaded alongside this skill.
metadata:
  author: coralogix
  version: 1.0.0
  summary: Dataset discovery and source-selection guidance for DataPrime system and user-defined datasets. Load when the user asks what datasets exist, how to use `list_datasets`, how to query `system/...` or `d
  tier: partner-managed
  agent_types: GENERIC
---

# Datasets Skill - Discovering system and user-defined datasets

## Dataset categories

Use `list_datasets` to discover available datasets:

- **System datasets**: `source system/<dataset>`
- **User-defined datasets**: `source default/<dataset>`

## Core workflow

1. Call `list_datasets` first.
2. Use the exact `source ...` path returned by `list_datasets`. Never guess a dataset name.
3. For any `system/...` dataset, always call `get_system_dataset_info` to retrieve dataset information and schema guidance before querying it.
4. Load or use `dataprime` skill to build the actual query correctly.
5. If the user's question should be answered from a specific dataset, call `query_dataprime` with that dataset in the `source ...` clause.

## When to use `get_system_dataset_info`

Use `get_system_dataset_info` only for `system/...` datasets, and always use it after discovery before querying a system dataset.

It is the required follow-up step for system datasets because it is intended to provide:
- what a specific system dataset is for
- whether a specific system dataset should be queried
- schema-oriented information for a specific system dataset

Do not use it for `default/...` datasets. In this scope, there is no matching detailed-info tool for user-defined datasets yet.

## Important notes

- `search_for_fields` is only for logs and spans, not arbitrary datasets.
- For a known system dataset with dedicated business logic or schema guidance, load the relevant domain skill as well.
- For fleet case analytics on `system/labs.cases.state_updates`, also load `case-analytics`.
