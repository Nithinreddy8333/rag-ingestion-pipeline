# payments-reconciler runbook

## Overview

The payments-reconciler pipeline is built with Spark and writes to Redshift. It reads from warehouse-loader and is maintained by team Cobalt.

## Schedule and SLA

The job runs once a day, with the first run of the day at 09:00 UTC. Output must land within 1 hours of the source closing. Output partitions are retained for 180 days.

## Failure modes

If the warehouse credentials rotate, pull the new secret from the vault path and redeploy the connection.

If the checkpoint store fills up, expire checkpoints older than three days and restart the consumer group.

## Restart procedure

Stop the payments-reconciler job from the scheduler, confirm no task is still writing to Redshift, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Clara Voss and the backup is Kenji Sato. Alerts go to #payments-alerts. For urgent issues call the on-call line at +1-555-475-3736 or write to payments-reconciler-oncall@example.com.
