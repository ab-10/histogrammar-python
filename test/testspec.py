#!/usr/bin/env python

# Copyright 2016 DIANA-HEP
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import math
import sys
import unittest

from histogrammar import *

tolerance = 1e-12
util.relativeTolerance = tolerance
util.absoluteTolerance = tolerance

class TestSpec(unittest.TestCase):
    def compare(self, x, y, name):
        if Factory.fromJson(x) != Factory.fromJson(y):
            sys.stderr.write("                                          FAILED " + name + "\n")
            sys.stderr.write("                  PYTHON                           |                   SPECIFICATION\n")
            left = json.dumps(x, sort_keys=True, indent=2)
            right = json.dumps(y, sort_keys=True, indent=2)
            for leftline, rightline in zip(left.split("\n"), right.split("\n")):
                if leftline != rightline:
                    sys.stderr.write("{0:50s} > {1}\n".format(leftline, rightline))
                else:
                    sys.stderr.write("{0:50s} | {1}\n".format(leftline, rightline))
            self.assertEqual(Factory.fromJson(x), Factory.fromJson(y))
        
    def runTest(self):
        testdata = json.load(open("../histogrammar-multilang/test-data.json"))
        for x in testdata:
            for k, v in x.items():
                if k != "strings" and v in ("nan", "inf", "-inf"):
                    x[k] = float(v)
        
        testresults = json.load(open("../histogrammar-multilang/test-results.json"))

        def stripNames(x):
            if hasattr(x, "quantity"):
                x.quantity.name = None
            elif hasattr(x, "quantityName"):
                x.quantityName = None
            for xi in x.children:
                stripNames(xi)

        for testresult in testresults:
            sys.stderr.write(testresult["expr"] + "\n")

            zero = testresult["zero-named"]
            one = testresult["one-named"]
            two = testresult["two-named"]

            h1 = eval(testresult["expr"])
            h2 = eval(testresult["expr"])

            self.compare(h1.toJson(), zero, "NAMED ZERO")
            self.compare((h1 + h1).toJson(), zero, "NAMED ZERO + ZERO")
            self.compare(h1.zero().toJson(), zero, "NAMED ZERO.zero()")

            for x in testdata:
                h1.fill(x)
                h2.fill(x)
            self.compare(h1.toJson(), one, "NAMED ONE")
            self.compare(h1.zero().toJson(), zero, "NAMED ONE.zero()")
            self.compare((h1 + h1.zero()).toJson(), one, "NAMED ONE + ZERO")
            self.compare((h1.zero() + h1).toJson(), one, "NAMED ZERO + ONE")

            self.compare((h1 + h2).toJson(), two, "NAMED TWO VIA PLUS")

            for x in testdata:
                h1.fill(x)
            self.compare(h1.toJson(), two, "NAMED TWO VIA FILL")

            zero = testresult["zero-anonymous"]
            one = testresult["one-anonymous"]
            two = testresult["two-anonymous"]

            h1 = eval(testresult["expr"])
            stripNames(h1)
            h2 = eval(testresult["expr"])
            stripNames(h2)

            self.compare(h1.toJson(), zero, "ANONYMOUS ZERO")
            self.compare((h1 + h1).toJson(), zero, "ANONYMOUS ZERO + ZERO")
            self.compare(h1.zero().toJson(), zero, "ANONYMOUS ZERO.zero()")

            for x in testdata:
                h1.fill(x)
                h2.fill(x)
            self.compare(h1.toJson(), one, "ANONYMOUS ONE")
            self.compare(h1.zero().toJson(), zero, "ANONYMOUS ONE.zero()")
            self.compare((h1 + h1.zero()).toJson(), one, "ANONYMOUS ONE + ZERO")
            self.compare((h1.zero() + h1).toJson(), one, "ANONYMOUS ZERO + ONE")

            self.compare((h1 + h2).toJson(), two, "ANONYMOUS TWO VIA PLUS")

            for x in testdata:
                h1.fill(x)
            self.compare(h1.toJson(), two, "ANONYMOUS TWO VIA FILL")
