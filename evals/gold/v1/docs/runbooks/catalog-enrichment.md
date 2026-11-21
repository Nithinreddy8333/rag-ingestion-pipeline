# catalog-enrichment runbook

## Overview

The catalog-enrichment pipeline is built with dbt and writes to Snowflake. It reads from churn-scores and is maintained by team Helix.

## Schedule and SLA

The job runs every 60 minutes, with the first run of the day at 23:00 UTC. Output must land within 24 hours of the source closing. Output partitions are retained for 180 days.

## Failure modes

If duplicate records appear after a retry, run the idempotent merge with the dedupe key and compare row counts.

If late-arriving events miss the window, widen the watermark to two hours and backfill the affected partition.

## Restart procedure

Stop the catalog-enrichment job from the scheduler, confirm no task is still writing to Snowflake, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Amara Okoye and the backup is Tomas Reyes. Alerts go to #catalog-alerts. For urgent issues call the on-call line at +1-555-948-3645 or write to catalog-enrichment-oncall@example.com.
