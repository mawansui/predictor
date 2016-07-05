# -*- coding: utf-8 -*-
#
# Copyright 2016 Ramil Nugmanov <stsouko@live.ru>
# This file is part of PREDICTOR.
#
# PREDICTOR is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
from modeler.structprepare import Pharmacophoreatommarker, StandardizeDragos, CGRatommarker
from io import StringIO
from CGRtools.SDFread import SDFread
from CGRtools.SDFwrite import SDFwrite
from CGRtools.RDFread import RDFread
from subprocess import Popen, PIPE, STDOUT
from utils.config import EED
import os


class Eed(object):
    def __init__(self, workpath='.', marker_rules=None, standardize=None,
                 cgr_marker=None, cgr_marker_prepare=None, cgr_marker_postprocess=None, cgr_stereo=False):
        self.__dragos_marker = Pharmacophoreatommarker(marker_rules, workpath) if marker_rules else None

        self.__cgr_marker = CGRatommarker(cgr_marker, prepare=cgr_marker_prepare,
                                          postprocess=cgr_marker_postprocess,
                                          stereo=cgr_stereo) if cgr_marker else None

        self.__dragos_std = StandardizeDragos(standardize) if standardize and not self.__cgr_marker else None
        self.__workpath = workpath

    def setworkpath(self, workpath):
        self.__workpath = workpath
        if self.__dragos_marker:
            self.__dragos_marker.setworkpath(workpath)

    def get(self, structures, **kwargs):
        reader = RDFread(structures) if self.__cgr_marker else SDFread(structures)
        data = list(reader.readdata())

        if self.__dragos_std:
            data = self.__dragos_std.get(data)

        if not data:
            return False

        if self.__cgr_marker:
            data = self.__cgr_marker.get(data)

        elif self.__dragos_marker:
            data = self.__dragos_marker.get(data)

        if not data:
            return False

        doubles = []

        writers = [SDFwrite(StringIO()) for _ in
                   range(self.__cgr_marker.getcount() if self.__cgr_marker
                         else self.__dragos_marker.getcount() if self.__dragos_marker else 1)]

        for s_numb, s in enumerate(data):
            if isinstance(s, list):
                for d in s:
                    tmp = [s_numb]
                    for w, x in zip(writers, d):
                        w.writedata(x[1])
                        tmp.append(x[0])
                    doubles.append(tmp)
            else:
                writers[0].writedata(s)
                doubles.append([s_numb])

        p = Popen([EED], stdout=PIPE, stdin=PIPE, stderr=STDOUT)
        with StringIO() as f:
            tmp = SDFwrite(f)
            for x in structure:
                tmp.writedata(x)

            res = p.communicate(input=f.getvalue().encode())[0].decode()
            if p.returncode == 0:
                return list(RDFread(StringIO(res)).readdata(remap=remap))

        with StringIO() as f:
            writer = SDFwrite(f)

        return
