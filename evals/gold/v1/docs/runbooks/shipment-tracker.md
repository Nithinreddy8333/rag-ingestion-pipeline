# shipment-tracker runbook

## Overview

The shipment-tracker pipeline is built with Kafka Streams and writes to Snowflake. It reads from fraud-features and is maintained by team Helix.

## Schedule and SLA

The job runs every 15 minutes, with the first run of the day at 15:00 UTC. Output must land within 2 hours of the source closing. Output partitions are retained for 180 days.

## Failure modes

If the checkpoint store fills up, expire checkpoints older than three days and restart the consumer group.

If the upstream schema changes without notice, pause the job, regenerate the schema contract, and replay the dead-letter queue.

## Restart procedure

Stop the shipment-tracker job from the scheduler, confirm no task is still writing to Snowflake, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Lena Brandt and the backup is Mei Tanaka. Alerts go to #shipment-alerts. For urgent issues call the on-call line at +1-555-856-5056 or write to shipment-tracker-oncall@example.com.
