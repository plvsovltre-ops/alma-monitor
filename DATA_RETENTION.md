# Data-retention policy for deployments

The repository has no production field data. In a deployed ALMA Monitor:

- the downloaded Mergin project is temporary working data for one job;
- incident state and delivery evidence are kept in private Cloud Storage;
- completed summaries may be kept in a restricted Google Sheet;
- service logs are kept according to the cloud project's logging policy;
- the authoritative field record remains subject to the Mergin project policy.

The reference code does not yet erase durable incident state or registry rows
automatically. Before allowing public data collection, the operator must approve
and enforce concrete retention periods, access roles, backup rules, and a tested
deletion process. Until that control exists, do not promise automatic deletion.

Deletion must preserve only the minimum audit information required by applicable
law and an approved operational policy. A deletion request must also be checked
against copies held by configured processors and against any legal preservation
obligation.
