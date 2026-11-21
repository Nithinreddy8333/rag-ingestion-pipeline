# Backfill Playbook

## Before you start

Announce the backfill in the data-changes channel and estimate the compute cost. Anything above 2 credits needs approval.

## Running it

Backfill one partition at a time, oldest first, with the write-audit-publish pattern so readers never see partial data.

## Afterwards

Reconcile row counts against the source, rerun downstream tests, and close the announcement thread with the totals.
