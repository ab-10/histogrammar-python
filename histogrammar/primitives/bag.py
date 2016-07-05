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
import numbers

from histogrammar.defs import *
from histogrammar.util import *

class Bag(Factory, Container):
    """Accumulate raw numbers, vectors of numbers, or strings, with identical values merged.

    A bag is the appropriate data type for scatter plots: a container that collects raw values, maintaining multiplicity but not order. (A "bag" is also known as a "multiset.") Conceptually, it is a mapping from distinct raw values to the number of observations: when two instances of the same raw value are observed, one key is stored and their weights add.

    Although the user-defined function may return scalar numbers, fixed-dimension vectors of numbers, or categorical strings, it may not mix types. Different Bag primitives in an analysis tree may collect different types.

    Consider using Bag with :doc:`Limit <histogrammar.primitives.limit.Limit>` for collections that roll over to a mere count when they exceed a limit, or :doc:`Sample <histogrammar.primitives.sample.Sample>` for reservoir sampling.
    """

    @staticmethod
    def ed(entries, values):
        """Create a Bag that is only capable of being added.

        Parameters:
            entries (float): the number of entries.
            values (dict from float, tuple of floats, or str to float): the number of entries for each unique item.
        """

        if not isinstance(entries, numbers.Real) and entries not in ("nan", "inf", "-inf"):
            raise TypeError("entries ({0}) must be a number".format(entries))
        if not isinstance(values, dict) and not all(isinstance(k, numbers.Real) for k, v in values.items()):
            raise TypeError("values ({0}) must be a dict from numbers to range type".format(values))
        if float(entries) < 0.0:
            raise ValueError("entries ({0}) cannot be negative".format(entries))
        out = Bag(None)
        out.entries = float(entries)
        out.values = values
        return out.specialize()

    @staticmethod
    def ing(quantity):
        """Synonym for ``__init__``."""
        return Bag(quantity)

    def __init__(self, quantity):
        """Create a Bag that is capable of being filled and added.

        Parameters:
            quantity (function returning a float, a tuple of floats, or a str): computes the quantity of interest from the data.

        Other parameters:
            entries (float): the number of entries, initially 0.0.
            values (dict from quantity return type to float): the number of entries for each unique item.
        """
        self.quantity = serializable(quantity)
        self.entries = 0.0
        self.values = {}
        super(Bag, self).__init__()
        self.specialize()

    @inheritdoc(Container)
    def zero(self): return Bag(self.quantity)

    @inheritdoc(Container)
    def __add__(self, other):
        if isinstance(other, Bag):
            out = Bag(self.quantity)

            out.entries = self.entries + other.entries

            out.values = dict(self.values)
            for value, count in other.values.items():
                if value in out.values:
                    out.values[value] += count
                else:
                    out.values[value] = count

            return out.specialize()

        else:
            raise ContainerException("cannot add {0} and {1}".format(self.name, other.name))

    @inheritdoc(Container)
    def fill(self, datum, weight=1.0):
        self._checkForCrossReferences()

        if weight > 0.0:
            q = self.quantity(datum)
            self._update(q, weight)

    def _update(self, q, weight):
        if isinstance(q, basestring):
            pass
        elif isinstance(q, (list, tuple)):
            try:
                q = tuple(floatOrNan(qi) for qi in q)
            except:
                raise TypeError("function return value ({0}) must be boolean, number, string, or list/tuple of numbers".format(q))
        else:
            try:
                q = floatOrNan(q)
            except:
                raise TypeError("function return value ({0}) must be boolean, number, string, or list/tuple of numbers".format(q))

        # no possibility of exception from here on out (for rollback)
        self.entries += weight
        if q in self.values:
            self.values[q] += weight
        else:
            self.values[q] = weight

    def _numpy(self, data, weights, shape):
        import numpy
        q = self.quantity(data)
        assert isinstance(q, numpy.ndarray)
        if shape[0] is None:
            shape[0] = q.shape[0]
        else:
            assert q.shape[0] == shape[0]

        self._checkNPWeights(weights, shape)
        weights = self._makeNPWeights(weights, shape)

        for x, w in zip(q, weights):
            if w > 0.0:
                if isinstance(x, numpy.ndarray):
                    x = x.tolist()
                self._update(x, float(w))
        
    @property
    def children(self):
        """List of sub-aggregators, to make it possible to walk the tree."""
        return []

    @inheritdoc(Container)
    def toJsonFragment(self, suppressName):
        aslist = sorted(x for x in self.values.items() if x[0] != "nan")
        if "nan" in self.values:
            aslist.append(("nan", self.values["nan"]))
        return maybeAdd({
            "entries": floatToJson(self.entries),
            "values": [{"w": floatToJson(n), "v": rangeToJson(v)} for v, n in aslist],
            }, name=(None if suppressName else self.quantity.name))

    @staticmethod
    @inheritdoc(Factory)
    def fromJsonFragment(json, nameFromParent):
        if isinstance(json, dict) and hasKeys(json.keys(), ["entries", "values"], ["name"]):
            if json["entries"] in ("nan", "inf", "-inf") or isinstance(json["entries"], numbers.Real):
                entries = json["entries"]
            else:
                raise JsonFormatException(json["entries"], "Bag.entries")

            if isinstance(json.get("name", None), basestring):
                name = json["name"]
            elif json.get("name", None) is None:
                name = None
            else:
                raise JsonFormatException(json["name"], "Bag.name")

            if json["values"] is None:
                values = None

            elif json["values"] is None or isinstance(json["values"], list):
                values = {}
                for i, nv in enumerate(json["values"]):
                    if isinstance(nv, dict) and hasKeys(nv.keys(), ["w", "v"]):
                        if nv["w"] in ("nan", "inf", "-inf") or isinstance(nv["w"], numbers.Real):
                            n = float(nv["w"])
                        else:
                            raise JsonFormatException(nv["w"], "Bag.values {0} n".format(i))

                        if nv["v"] in ("nan", "inf", "-inf") or isinstance(nv["v"], numbers.Real):
                            v = floatOrNan(nv["v"])
                        elif isinstance(nv["v"], basestring):
                            v = nv["v"]
                        elif isinstance(nv["v"], (list, tuple)):
                            for j, d in enumerate(nv["v"]):
                                if d not in ("nan", "inf", "-inf") and not isinstance(d, numbers.Real):
                                    raise JsonFormatException(d, "Bag.values {0} v {1}".format(i, j))
                            v = tuple(map(floatOrNan, nv["v"]))
                        else:
                            raise JsonFormatException(nv["v"], "Bag.values {0} v".format(i))

                        values[v] = n

                    else:
                        raise JsonFormatException(nv, "Bag.values {0}".format(i))

            elif json["values"] is None:
                values = None

            else:
                raise JsonFormatException(json["values"], "Bag.values")

            out = Bag.ed(entries, values)
            out.quantity.name = nameFromParent if name is None else name
            return out.specialize()

        else:
            raise JsonFormatException(json, "Bag")
        
    def __repr__(self):
        return "<Bag size={0}>".format(len(self.values))

    def __eq__(self, other):
        if len(self.values) != len(other.values):
            return False

        one = sorted(x for x in self.values.items() if x[0] != "nan") + [("nan", self.values.get("nan"))]
        two = sorted(x for x in other.values.items() if x[0] != "nan") + [("nan", other.values.get("nan"))]

        for (v1, w1), (v2, w2) in zip(one, two):
            if isinstance(v1, basestring) and isinstance(v2, basestring):
                if v1 != v2:
                    return False
            elif isinstance(v1, numbers.Real) and isinstance(v2, numbers.Real):
                if not numeq(v1, v2):
                    return False
            elif isinstance(v1, tuple) and isinstance(v2, tuple) and len(v1) == len(v2):
                for v1i, v2i in zip(v1, v2):
                    if isinstance(v1i, numbers.Real) and isinstance(v2i, numbers.Real):
                        if not numeq(v1i, v2i):
                            return False
                    else:
                        return False
            else:
                return False

            if v1 == "nan" and v2 == "nan" and w1 is None and w2 is None:
                pass
            elif isinstance(w1, numbers.Real) and isinstance(w2, numbers.Real):
                if not numeq(w1, w2):
                    return False
            else:
                return False

        return isinstance(other, Bag) and self.quantity == other.quantity and numeq(self.entries, other.entries)

    def __ne__(self, other): return not self == other

    def __hash__(self):
       return hash((self.quantity, self.entries, tuple(self.values.items())))

Factory.register(Bag)
