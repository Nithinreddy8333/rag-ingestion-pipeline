# loyalty-points runbook

## Overview

The loyalty-points pipeline is built with Spark and writes to BigQuery. It reads from currency-rates and is maintained by team Garnet.

## Schedule and SLA

The job runs every 30 minutes, with the first run of the day at 14:00 UTC. Output must land within 1 hours of the source closing. Output partitions are retained for 180 days.

## Failure modes

If the upstream schema changes without notice, pause the job, regenerate the schema contract, and replay the dead-letter queue.

If duplicate records appear after a retry, run the idempotent merge with the dedupe key and compare row counts.

## Restart procedure

Stop the loyalty-points job from the scheduler, confirm no task is still writing to BigQuery, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Priya Nair and the backup is Jonas Weber. Alerts go to #loyalty-alerts. For urgent issues call the on-call line at +1-555-153-2677 or write to loyalty-points-oncall@example.com.
