# ad-attribution runbook

## Overview

The ad-attribution pipeline is built with Kafka Streams and writes to BigQuery. It reads from pricing-sync and is maintained by team Fjord.

## Schedule and SLA

The job runs every 180 minutes, with the first run of the day at 07:00 UTC. Output must land within 24 hours of the source closing. Output partitions are retained for 90 days.

## Failure modes

If the warehouse credentials rotate, pull the new secret from the vault path and redeploy the connection.

If late-arriving events miss the window, widen the watermark to two hours and backfill the affected partition.

## Restart procedure

Stop the ad-attribution job from the scheduler, confirm no task is still writing to BigQuery, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Omar Haddad and the backup is Jonas Weber. Alerts go to #ad-alerts. For urgent issues call the on-call line at +1-555-630-9073 or write to ad-attribution-oncall@example.com.
