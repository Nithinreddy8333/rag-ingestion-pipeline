# email-events runbook

## Overview

The email-events pipeline is built with Kafka Streams and writes to Iceberg on GCS. It reads from recommendation-batch and is maintained by team Cobalt.

## Schedule and SLA

The job runs once a day, with the first run of the day at 21:00 UTC. Output must land within 1 hours of the source closing. Output partitions are retained for 365 days.

## Failure modes

If the warehouse credentials rotate, pull the new secret from the vault path and redeploy the connection.

If the checkpoint store fills up, expire checkpoints older than three days and restart the consumer group.

## Restart procedure

Stop the email-events job from the scheduler, confirm no task is still writing to Iceberg on GCS, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Clara Voss and the backup is Kenji Sato. Alerts go to #email-alerts. For urgent issues call the on-call line at +1-555-917-7428 or write to email-events-oncall@example.com.
