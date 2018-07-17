import argparse
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from jira import JIRA
from jira.exceptions import JIRAError
import json

# json based config, mainly jira credentials and Influx credentials
config_filepath = 'config.json'
# Jira query to get the epic tickets == milestones
jql = 'project in (INFRA, VIALA, VIALJS, GRID, VIALI, VM) AND issuetype = Epic AND status = "In Progress"'
# Number of jira issues to query per request
jql_issue_count = 50


def main(verbose=False, dryrun=False):
    # Get the config file.
    with open(config_filepath) as json_config_file:
        config = json.load(json_config_file)
        
    # Get the Jira Influx points. These will be ready to be passed through to Influx.
    # Catching jira errors here, because the error messages consist of a whole webpage.
    # Besides that: all 5 invocations of the JIRA api can throw a JIRAError.
    try:
        epics_json = get_jira_points(config, verbose, dryrun)
    except JIRAError as e:
        if e.status_code == 401:
            print 'Error: Jira authorisation problem'
            return 1
        elif e.status_code == 404:
            print 'Error: Wrong jira url'
            return 1
        else:
            raise
    
    # Connect to the Influxdb.
    client = InfluxDBClient(
        config['influxdb']['host'],
        config['influxdb']['port'],
        config['influxdb']['user'],
        config['influxdb']['pass'],
        config['influxdb']['database'],
        timeout=10,
        ssl=True,
        verify_ssl=True)
    # Write the Influx points.
    client.write_points(epics_json)
    
    if dryrun:
        print 'Everything looks good!'
        

def get_jira_points(config, verbose=False, dryrun=False):
    """
    This function needs the configuration file containing the Jira connection.
    It outputs data in infux (points) format. Verbose=True to output the Jira
    milestone information to the terminal.
    """
    epics_json = []
    # Connect to jira
    jira_api = JIRA(config['jira']['host'], basic_auth=(config['jira']['user'], config['jira']['pass']), max_retries=0)
    
    if dryrun:
        return []

    # First get all Epics (milestones).
    epics = jira_api.search_issues(jql)
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
            version = jira_api.version(epic.fields.fixVersions[0].id)
        else:
            version = None
        
        # Get all tickets within the epic. A maximum of 100 tickets and a
        # default of 50 tickets can be queried from Jira in 1 request.
        issues = jira_api.search_issues('"Epic link"=%s' % epic.key, maxResults=jql_issue_count)
        loopcount = issues.total/jql_issue_count + 1
        total_tickets = issues.total
        for i in xrange(1, loopcount):
            issues.extend(jira_api.search_issues('"Epic link"=%s' % epic.key, startAt=jql_issue_count*i, maxResults=jql_issue_count))
            i += 1
        
        # Having all tickets, get all information about the tickets.
        open_tickets = 0
        resolved_tickets = 0
        for issue in issues:
            if issue.fields.timespent:
                time_spent += issue.fields.timespent
            if issue.fields.timeestimate:
                time_estimate += issue.fields.timeestimate
            if issue.fields.status.name in ('Open', 'Reopened'):
                open_tickets += 1
            elif issue.fields.status.name in ('Closed', 'Resolved', 'In Releasebranch'):
                resolved_tickets += 1
        
        # Print stuff if verbose.
        if verbose:
            print '%s (%s)' % (epic.fields.customfield_10501, epic.key)
            if version:
                print 'startdate: %s, enddate: %s' % (version.startDate, version.releaseDate)
            print 'time spent: %d' % int(time_spent/3600)
            print 'time estimate: %d'% int(time_estimate/3600)
            print 'total: %d' % total_tickets
            print 'open: %d' % open_tickets
            print 'in progress: %d' % (total_tickets - open_tickets - resolved_tickets)
            print 'resolved: %d' % resolved_tickets
            print '------------------------'
        
        # Create the json.
        epics_json.append(
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
        epics_json.append(
            {
                "measurement": "milestone-tickets",
                "tags": {
                    "product": "voipgrid",
                    "team": epic.fields.project.key,
                    "milestone": epic.key
                },
                "fields": {
                    "open": open_tickets,
                    "progress": (total_tickets - open_tickets - resolved_tickets),
                    "resolved": resolved_tickets
                }
            }
        )
        if version:
            epics_json.append(
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
    return epics_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true', help='Output the jira milestone information.')
    parser.add_argument('-d', '--dryrun', action='store_true', help='Run the script without actually querying Jira or saving points to InfluxDB. The purpose of the dryrun is to test the connections.')
    args = parser.parse_args()
    main(verbose=args.verbose, dryrun=args.dryrun)
