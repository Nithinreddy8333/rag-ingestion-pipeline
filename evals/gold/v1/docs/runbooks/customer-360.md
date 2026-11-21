# customer-360 runbook

## Overview

The customer-360 pipeline is built with Dagster assets and writes to Snowflake. It reads from audit-archiver and is maintained by team Helix.

## Schedule and SLA

The job runs every 360 minutes, with the first run of the day at 17:00 UTC. Output must land within 4 hours of the source closing. Output partitions are retained for 180 days.

## Failure modes

If the checkpoint store fills up, expire checkpoints older than three days and restart the consumer group.

If the source API starts rate limiting, halve the batch size, enable the backoff flag, and resume from the last checkpoint.

## Restart procedure

Stop the customer-360 job from the scheduler, confirm no task is still writing to Snowflake, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Rahul Menon and the backup is Priya Nair. Alerts go to #customer-alerts. For urgent issues call the on-call line at +1-555-458-9137 or write to customer-360-oncall@example.com.
