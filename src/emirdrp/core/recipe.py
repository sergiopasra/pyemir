#
# Copyright 2008-2021 Universidad Complutense de Madrid
#
# This file is part of PyEmir
#
# SPDX-License-Identifier: GPL-3.0+
# License-Filename: LICENSE.txt
#

import logging
import collections.abc

import numina.ext.gtc
import numina.core.recipes as recipes
import numina.util.flow as flowmod

import emirdrp.core.correctors as cor
import emirdrp.processing.info
import emirdrp.products as prods
import emirdrp.datamodel


class EmirRecipe(recipes.BaseRecipe):
    """Base clase for all EMIR Recipes


    Attributes
    ----------
    logger :
         recipe logger

    datamodel : EmirDataModel

    """
    logger = logging.getLogger(__name__)
    datamodel = emirdrp.datamodel.EmirDataModel()

    def types_getter(self):
        imgtypes = [prods.MasterBadPixelMask,
                    prods.MasterBias,
                    prods.MasterDark,
                    prods.MasterIntensityFlat,
                    prods.MasterSpectralFlat,
                    prods.MasterSky
                    ]
        getters = [cor.get_corrector_p, cor.get_corrector_b, cor.get_corrector_d,
                   [cor.get_corrector_f, cor.get_checker], cor.get_corrector_sf, cor.get_corrector_s]

        return imgtypes, getters

    def get_filters(self):
        imgtypes, getters = self.types_getter()
        used_getters = []
        for rtype, getter in zip(imgtypes, getters):
            self.logger.debug('get_filters, %s  %s', rtype, getter)
            if rtype is None:
                # Unconditional
                if isinstance(getter, collections.abc.Iterable):
                    used_getters.extend(getter)
                else:
                    used_getters.append(getter)
            else:
                # Search
                for key, val in self.RecipeInput.stored().items():
                    if isinstance(val.type, rtype):
                        if isinstance(getter, collections.abc.Iterable):
                            used_getters.extend(getter)
                        else:
                            used_getters.append(getter)
                        break
                else:
                    pass
        return used_getters

    def init_filters_generic(self, rinput, getters, ins):
        # with BPM, bias, dark, flat and sky
        if numina.ext.gtc.check_gtc():
            self.logger.debug('running in GTC environment')
        else:
            self.logger.debug('running outside of GTC environment')

        meta = emirdrp.processing.info.gather_info(rinput)
        self.logger.debug('obresult info')
        for entry in meta['obresult']:
            self.logger.debug('frame info is %s', entry)
        correctors = [getter(rinput, meta, ins, self.datamodel) for getter in getters]
        flow = flowmod.SerialFlow(correctors)
        return flow

    def init_filters(self, rinput, ins='EMIR'):

        a = rinput.attrs()
        b = rinput.stored()

        for k,v in a.items():
            vv = b[k]
            #print(k,v,vv.type)

        #print(rinput.attrs())
        #print(rinput.stored())

        tree = _Ft(prods.MasterBadPixelMask)
        node_bias = _Ft(prods.MasterBias)
        tree.add(node_bias)
        node_dark = _Ft(prods.MasterDark)
        node_bias.add(node_dark)
        node_dark.add(_Ft(prods.MasterIntensityFlat, children=[_Ft(prods.MasterSky)]))
        node_dark.add(_Ft(prods.MasterSpectralFlat, children=[_Ft(prods.SkySpectrum)]))

        def func(tree):
            a = rinput.attrs()
            b = rinput.stored()
            for v in b.values():
                # print('b', v.type, tree.content)
                if isinstance(v.type, tree.content):
                    val = a[v.dest]
                    # print(v.dest, v.optional, a[v.dest])
                    if val is None:
                        if v.optional:
                            print('Nothing')
                            break
                        else:
                            raise ValueError('undefined')
                    else:
                        print('Node')
                        break

                    #print('c', v, tree.content)
            # print(tree.content)

        visit(tree, func)

        getters = self.get_filters()
        return self.init_filters_generic(rinput, getters, ins)

    def aggregate_result(self, result, rinput):
        return result


class _Ft(object):
    def __init__(self, content, children=None):
        self.content = content
        if children is None:
            self.children = []
        else:
            self.children = children

    def add(self, node):
        self.children.append(node)


def visit(tree, func):
    func(tree)
    for c in tree.children:
        visit(c, func)