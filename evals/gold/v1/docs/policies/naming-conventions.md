# Naming Conventions

## Tables

Staging tables start with stg_, facts with fct_ and dimensions with dim_. Names are snake_case and singular nouns are avoided.

## Columns

Timestamps end in _at, dates in _date and booleans start with is_ or has_. Money columns state the currency in a sibling column.

## Jobs

Job names follow domain-entity-action, for example orders-cdc or billing-export, and never include an environment name.
