from vertebra_detector import CobbAngleDetector

import PIL
import numpy as np
import os
import random
from fastai.vision import *
import fastai
#from .nb_heatmap import *
import torchvision.transforms as T

if (fastai.__version__ != "1.0.61"):
    print('Wrong fastai version: ', fastai.__version__)
else:
    defaults.device = torch.device('cpu')
    modelpath = '/Volumes/1TB/Users/peterbernstein/Django/SpineSplinr/DL_MODELS/vertebrae_detection_model.pkl'
    net_folder = Path(modelpath)
    xray_learn_model = load_learner(net_folder.parent, net_folder.name)

    imgdir = 'tests/data2'
    fNames = list(filter(lambda x: x.lower().endswith(('.png', '.jpg', '.jpeg')), os.listdir(imgdir)))
    n = 10

    rlist = random.sample(list(fNames), n)
    for r in rlist:
        path2img = imgdir + '/' + r
        img_pil = PIL.Image.open(path2img)
        cad = CobbAngleDetector(xray_learn_model)
        cad.fit(img_pil)
        cad.generateCOBB()
        print('Errors: ',cad.errors)
