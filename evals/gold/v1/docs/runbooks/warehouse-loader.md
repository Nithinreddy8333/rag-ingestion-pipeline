# warehouse-loader runbook

## Overview

The warehouse-loader pipeline is built with Spark and writes to Delta Lake on S3. It reads from recommendation-batch and is maintained by team Helix.

## Schedule and SLA

The job runs every 60 minutes, with the first run of the day at 20:00 UTC. Output must land within 24 hours of the source closing. Output partitions are retained for 30 days.

## Failure modes

If the checkpoint store fills up, expire checkpoints older than three days and restart the consumer group.

If the source API starts rate limiting, halve the batch size, enable the backoff flag, and resume from the last checkpoint.

## Restart procedure

Stop the warehouse-loader job from the scheduler, confirm no task is still writing to Delta Lake on S3, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Ines Duarte and the backup is Ines Duarte. Alerts go to #warehouse-alerts. For urgent issues call the on-call line at +1-555-222-7365 or write to warehouse-loader-oncall@example.com.
