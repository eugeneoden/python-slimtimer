import string
import StringIO
import httplib
import time
import re
import datetime
import elementtree.ElementTree as ET

# SlimTimerAPI

#
# A task
#
# We sync this with SlimTimer using an explicit call to update(). This is
# a little less elegant than doing it through overloads of __setattr__ but it
# better suited to batch changes and our use of the API
#
class SlimTimerTask:

    def __init__(self, session, name, id=0):
        self.__session  = session
        self.name       = name
        self.id         = id
        self.tags       = []
        self.coworkers  = []
        self.reporters  = []
        self.complete   = False

        # These fields are read-only.
        # TODO: Overload __setattr__ and throw an Exception if these are ever
        # set
        self.hours      = 0
        self.owner      = ''
        self.updated_at = 0
        self.created_at = 0
        self.completed_on = 0

    def update(self):
        result = self.__session.update_task(self)
        # I have no idea about Python but this seems to provide the semantics
        # we want here, rather than self = result
        self.__dict__ = result.__dict__

    def delete(self):
        # If we haven't been created then there's nothing to delete
        if (self.id):
            self.__session.delete_task(self)

#
# A time entry
#
# At the moment this is just a glorified dictionary. In the future it should
# probably have a link back to the session so it can be live.
#
class SlimTimerEntry:

    def __init__(self):
        self.id         = 0
        self.start_time = None
        self.end_time   = None
        self.duration   = 0
        self.tags       = ''
        self.comments   = ''
        self.task        = None

#
# The session
#
class SlimTimerSession:

    def __init__(self, username, password, apikey):
        self.__username = username
        self.__password = password
        self.__apikey   = apikey

        self.__token    = ''
        self.__userid   = ''

        self.__conn     = httplib.HTTPConnection("www.slimtimer.com")

        self._logon()

    def __del__(self):
        self.__conn.close()

    def get_task_by_id(self, id):

        url = "%s/tasks/%s?%s" % \
              (self._get_base_url(), id, self._get_url_params())

        self.__conn.request("GET", url, "", { "Accept": "application/xml" })
        response = self.__conn.getresponse()

        data = response.read()

        if not response.status == 200:
            return None

        return self._parse_task(ET.fromstring(data))

    def get_task_by_name(self, name, completed='both'):

        completed = string.lower(completed)
        completed = {'both': 'yes',
                     'yes': 'only',
                     'no': 'no',
                     'true': 'only',
                     'false': 'no'}[completed]

        url = "%s/tasks?%s&show_completed=%s" % \
              (self._get_base_url(), self._get_url_params(), completed)

        self.__conn.request("GET", url, "", { "Accept": "application/xml" })
        response = self.__conn.getresponse()

        data = response.read()

        if not response.status == 200:
            return None

        for task in ET.fromstring(data).findall("task"):
            if task.findtext("name") == name:
                return self._parse_task(task)

        return None

    def update_task(self, task):
        """
        Updates the given task or creates it if the task ID is 0
        """
        create = task.id == 0

        xml = self._serialise_task(task)

        method = ['PUT','POST'][create]

        if create:
            url = "%s/tasks?%s" % \
                  (self._get_base_url(), self._get_url_params())
        else:
            url = "%s/tasks/%s?%s" % \
                  (self._get_base_url(), task.id, self._get_url_params())

        headers = { "Accept":"application/xml",
                    "Content-Type":"application/xml" }
        self.__conn.request(method, url, xml, headers) 
        response = self.__conn.getresponse()

        data = response.read()

        if not response.status == 200:
            raise Exception("Could not update/create task."\
                    " Response was [%s]: %s" % (response.status, data))

        return self._parse_task(ET.fromstring(data))

    def update_time_entry(self, entry):
        """
        Updates the given entry or creates it if the entry ID is 0
        """
        create = entry.id == 0

        xml = self._serialise_time_entry(entry)

        method = ['PUT','POST'][create]

        if create:
            url = "%s/time_entries?%s" % \
                  (self._get_base_url(), self._get_url_params())
        else:
            url = "%s/time_entries/%s?%s" % \
                  (self._get_base_url(), entry.id, self._get_url_params())

        headers = { "Accept":"application/xml",
                    "Content-Type":"application/xml" }
        self.__conn.request(method, url, xml, headers) 
        response = self.__conn.getresponse()

        data = response.read()

        if not response.status == 200:
            raise Exception("Could not update/create time entry."\
                    " Response was [%s]: %s" % (response.status, data))

        return self._parse_time_entry(ET.fromstring(data))

    def delete_task(self, task):

        url = "%s/tasks/%s?%s" % \
              (self._get_base_url(), task.id, self._get_url_params())

        self.__conn.request("DELETE", url, "",
                            { "Accept": "application/xml" })
        response = self.__conn.getresponse()

        if not response.status == 200:
            raise Exception("Task not found for deletion")

        # We seem to need to reset the connection after a delete
        self._reset_connection()

    def delete_entry(self, entry):

        url = "%s/time_entries/%s?%s" % \
              (self._get_base_url(), entry.id, self._get_url_params())

        self.__conn.request("DELETE", url, "",
                            { "Accept": "application/xml" })
        response = self.__conn.getresponse()

        if not response.status == 200:
            raise Exception("Entry not found for deletion")

        # We seem to need to reset the connection after a delete
        self._reset_connection()

    def get_time_entries(self, range_start = None, range_end = None):

        result = []

        # Prepare range filter
        filters = []
        if range_start:
            filters.append("range_start=%s" % self._format_date(range_start))
        if range_end:
            filters.append("range_end=%s" % self._format_date(range_end))
        filter_str = '&'.join(filters)
        if filter_str:
            filter_str = '&' + filter_str

        url = "%s/time_entries?%s%s" % \
              (self._get_base_url(), self._get_url_params(), filter_str)

        self.__conn.request("GET", url, "", { "Accept": "application/xml" })
        response = self.__conn.getresponse()

        data = response.read()

        if not response.status == 200:
            return None

        for entry in ET.fromstring(data).findall("time-entry"):
            result.append(self._parse_time_entry(entry))

        return result

    def get_username(self):
        return self.__username

    # Internal methods

    def _logon(self):
        """ Get an access token and user id """

        # Lazy operation
        if self.__token and self.__userid:
            return (self.__token, self.__userid)

        # Parameter checking
        if not self.__username or not self.__apikey:
            raise Exception("Invalid username or API key")

        # Build request
        request = '<request><user><email>%s</email>\
            <password>%s</password></user><api-key>%s</api-key>\
            </request>' % (self.__username, self.__password, self.__apikey)

        headers = { "Accept":"application/xml",
                    "Content-Type":"application/xml" }
        self.__conn.request("POST", "/users/token", request, headers) 
        response = self.__conn.getresponse()

        data = response.read()

        if response.status != 200:
            raise Exception("Server returned error: %s)" % data)

        result = ET.fromstring(data)
        self.__token = result.findtext("access-token")
        self.__userid = result.findtext("user-id")

        return (self.__token, self.__userid)

    def _reset_connection(self):
        """ Establish a new connection """

        self.__userid = 0
        self.__token  = 0
        self.__conn.close()

        self.__conn   = httplib.HTTPConnection("www.slimtimer.com")
        self._logon()

    def _get_base_url(self):
        """ Get the start of the URL """

        # This should have been established by _logon
        assert self.__userid

        return "/users/%s" % self.__userid

    def _get_url_params(self):
        """ Get common URL parameters """

        # These should have been established by _logon
        assert self.__apikey
        assert self.__token

        return "api_key=%s&access_token=%s" % (self.__apikey, self.__token)

    def _parse_task(self, task_element):
        id   = int(task_element.findtext("id"))
        name = task_element.findtext("name")

        task = SlimTimerTask(self, name, id)

        tags_text = task_element.findtext("tags")
        if (tags_text): task.tags = self._parse_tags(tags_text)

        task.coworkers = self._parse_people(task_element.find("coworkers"))
        task.reporters = self._parse_people(task_element.find("reporters"))

        task.complete = not task_element.findtext("completed-on") == ""
        task.hours = float(task_element.findtext("hours"))

        owners = self._parse_people(task_element.find("owners"))
        if len(owners):
            task.owner = owners[0]

        task.created_at = self._parse_date(task_element.findtext("created-at"))
        task.updated_at = self._parse_date(task_element.findtext("updated-at"))

        if task.complete:
            task.completed_on = \
                self._parse_date(task_element.findtext("completed-on"))

        return task

    def _parse_tags(self, tags_text):
        pat = r'"[^"]*"|[^," \t][^,"]+[^," \t]'
        return re.findall(pat, tags_text)

    def _parse_people(self, list_element):
        emails = []
        for person in list_element.findall("person"):
            emails.append(self._parse_person(person)['email'])
        return emails

    def _parse_person(self, person_element):
        person = {}
        person['name'] = person_element.findtext("name")
        person['userid'] = person_element.findtext("user-id")
        person['email'] = person_element.findtext("email")
        return person

    def _parse_date(self, date_text):
        try:
            return datetime.datetime(*(time.strptime(date_text,
                                        "%Y-%m-%dT%H:%M:%SZ")[0:6]))
        except:
            return None

    def _format_date(self, date):
        return date.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _parse_time_entry(self, entry_element):
        entry = SlimTimerEntry()
        entry.id = int(entry_element.findtext("id"))
        entry.start_time = \
            self._parse_date(entry_element.findtext("start-time"))
        entry.end_time = self._parse_date(entry_element.findtext("end-time"))
        entry.duration = int(entry_element.findtext("duration-in-seconds"))
        entry.tags     = entry_element.findtext("tags")
        entry.comments = entry_element.findtext("comments")
        entry.task = self._parse_task(entry_element.find("task"))

        return entry

    def _serialise_task(self, task):

        xml_task = ET.Element("task")

        if task.id != 0:
            id = ET.SubElement(xml_task, "id")
            id.set("type", "integer")
            id.text = str(task.id)

        name = ET.SubElement(xml_task, "name")
        name.text = task.name

        if len(task.tags):
            tags = ET.SubElement(xml_task, "tags")
            tags.text = string.join(task.tags, ",")

        if len(task.coworkers):
            coworkers = ET.SubElement(xml_task, "coworker_emails")
            coworkers.text = string.join(task.coworkers, ",")

        if len(task.reporters):
            reporters = ET.SubElement(xml_task, "reporter_emails")
            reporters.text = string.join(task.reporters, ",")

        completed = ET.SubElement(xml_task, "completed_on")
        if task.complete:
            completed.text = time.strftime("%Y-%m-%d %H:%M:%S",
                                           time.gmtime())
        else:
            completed.text = ""

        xml = StringIO.StringIO()
        ET.ElementTree(xml_task).write(xml)
        result = xml.getvalue()
        xml.close()

        return result

    def _serialise_time_entry(self, entry):

        xml_entry = ET.Element("time-entry")

        if entry.id != 0:
            id = ET.SubElement(xml_entry, "id")
            id.set("type", "integer")
            id.text = str(entry.id)

        start_time = ET.SubElement(xml_entry, "start-time")
        start_time.set("type", "datetime")
        start_time.text = entry.start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        duration = (entry.end_time - entry.start_time).seconds
        if not duration:
            duration = 59

        xml_duration = ET.SubElement(xml_entry, "duration-in-seconds")
        xml_duration.set("type", "integer")
        xml_duration.text = str(duration)

        task_id = ET.SubElement(xml_entry, "task-id")
        task_id.set("type", "integer")
        task_id.text = str(entry.task.id)

        if len(entry.tags):
            tags = ET.SubElement(xml_entry, "tags")

            if isinstance(entry.tags, list):
                tags.text = string.join(entry.tags, ",")
            else:
                tags.text = str(entry.tags)

        xml = StringIO.StringIO()
        ET.ElementTree(xml_entry).write(xml)
        result = xml.getvalue()
        xml.close()

        return result

# vim:set ts=4 sw=4 ai et:
