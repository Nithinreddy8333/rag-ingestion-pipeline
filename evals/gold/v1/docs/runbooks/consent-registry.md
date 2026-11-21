# consent-registry runbook

## Overview

The consent-registry pipeline is built with Kafka Streams and writes to BigQuery. It reads from customer-360 and is maintained by team Garnet.

## Schedule and SLA

The job runs every 360 minutes, with the first run of the day at 16:00 UTC. Output must land within 1 hours of the source closing. Output partitions are retained for 365 days.

## Failure modes

If late-arriving events miss the window, widen the watermark to two hours and backfill the affected partition.

If the warehouse credentials rotate, pull the new secret from the vault path and redeploy the connection.

## Restart procedure

Stop the consent-registry job from the scheduler, confirm no task is still writing to BigQuery, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Kenji Sato and the backup is Mei Tanaka. Alerts go to #consent-alerts. For urgent issues call the on-call line at +1-555-723-1064 or write to consent-registry-oncall@example.com.
