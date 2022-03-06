import unittest
from splineapp.dl_detektor.vertebra_detector import getImgResized
from PIL import Image
import numpy as np

testfile='/Volumes/1TB/Users/peterbernstein/Downloads/herbrig_annika.jpg'

class MyTestCase(unittest.TestCase):
    def test_diffSizeImage(self):
        modelsize=(500,500)
        pimg=Image.open(testfile,'r')
        origsize=pimg.size
        rpimg=getImgResized(pimg,modelsize)
        if rpimg==None:
            success=False
        elif ((rpimg.size==modelsize) & (origsize!=modelsize)):
            s1=np.sum(pimg)
            s2=np.sum(rpimg)
            if (s1!=s2):
                success=True
            else:
                success=False
        elif ((rpimg.size==modelsize) & (origsize==modelsize)):
            success=True
        else:
            success=False
        self.assertEqual(success, True)



if __name__ == '__main__':
    unittest.main()
