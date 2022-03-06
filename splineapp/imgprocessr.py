import warnings
from io import BytesIO
from PIL import Image as pimg
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile

from SpineSplinr import settings
#from .dl_detektor.vertebra_detector import *
import requests

import logging
# Get an instance of a logger
from splineapp.dl_detektor.vertebra_detector import CobbAngleDetector

logger = logging.getLogger(__name__)


def flip_horizontal(im): return im.transpose(pimg.FLIP_LEFT_RIGHT)
def flip_vertical(im): return im.transpose(pimg.FLIP_TOP_BOTTOM)
def rotate_180(im): return im.transpose(pimg.ROTATE_180)
def rotate_90(im): return im.transpose(pimg.ROTATE_90)
def rotate_270(im): return im.transpose(pimg.ROTATE_270)
def transpose(im): return rotate_90(flip_horizontal(im))
def transverse(im): return rotate_90(flip_vertical(im))
orientation_funcs = [None,
                 lambda x: x,
                 flip_horizontal,
                 rotate_180,
                 flip_vertical,
                 transpose,
                 rotate_270,
                 transverse,
                 rotate_90
                ]
def apply_orientation(im):
    """
    Extract the oritentation EXIF tag from the image, which should be a PIL Image instance,
    and if there is an orientation tag that would rotate the image, apply that rotation to
    the Image instance given to do an in-place rotation.

    :param Image im: Image instance to inspect
    :return: A possibly transposed image instance
    """

    try:
        kOrientationEXIFTag = 0x0112
        if hasattr(im, '_getexif'): # only present in JPEGs
            e = im._getexif()       # returns None if no EXIF data
            if e is not None:
                #log.info('EXIF data found: %r', e)
                orientation = e[kOrientationEXIFTag]
                f = orientation_funcs[orientation]
                return f(im)
    except:
        # We'd be here with an invalid orientation value or some random error?
        pass # log.exception("Error applying EXIF Orientation tag")
    return im


class ImgModifier:
    def __init__(self, learn_model, original_img, destination_img, method='resize_img'):
        self.learn_model=learn_model
        self.method=method
        self.image_field = original_img
        self.mod_img_field = destination_img
        self.img_name = method+'.jpg'
        self.buffer = BytesIO()
        self.data={} # storage for pkl file
        self.formatted_data={} # storage for formatted
        self.errors={}
        self.imgready=False
        warnings.simplefilter('error', pimg.DecompressionBombWarning)

    def open_img(self):
        try:
            img = pimg.open(self.image_field)
        except Exception as e:
            logger.error('Could not open img due to: %s'%str(e))
            return
        logger.info("Size of Image: %s"%str(img.size))
        return img


    def modify(self):
        if self.method=='resize_img':
            self.resize_img()
        if self.method=='xray_cobb':
            self.xray_cobb()
            return self.buffer
        if self.method=='upright':
            self.upright()
            return self.buffer

    def resize_img(self,width=100,height=100):
        #img = pimg.open(requests.get(self.image_field,stream=True).raw)
        img=pimg.open(self.image_field)
        if img.size[0] > width or img.size[1] > height:
            new_img = img.resize((width, height))
        else:
            new_img=img
        new_img=apply_orientation(new_img)
        #new_img.save(fp=self.buffer, format='JPEG')
        new_img.save(self.mod_img_field)
        self.imgready=True
### XRAY MODEL ##
    def xray_cobb(self):
        img=self.open_img()
        if (img.size[0]>100) & (img.size[1]>100): #check if the img has a meaningful size
            cad=CobbAngleDetector(self.learn_model)
            cad.fit(img)
            cad.generateCOBB()
            cad.generateAnnotatedImage()
            logger.info("Errors by CobbAngleDetector: %s"%str(cad.errors))
            if len(cad.errors)>0:
                logger.debug('Entering return path because of errors in CobbAngleDetector')
                self.errors[self.method]=cad.errors
                return
            else:
                logger.debug('Entering save path, Image Field: %s'%str(self.image_field))
                #self.data[self.method]=str(cad.cobbdata['COBBAngles'])
                included_keys = ['UpperVertebra', 'LowerVertebra', 'EndVertebrae', 'COBBAngles','MinConfidence','MaxConfidence','MeanConfidence']
                d2 = {k: v for k, v in cad.cobbdata.items() if k in included_keys}
                d2['EndVertebrae'] = [v[0] + '-' + v[1] for v in d2['EndVertebrae']]
                self.formatted_data=d2
                self.data=cad.cobbdata
                new_img=cad.annotated_image
                try:
                    #new_img.save(self.mod_img_field)
                    new_img.save(fp=self.buffer, format='JPEG')
                    return new_img
                except Exception as e:
                    logger.error('ImgProcessor Exception: %s'%str(e))
                self.imgready=True
        else:
            self.errors[self.method]=['XRAY: Image too small']
            logger.error(self.errors)

    ####UPRIGHT
    def upright(self):
        img=self.open_img()
        #if (img.size[0]>100) & (img.size[1]>100): #check if the img has a meaningful size
        # to be continued as WaistLine Detector Class instantiation