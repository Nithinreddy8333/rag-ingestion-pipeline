# returns-ledger runbook

## Overview

The returns-ledger pipeline is built with Flink and writes to BigQuery. It reads from tax-calculator and is maintained by team Helix.

## Schedule and SLA

The job runs every 360 minutes, with the first run of the day at 13:00 UTC. Output must land within 4 hours of the source closing. Output partitions are retained for 365 days.

## Failure modes

If the upstream schema changes without notice, pause the job, regenerate the schema contract, and replay the dead-letter queue.

If the source API starts rate limiting, halve the batch size, enable the backoff flag, and resume from the last checkpoint.

## Restart procedure

Stop the returns-ledger job from the scheduler, confirm no task is still writing to BigQuery, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Rahul Menon and the backup is Kenji Sato. Alerts go to #returns-alerts. For urgent issues call the on-call line at +1-555-799-7233 or write to returns-ledger-oncall@example.com.
