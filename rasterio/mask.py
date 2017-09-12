"""Mask the area outside of the input shapes with no data."""

import logging
import warnings

import numpy as np

from rasterio.features import geometry_mask, geometry_window


logger = logging.getLogger(__name__)


def raster_geom_mask(raster, shapes, all_touched=False, invert=False,
                    crop=False, pad=False):
    """Create a mask from shapes, transform, and optional window within original 
    raster.

    By default, mask is intended for use as a numpy mask, where pixels that 
    overlap shapes are False.
    
    If shapes do not overlap the raster and crop=True, an exception is 
    raised.  Otherwise, a warning is raised, and a completely True mask
    is returned (if invert is False).

    Parameters
    ----------
    raster: rasterio RasterReader object
        Raster for which the mask will be created.
    shapes: list of polygons
        GeoJSON-like dict representation of polygons that will be used to 
        create the mask.
    all_touched: bool (opt)
        Use all pixels touched by features. If False (default), use only
        pixels whose center is within the polygon or that are selected by
        Bresenham's line algorithm.
    invert: bool (opt)
        If True, mask will be `True` for pixels inside shapes and `False`
        outside shapes.
        False by default.
    crop: bool (opt)
        Whether to crop the raster to the extent of the shapes. Defaults to
        False.
    pad: bool (opt)
        If True, the features will be padded in each direction by
        one half of a pixel prior to cropping raster. Defaults to False.

    Returns
    -------
    tuple

        Three elements:

            mask : numpy ndarray of type 'bool'
                Mask that is `True` outside shapes, and `False` within shapes.

            out_transform : affine.Affine()
                Information for mapping pixel coordinates in `masked` to another
                coordinate system.
            
            window: rasterio.windows.Window instance
                Window within original raster covered by shapes.  None if crop
                is False.
    """
    if crop and invert:
        raise ValueError("crop and invert cannot both be True.")
    
    if crop and pad:
        pad_x = 0.5  # pad by 1/2 of pixel size
        pad_y = 0.5
    else:
        pad_x = 0
        pad_y = 0

    north_up = raster.transform.e <= 0

    window = geometry_window(raster, shapes, north_up=north_up, pad_x=pad_x, 
                             pad_y=pad_y)

    # If shapes do not overlap raster, raise Exception or UserWarning
    # depending on value of crop
    if window.flatten() == (0, 0, 0, 0):
        if crop:
            raise ValueError('Input shapes do not overlap raster.')
        else:
            warnings.warn('shapes are outside bounds of raster. '
                          'Are they in different coordinate reference systems?')

        # Return an entirely True mask (if invert is False)
        mask = np.ones(shape=raster.shape[-2:], dtype='bool') * (not invert)
        return mask, raster.transform, None

    if crop:
        transform = raster.window_transform(window)
        out_shape = (window.height, window.width)

    else:
        window = None
        transform = raster.transform
        out_shape = (raster.height, raster.width)

    mask = geometry_mask(shapes, transform=transform, invert=invert,
                         out_shape=out_shape, all_touched=all_touched)

    return mask, transform, window


def mask(raster, shapes, all_touched=False, invert=False, nodata=None,
         filled=True, crop=False, pad=False):
    """Creates a masked or filled array using input shapes.  
    Pixels are masked or set to nodata outside the input shapes, unless 
    `invert` is `True`.
    
    If shapes do not overlap the raster and crop=True, an exception is 
    raised.  Otherwise, a warning is raised.

    Parameters
    ----------
    raster: rasterio RasterReader object
        Raster to which the mask will be applied.
    shapes: list of polygons
        GeoJSON-like dict representation of polygons that will be used to 
        create the mask.
    all_touched: bool (opt)
        Use all pixels touched by features. If False (default), use only
        pixels whose center is within the polygon or that are selected by
        Bresenham's line algorithm.
    invert: bool (opt)
        If True, mask will be `True` for pixels inside shapes and `False`
        outside shapes.
        False by default.
    nodata: int or float (opt)
        Value representing nodata within each raster band. If not set,
        defaults to the nodata value for the input raster. If there is no
        set nodata value for the raster, it defaults to 0.
    filled: bool (opt)
        If True, the pixels outside the features will be set to nodata.  
        If False, the output array will contain the original pixel data, 
        and only the mask will be based on shapes.  Defaults to True.
    crop: bool (opt)
        Whether to crop the raster to the extent of the shapes. Defaults to
        False.
    pad: bool (opt)
        If True, the features will be padded in each direction by
        one half of a pixel prior to cropping raster. Defaults to False.

    Returns
    -------
    tuple

        Two elements:

            masked : numpy ndarray or numpy.ma.MaskedArray
                Data contained in raster after applying the mask (`filled` is 
                `True`) and mask where all pixels are `True` outside shapes 
                (`invert` is `False`).

            out_transform : affine.Affine()
                Information for mapping pixel coordinates in `masked` to another
                coordinate system.
    """

    if nodata is None:
        if raster.nodata is not None:
            nodata = raster.nodata
        else:
            nodata = 0

    shape_mask, transform, window = raster_geom_mask(
        raster, shapes, all_touched=all_touched, invert=invert, crop=crop,
        pad=pad)

    height, width = shape_mask.shape
    out_shape = (raster.count, height, width)

    out_image = raster.read(window=window, out_shape=out_shape, masked=True)
    out_image.mask = out_image.mask | shape_mask

    if filled:
        out_image = out_image.filled(nodata)

    return out_image, transform


