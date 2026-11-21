# clickstream-sessionizer runbook

## Overview

The clickstream-sessionizer pipeline is built with Kafka Streams and writes to Snowflake. It reads from fraud-features and is maintained by team Ember.

## Schedule and SLA

The job runs every 60 minutes, with the first run of the day at 18:00 UTC. Output must land within 12 hours of the source closing. Output partitions are retained for 90 days.

## Failure modes

If the warehouse credentials rotate, pull the new secret from the vault path and redeploy the connection.

If the source API starts rate limiting, halve the batch size, enable the backoff flag, and resume from the last checkpoint.

## Restart procedure

Stop the clickstream-sessionizer job from the scheduler, confirm no task is still writing to Snowflake, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Rahul Menon and the backup is Mei Tanaka. Alerts go to #clickstream-alerts. For urgent issues call the on-call line at +1-555-695-4078 or write to clickstream-sessionizer-oncall@example.com.
