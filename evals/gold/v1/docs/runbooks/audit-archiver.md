# audit-archiver runbook

## Overview

The audit-archiver pipeline is built with Spark and writes to Delta Lake on S3. It reads from churn-scores and is maintained by team Helix.

## Schedule and SLA

The job runs every 360 minutes, with the first run of the day at 10:00 UTC. Output must land within 12 hours of the source closing. Output partitions are retained for 730 days.

## Failure modes

If the upstream schema changes without notice, pause the job, regenerate the schema contract, and replay the dead-letter queue.

If late-arriving events miss the window, widen the watermark to two hours and backfill the affected partition.

## Restart procedure

Stop the audit-archiver job from the scheduler, confirm no task is still writing to Delta Lake on S3, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Kenji Sato and the backup is Priya Nair. Alerts go to #audit-alerts. For urgent issues call the on-call line at +1-555-304-5541 or write to audit-archiver-oncall@example.com.
