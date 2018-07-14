from influxdb import InfluxDBClient
from jira import JIRA
import json

# json based config, mainly jira credentials and Influx credentials
config_filepath = 'config.json'
# Jira query to get the 
jql = 'project in (INFRA, VIALA, VIALJS, GRID, VIALI, VM) AND issuetype = Epic AND status = "In Progress"'
jql_issue_count = 50


def main(verbose=True):
    # Get the config file.
    with open(config_filepath) as json_data_file:
        config = json.load(json_data_file)
    # Get the Jira Influx points. These will be ready to be passed through to Influx.
    json_body = get_jira_points(config, verbose)
    # Connect to the Influxdb.
    client = InfluxDBClient(
        config['influxdb']['host'],
        config['influxdb']['port'],
        config['influxdb']['user'],
        config['influxdb']['pass'],
        config['influxdb']['database'])
    # Write the Influx points.
    client.write_points(json_body)


def get_jira_points(config, verbose=False):
    """
    This function needs the configuration file containing the Jira connection.
    It outputs data in infux (points) format. Verbose=True to output the Jira
    milestone information to the terminal.
    """
    json_body = []
    jira = JIRA(config['jira']['host'], basic_auth=(config['jira']['user'], config['jira']['pass']))
    # First get all Epics (milestones).
    epics = jira.search_issues(jql)
    if verbose:
        print '------------------------'
    
    # Loop over the epics to collect all information.
    for epic in epics:
        time_spent = 0
        time_estimate = 0
        
        # Add the timespent and estimation of the epic ticket itself.
        if epic.fields.timespent:
            time_spent += epic.fields.timespent
        if epic.fields.timeestimate:
            time_estimate += epic.fields.timeestimate
        # Get the version for the start and enddate
        if len(epic.fields.fixVersions):
            version = jira.version(epic.fields.fixVersions[0].id)
        else:
            version = False
        
        # Get all tickets within the epic. A maximum of 100 tickets and a
        # default of 50 tickets can be queried from Jira in 1 request.
        issues = jira.search_issues('"Epic link"=%s' % epic.key, maxResults=jql_issue_count)
        loopcount = issues.total/jql_issue_count + 1
        total = issues.total
        i = 1
        while i < loopcount:
            issues.extend(jira.search_issues('"Epic link"=%s' % epic.key, startAt=jql_issue_count*i, maxResults=jql_issue_count))
            i += 1
        
        # Having all tickets, get all information about the tickets.
        open = 0
        resolved = 0
        for issue in issues:
            if issue.fields.timespent:
                time_spent += issue.fields.timespent
            if issue.fields.timeestimate:
                time_estimate += issue.fields.timeestimate
            if issue.fields.status.name == ('Open', 'Reopened'):
                open += 1
            elif issue.fields.status.name in ('Closed', 'Resolved', 'In Releasebranch'):
                resolved += 1
        
        # Print stuff if verbose.
        if verbose:
            print '%s (%s)' % (epic.fields.customfield_10501, epic.key)
            if version:
                print 'startdate: %s, enddate: %s' % (version.startDate, version.releaseDate)
            print 'time spent: %d' % int(time_spent/3600)
            print 'time estimate: %d'% int(time_estimate/3600)
            print 'total: %d' % total
            print 'open: %d' % open
            print 'in progress: %d' % (total - open - resolved)
            print 'resolved: %d' % resolved
            print '------------------------'
        
        # Create the json.
        json_body.append(
            {
                "measurement": "milestone-hours",
                "tags": {
                    "product": "voipgrid",
                    "team": epic.fields.project.key,
                    "milestone": epic.key
                },
                "fields": {
                    "time_spent": time_spent/3600,
                    "time_estimate": time_estimate/3600
                }
            }
        )
        json_body.append(
            {
                "measurement": "milestone-tickets",
                "tags": {
                    "product": "voipgrid",
                    "team": epic.fields.project.key,
                    "milestone": epic.key
                },
                "fields": {
                    "open": open,
                    "progress": (total - open - resolved),
                    "resolved": resolved
                }
            }
        )
        if version:
            json_body.append(
                {
                    "measurement": "milestone-date",
                    "tags": {
                        "product": "voipgrid",
                        "team": epic.fields.project.key,
                        "milestone": epic.key
                    },
                    "fields": {
                        "startdate": str(version.startDate),
                        "enddate": str(version.releaseDate)
                    }
                }
            )
    return json_body


if __name__ == "__main__":
    main()
