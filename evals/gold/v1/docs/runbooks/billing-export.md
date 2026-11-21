# billing-export runbook

## Overview

The billing-export pipeline is built with Spark and writes to Redshift. It reads from clickstream-sessionizer and is maintained by team Borealis.

## Schedule and SLA

The job runs every 30 minutes, with the first run of the day at 03:00 UTC. Output must land within 24 hours of the source closing. Output partitions are retained for 730 days.

## Failure modes

If the upstream schema changes without notice, pause the job, regenerate the schema contract, and replay the dead-letter queue.

If the source API starts rate limiting, halve the batch size, enable the backoff flag, and resume from the last checkpoint.

## Restart procedure

Stop the billing-export job from the scheduler, confirm no task is still writing to Redshift, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Kenji Sato and the backup is Rahul Menon. Alerts go to #billing-alerts. For urgent issues call the on-call line at +1-555-690-7499 or write to billing-export-oncall@example.com.
