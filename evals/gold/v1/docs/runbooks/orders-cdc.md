# orders-cdc runbook

## Overview

The orders-cdc pipeline is built with Spark and writes to Redshift. It reads from warehouse-loader and is maintained by team Garnet.

## Schedule and SLA

The job runs every 60 minutes, with the first run of the day at 03:00 UTC. Output must land within 12 hours of the source closing. Output partitions are retained for 30 days.

## Failure modes

If the checkpoint store fills up, expire checkpoints older than three days and restart the consumer group.

If the source API starts rate limiting, halve the batch size, enable the backoff flag, and resume from the last checkpoint.

## Restart procedure

Stop the orders-cdc job from the scheduler, confirm no task is still writing to Redshift, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Omar Haddad and the backup is Priya Nair. Alerts go to #orders-alerts. For urgent issues call the on-call line at +1-555-319-1614 or write to orders-cdc-oncall@example.com.
