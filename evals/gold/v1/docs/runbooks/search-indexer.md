# search-indexer runbook

## Overview

The search-indexer pipeline is built with Spark and writes to Delta Lake on S3. It reads from orders-cdc and is maintained by team Dynamo.

## Schedule and SLA

The job runs every 30 minutes, with the first run of the day at 18:00 UTC. Output must land within 4 hours of the source closing. Output partitions are retained for 180 days.

## Failure modes

If the source API starts rate limiting, halve the batch size, enable the backoff flag, and resume from the last checkpoint.

If late-arriving events miss the window, widen the watermark to two hours and backfill the affected partition.

## Restart procedure

Stop the search-indexer job from the scheduler, confirm no task is still writing to Delta Lake on S3, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Omar Haddad and the backup is Jonas Weber. Alerts go to #search-alerts. For urgent issues call the on-call line at +1-555-249-7864 or write to search-indexer-oncall@example.com.
