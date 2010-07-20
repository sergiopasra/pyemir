#
# Copyright 2008-2010 Sergio Pascual
# 
# This file is part of PyEmir
# 
# PyEmir is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# PyEmir is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with PyEmir.  If not, see <http://www.gnu.org/licenses/>.
# 

'''Recipe for image simulation.'''


import logging

import numpy

from numina.recipes import RecipeBase
import numina.qa as qa
from numina.simulation import RunCounter
from emir.instrument.detector import EmirDetector
from emir.dataproducts import create_raw
from emir.recipes import EmirRecipeMixin

_logger = logging.getLogger("emir.recipes")

class Recipe(RecipeBase, EmirRecipeMixin):
    '''Recipe to simulate EMIR images.'''
    
    required_parameters = ['detector', 
                           'readout',
                           'nformat'
                           ]
    
    capabilities = ['simulate_image']
    
    def __init__(self, values):
        super(Recipe, self).__init__(values)
        #
        _logger.info('Run counter created')
        self.runcounter = RunCounter("r%05d")
        
        _logger.info('Creating detector')
        
        self.detector = EmirDetector(**self.parameters['detector'])
        _logger.info('Configuring detector')
        self.detector.configure(self.parameters['readout'])
        
        self.input = numpy.zeros(self.parameters['detector']['shape'])
        self.detector.exposure(self.parameters['readout']['exposure'])
        self.repeat = self.parameters['readout']['repeat']
     
    def run(self):
        _logger.info('Creating simulated array')    
        output = self.detector.lpath(self.input)
        run, cfile = self.runcounter.runstring()
        headers = {'RUN': run, 'FILENAME': cfile}
        
        _logger.info('Collecting detector metadata')
        headers.update(self.detector.metadata())
        
        _logger.info('Building FITS structure')
        hdulist = create_raw(output, headers)
        return {'qa': qa.UNKNOWN, 'simulated_image': hdulist}

if __name__ == '__main__':
    import os
    import simplejson as json
    import tempfile
    
    from numina.user import main
    from numina.jsonserializer import to_json
      
    pv = {'detector': {'shape': (2048, 2048),
                             'ron': 2.16,
                             'dark': 0.37,
                             'gain': 3.028,
                             'flat': 1.0,
                             'well': 65536,},
                'readout': {'mode': 'cds',
                            'reads': 3,
                            'repeat': 3,
                            'scheme': 'perline',
                            'exposure': 0},
            'nformat': "r%05d",
            'observing_mode': 'simulate_image'
                }
    
    tmpdir = tempfile.mkdtemp(suffix='emir')
    os.chdir(tmpdir)
    _logger.info('Working directory is %s', tmpdir)
    
    conffile = 'config.json'
    
    f = open(conffile, 'w+')
    try:
        json.dump(pv, f, default=to_json, encoding='utf-8', indent=2)
    finally:
        f.close()
            
    main(['--run', conffile])
        


