
import argparse
from astropy.io import fits
import numina.array.nirproc as N
import numpy as np


def process_images(images, nreject=3):

    tread = 1.055289     # lectura productiva [s]
    tread_nd = 1.048046 # lectura no productiva [s]

    nimages_t = len(images)
    nimages = nimages_t - nreject

    # nimages must be >= 2

    arrs = []
    arr, ref_hdr = fits.getdata(images[nreject], header=True)
    arrs.append(arr)

    toper = ref_hdr['toper']
    nrdil = ref_hdr['nrdil']
    nrdil_nd = ref_hdr['nrdil_nd']
    nfrsec = ref_hdr['nfrsec']
    gain = ref_hdr['gain']
    ron = ref_hdr['ron']

    gain = max(0.1, gain)

    exptime = ref_hdr['exptime']
    print(toper, nrdil, nrdil_nd, nfrsec, exptime)

    dt = (toper / 1000.0 + nrdil_nd * tread_nd + nrdil * tread) / exptime
    print('dt=', dt)
    cube = np.empty((nimages, 2048,2048))
    cube[0] = arr

    for idx, img in enumerate(images[nreject + 1:], 1):
        arr, hdr = fits.getdata(img, header=True)
        cube[idx] = arr

    # WORKAROUND
    # FIXME: we are passing Integration time
    # we should pass DT instead
    print(len(cube))
    m0, m1, m2, m3 = N.ramp_array(cube, ti=dt * (len(cube)-1), gain=gain, ron=ron)
    # print(m0.dtype)
    # print(m1.dtype)
    # print(m2.dtype)
    # print(m3.dtype)
    hm1 = fits.PrimaryHDU(m0, header=ref_hdr)
    hm2 = fits.ImageHDU(m1)
    hm3 = fits.ImageHDU(m2)
    hm4 = fits.ImageHDU(m3)
    hf = fits.HDUList([hm1, hm2, hm3, hm4])
    return hf


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('images', nargs='+')
    parser.add_argument('--output', default='ramp.fits')
    parser.add_argument('--reject', type=int, default=0)
    cli = parser.parse_args(args)

    hf = process_images(cli.images, nreject=cli.reject)
    print('reject', cli.reject)

    hf.writeto(cli.output, overwrite=True)


if __name__ == '__main__':

    main()