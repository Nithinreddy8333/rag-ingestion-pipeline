# recommendation-batch runbook

## Overview

The recommendation-batch pipeline is built with Flink and writes to Iceberg on GCS. It reads from inventory-snapshot and is maintained by team Borealis.

## Schedule and SLA

The job runs every 360 minutes, with the first run of the day at 16:00 UTC. Output must land within 12 hours of the source closing. Output partitions are retained for 365 days.

## Failure modes

If duplicate records appear after a retry, run the idempotent merge with the dedupe key and compare row counts.

If the warehouse credentials rotate, pull the new secret from the vault path and redeploy the connection.

## Restart procedure

Stop the recommendation-batch job from the scheduler, confirm no task is still writing to Iceberg on GCS, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Kenji Sato and the backup is Priya Nair. Alerts go to #recommendation-alerts. For urgent issues call the on-call line at +1-555-673-1930 or write to recommendation-batch-oncall@example.com.
