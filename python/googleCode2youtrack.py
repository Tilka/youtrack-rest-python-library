#!/usr/bin/env python2

import HTMLParser
import calendar
import re
import itertools
import json
from urllib import unquote
import urllib
import urllib2
import xml
import datetime
import sys
import gdata.projecthosting.client
import gdata.projecthosting.data
import gdata.gauth
import gdata.client
import gdata.data

import googleCode
import googleCode.dolphin_emu
from youtrack import YouTrackException, Issue, Comment
from youtrack.connection import Connection
from youtrack.importHelper import create_bundle_safe


html = HTMLParser.HTMLParser()


def main():
    target_url, target_login, target_password, project_name, project_id, file_name = sys.argv[1:]
    googlecode2youtrack(project_name, target_url, target_login, target_password,
        project_id, file_name)


def create_and_attach_custom_field(target, project_id, field_name, field_type):
    normalized_name = field_name.lower()
    if normalized_name not in [field.name.lower() for field in target.getProjectCustomFields(project_id)]:
        if normalized_name not in [field.name.lower() for field in target.getCustomFields()]:
            target.createCustomFieldDetailed(field_name, field_type, False, True)
        if field_type in ["integer", "string", "date"]:
            target.createProjectCustomFieldDetailed(project_id, field_name, "No " + field_name)
        else:
            bundle_name = field_name + " bundle"
            create_bundle_safe(target, bundle_name, field_type)
            target.createProjectCustomFieldDetailed(project_id, field_name, "No " + field_name, {"bundle": bundle_name})


def add_value_to_field(target, project_id, field_name, field_type, value):
    if field_type.startswith("user"):
        create_user(target, value)
    if field_type in ["integer", "string", "date"]:
        return
    project_field = target.getProjectCustomField(project_id, field_name)
    bundle = target.getBundle(field_type, project_field.bundle)
    try:
        target.addValueToBundle(bundle, value)
    except YouTrackException:
        pass


def create_user(target, value):
    email = value if (value.find("@") != -1) else (value + "@gmail.com")
    try:
        target.createUserDetailed(value, value, email, email)
    except YouTrackException:
        pass


def to_unix_date(dt_str):
    dt, _, us = dt_str.partition(".")
    dt = datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
    us = int(us.rstrip("Z"), 10)
    res = dt + datetime.timedelta(microseconds=us)
    return str(calendar.timegm(res.timetuple()) * 1000)


def get_yt_field_name(g_field_name):
    if g_field_name in googleCode.FIELD_NAMES:
        return googleCode.FIELD_NAMES[g_field_name]
    return g_field_name


def get_custom_field_values(g_issue):
    values = {}
    for label in g_issue.get('labels', []):
        if "-" not in label:
            continue
        name, value = label.split("-", 1)
        yt_name = get_yt_field_name(name)
        if yt_name in googleCode.FIELD_TYPES:
            if yt_name in values:
                values[yt_name].append(value)
            else:
                values[yt_name] = [value]
    return values


def to_yt_comment(target, comment):
    yt_comment = Comment()
    yt_comment.author = comment['author']['name']
    create_user(target, yt_comment.author)
    yt_comment.text = html.unescape(comment['content']).encode('utf-8') or "''(No comment was entered for this change.)''"
    yt_comment.created = to_unix_date(comment['published'])
    return yt_comment


def to_yt_issue(target, project_id, g_issue, g_comments):
    issue = Issue()
    issue.numberInProject = issue_id(g_issue)
    issue.summary = g_issue['summary'].encode('utf-8') or '(No Summary)'
    issue.description = html.unescape(g_comments[0]['content'].replace("<b>", "*").replace("</b>", "*")).encode('utf-8')
    issue.created = to_unix_date(g_issue['published'])
    issue.updated = to_unix_date(g_issue['updated'])
    reporter = g_issue['author']['name']
    create_user(target, reporter)
    issue.reporterName = reporter
    assignee = g_issue['owner']['name'] if 'owner' in g_issue else None
    assignee_field_name = get_yt_field_name("owner")
    if assignee is not None:
        add_value_to_field(target, project_id, assignee_field_name, googleCode.FIELD_TYPES[assignee_field_name],
            assignee)
        issue[assignee_field_name] = assignee
    status_field_name = get_yt_field_name("status")
    status = g_issue['status'] if 'status' in g_issue else None
    if status is not None:
        add_value_to_field(target, project_id, status_field_name, googleCode.FIELD_TYPES[status_field_name], status)
        issue[status_field_name] = status

    for field_name, field_value in get_custom_field_values(g_issue).items():
        for value in field_value:
            add_value_to_field(target, project_id, field_name, googleCode.FIELD_TYPES[field_name], value)
        issue[field_name] = field_value

    issue.comments = []
    for comment in g_comments[1:]:
        yt_comment = to_yt_comment(target, comment)
        if yt_comment is not None:
            issue.comments.append(yt_comment)

    return issue


def get_tags(issue):
    return [label for label in issue['labels'] if
            get_yt_field_name(label.split("-")[0]) not in googleCode.FIELD_TYPES.keys()]


def import_tags(target, project_id, issue):
    for tag in get_tags(issue):
        try:
            target.executeCommand(project_id + "-" + issue_id(issue), "tag " + tag)
        except YouTrackException, e:
            print str(e)


def issue_id(i):
    return str(i['id'])


def get_attachments(projectName, issue):
    content = urllib.urlopen('https://code.google.com/p/{}/issues/detail?id={}'.format(projectName, issue_id(issue))).read()

    attach = re.compile(
        '<a href="(http://' + projectName + '\.googlecode\.com/issues/attachment\?aid=\S+name=(\S+)&\S+)">Download</a>')

    res = []
    for m in attach.finditer(content):
        res.append((xml.sax.saxutils.unescape(m.group(1)), m.group(2)))

    return res


def import_attachments(target, project_id, project_name, issue, author_login):
    for (url, name) in get_attachments(project_name, issue):
        print "  Transfer attachment [" + name + "]"
        try:
            content = urllib2.urlopen(urllib2.Request(url))
        except:
            print "Unable to import attachment [ " + name + " ] for issue [ " + issue_id(issue) + " ]"
            continue
        print target.createAttachment(project_id + "-" + issue_id(issue), unquote(name).decode('utf-8'), content,
            author_login,
            contentLength=int(content.headers.dict['content-length']),
            #contentType=content.info().type, octet/stream always :(
            created=None,
            group=None)


def get_project(project_name, file_name):
    data = json.load(open(file_name))
    projects = data['projects']
    for project in projects:
        if project['externalId'] == project_name:
            return project
    raise Exception('cannot find project in json file')


def googlecode2youtrack(project_name, target_url, target_login, target_password, project_id, file_name):
    target = Connection(target_url, target_login, target_password)

    try:
        target.getProject(project_id)
    except YouTrackException:
        target.createProjectDetailed(project_id, project_name, "", target_login)

    for field_name, field_type in googleCode.FIELD_TYPES.items():
        create_and_attach_custom_field(target, project_id, field_name, field_type)

    start = 0
    max = 30

    project = get_project(project_name, file_name)
    issues = project['issues']
    print('Found {} issues.'.format(issues['totalResults']))

    while True:
        issues_chunk = issues['items'][start:start + max]
        start += max

        if len(issues_chunk) == 0:
            break

        print 'Importing issues {} to {}...'.format(issues_chunk[0]['id'], issues_chunk[-1]['id'])
        target.importIssues(
                project_id, project_name + " assignees",
                [to_yt_issue(target, project_id, issue, issue['comments']['items']) for issue in issues_chunk]
        )
        for issue in issues_chunk:
            import_tags(target, project_id, issue)
            import_attachments(target, project_id, project_name, issue, target_login)


if __name__ == "__main__":
    main()
