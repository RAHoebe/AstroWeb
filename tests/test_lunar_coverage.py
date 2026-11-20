import numpy as np
from astroweb.lunar_detail import coverage


def test_empty_white_or_black_map_margins_do_not_cover_underlying_imagery():
    image=np.full((100,100,3),80,np.uint8)
    image[:,:10]=255
    image[:,-10:]=0
    image[45:55,45:55]=0  # A real interior crater shadow remains part of the layer.
    mask=coverage(image)
    assert mask[:,0].max()==0 and mask[:,-1].max()==0
    assert mask[50,50]>.9
