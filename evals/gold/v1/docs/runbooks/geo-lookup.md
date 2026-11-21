# geo-lookup runbook

## Overview

The geo-lookup pipeline is built with dbt and writes to Redshift. It reads from consent-registry and is maintained by team Helix.

## Schedule and SLA

The job runs every 30 minutes, with the first run of the day at 17:00 UTC. Output must land within 1 hours of the source closing. Output partitions are retained for 30 days.

## Failure modes

If the source API starts rate limiting, halve the batch size, enable the backoff flag, and resume from the last checkpoint.

If the warehouse credentials rotate, pull the new secret from the vault path and redeploy the connection.

## Restart procedure

Stop the geo-lookup job from the scheduler, confirm no task is still writing to Redshift, then start it with the resume flag so it continues from the last committed offset. Never restart with a full refresh during business hours.

## Contacts

The service owner is Omar Haddad and the backup is Lena Brandt. Alerts go to #geo-alerts. For urgent issues call the on-call line at +1-555-205-9627 or write to geo-lookup-oncall@example.com.
