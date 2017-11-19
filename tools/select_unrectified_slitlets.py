from __future__ import division
from __future__ import print_function

import argparse
from astropy.io import fits
import json
import numpy as np
import os.path
import re
import sys

from numina.array.display.pause_debugplot import pause_debugplot
from numina.array.display.ximshow import ximshow
from emirdrp.instrument.csu_configuration import CsuConfiguration

from arg_file_is_new import arg_file_is_new
from fit_boundaries import bound_params_from_dict
from fit_boundaries import expected_distorted_frontiers
from fit_boundaries import overplot_boundaries_from_params
from fit_boundaries import overplot_frontiers_from_params
from nscan_minmax_frontiers import nscan_minmax_frontiers

from numina.array.display.pause_debugplot import DEBUGPLOT_CODES
from emirdrp.core import EMIR_NAXIS1
from emirdrp.core import EMIR_NAXIS2


def list_slitlets_from_string(s, islitlet_min, islitlet_max):
    """Return list of slitlets from string specification.

    Parameters
    ----------
    s : string
        String defining the slitlets. The slitlets must be specify
        as a set of n1[,n2[,step]] tuples. If only n1 is provided,
        the slitlet number n1 is considered. When n1 and n2 are given
        but step is missing, step=1 is assumed. Finally, when all
        n1, n2 and step are given, slitlets considered are those
        returned by range(n1, n2 + 1, step) function.
    islitlet_min : int
        Minimum slitlet number allowed.
    islitlet_max : int
        Maximum slitlet number allowed.

    Returns
    -------
    list_slitlets : Python list
        List of slitlets.

    """

    # protection
    if not isinstance(s, str):
        print('type(s): ', type(s))
        print('ERROR: function expected a string parameter')

    # initialize empty output
    set_slitlets = set()

    # remove leading blank spaces
    s = re.sub('^ *', '', s)
    # remove trailing blank spaces
    s = re.sub(' *$', '', s)
    # remove blank space before ','
    s = re.sub(' *,', ',', s)
    # remove blank spaces after  ','
    s = re.sub(', *', ',', s)
    # remove many blank spaces by a single blank space
    s = re.sub(' +', ' ', s)
    stuples = s.split()
    for item in stuples:
        subitems = item.split(',')
        nsubitems = len(subitems)
        if nsubitems == 1:
            n1 = int(subitems[0])
            n2 = n1
            step = 1
        elif nsubitems == 2:
            n1 = int(subitems[0])
            n2 = int(subitems[1])
            step = 1
        elif nsubitems == 3:
            n1 = int(subitems[0])
            n2 = int(subitems[1])
            step = int(subitems[2])
        else:
            raise ValueError('Unexpected slitlet range:', s)
        for i in range(n1, n2 + 1, step):
            if islitlet_min <= i <= islitlet_max:
                set_slitlets.add(i)
            else:
                print('islitlet_min: ', islitlet_min)
                print('islitlet_max: ', islitlet_max)
                print('i...........: ', i)
                raise ValueError("Slitlet number out of range!")

    list_slitlets = list(set_slitlets)
    list_slitlets.sort()

    # return result
    return list_slitlets


def main(args=None):

    # parse command-line options
    parser = argparse.ArgumentParser()

    # positional arguments
    parser.add_argument("fitsfile",
                        help="FITS file name to be displayed",
                        type=argparse.FileType('r'))
    parser.add_argument("--fitted_bound_param", required=True,
                        help="JSON file with fitted boundary coefficients "
                             "corresponding to the multislit model",
                        type=argparse.FileType('r'))
    parser.add_argument("--slitlets", required=True,
                        help="Slitlet selection: string between double "
                             "quotes providing tuples of the form "
                             "n1[,n2[,step]]",
                        type=str)

    # optional arguments
    parser.add_argument("--outfile",
                        help="Output FITS file name",
                        type=lambda x: arg_file_is_new(parser, x))
    parser.add_argument("--maskonly",
                        help="Generate mask for the indicated slitlets",
                        action="store_true")
    parser.add_argument("--debugplot",
                        help="Integer indicating plotting/debugging" +
                             " (default=0)",
                        type=int, default=0,
                        choices=DEBUGPLOT_CODES)
    parser.add_argument("--echo",
                        help="Display full command line",
                        action="store_true")

    args = parser.parse_args()

    if args.echo:
        print('\033[1m\033[31mExecuting: ' + ' '.join(sys.argv) + '\033[0m\n')

    # read input FITS file
    hdulist_image = fits.open(args.fitsfile.name)
    image_header = hdulist_image[0].header
    image2d = hdulist_image[0].data

    naxis1 = image_header['naxis1']
    naxis2 = image_header['naxis2']

    if image2d.shape != (naxis2, naxis1):
        raise ValueError("Unexpected error with NAXIS1, NAXIS2")

    if image2d.shape != (EMIR_NAXIS2, EMIR_NAXIS1):
        raise ValueError("NAXIS1, NAXIS2 unexpected for EMIR detector")

    # remove path from fitsfile
    if args.outfile is None:
        sfitsfile = os.path.basename(args.fitsfile.name)
    else:
        sfitsfile = os.path.basename(args.outfile.name)

    # check that the FITS file has been obtained with EMIR
    instrument = image_header['instrume']
    if instrument != 'EMIR':
        raise ValueError("INSTRUME keyword is not 'EMIR'!")

    # read GRISM, FILTER and ROTANG from FITS header
    grism = image_header['grism']
    spfilter = image_header['filter']
    rotang = image_header['rotang']

    # read fitted_bound_param JSON file
    fittedpar_dict = json.loads(open(args.fitted_bound_param.name).read())
    params = bound_params_from_dict(fittedpar_dict)
    if abs(args.debugplot) in [21, 22]:
        params.pretty_print()

    parmodel = fittedpar_dict['meta-info']['parmodel']
    if parmodel != 'multislit':
        raise ValueError("Unexpected parameter model: ", parmodel)

    # define slitlet range
    islitlet_min = fittedpar_dict['tags']['islitlet_min']
    islitlet_max = fittedpar_dict['tags']['islitlet_max']
    list_islitlet = list_slitlets_from_string(
        s=args.slitlets,
        islitlet_min=islitlet_min,
        islitlet_max=islitlet_max
    )

    # read CsuConfiguration object from FITS file
    csu_config = CsuConfiguration()
    csu_config.define_from_fits(args.fitsfile)

    # define csu_bar_slit_center associated to each slitlet
    list_csu_bar_slit_center = []
    for islitlet in list_islitlet:
        list_csu_bar_slit_center.append(
            csu_config.csu_bar_slit_center[islitlet - 1])

    # initialize output data array
    image2d_output = np.zeros((naxis2, naxis1))

    # main loop
    for islitlet, csu_bar_slit_center in \
            zip(list_islitlet, list_csu_bar_slit_center):
        list_expected_frontiers = expected_distorted_frontiers(
            islitlet, csu_bar_slit_center,
            params, parmodel, numpts=101, deg=5, debugplot=0
        )
        pol_lower_expected = list_expected_frontiers[0].poly_funct
        pol_upper_expected = list_expected_frontiers[1].poly_funct
        for j in range(EMIR_NAXIS1):
            xchannel = j + 1
            y0_lower = pol_lower_expected(xchannel)
            y0_upper = pol_upper_expected(xchannel)
            n1, n2 = nscan_minmax_frontiers(y0_frontier_lower=y0_lower,
                                            y0_frontier_upper=y0_upper,
                                            resize=True)
            # note that n1 and n2 are scans (ranging from 1 to NAXIS2)
            if args.maskonly:
                image2d_output[(n1 - 1):n2, j] = np.repeat(
                    [1.0], (n2 - n1 + 1)
                )
            else:
                image2d_output[(n1 - 1):n2, j] = image2d[(n1 - 1):n2, j]

    # update the array of the output file
    hdulist_image[0].data = image2d_output

    # save output FITS file
    hdulist_image.writeto(args.outfile)

    # close original image
    hdulist_image.close()

    # display full image
    if abs(args.debugplot) % 10 != 0:
        ax = ximshow(image2d=image2d_output,
                     title=sfitsfile + "\n" + args.slitlets,
                     image_bbox=(1, naxis1, 1, naxis2), show=False)

        # overplot boundaries
        overplot_boundaries_from_params(
            ax=ax,
            params=params,
            parmodel=parmodel,
            list_islitlet=list_islitlet,
            list_csu_bar_slit_center=list_csu_bar_slit_center
        )

        # overplot frontiers
        overplot_frontiers_from_params(
            ax=ax,
            params=params,
            parmodel=parmodel,
            list_islitlet=list_islitlet,
            list_csu_bar_slit_center=list_csu_bar_slit_center,
            micolors=('b', 'b'), linetype='-',
            labels=False    # already displayed with the boundaries
        )

        # show plot
        pause_debugplot(12, pltshow=True)


if __name__ == "__main__":

    main()
