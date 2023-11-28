from logging import Logger
import logging
from fastapi import FastAPI
import requests
import os
import json
from starlette_exporter import PrometheusMiddleware, handle_metrics
from prometheus_client import Gauge, Info
from jira import JIRA
from icecream import ic
from collections import Counter
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

JIRA_API_KEY = os.environ.get("JIRA_API_KEY")
JIRA_USER = os.environ.get("JIRA_USER")
JIRA_HOST = os.environ.get("JIRA_HOST")
TEMPO_SERVER = os.environ.get("TEMPO_SERVER")

#jira = JIRA(server=JIRA_HOST, basic_auth=(JIRA_USER,JIRA_API_KEY))

app = FastAPI(title="JiraKPIs")

resource = Resource(attributes={"service.name": "jiraKPIs"})
tracer = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer)
tracer.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"http://{TEMPO_SERVER}:4317")))

# tracer = trace.get_tracer("JiraKPIs")
LoggingInstrumentor().instrument()
FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer)
app.add_middleware(PrometheusMiddleware)

tracer = trace.get_tracer(__name__)

with open('config.json','r') as f:
    CONFIG_MAP = json.load(f)

@app.get("/")
async def read_root():
    return {"projects": "hello"}

ISSUE_WEIGHT = Gauge("jirakpis_Users_by_weight","Issue Weight by User",["group","sprint","user"])
ISSUE_STATUS = Gauge("jirakpis_Issues_by_status","Issue Counts by Status",["group","sprint","status"])
ISSUE_TYPE = Gauge("jirakpis_Issues_by_type","Issue Counts by Type",["group","sprint","type"])
TICKETS_USER = Gauge("jirakpis_tickets_by_user","Ticket Count by User",["group","sprint","user"])
EPIC_STATUS = Gauge("jirakpis_epics_by_status","Epic Counts by Status",["group","status"])
BACKLOG_ISSUE_COUNT = Gauge("jirakpis_summary_issue_backlog_count","Number of issues in the Backlog",["group"])
SPRINT_ISSUE_COUNT = Gauge("jirakpis_summary_issue_count","Number of issues in the sprint",["group","sprint"])
FUTURE_ISSUE_COUNT = Gauge("jirakpis_future_issue_count","Number of issues in future sprints",["group","sprint"])
SPRINT_WEIGHT = Gauge("jirakpis_summary_weight","sprint issues weight",["group","sprint"])
SPRINT_COUNT_PRIORITY = Gauge("jirakpis_summary_count_priority","Ticket Count by Priority",["group","sprint","priority"])
SPRINT_EPIC_COUNT = Gauge("jirakpis_summary_count_epic","Ticket Count by Epic",["group","sprint","epic"])
TEAMS_INFO = Gauge("jirakpis_teams_info","List of projects",["team"])

async def get_projects(CONFIG_MAP,jira):
    selectedProjects = []
    projects = jira.projects()
    for proj in projects:
        if proj.key in CONFIG_MAP.keys():
            TEAMS_INFO.labels(proj).set(1)
            selectedProjects.append(proj)
    
    return selectedProjects

async def get_team_issues(activeSprints,futureSprints,jira):
    issues = {}
    for team in activeSprints:
        #let's get current sprint info
        issues[team] = {}
        issues[team]['current'] = {}
        issues[team]['future'] = {}
        for sprint in activeSprints[team]:
            sprintJql = f"project = {team} and sprint = {sprint.id}"
            issues[team]['current'][sprint.name] = jira.search_issues(jql_str=sprintJql,maxResults=False)
        for sprint in futureSprints[team]:
            sprintJql = f"project = {team} and sprint = {sprint.id}"
            issues[team]['future'][sprint.name] = jira.search_issues(jql_str=sprintJql,maxResults=False)
    return issues

async def get_team_boards(projects,jira):
    activeSprints = {}
    futureSprints = {}

    for team in projects:
        boardsAll = jira.boards(projectKeyOrID=team.key)
        ic(boardsAll)
        currentboardId = ""
        planningBoardId = ""
        for board in boardsAll:
            if board.name.lower() == CONFIG_MAP[team.key]['planningBoard'].lower():
                currentboardId = board.id
    
        activeSprints[team.key] = jira.sprints(state='active',board_id=currentboardId)
        futureSprints[team.key] = jira.sprints(state='future',board_id=currentboardId)
    return activeSprints,futureSprints

async def team_metrics(issues):
    for team in issues:
        ## Deal with Current Sprint first
        for sprintType in issues[team]:
            issueTypes = Counter()
            if sprintType == "current":
                for curr_sprint in issues[team][sprintType]:
                    status = Counter()
                    priority = Counter()
                    ticket_user = Counter()
                    ticket_type = Counter()
                    currentWeight = 0
                    epics = Counter()
                    SPRINT_ISSUE_COUNT.labels(team,curr_sprint).set(len(issues[team][sprintType][curr_sprint]))
                    for currentIssue in issues[team][sprintType][curr_sprint]:
                        status[currentIssue.fields.status.name] += 1
                        if currentIssue.raw['fields']['customfield_10016']:
                            currentWeight += int(currentIssue.raw['fields']['customfield_10016'])
                        status[currentIssue.fields.status.name] += 1
                        priority[currentIssue.fields.priority.name] += 1
                        if currentIssue.fields.assignee:
                            ticket_user[currentIssue.fields.assignee.displayName] += 1
                        
                        if 'parent' in currentIssue.raw['fields']:
                            if currentIssue.raw['fields']['parent']['fields']['issuetype']['name'].lower() == "epic":
                                epics[currentIssue.raw['fields']['parent']['fields']['summary']] += 1
                        
                        if currentIssue.fields.issuetype:
                            ticket_type[currentIssue.fields.issuetype.name] += 1

                    for stat in status:
                        ISSUE_STATUS.labels(team,curr_sprint,stat).set(status[stat])
                    for pri in priority:
                        SPRINT_COUNT_PRIORITY.labels(team,curr_sprint,pri).set(priority[pri])
                    for epic in epics:
                        SPRINT_EPIC_COUNT.labels(team,curr_sprint,epic).set(epics[epic])
                    for user in ticket_user:
                        TICKETS_USER.labels(team,curr_sprint,user).set(ticket_user[user])
                    for type in ticket_type:
                        ISSUE_TYPE.labels(team,curr_sprint,type).set(ticket_type[type])
                        
                    SPRINT_WEIGHT.labels(team,curr_sprint).set(currentWeight)
            elif sprintType == "future":
                for future_sprint in issues[team][sprintType]:
                    status = Counter()
                    priority = Counter()
                    futureWeight = 0
                    FUTURE_ISSUE_COUNT.labels(team,future_sprint).set(len(issues[team][sprintType][future_sprint]))
                    for futureIssue in issues[team][sprintType][future_sprint]:
                        status[futureIssue.fields.status.name] += 1
                        if futureIssue.raw['fields']['customfield_10016']:
                            futureWeight += int(futureIssue.raw['fields']['customfield_10016'])
                        status[futureIssue.fields.status.name] += 1
                        priority[futureIssue.fields.priority.name] += 1
                    for stat in status:
                        ISSUE_STATUS.labels(team,future_sprint,stat).set(status[stat])
                    for pri in priority:
                        SPRINT_COUNT_PRIORITY.labels(team,future_sprint,pri).set(priority[pri])
                    
                    SPRINT_WEIGHT.labels(team,future_sprint).set(futureWeight)

async def epic_metrics(projects,jira):
    for team in projects:
        epics_status = Counter()
        teamJql = f"project = {team} and type = epic"
        for epic in jira.search_issues(jql_str=teamJql,maxResults=False):
            epics_status[epic.fields.status.name] += 1
        for status in epics_status:
            EPIC_STATUS.labels(team,status).set(epics_status[status])


async def build_metrics(request):
    
    ISSUE_WEIGHT.clear()
    ISSUE_STATUS.clear()
    EPIC_STATUS.clear()
    ISSUE_TYPE.clear()
    TICKETS_USER.clear()
    SPRINT_ISSUE_COUNT.clear()
    FUTURE_ISSUE_COUNT.clear()
    SPRINT_WEIGHT.clear()
    SPRINT_COUNT_PRIORITY.clear()
    SPRINT_EPIC_COUNT.clear()

    TEAMS_INFO.clear()
    BACKLOG_ISSUE_COUNT.clear()

    status = Counter()
    jira = JIRA(server=JIRA_HOST, basic_auth=(JIRA_USER,JIRA_API_KEY))
    
    with tracer.start_as_current_span("get_projects"):
        logging.info("Getting projects")
        projects = await get_projects(CONFIG_MAP,jira)
    with tracer.start_as_current_span("get_team_boards"):
        logging.info("Getting Team Boards")
        activeSprints,futureSprints = await get_team_boards(projects,jira)
    with tracer.start_as_current_span("get_team_issues"):
        logging.info("Getting Team Issues")
        issues = await get_team_issues(activeSprints,futureSprints,jira)
    with tracer.start_as_current_span("team_metrics"):
        logging.info("Getting Team Metrics")
        await team_metrics(issues)
    with tracer.start_as_current_span("epic_metrics"):
        logging.info("Getting Epic Metrics")
        await epic_metrics(projects,jira)

    logging.info("Finished Metrics")
    return handle_metrics(request)



app.add_route("/metrics", build_metrics)
