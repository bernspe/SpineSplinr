
import time

import cv2
import PIL
import numpy as np

import torch
import torchvision


class MLProcessModel:
    type=''
    resultdir=''

    def __init__(self, type='dummy', mlmodeldir='.', ssm=None):
        self.type=type
        ### Hier müßte dann das Model geladen werden

        print('Numpy version: %s'%str(np.__version__))
        print('Open-CV Version: %s'%str(cv2.__version__))
        print('PIL version: %s'%str(PIL.__version__))
        print('Torch version: %s, Torchvision version: %s'%(str(torch.__version__),str(torchvision.__version__)))
        self.resultdir=mlmodeldir+'results/'
        self.ssm=ssm

    def inference(self, img=None):
        if img:
            ## Dummy Timeconsuming procedure
            time.sleep(5)
            print('Image %s was processed'%str(img))

            # Die Daten werden dann zurückgegeben
            mock_prediction=[(100,40),(140,40), (180,40)]
            mock_performance=[0.4,0.7,0.9]

            #Labeln des Images, der Name des gespeicherten Bildes zurückgegeben
            imgname = self.label_img(img,mock_prediction,mock_performance)
            return mock_prediction,mock_performance, imgname
        else:
            print('No image.')

    def label_img(self, img, prediction, performance):
        image = cv2.imread(img)
        # assign a new name identifier to the modified image - so that it does not interfere with other images
        if self.ssm:
            imgname = 'modified_' + str(self.ssm) + '.jpg'
        else:
            imgname = img.rsplit('/')[-1]

        # Schreiben des Images
        w = image.shape[0]
        h = image.shape[1]
        heatmap = np.zeros((w, h), dtype=np.uint8)
        for p, conf in zip(prediction, performance):
            cv2.circle(image,p,10,(0,0,0),-1) # delete circle spots in original image
            cv2.circle(heatmap, p, 10, int(conf * 255), -1)
        # Scale
        image[h-10:h,:,:]=np.zeros((10,w,3), dtype=np.uint8)
        for i in range(w):
            c = int(i / w * 255)
            cv2.line(heatmap, (i, h - 10), (i, h), c)
        im3 = cv2.applyColorMap(heatmap, cv2.COLORMAP_RAINBOW)
        target_img = image + im3
        cv2.imwrite(self.resultdir + imgname, target_img)
        print('Write image to %s' % (self.resultdir + imgname))
        return imgname

