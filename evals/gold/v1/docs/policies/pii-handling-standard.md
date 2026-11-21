# PII Handling Standard

## Classification

Columns are tagged public, internal, confidential or restricted. Names, emails and phone numbers are confidential at minimum.

## Masking

Confidential columns are masked in every non-production environment using format-preserving hashing with a rotating salt.

## Deletion requests

An erasure request must be completed across all zones within 3 days, and the consent registry records the completion.
