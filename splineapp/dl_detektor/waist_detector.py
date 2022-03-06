import torchvision.transforms as T
import numpy as np
import pandas as pd
import scipy.interpolate as ip
from scipy.signal import argrelextrema
from PIL import ImageFont,ImageDraw,ImageColor
try:
    from SpineSplinr.settings import FONT_ROOT, FONT_FILE_SPLINE
except:
    FONT_FILE_SPLINE='./fonts/acmesa.ttf'
try:
    from .nb_heatmap import *
except:
    from nb_heatmap import *

defaults.device = torch.device('cpu')
