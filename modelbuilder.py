# -*- coding: utf-8 -*-
#
# Copyright 2015, 2016 Ramil Nugmanov <stsouko@live.ru>
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
import os
import threading
from utils.config import GACONF
from copy import deepcopy
import sys
from modeler.fragmentor import Fragmentor
from modeler.descriptoragregator import Descriptorsdict, Descriptorchain
from modeler.eed import Eed
from modeler.cxcalc import Pkab
from modeler.svmodel import Model as SVM
import argparse
import dill as pickle
import gzip
import tempfile
import time
import subprocess as sp
from CGRtools.FEAR import FEAR
from CGRtools.CGRcore import CGRcore
from CGRtools.RDFread import RDFread
from modeler.parsers import MBparser
from collections import Counter
from itertools import product, cycle


class DefaultList(list):
    @staticmethod
    def __copy__():
        return []


def descstarter(func, in_file, out_file, fformat, header):
    with open(in_file) as f:
        dsc = func(structures=f, parsesdf=True)
        if dsc:
            fformat(out_file, dsc['X'], dsc['Y'], header=header)
        else:
            print('BAD Descriptor generator params')
            return False
    return True


class Modelbuilder(MBparser):
    def __init__(self, **kwargs):
        self.__options = kwargs

        """ Descriptor generator Block
        """
        descgenerator = {}
        if self.__options['fragments']:
            descgenerator['F'] = [Fragmentor(**x) for x in self.parsefragmentoropts(self.__options['fragments'])]

        if self.__options['extention']:
            descgenerator['E'] = [Descriptorsdict(self.parseext(self.__options['extention']),
                                                  isreaction=self.__options['isreaction'])]

        if self.__options['eed']:
            descgenerator['D'] = [Eed(**x) for x in self.parsefragmentoropts(self.__options['eed'])]

        if self.__options['pka']:
            descgenerator['P'] = [Pkab(**x) for x in self.parsefragmentoropts(self.__options['pka'])]

        if self.__options['chains']:
            if self.__options['ad'] and len(self.__options['ad']) != len(self.__options['chains']):
                print('number of generators chains should be equal to number of ad modifiers')
                return

            self.__descgens = []
            for ch, ad in zip(self.__options['chains'], self.__options['ad'] or cycle([None])):
                gen_chain = [x for x in ch.split(':') if x in descgenerator]
                if ad:
                    ad_marks = [x in ('y', 'Y', '1', 'True', 'true') for x in ad.split(':')]
                    if len(ad_marks) != len(gen_chain):
                        print('length of generators chain should be equal to length of ad modifier')
                        return
                else:
                    ad_marks = cycle([True])

                ad_chain = {}
                for k, v in zip(gen_chain, ad_marks):
                    ad_chain.setdefault(k, []).append(v)

                combo = []
                for k, v in ad_chain.items():
                    if len(v) > 1:
                        if len(descgenerator[k]) != len(v):
                            print('length of same generators chain should be equal to number of same generators')
                            return
                        combo.append([list(zip(descgenerator[k], v))])
                    else:
                        combo.append(list(zip(descgenerator[k], cycle(v))))

                self.__descgens.extend(
                    [Descriptorchain(*[g for gs in c for g in (gs if isinstance(gs, list) else [gs])]) for c in
                     product(*combo)])
        else:
            self.__descgens = [y for x in descgenerator.values() for y in x]

        if not self.__options['output']:
            if os.path.isdir(self.__options['model']) or \
               (os.path.exists(self.__options['model']) and not os.access(self.__options['model'], os.W_OK)) or \
               (os.path.exists(self.__options['model'] + '.save') and
                    not (os.access(self.__options['model'] + '.save', os.W_OK) or
                         self.__options['model'] + '.save' == self.__options['reload'])) or \
               not os.access(os.path.dirname(self.__options['model']), os.W_OK):
                print('path for model saving not writable')
                return

            if self.__options['reload']:
                ests, description, self.__descgens = pickle.load(gzip.open(self.__options['reload'], 'rb'))
            else:
                description = self.parsemodeldescription(self.__options['description'])
                if self.__options['isreaction']:
                    description['is_reaction'] = True
                    description['hashes'] = self.__gethashes(self.__options['input'])
                    print(description['hashes'])

                ests = []
                svm = {'svr', 'svc'}.intersection(self.__options['estimator']).pop()
                # rf = {'rf'}.intersection(self.__options['estimator']).pop()
                if svm:
                    if self.__options['svm']:
                        estparams = self.getsvmparam(self.__options['svm'])
                    else:
                        estparams = self.__dragossvmfit(svm)

                    estparams = self.__chkest(estparams)
                    if not estparams:
                        return
                    ests.append((lambda *vargs, **kwargs: SVM(*vargs, estimator=svm, **kwargs),
                                 estparams))
                elif False:  # rf:  # todo: not implemented
                    if self.__options['rf']:
                        estparams = None
                        estparams = self.__chkest(estparams)
                        if not estparams:
                            ests.append((lambda *vargs, **kwargs: None,
                                         estparams))
                    else:
                        return

                if not ests:
                    return

                pickle.dump((ests, description, self.__descgens), gzip.open(self.__options['model'] + '.save', 'wb'))

            self.fit(ests, description)
        else:
            self.__gendesc(self.__options['output'], fformat=self.__options['format'], header=True)

    def fit(self, ests, description):
        models = [g(x, y.values(), open(self.__options['input']), parsesdf=True,
                    dispcoef=self.__options['dispcoef'], fit=self.__options['fit'],
                    scorers=self.__options['scorers'],
                    n_jobs=self.__options['n_jobs'], nfold=self.__options['nfold'],
                    smartcv=self.__options['smartcv'], rep_boost=self.__options['rep_boost'],
                    repetitions=self.__options['repetition'],
                    normalize='scale' in y or self.__options['normalize']) for g, e in ests
                  for x, y in zip(self.__descgens, e)]

        # todo: удалять совсем плохие фрагментации.
        if 'tol' not in description:
            description['tol'] = models[0].getmodelstats()['dragostolerance']
        print('name', description['name'])
        print('desc', description['desc'])
        print('tol', description['tol'])
        print('nlim', description.get('nlim'))
        pickle.dump(dict(models=models, config=description),
                    gzip.open(self.__options['model'], 'wb'))

    def __gethashes(self, inputfile, stereo=False, b_templates=None, e_rules=None, c_rules=None):
        hashes = set()
        _cgr = CGRcore(type='0', stereo=stereo, balance=0,
                       b_templates=open(b_templates) if b_templates else None,
                       e_rules=open(e_rules) if e_rules else None,
                       c_rules=open(c_rules) if c_rules else None)
        _fear = FEAR(isotop=False, stereo=False, hyb=False, element=True, deep=0)
        with open(inputfile) as f:
            for num, data in enumerate(RDFread(f).readdata(), start=1):
                if num % 100 == 1:
                    print("reaction: %d" % num, file=sys.stderr)
                g = _cgr.getCGR(data)
                hashes.update(x[1] for x in _fear.chkreaction(g, gennew=True)[-1])
        return list(hashes)

    def __chkest(self, estimatorparams):
        if not estimatorparams or 1 < len(estimatorparams) < len(self.__descgens) or \
                        len(estimatorparams) > len(self.__descgens):
            print('NUMBER of estimator params files SHOULD BE EQUAL to '
                  'number of descriptor generator params files or to 1')
            return False

        if len(estimatorparams) == 1:
            tmp = []
            for i in range(len(self.__descgens)):
                tmp.append(deepcopy(estimatorparams[0]))
            estimatorparams = tmp
        return estimatorparams

    def __gendesc(self, output, fformat='svm', header=False):
        queue = enumerate(self.__descgens, start=1)
        workpath = tempfile.mkdtemp(dir=self.__options['workpath'])
        while True:
            if threading.active_count() < self.__options['n_jobs']:
                tmp = next(queue, None)
                if tmp:
                    n, dgen = tmp
                    subworkpath = os.path.join(workpath, str(n))
                    os.mkdir(subworkpath)
                    dgen.setworkpath(subworkpath)
                    t = threading.Thread(target=descstarter,
                                         args=[dgen.get, self.__options['input'], '%s.%d' % (output, n),
                                               (self.savesvm if fformat == 'svm' else self.savecsv), header])
                    t.start()
                else:
                    break
            time.sleep(5)

        return True

    def __dragossvmfit(self, tasktype):
        """ files - basename for descriptors.
        """
        workpath = tempfile.mkdtemp(dir=self.__options['workpath'])
        files = os.path.join(workpath, 'drag')
        dragos_work = os.path.join(workpath, 'work')

        execparams = [GACONF, workpath, tasktype]
        if self.__gendesc(files):
            if sp.call(execparams) == 0:
                best = {}
                with open(os.path.join(dragos_work, 'best_pop')) as f:
                    for line in f:
                        dset, normal, *_, attempt, _, _ = line.split()
                        best.setdefault(int(dset[5:]), (normal, attempt))

                cleared, svmpar, scale = [], [], []
                for k, (nv, av) in best.items():
                    cleared.append(self.__descgens[k - 1])
                    svmpar.append(os.path.join(dragos_work, av, 'svm.pars'))
                    scale.append(nv)

                self.__descgens = cleared

                svm = []
                svmpar = self.getsvmparam(svmpar)
                if len(svmpar) == len(scale):
                    for x, y in zip(svmpar, scale):
                        svm.append({'scale' if y == 'scaled' else 'orig': list(x.values())[0]})
                    return svm
        return []


def argparser():
    rawopts = argparse.ArgumentParser(description="Model Builder",
                                      epilog="Copyright 2015, 2016 Ramil Nugmanov <stsouko@live.ru>",
                                      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    rawopts.add_argument("--workpath", "-w", type=str, default='.', help="work path")

    rawopts.add_argument("--input", "-i", type=str, default='input.sdf', help="input SDF or RDF")
    rawopts.add_argument("--output", "-o", type=str, default=None, help="output SVM|CSV")
    rawopts.add_argument("--format", "-of", type=str, default='svm', choices=['svm', 'csv'], help="output format")

    rawopts.add_argument("--reload", type=str, default=None, help="saved state before fitting")

    rawopts.add_argument("--model", "-m", type=str, default='output.model', help="output model")

    rawopts.add_argument("--isreaction", "-ir", action='store_true', help="set as reaction model")

    rawopts.add_argument("--extention", "-e", action='append', type=str, default=None,
                         help="extention data files. -e extname:filename [-e extname2:filename2]")

    rawopts.add_argument("--fragments", "-f", type=str, default=None, help="ISIDA Fragmentor keys file")

    rawopts.add_argument("--eed", type=str, default=None, help="DRAGOS EED keys file")

    rawopts.add_argument("--pka", type=str, default=None, help="CXCALC pka keys file")

    rawopts.add_argument("--chains", "-c", action='append', type=str, default=None,
                         help="descriptors chains. where F-fragmentor, D-eed, E-extention, P-pka. "
                              "-c F:E [-c E:D:P]")
    rawopts.add_argument("-ad", action='append', type=str, default=None,
                         help="consider descriptor generator AD in descriptors chains. "
                              "example: -ad y:n:y [True = y Y True true 1] for -c F:E:P [ignore extention AD] "
                              "number of -ad should be equal to number of --chains or skipped")

    rawopts.add_argument("--description", "-ds", type=str, default='model.dsc', help="model description file")

    rawopts.add_argument("--svm", "-s", action='append', type=str, default=None,
                         help="SVM params. use Dragos Genetics if don't set."
                              "can be multiple [-s 1 -s 2 ...]"
                              "(number of files should be equal to number of configured descriptor generators) "
                              "or single for all")

    rawopts.add_argument("--nfold", "-n", type=int, default=5, help="number of folds")
    rawopts.add_argument("--repetition", "-r", type=int, default=1, help="number of repetitions")
    rawopts.add_argument("--rep_boost", "-R", type=int, default=25,
                         help="percentage of repetitions for use in greed search for optimization speedup")
    rawopts.add_argument("--n_jobs", "-j", type=int, default=2, help="number of parallel fit jobs")

    rawopts.add_argument("--estimator", "-E", action='append', type=str, default=DefaultList(['svr']),
                         choices=['svr', 'svc'],
                         help="estimator")
    rawopts.add_argument("--scorers", "-T", action='append', type=str, default=DefaultList(['rmse', 'r2']),
                         choices=['rmse', 'r2', 'ba', 'kappa'],
                         help="needed scoring functions. -T rmse [-T r2]")
    rawopts.add_argument("--fit", "-t", type=str, default='rmse', choices=['rmse', 'r2', 'ba', 'kappa'],
                         help="crossval score for parameters fit. (should be in selected scorers)")

    rawopts.add_argument("--dispcoef", "-p", type=float, default=0,
                         help="score parameter. mean(score) - dispcoef * sqrt(variance(score)). [-score for rmse]")

    rawopts.add_argument("--normalize", "-N", action='store_true', help="normalize X vector to range(0, 1)")
    rawopts.add_argument("--smartcv", "-S", action='store_true', help="smart crossvalidation [NOT implemented]")

    return vars(rawopts.parse_args())


if __name__ == '__main__':
    main = Modelbuilder(**argparser())
