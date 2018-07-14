# Jira stats

This script collects all relevant data about our milestones from Jira and puts it into influxDB. It is intended to run every evening at 20:00, so a daily progress of the milestone will be gained.

Collected data:
* time spent on the milestone
* remaining time estimate of the milestone
* number of open tickets
* number of tickets in progress
* number of resolved tickets
* start date of the milestone
* end date of the milestone
