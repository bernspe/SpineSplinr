import unittest
from splineapp.dl_detektor.vertebra_detector import CobbAngleDetector

from PIL import Image
import numpy as np
import os
import random
from fastai.vision import *
import fastai
from splineapp.dl_detektor.nb_heatmap import *
import torchvision.transforms as T

class vert_det_v3_test1(unittest.TestCase):

    def test_XrayImage(self):

        if (fastai.__version__ != "1.0.61"):
            print('Wrong fastai version: %s', fastai.__version__)
            return False

        modelpath = '/Volumes/1TB/Users/peterbernstein/Django/SpineSplinr/DL_MODELS/vertebrae_detection_model.pkl'
        net_folder = Path(modelpath)
        self.learn_model = load_learner(net_folder.parent, net_folder.name)

        imgdir = 'data2'
        fNames = list(filter(lambda x: x.lower().endswith(('.png', '.jpg', '.jpeg')), os.listdir(imgdir)))
        n = 1

        defaults.device = torch.device('cpu')

        rlist = random.sample(list(self.fNames), self.n)
        path2img = self.imgdir + '/' + rlist[0]
        img_pil = Image.open(path2img)
        cad = CobbAngleDetector(self.learn_model)
        cad.fit(img_pil)
        cad.generateCOBB()
        l= len(cad.errors)
        if l==0:
            success=True
        else:
            success=False
        self.assertEqual(success, True)



if __name__ == '__main__':
    unittest.main()