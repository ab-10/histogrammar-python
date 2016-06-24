#!/usr/bin/env python

# Copyright 2016 Jim Pivarski
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

from histogrammar.defs import *
from histogrammar.util import *
from histogrammar.primitives.count import *

class Fraction(Factory, Container):
    """Accumulate two aggregators, one containing only entries that pass a given selection (numerator) and another that contains all entries (denominator).

    The aggregator may be a simple :doc:`Count <histogrammar.primitives.count.Count>` to measure the efficiency of a cut, a :doc:`Bin <histogrammar.primitives.bin.Bin>` to plot a turn-on curve, or anything else to be tested with and without a cut.

    As a side effect of NaN values returning false for any comparison, a NaN return value from the selection is treated as a failed cut (the denominator is filled but the numerator is not).
    """

    @staticmethod
    def ed(entries, numerator, denominator):
        """
        * `entries` (double) is the number of entries.
        * `numerator` (past-tense aggregator) is the filled numerator.
        * `denominator` (past-tense aggregator) is the filled denominator.
        """
        if not isinstance(entries, (int, long, float)):
            raise TypeError("entries ({}) must be a number".format(entries))
        if not isinstance(numerator, Container):
            raise TypeError("numerator ({}) must be a Container".format(numerator))
        if not isinstance(denominator, Container):
            raise TypeError("denominatior ({}) must be a Container".format(denominatior))
        if entries < 0.0:
            raise ValueError("entries ({}) cannot be negative".format(entries))

        out = Fraction(None, None)
        out.entries = float(entries)
        out.numerator = numerator
        out.denominator = denominator
        return out.specialize()

    @staticmethod
    def ing(quantity, value):
        """Synonym for ``__init__``."""
        return Fraction(quantity, value)

    def __init__(self, quantity, value):
        """
        * `quantity` (function returning boolean or double) computes the quantity of interest from the data and interprets it as a selection (multiplicative factor on weight).
        * `value` (present-tense aggregator) generates sub-aggregators for the numerator and denominator.
        * `entries` (mutable double) is the number of entries, initially 0.0.
        * `numerator` (present-tense aggregator) is the sub-aggregator of entries that pass the selection.
        * `denominator` (present-tense aggregator) is the sub-aggregator of all entries.
        """
        if value is not None and not isinstance(value, Container):
            raise TypeError("value ({}) must be None or a Container".format(value))
        self.entries = 0.0
        self.quantity = serializable(quantity)
        if value is not None:
            self.numerator = value.zero()
            self.denominator = value.zero()
        super(Fraction, self).__init__()
        self.specialize()

    @staticmethod
    def build(numerator, denominator):
        """
        * `numerator` (past-tense aggregator) is the filled numerator.
        * `denominator` (past-tense aggregator) is the filled denominator.
        """
        if not isinstance(numerator, Container):
            raise TypeError("numerator ({}) must be a Container".format(numerator))
        if not isinstance(denominator, Container):
            raise TypeError("denominatior ({}) must be a Container".format(denominatior))
        # check for compatibility
        numerator + denominator
        # return object
        return Fraction.ed(denominator.entries, numerator, denominator)

    @inheritdoc(Container)
    def zero(self):
        out = Fraction(self.quantity, None)
        out.numerator = self.numerator.zero()
        out.denominator = self.denominator.zero()
        return out.specialize()

    @inheritdoc(Container)
    def __add__(self, other):
        if isinstance(other, Fraction):
            out = Fraction(self.quantity, None)
            out.numerator = self.numerator + other.numerator
            out.denominator = self.denominator + other.denominator
            return out.specialize()
        else:
            raise ContainerException("cannot add {} and {}".format(self.name, other.name))

    @inheritdoc(Container)
    def fill(self, datum, weight=1.0):
        self._checkForCrossReferences()
        w = self.quantity(datum)
        if not isinstance(w, (bool, int, long, float)):
            raise TypeError("function return value ({}) must be boolean or number".format(w))
        w *= weight

        if weight > 0.0:
            self.denominator.fill(datum, weight)
        if w > 0.0:
            self.numerator.fill(datum, w)

        # no possibility of exception from here on out (for rollback)
        self.entries += weight

    @property
    def children(self):
        return [self.numerator, self.denominator]

    @inheritdoc(Container)
    def toJsonFragment(self, suppressName):
        if getattr(self.numerator, "quantity", None) is not None:
            binsName = self.numerator.quantity.name
        elif getattr(self.numerator, "quantityName", None) is not None:
            binsName = self.numerator.quantityName
        else:
            binsName = None

        return maybeAdd({
            "entries": floatToJson(self.entries),
            "type": self.numerator.name,
            "numerator": self.numerator.toJsonFragment(True),
            "denominator": self.denominator.toJsonFragment(True),
            }, **{"name": None if suppressName else self.quantity.name,
                  "sub:name": binsName})

    @staticmethod
    @inheritdoc(Factory)
    def fromJsonFragment(json, nameFromParent):
        if isinstance(json, dict) and hasKeys(json.keys(), ["entries", "type", "numerator", "denominator"], ["name", "sub:name"]):
            if isinstance(json["entries"], (int, long, float)):
                entries = float(json["entries"])
            else:
                raise JsonFormatException(json, "Fraction.entries")

            if isinstance(json.get("name", None), basestring):
                name = json["name"]
            elif json.get("name", None) is None:
                name = None
            else:
                raise JsonFormatException(json["name"], "Fraction.name")

            if isinstance(json["type"], basestring):
                factory = Factory.registered[json["type"]]
            else:
                raise JsonFormatException(json, "Fraction.type")

            if isinstance(json.get("sub:name", None), basestring):
                subName = json["sub:name"]
            elif json.get("sub:name", None) is None:
                subName = None
            else:
                raise JsonFormatException(json["sub:name"], "Fraction.sub:name")

            numerator = factory.fromJsonFragment(json["numerator"], subName)
            denominator = factory.fromJsonFragment(json["denominator"], subName)

            out = Fraction.ed(entries, numerator, denominator)
            out.quantity.name = nameFromParent if name is None else name
            return out.specialize()

        else:
            raise JsonFormatException(json, "Fraction")

    def __repr__(self):
        return "<Fraction values={}>".format(self.numerator.name)

    def __eq__(self, other):
        return isinstance(other, Fraction) and numeq(self.entries, other.entries) and self.quantity == other.quantity and self.numerator == other.numerator and self.denominator == other.denominator

    def __hash__(self):
        return hash((self.entries, self.quantity, self.numerator, self.denominator))

Factory.register(Fraction)
