# -*- coding: utf-8 -*-
import os
from FEAR.RDFread import RDFread
from FEAR.CGR import CGR
import sched
import time

__author__ = 'stsouko'
import requests
import json

SERVER = "http://130.79.41.70"
PORT = 5000
CHEMAXON = "%s:8080/webservices" % SERVER
STANDARD = open(os.path.join(os.path.dirname(__file__), "std_rules.xml")).read()

INTERVAL = 3

TASK_CREATED = 0
REQ_MAPPING = 1
LOCK_MAPPING = 2
MAPPING_DONE = 3


def serverget(url, params):
    q = requests.get("%s:%d/%s" % (SERVER, PORT, url), params=params)
    return q.json()


def serverput(url, params):
    requests.put("%s:%d/%s" % (SERVER, PORT, url), params=params)


def chemaxpost(url, data):
    q = requests.post("%s/rest-v0/util/%s" % (CHEMAXON, url),
                      data=json.dumps(data),
                      headers={'content-type': 'application/json'})
    return q.text


def gettask():
    return serverget('tasks', {'task_status': REQ_MAPPING})


def run():
    fear = CGR()
    tasks = gettask()

    for i in tasks:
        serverput("task_status/%s" % (i['id']), {'task_status': LOCK_MAPPING})
        chemicals = serverget("task_reactions/%s" % (i['id']), None)
        for j in chemicals:
            structure = serverget("reaction_structure/%s" % (j['reaction_id']), None)

            data = {"structure": structure, "parameters": {"standardizerDefinition": STANDARD}}
            standardised = chemaxpost('convert/standardizer', data)

            data = {"structure": standardised, "parameters": {"autoMappingStyle": "OFF"}}
            r_structure = chemaxpost('convert/reactionConverter', data)

            data = {"structure": r_structure, "parameters": "rxn"}
            structure = chemaxpost('calculate/stringMolExport', data)

            with open('/tmp/tmp_standard.rxn', 'w') as tmp:
                tmp.write(structure)

            fearinput = RDFread('/tmp/tmp_standard.rxn')
            fearinput = next(fearinput.readdata())
            try:
                res = fear.firstcgr(fearinput)
                if not res:
                    rhash = fearinput['meta']['!reaction_center_hash_0'].split("'")[0][5:]
                    models = serverget("models", {'model_hash': rhash})
                    serverput("reaction/%s" % (i['id']), {'models': ','.join([str(x['id']) for x in models])})
            except:
                pass

            data = {"structure": r_structure, "parameters": {"method": "DEHYDROGENIZE"}}
            structure = chemaxpost('convert/hydrogenizer', data)

            serverput("reaction_structure/%s" % (i['id']), {'reaction_structure': structure})


        serverput("task_status/%s" % (i['id']), {'task_status': MAPPING_DONE})


class PeriodicScheduler(object):
    def __init__(self):
        self.scheduler = sched.scheduler(time.time, time.sleep)

    def setup(self, interval, action, actionargs=()):
        action(*actionargs)
        self.scheduler.enter(interval, 1, self.setup, (interval, action, actionargs))

    def run(self):
        self.scheduler.run()


def main():
    periodic_scheduler = PeriodicScheduler()
    periodic_scheduler.setup(INTERVAL, run)
    periodic_scheduler.run()

if __name__ == '__main__':
    main()