# -*- coding: utf-8 -*-
#
# Copyright 2015 Ramil Nugmanov <stsouko@live.ru>
# Copyright 2015 Oleg Varlamov <ovarlamo@gmail.com>
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
import bcrypt
import hashlib
from app.config import DEBUG, DB_PASS, DB_HOST, DB_NAME, DB_USER
from datetime import datetime
from pony.orm import Database, sql_debug, PrimaryKey, Required, Optional, Set


if DEBUG:
    db = Database("sqlite", "database.sqlite", create_db=True)
    sql_debug(True)
else:
    db = Database('postgres', user=DB_USER, password=DB_PASS, host=DB_HOST, database=DB_NAME)


class Users(db.Entity):
    id = PrimaryKey(int, auto=True)
    email = Required(str, unique=True)
    password = Required(str)
    active = Required(bool, default=True)
    token = Required(str)
    tasks = Set("Tasks")

    @staticmethod
    def hash_password(password):
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def verify_password(self, password):
        return bcrypt.hashpw(password.encode(), self.password.encode()) == self.password.encode()

    @staticmethod
    def gen_token(password):
        return hashlib.md5(password.encode()).hexdigest()


class Tasks(db.Entity):
    id = PrimaryKey(int, auto=True)
    user = Optional(Users)
    structures = Set("Structures")
    date = Required(datetime, default=datetime.now())
    task_type = Required(int, default=0)  # 0 - common models, 1,2,... - searches


class Structures(db.Entity):
    id = PrimaryKey(int, auto=True)
    structure = Optional(str)
    isreaction = Required(bool, default=False)
    temperature = Optional(float)
    pressure = Optional(float)
    additives = Set("Additiveset")

    task = Required(Tasks)
    status = Required(int, default=0)
    results = Set("Results")
    models = Set("Models")


class Results(db.Entity):
    id = PrimaryKey(int, auto=True)
    structure = Required(Structures)
    model = Required("Models")

    attrib = Required(str)
    value = Required(str)
    type = Required(int)


class Models(db.Entity):
    id = PrimaryKey(int, auto=True)
    name = Required(str)
    description = Required(str)
    example = Optional(str)
    destinations = Set("Destinations")
    model_type = Required(int, default=0)  # нечетные для реакций, четные для молекул и 0 для подготовки.

    structures = Set(Structures)
    results = Set(Results)


class Destinations(db.Entity):
    id = PrimaryKey(int, auto=True)
    model = Required(Models)
    host = Required(str)
    port = Required(int, default=6379)
    password = Optional(str)


class Additives(db.Entity):
    id = PrimaryKey(int, auto=True)
    structure = Optional(str)
    name = Required(str, unique=True)
    type = Required(int, default=0)
    additivesets = Set("Additiveset")


class Additiveset(db.Entity):
    amount = Required(float, default=1)
    additive = Required(Additives)
    structure = Required(Structures)


db.generate_mapping(create_tables=True)
