# -*- coding: utf-8 -*-
#
# Copyright 2015, 2016 Ramil Nugmanov <stsouko@live.ru>
# This file is part of PREDICTOR.
#
# PREDICTOR is free software; you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
import traceback
import json
import threading
import time
import modeler.modelset as models
from utils.utils import serverget, serverput, serverpost, serverdel, gettask
from utils.config import INTERVAL, THREAD_LIMIT, REQ_MODELLING, LOCK_MODELLING, MODELLING_DONE, WORK_PATH, MODEL_REFRESH
import schedule

TASKS = []
LOSE = []
SOLVENTS = {}


def getmodel(model_name):
    Model, init = models.MODELS[model_name]
    try:
        if init:
            model = Model(WORK_PATH, init)
        else:
            model = Model(WORK_PATH)
    except:
        model = None
    return model


def taskthread(task_id):
    tmpLOSE = []
    if serverput("task_status/%s" % task_id, {'task_status': LOCK_MODELLING}):
        chemicals = serverget("task_reactions/%s" % task_id, None)
        for r in chemicals:
            reaction_id = r['reaction_id']
            reaction = serverget("reaction/%s" % reaction_id, None)
            if reaction:
                for model_id, model_name in reaction['models'].items():
                    try:
                        model_result = getmodel(model_name).getresult(reaction)
                    except Exception:
                        model_result = None
                        print(traceback.format_exc())
                    if model_result:
                        reaction_result = dict(modelid=model_id, result=json.dumps(model_result))
                        if not serverpost("reaction_result/%s" % reaction_id, reaction_result):
                            # если не удалось записать результаты моделирования, то схороним их на повторную отправку.
                            tmpLOSE.append(("reaction_result/%s" % reaction_id, reaction_result))

    if tmpLOSE or not serverput("task_status/%s" % task_id, {'task_status': MODELLING_DONE}):
        LOSE.append((tmpLOSE, ("task_status/%s" % task_id, {'task_status': MODELLING_DONE})))


def run():
    TASKS.extend(gettask(REQ_MODELLING)) #todo: надо запилить приоритеты. в начало совать важные в конец остальное
    if LOSE:
        for i in range(len(LOSE)):
            tmp = []
            for j in LOSE[i][0]:
                if not serverpost(*j):
                    tmp.append(j)
            if tmp or not serverput(*LOSE[i][1]):
                LOSE[i] = (tmp, LOSE[i][1])

    if TASKS and threading.active_count() < THREAD_LIMIT:
        i = TASKS.pop(0)
        t = threading.Thread(target=taskthread, args=([i['id']]))
        t.start()


def spider():
    registeredmodels = {x['name']: x['id'] for x in serverget("models", None)}
    models.find_models()

    todelete = set(registeredmodels).difference(models.MODELS)
    toattach = set(models.MODELS).difference(registeredmodels)

    print('available models', models.MODELS)
    print('removed models %s' % todelete)
    print('new models %s' % toattach)

    for x in toattach:
        model = getmodel(x)
        if model:
            try:
                data = {'name': x, 'desc': model.getdesc(), 'example': model.getexample(),
                        'is_reaction': model.is_reation(), 'hashes': model.gethashes()}
                print(serverpost("models", data))
            except Exception:
                print(traceback.format_exc())
                pass

    for x in todelete:
        serverdel("models", {'id': registeredmodels[x]})


def main():
    spider()
    schedule.every(MODEL_REFRESH).minutes.do(spider)
    schedule.every(INTERVAL).seconds.do(run)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()
