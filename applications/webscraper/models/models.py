import feedparser  # autodetection of date formats
import datetime  # date / time support
import logging  # support for logging to console (debuggin)
from gluon.storage import Storage  # Support for dictionary container Storage
from Scraper import Scraper  # Own Web-Scraper
from utils import *  # for generic helpers

class Task(object):
    _STRING_TYPES = {
        unicode: "string",
        str: "string",
        int: "integer",
        float: "double",
        datetime.datetime: "datetime",
        "string": unicode,
        "integer": int,
        "double": float,
        "datetime": datetime.datetime,
    }

    class Selector(object):  # contains information for selecting a ressource on a xml/html page
        def __init__(self, name, xpath, type=None, regex=None):
            if not type and not regex:
                regex = ".*"

            if type and isinstance(type, basestring):
                ## type can be a type or string representation of a type ##
                self.type = Task._STRING_TYPES[type]

            if type in [unicode, str]:
                self.output_cast = type
                regex = regex or "\w[\w\s]*\w|\w"
            elif type == int:
                self.output_cast = lambda s : int(str2float(s))
                regex = regex or "\d[\d.,]+"
            elif type == float:
                self.output_cast = str2float
                regex = regex or "\d[\d.,]+"
            elif type == datetime.datetime:
                self.output_cast = lambda data: datetime.datetime(*(feedparser._parse_date(data)[:6]))
                regex = regex or "\d+ \w+ \d+"

            self.name = name
            self.xpath = xpath
            self.regex = regex
            self.type = type or unicode


        @property
        def string_type(self):
            return Task._STRING_TYPES[self.type]

        @staticmethod
        def from_task_row(task_row):
            return [Task.Selector(name=task_row.selector_names[i], xpath=task_row.selector_xpaths[i], regex=task_row.selector_regexes[i], type=Task._STRING_TYPES[task_row.selector_types[i]]) for i in range(len(task_row.selector_names))]

    class Url(object):
        def __init__(self, url, table=None, column=None, start_parameter=None):
            self.url = url
            self.table = table
            self.column = column
            self.start_parameter = start_parameter

        @property
        def urls(self):
            if self.table:  # The url must be generated
                rows = db().select(db[self.table].ALL)
                return {self.url % self.start_parameter} | set(self.url % row[self.column] for row in set(rows) if row[self.column])  # Convert result into a set to remove duplicates
            else:
                return [self.url]

        @staticmethod
        def from_task_row(task_row):
            return [Task.Url(url=task_row.urls[i], table=task_row.url_tables[i], column=task_row.url_columns[i], start_parameter=task_row.url_start_parameters[i]) for i in range(len(task_row.urls))]


    def __init__(self, name, urls, selectors, creation_datetime=None, table_name=None, period=0, status=""):
        self.name = name
        self.table_name = table_name or name
        self.urls = urls
        self.selectors = selectors
        self.period = period
        self.creation_datetime = creation_datetime or datetime.datetime.now()
        self.status = status

    @property
    def urls(self):
        result = set()
        for url in self._urls:
            result |= set(url.urls)
        return result

    @urls.setter
    def urls(self, value):
        self._urls = value

    @staticmethod
    def _define_tables():
        db.define_table('Task',
            Field("name", type="string", unique=True),
            Field("table_name", type="string"),
            Field("urls", type="list:string"),
            Field("url_start_parameters", type="list:string"),
            Field("url_tables", type="list:string"),
            Field("url_columns", type="list:string"),
            Field("creation_datetime", type="datetime", default=request.now),
            Field("period", type="integer", default=10),  # in seconds
            Field("status", type="string", default=""),
            ## selectors ##
            Field("selector_names", type="list:string"),
            Field("selector_xpaths", type="list:string"),
            Field("selector_regexes", type="list:string"),
            Field("selector_types", type="list:string"),
            redefine=True
        )

        for task_row in db().select(db.Task.ALL):
            fields = [Field(selector.name, type=selector.string_type) for selector in Task.Selector.from_task_row(task_row)]
            db.define_table(task_row.table_name, *fields, redefine=True)

    def put(self):
        """ Serializes the entity into the database """
        kwargs = {
            "name": self.name,
            "table_name": self.table_name,
            "urls": [url.url for url in self._urls],
            "url_tables": [url.table for url in self._urls],
            "url_columns": [url.column for url in self._urls],
            "url_start_parameters": [url.start_parameter for url in self._urls],
            "creation_datetime": self.creation_datetime,
            "period": self.period,
            "status": self.status,
            "selector_names": [selector.name for selector in self.selectors],
            "selector_xpaths": [selector.xpath for selector in self.selectors],
            "selector_regexes": [selector.regex for selector in self.selectors],
            "selector_types": [selector.string_type for selector in self.selectors],
        }
        db.Task.update_or_insert(db.Task.name == self.name, **kwargs)

    def delete(self):
        self.unschedule()
        db(db.Task.name == self.name).delete()
        self._define_tables()

    @staticmethod
    def deserialize(row):
        ## Remove 'None' serializations from db ##
        row = Storage(row.as_dict())

        for k1, v1 in list(row.iteritems()):
            if hasattr(v1, "__iter__"):
                for k2, v2 in enumerate(v1):
                    v1[k2] = v2 if v2 != "None" else None
            else:
                row[k1] = v1 if v1 != "None" else None
        return row

    @staticmethod
    def from_task_row(task_row):
        task_row = Task.deserialize(task_row)

        return Task(
            name=task_row.name,
            table_name=task_row.table_name,
            urls=Task.Url.from_task_row(task_row),
            period=task_row.period,
            status=task_row.status,
            creation_datetime=task_row.creation_datetime,
            selectors=Task.Selector.from_task_row(task_row),
        )

    @staticmethod
    def get_by_name(name):
        try:
            return Task.from_task_row(db.Task(db.Task.name == name))
        except:
            pass

    @staticmethod
    def get_all():
        return [Task.from_task_row(task_row) for task_row in db().select(db.Task.ALL)]

    def schedule(self, repeats=0):
        self.status = "Scheduled"
        self.put()
        self.unschedule()
        scheduler.queue_task('run_by_name', uuid=self.name, pvars=dict(name=self.name), repeats=repeats, period=self.period or 1, immediate=True, retry_failed=0, timeout=10000)  # repeats=0 and retry_failed=-1 means indefinitely

    def unschedule(self):
        db(db.scheduler_task.uuid == self.name).delete()

    def delete_results(self):
        try:
            db[self.table_name].drop()
        except Exception as e:
            pass
        Task._define_tables()

    def get_results(self, with_title=False):
        task_rows = db().select(db[self.table_name].ALL)

        result = [tuple(task_row.as_dict()[selector.name] for selector in self.selectors) for task_row in task_rows]
        if with_title:
            result = [tuple(selector.name for selector in self.selectors)] + result

        return result

    @staticmethod
    def delete_all_results():
        for task in Task.get_all():
            task.delete_results()
        Task._define_tables()

    @staticmethod
    def delete_all_tasks():
        scheduler.terminate_process()
        Task.delete_all_results()
        db.scheduler_task.drop()
        db.scheduler_run.drop()
        db.Task.drop()
        Task._define_tables()

    def run(self, store=True, return_result=False):
        partial_result = result = []
        visited_urls = set()
        remaining_urls = self.urls

        while remaining_urls:  # and len(visited_urls) < 10:  # urls may change during iteration. Therefore for-each is not applicable.
            url = remaining_urls.pop()

            ## Fetch Result ##
            partial_result = Scraper.http_request(url, selectors=self.selectors)
            result += partial_result

            ## Store result in database ##
            if partial_result and store:
                for row in partial_result:
                    row_dict = {self.selectors[i].name: data for i, data in enumerate(row)}  # map selector names and data together
                    db[self.table_name].update_or_insert(**row_dict)

            ## Update urls ##
            visited_urls |= {url}
            remaining_urls = self.urls - visited_urls  # Need to be evaluated after new results have committed (For recursive Crawler)

            ## Log status ##
            if len(visited_urls) != len(remaining_urls)+len(visited_urls):
                self.status = "Progress: %s/%s" % (len(visited_urls), len(remaining_urls)+len(visited_urls))
            else:
                self.status = ""
            self.put()
            logging.warning(self.status)

            ## Must commit any progress such that the recursive crawler can fetch new urls ##
            db.commit()

        if return_result:
            return result

    @staticmethod
    def run_by_name(name, **kwargs):
        return Task.get_by_name(name).run(**kwargs)

    @staticmethod
    def example_tasks():
        table_row_selector = """//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]"""

        return [
            ##### Leichtathletik #####
            Task(
                name="Leichthatletik_Sprint_100m_Herren",  # task name
                urls=[Task.Url(url="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior")],
                selectors=[
                    Task.Selector(name="athlete_id", xpath=table_row_selector + "/td[4]/a/@href", type=int),
                    Task.Selector(name="first_name", xpath=table_row_selector + "/td[4]/a/text()", type=unicode),
                    Task.Selector(name="last_name", xpath=table_row_selector + "/td[4]/a/span/text()", type=unicode),
                    Task.Selector(name="result_time", xpath=table_row_selector + "/td[2]/text()", type=float),
                    Task.Selector(name="competition_date", xpath=table_row_selector + "/td[9]/text()", type=datetime.datetime),
                ],
            ),
            Task(
                name="Leichthatletik_Athleten",  # task name
                urls=[Task.Url(url="http://www.iaaf.org/athletes/athlete=%s", table="Leichthatletik_Sprint_100m_Herren", column="athlete_id")],
                selectors=[
                    Task.Selector(name="athlete_id", xpath="""//meta[@property = "og:url"]/@content""", type=int),
                    Task.Selector(name="name", xpath="""//div[@class = "name-container athProfile"]/h1/text()""", type=unicode),
                    Task.Selector(name="birthday", xpath="""//div[@class = "country-date-container"]//span[4]//text()""", type=datetime.datetime),
                    Task.Selector(name="country", xpath="""//div[@class = "country-date-container"]//span[2]//text()""", type=unicode),
                ],
            ),
            ##### ImmoScout #####
            Task(
                name="Wohnungen",  # task name
                urls=[
                    Task.Url(url="http://www.immobilienscout24.de%s", start_parameter="/Suche/S-T/Wohnung-Miete/Bayern/Muenchen", table="Wohnungen", column="naechste_seite"),
                    Task.Url(url="http://www.immobilienscout24.de%s", start_parameter="/Suche/S-T/Wohnung-Miete/Berlin/Berlin", table="Wohnungen", column="naechste_seite"),
                ],
                selectors=[
                    Task.Selector(name="wohnungs_id", xpath="""//span[@class="title"]//a/@href""", type=int),
                    Task.Selector(name="naechste_seite", xpath="""//span[@class="nextPageText"]/..//@href"""),
                ],
            ),
            Task(
                name="Wohnungsdetails",  # task name
                urls=[Task.Url(url="http://www.immobilienscout24.de/expose/%s", table="Wohnungen", column="wohnungs_id")],
                selectors=[
                    Task.Selector(name="wohnungs_id", xpath="""//a[@id="is24-ex-remember-link"]/@href""", type=int),
                    Task.Selector(name="postleitzahl", xpath="""//div[@data-qa="is24-expose-address"]//text()""", type=int, regex="\d{5}"),
                    Task.Selector(name="zimmeranzahl", xpath="""//dd[@class="is24qa-zimmer"]//text()""", type=int),
                    Task.Selector(name="wohnflaeche", xpath="""//dd[@class="is24qa-wohnflaeche-ca"]//text()""", type=int),
                    Task.Selector(name="kaltmiete", xpath="""//dd[@class="is24qa-kaltmiete"]//text()""", type=int),
                ],
            ),
        ]