# support-tickets-etl runbook

## Overview

The support-tickets-etl pipeline is built with Airflow with Python operators and writes to Delta Lake on S3. It reads from customer-360 and is maintained by team Borealis.

## Schedule and SLA

The job runs every 15 minutes, with the first run of the day at 23:00 UTC. Output must land within 24 hours of the source closing. Output partitions are retained for 90 days.

## Failure modes

If duplicate records appear after a retry, run the idempotent merge with the dedupe key and compare row counts.

If the checkpoint store fills up, expire checkpoints older than three days and restart the consumer group.

## Restart procedure

Stop the support-tickets-etl job from the scheduler, confirm no task is still writing to Delta Lake on S3, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Clara Voss and the backup is Rahul Menon. Alerts go to #support-alerts. For urgent issues call the on-call line at +1-555-230-1451 or write to support-tickets-etl-oncall@example.com.
