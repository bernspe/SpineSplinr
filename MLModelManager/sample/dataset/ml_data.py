import os
import random


class MLDataset:
    name=''
    fNames=[]

    def __init__(self, name='upright', mlmodeldir='.'):
        self.name=name
        self.fNames = list(filter(lambda x: x.lower().endswith(('.png', '.jpg', '.jpeg')), os.listdir(mlmodeldir)))
        self.fNames = [mlmodeldir+f for f in self.fNames]

    def img_generator(self, n):
        if len(self.fNames)>0:
            i=0
            while i<n:
                i+=1
                yield random.choice(self.fNames)

