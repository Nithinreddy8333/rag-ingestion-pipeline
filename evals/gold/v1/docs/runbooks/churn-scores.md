# churn-scores runbook

## Overview

The churn-scores pipeline is built with Kafka Streams and writes to Postgres. It reads from clickstream-sessionizer and is maintained by team Ember.

## Schedule and SLA

The job runs once a day, with the first run of the day at 14:00 UTC. Output must land within 4 hours of the source closing. Output partitions are retained for 180 days.

## Failure modes

If the checkpoint store fills up, expire checkpoints older than three days and restart the consumer group.

If duplicate records appear after a retry, run the idempotent merge with the dedupe key and compare row counts.

## Restart procedure

Stop the churn-scores job from the scheduler, confirm no task is still writing to Postgres, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Jonas Weber and the backup is Clara Voss. Alerts go to #churn-alerts. For urgent issues call the on-call line at +1-555-325-2673 or write to churn-scores-oncall@example.com.
