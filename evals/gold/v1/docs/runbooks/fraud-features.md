# fraud-features runbook

## Overview

The fraud-features pipeline is built with Kafka Streams and writes to Delta Lake on S3. It reads from currency-rates and is maintained by team Borealis.

## Schedule and SLA

The job runs once a day, with the first run of the day at 10:00 UTC. Output must land within 6 hours of the source closing. Output partitions are retained for 180 days.

## Failure modes

If late-arriving events miss the window, widen the watermark to two hours and backfill the affected partition.

If the source API starts rate limiting, halve the batch size, enable the backoff flag, and resume from the last checkpoint.

## Restart procedure

Stop the fraud-features job from the scheduler, confirm no task is still writing to Delta Lake on S3, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Ines Duarte and the backup is Amara Okoye. Alerts go to #fraud-alerts. For urgent issues call the on-call line at +1-555-174-2934 or write to fraud-features-oncall@example.com.
