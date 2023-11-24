# jira-prometheus

Tracking of Issues in Prometheus

This project will create a FastAPI applicaiton that exposes the /metrics path that Prometheus can scrape.

## Goal of this project

The goal of this project was to be able to chart progress via Grafana for a team.  Since Grafana's Jira data source is part of their Enterprise offering, I created this tool to track the metrics.  I have no idea how this compares to the Grafana data source as I haven't ever used it.

## Configuration

The configuration for which projects to pull is is all handled in the config.json file.  This allows you to only handle metrics for certain projects. You will need to configure the appropriate sprint field name and the name of the correct planning board.  Jira's APIs are pretty robust but the innards of Jira are not exactly straightfoward.

In addition to the config.json you will need to set 3 ENV variables.  You will need to setup a JIRA API key

* JIRA_HOST - Typically https://[org].atlassian.net/
* JIRA_USER - The user for the API Key
* JIRA_API_KEY - Your JIRA API key for the JIRA_USER user

This project was based off the Gitlab version I did called gitlab-prometheus.
