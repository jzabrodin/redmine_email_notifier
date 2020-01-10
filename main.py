# -*- coding: utf-8 -*-

import datetime
import requests as req
import xmlschema

from smtplib import SMTP
from email.mime.text import MIMEText
import sys
from eztable import Table


def return_unicode_string(_str):
    return u''.join(_str)


class RedmineConnection:

    parameters = None
    server = None

    def initialize_parameters(self):

        self.parameters = {
            "key": "<YOUR_API_KEY>",
            "server": "http://redmine.com.ua",
            "copy_to": "zabrodin@mail.com",
            "smtp_login": "test",
            "smtp_pass": "test",
            "smtp_server": "mail.com",
            "limit": 100,
            "assigned_to_id": 23,
            "from": "test@mail.com"
        }

    def send_mail(self, to, subject, text):

        self.initialize_parameters()

        parameters = self.parameters

        if self.server is None:
            server_login = self.parameters["smtp_login"]
            server_password = self.parameters["smtp_pass"]
            smtp_server = self.parameters["smtp_server"]
            server = SMTP(smtp_server, 587)
            server.login(server_login, server_password)
            self.server = server

        msg = MIMEText(text, _charset="utf-8")
        msg['Subject'] = subject
        msg['From'] = parameters["from"]
        msg['To'] = ""+to

        self.server.sendmail(parameters["from"], to, msg.as_string())


class RedmineIssues:

    # datatype users or issues
    def get_data(self):

        connection = RedmineConnection()
        connection.initialize_parameters()
        parameters = connection.parameters

        key = parameters["key"]
        server = parameters["server"]
        limit = parameters["limit"]
        assigned_to_id = parameters["assigned_to_id"]

        url = "{0}/{1}?key={2}&limit={3}&assigned_to_id={4}".format(
            server,
            "issues.xml",
            key,
            limit,  # limit
            assigned_to_id
        )
        print "getting data at : "+url+"&"
        data = req.get(url)
        content = u''.join(data.text).encode("utf-8")

        if content:
            print "issues updated!"
            f = open("issues.xml", "w")
            f.write(content)
            f.close()
        else:
            "sorry, something wrong :("

        f = open("issues.xml", "r")

        my_sch = xmlschema.XMLSchema('issues.xsd')
        data = my_sch.to_dict('issues.xml')
        return data


class RedmineUsers:

    data = None

    # Образец :
    # {'last_login_on': u'2018-10-09 08:28:21 UTC',
    #  'firstname': u'firstname',
    #  'lastname': u'lastname', 'created_on': u'2018-07-27 13:58:14 UTC',
    #  'mail': u'login@mail.com.ua', 'login': u'login', 'id': 48}

    def get_user_info(self):

        connection = RedmineConnection()
        connection.initialize_parameters()

        my_sch = xmlschema.XMLSchema('users.xsd')
        data = my_sch.to_dict('users.xml')

        self.data = data

        return data

    def get_user_by_id(self, id):

        if self.data == None:
            connection = RedmineConnection
            connection.initialize_parameters()
            self.get_user_info()

        for user in self.data['user']:

            if user['id'] == id:
                return user


def process_data(data, connection):

    parameters = connection.parameters

    today = datetime.datetime.today()

    authors_issues = {}

    for issue in data['issue']:

        uni_author_name = issue['author']["@id"]
        status = issue['status']['@id']

        # http://<redmine>/issue_statuses.xml
        #  4 - обратная связь от постановщика
        # 12 - Требуется тест. пользователем
        if not status in [4, 12]:
            continue

        strDate = issue['updated_on'][:-4]

        if len(strDate) == 16:
            issue_date = datetime.datetime.strptime(strDate, "%Y-%m-%dT%H:%M")
        else:
            issue_date = datetime.datetime.strptime(
                strDate, "%Y-%m-%d %H:%M:%S")

        delta = today - issue_date

        if delta.days < 7:
            print "Номер задачи {0}, прошло дней {1} дата задачи {2}".format(
                issue['id'], delta.days, issue_date)
            continue
        else:
            print "Номер задачи {0}, прошло дней {1} дата задачи {2}".format(
                issue['id'], delta.days, issue_date)

        info = u"{1} {2}/issues/{0}".format(
            issue['id'], issue['subject'], parameters["server"])

        if authors_issues.has_key(uni_author_name):
            # если автор уже есть, то добавляем задачу в его массив
            authors_issues[uni_author_name].append(info)
        else:
            authors_issues[uni_author_name] = []
            authors_issues[uni_author_name].append(info)

    return authors_issues


def printDataGroupedByProjects(data):

    if not data.has_key("issue"):
        print "data doesn't have key issue"

    project = {}

    p = Table(
        # ['project' , ('issue_id',int) , 'issue_subject','issue']
        ['project', 'tracker', ('issue_id', int),
         'issue_status', 'issue_subject', 'issue_description']
    )

    for issue in data['issue']:
        project_name = issue["project"]["@name"]
        issue_id = issue["id"]
        issue_status = issue["status"]["@name"]
        issue_subject = str((issue["subject"])).strip()
        tracker = issue["tracker"]["@name"]
        issue_description = issue["description"]
        # p.append([project_name,issue_id,issue_subject,issue["description"]])
        p.append([project_name, tracker, issue_id, issue_status,
                  issue_subject, issue_description])

    p.to_csv(open("issues.csv", "w"))


def sendNotificationAboutUnclosedTasks(data, connection, params):

    issues = process_data(data, connection)

    redmineUsers = RedmineUsers()
    redmineUsers.get_user_info()

    for k in issues.keys():

        user_info = redmineUsers.get_user_by_id(k)

        message = "Добрый день {0} {1}! \n email : {2} \n " \
                  "У Вас есть незакрытые задачи в Redmine.".format(
                      user_info['firstname'],
                      user_info['lastname'],
                      user_info['mail']
                  )

        for issue in issues[k]:
            message += "\n \t"+issue

        connection.send_mail(
            connection.parameters["copy_to"],
            "Незакрытые задачи в Redmine",
            u''.join(message)
        )
        connection.send_mail(
            user_info['mail'],
            "Незакрытые задачи в Redmine",
            u''.join(message)
        )

    if connection.server != None:
        connection.server.quit()


def main():

    reload(sys)
    sys.setdefaultencoding("utf8")

    connection = RedmineConnection()
    connection.initialize_parameters()

    redmineIssues = RedmineIssues()
    data = redmineIssues.get_data()

    printDataGroupedByProjects(data)

    # sendNotificationAboutUnclosedTasks(data, connection,connection.parameters)
