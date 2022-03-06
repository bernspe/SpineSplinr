
import shutil
import time



class MLProcessModel:
    type=''
    resultdir=''

    def __init__(self, type='dummy', mlmodeldir='.', ssm=None):
        self.type=type
        ### Hier müßte dann das Model geladen werden
        #import cv2
        import PIL
        import numpy
        import torch
        import torchvision
        import os
        print('Numpy version: %s'%str(numpy.__version__))
        #print('Open-CV Version: %s'%str(cv2.__version__))
        print('PIL version: %s'%str(PIL.__version__))
        print('Torch version: %s, Torchvision version: %s'%(str(torch.__version__),str(torchvision.__version__)))
        print('Changing current working dir to: ',mlmodeldir)
        self.resultdir=mlmodeldir+'results/'
        self.ssm=ssm
        print('Current working Directory: ',os.getcwd())

    def inference(self, img=None):
        if img:
            print('Open File %s'%str(img))
            #image=cv2.imread(img)
            #image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            # assign a new name identifier to the modified image - so that it does not interfere with other images
            if self.ssm:
                imgname = 'modified_' + str(self.ssm) + '.jpg'
            else:
                imgname = img.rsplit('/')[-1]

            # Das wird in der Test-Console ausgegeben
            print(' Hier läuft dann die inference')

            ## Dummy Timeconsuming procedure
            time.sleep(5)
            print('Image %s was processed'%str(img))

            # Die Daten werden dann zurückgegeben
            mock_prediction=[(33,44),(22,11)]
            mock_performance=[0.7,0.9]

            #Schreiben des Images
            #for p, conf in zip(mock_prediction,mock_performance):
            #    cv2.circle(image, (p[0], p[1]), 2, (int(mock_performance*100), 255, 255), 2) ## Color gradient in HSV values
            #cv2.imwrite(image, self.resultdir+imgname)
            shutil.copyfile(img,self.resultdir+imgname)

            return mock_prediction,mock_performance, imgname
        else:
            print('No image.')
