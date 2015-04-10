# -*- coding: utf-8 -*-
#
# Copyright 2015 Ramil Nugmanov <stsouko@live.ru>
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
import os
import pickle
import time
from modelset import register_model, chemaxpost
import subprocess as sp


class Model():
    def __init__(self):
        self.modelpath = os.path.dirname(__file__)
        self.fragmentor = os.path.join(self.modelpath, 'sn2', "Fragmentor")
        self.condenser = os.path.join(self.modelpath, 'sn2', "condenser")
        self.header = os.path.join(self.modelpath, 'sn2', "model.hdr")
        self.solvent_file = os.path.join(self.modelpath, 'sn2', "solvents.csv")
        model = os.path.join(self.modelpath, 'sn2', "model.svm")
        self.model = pickle.load(open(model, 'rb'))
        self.solvents = self.load_solvents()

    def load_solvents(self):
        solvents = {}
        with open(self.solvent_file, 'r') as f:
            for line in f:
                key, *value = line.split(';')
                solvents[key] = [float(x) for x in value]
        return solvents

    def getdesc(self):
        desc = 'sn2 reactions of azides salts with halogen alkanes constants prediction'
        return desc

    def getname(self):
        name = 'sn2 halogens-azides'
        return name

    def is_reation(self):
        return 1

    def gethashes(self):
        hashlist = ['1006099,1017020,2007079', '1006099,1035020,2007079', '1006099,1053020,2007079', # balanced fp
                    '1006099,1017018,2007079', '1006099,1035018,2007079', '1006099,1053018,2007079', #unbal leaving gr
                    '1006099,1017018,2007081', '1006099,1035018,2007081', '1006099,1053018,2007081'] #unbal leav and nuc
        return hashlist

    def getresult(self, chemical):
        data = {"structure": chemical['structure'], "parameters": "rdf"}
        structure = chemaxpost('calculate/stringMolExport', data)
        temperature = chemical['temperature'] if chemical['temperature'] else 298
        solvent = chemical['solvents'][0]['name'] if chemical['solvents'][0] else 'Undefined'

        fixtime = int(time.time())
        temp_file_rdf = os.path.join(self.modelpath, 'sn2', "structure-%d.rdf" % fixtime)
        temp_file_sdf = os.path.join(self.modelpath, 'sn2', "structure-%d.sdf" % fixtime)
        temp_file_frag = os.path.join(self.modelpath, 'sn2', "structure-%d" % fixtime)
        temp_file_hdr = temp_file_frag + '.hdr'
        temp_file_csv = temp_file_frag + '.csv'

        if structure:
            with open(temp_file_rdf, 'w') as f:
                f.write(structure)
            try:
                sp.call([self.condenser, '-i', temp_file_rdf, '-o', temp_file_sdf])
                sp.call([self.fragmentor, '-i', temp_file_sdf, '-o', temp_file_frag, '-h', self.header, '-t', '3', '-l',
                         '3', '-u', '6', '-f', 'CSV', '--UseFormalCharge', '--DoAllWays'])
            except:
                print('YOU DO IT WRONG')
                result = False
            else:
                with open(temp_file_csv, 'r') as f:
                    fragments = [int(x) for x in f.readline().split(';')[1:165]]

                vector = [temperature] + self.solvents.get(solvent, [0]*13) + fragments

                if os.path.getsize(self.header) != os.path.getsize(temp_file_hdr):
                    result = [dict(type='text', attrib='applicability domain ',
                                   value='pure. molecule consist untrained fragments')]
                else:
                    result = [dict(type='text', attrib='applicability domain ',
                                   value='good')]

                constant = self.model.predict(vector)[0]
                result.append(dict(type='text', attrib='tabulated constant', value='%.2f' % constant))
            finally:
                os.remove(temp_file_rdf)
                os.remove(temp_file_sdf)
                os.remove(temp_file_csv)
                os.remove(temp_file_hdr)

            return result
        else:
            return False
"""
result - list with data returned by model.
result show on page in same order. [1,2,3] show as:
1
2
3

result items is dicts.
dicts consist next keys:
'value' - text field. use for show result
'attrib' - text field. use as header
'type' - may be 'text', 'link' or 'structure'.
  'text' type show 'value' in page as text
  'link' type show as clickable link
  'structure' type show as picture. it may be in formats recognized by marvin

example:
                result = [dict(type='text', attrib='this string show as description', value='this string show as value'),
                          dict(type='link', attrib='this string show as description for link', value='download/1427724576.zip'),
                          dict(type='structure', attrib='this string show as description for structure image', value='<?xml version="1.0" encoding="UTF-8"?><cml xmlns="http://www.chemaxon.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.chemaxon.com/marvin/help/formats/schema/mrvSchema_14_7_14.xsd" version="ChemAxon file format v14.7.14, generated by v14.7.28.0"><MDocument>  <MChemicalStruct>    <molecule molID="m1">      <atomArray atomID="a1 a2 a3 a4 a5 a6 a7 a8 a9 a10 a11 a12 a13 a14 a15 a16 a17 a18" elementType="C C C C C C C C C C C C C C C C C C" x2="-1.278749942779541 -2.612389942779541 -3.946183942779541 -3.946183942779541 -2.612389942779541 -1.278749942779541 0.05489005722045892 1.388684057220459 1.388684057220459 0.05489005722045892 2.722324057220459 1.388684057220459 0.05489005722045892 2.722324057220459 4.055964057220459 5.389758057220459 5.389758057220459 4.055964057220459" y2="0.8937500011920929 1.663750001192093 0.8937500011920929 -0.6462499988079071 -1.4162499988079071 -0.6462499988079071 -1.4162499988079071 -0.6462499988079071 0.8937500011920929 1.663750001192093 3.203750001192093 3.973750001192093 3.203750001192093 1.663750001192093 0.8937500011920929 1.663750001192093 3.203750001192093 3.973750001192093"/>      <bondArray>        <bond id="b1" atomRefs2="a1 a2" order="2"/>        <bond id="b2" atomRefs2="a1 a6" order="1"/>        <bond id="b3" atomRefs2="a1 a10" order="1"/>        <bond id="b4" atomRefs2="a2 a3" order="1"/>        <bond id="b5" atomRefs2="a3 a4" order="2"/>        <bond id="b6" atomRefs2="a4 a5" order="1"/>        <bond id="b7" atomRefs2="a5 a6" order="2"/>        <bond id="b8" atomRefs2="a6 a7" order="1"/>        <bond id="b9" atomRefs2="a7 a8" order="2"/>        <bond id="b10" atomRefs2="a8 a9" order="1"/>        <bond id="b11" atomRefs2="a9 a10" order="2"/>        <bond id="b12" atomRefs2="a11 a12" order="1"/>        <bond id="b13" atomRefs2="a12 a13" order="2"/>        <bond id="b14" atomRefs2="a15 a16" order="1"/>        <bond id="b15" atomRefs2="a16 a17" order="2"/>        <bond id="b16" atomRefs2="a17 a18" order="1"/>        <bond id="b17" atomRefs2="a11 a14" order="1"/>        <bond id="b18" atomRefs2="a11 a18" order="2"/>        <bond id="b19" atomRefs2="a14 a15" order="2"/>        <bond id="b20" atomRefs2="a9 a14" order="1"/>        <bond id="b21" atomRefs2="a13 a10" order="1"/>      </bondArray>    </molecule>  </MChemicalStruct></MDocument></cml>')]
"""
model = Model()
register_model(model.getname(), model)