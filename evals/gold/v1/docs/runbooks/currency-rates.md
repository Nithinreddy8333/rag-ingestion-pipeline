# currency-rates runbook

## Overview

The currency-rates pipeline is built with Kafka Streams and writes to BigQuery. It reads from catalog-enrichment and is maintained by team Ember.

## Schedule and SLA

The job runs every 60 minutes, with the first run of the day at 18:00 UTC. Output must land within 4 hours of the source closing. Output partitions are retained for 730 days.

## Failure modes

If the source API starts rate limiting, halve the batch size, enable the backoff flag, and resume from the last checkpoint.

If the upstream schema changes without notice, pause the job, regenerate the schema contract, and replay the dead-letter queue.

## Restart procedure

Stop the currency-rates job from the scheduler, confirm no task is still writing to BigQuery, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Jonas Weber and the backup is Amara Okoye. Alerts go to #currency-alerts. For urgent issues call the on-call line at +1-555-954-3147 or write to currency-rates-oncall@example.com.
