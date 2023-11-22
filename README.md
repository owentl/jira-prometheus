# jira-prometheus
Create Prometheus metrics from Jira issues and epics

This project will create a FastAPI applicaiton that exposes the /metrics path that Prometheus can scrape.

The goal of this project was to be able to chart progress via Grafana for a team.  Since Grafana's Jira data source is part of their Enterprise offering, I created this tool to track the metrics.  I have no idea how this compares to the Grafana data source as I haven't ever used it.

The configuration is all handled in the config.json file where you can set the projects that you want to chart as well as the appropriate sprint field name and the name of the correct planning board.  Jira's APIs are pretty robust but the innards of Jira are not exactly straightfoward.

This project was based off the Gitlab version I did called gitlab-prometheus
