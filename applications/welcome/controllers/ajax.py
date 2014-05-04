task = Storage(
        name="Leichtatlethik",
        url="http://www.iaaf.org/records/toplists/sprints/100-metres/outdoor/men/senior/2013",
        ## first name, last name, time, date ##
        selectors = [Selector(xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[4]/a/text()""", type=unicode),
                     Selector(xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[4]/a/span/text()""", type=unicode),
                     Selector(xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[2]/text()""", type=float),
                     Selector(xpath="""//table[@class = "records-table toggled-table condensedTbl"]/tr[@id]/td[9]/text()""", type=datetime.datetime)],
        period=10
    )

def add_task():
    db.Task.update_or_insert(_key=dict(name=task.name), **task)
    scheduler.queue_task(run_task, pvars=dict(name=task.name), repeats=0, period=task.period, immediate=True, retry_failed=-1)
    return db().select(db.Task.ALL)

def delete_all_tasks():
    db.scheduler_task.drop()
    db.scheduler_run.drop()
    db.Task.drop()
    return True

def get_tasks():
    return scheduler.tasks

def run_task_name():
    return run_task(request.vars.name)

def test():
    pprint(http_request(task.url, selectors=task.selectors))