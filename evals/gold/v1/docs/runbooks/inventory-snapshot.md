# inventory-snapshot runbook

## Overview

The inventory-snapshot pipeline is built with Airflow with Python operators and writes to Iceberg on GCS. It reads from geo-lookup and is maintained by team Atlas.

## Schedule and SLA

The job runs every 180 minutes, with the first run of the day at 17:00 UTC. Output must land within 4 hours of the source closing. Output partitions are retained for 365 days.

## Failure modes

If late-arriving events miss the window, widen the watermark to two hours and backfill the affected partition.

If the upstream schema changes without notice, pause the job, regenerate the schema contract, and replay the dead-letter queue.

## Restart procedure

Stop the inventory-snapshot job from the scheduler, confirm no task is still writing to Iceberg on GCS, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Ines Duarte and the backup is Jonas Weber. Alerts go to #inventory-alerts. For urgent issues call the on-call line at +1-555-564-6924 or write to inventory-snapshot-oncall@example.com.
