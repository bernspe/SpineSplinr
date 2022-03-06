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
#torch.nn.Module.dump_patches = True

vertebrae=['T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12','L1','L2','L3','L4','L5']

# getting the angle of 3 points (corner = p1), points = [x,y]
def get_angle(p0, p1=np.array([0,0]), p2=None):
    if p2 is None:
        p2 = p1 + np.array([1, 0])
    v0 = np.array(p0) - np.array(p1)
    v1 = np.array(p2) - np.array(p1)
    angle = np.math.atan2(np.linalg.det([v0,v1]),np.dot(v0,v1))
    return np.degrees(angle)


# the following function takes predictions as an argument and translates this dict into COBB angles and additional parameters
# return data dict and a list with errors
def prediction2CobbData(prediction, diff_thresh = 70):
    # Werte aus dem prediction dict extrahieren und upper und lower vertebrae herausfinden
    errors = []
    try:
        nancount=Counter(prediction.values())[None]
        if nancount>5:
            errors.append('Too many NaNs in prediction')
            return None,errors
    except:
        pass

    df = pd.DataFrame(prediction).T.rename(columns={0: 'x', 1: 'y', 2: 'confidence'}).astype(float)

    df['VIdx'] = np.arange(0, len(vertebrae))

    n=df.y.isna().sum()
    #interpolate missing values if they are not too many
    if n>0:
        df=df.interpolate(limit=3).dropna()
        if n>3:
            errors.append('Missing values: %i' % n)
    df[['xdiff', 'ydiff', 'IdxDiff']] = df[['x', 'y', 'VIdx']].diff()

    # check if y's are in order or doubled (0)
    df = df.sort_values(by=['y']).drop_duplicates(subset='y')
    if (df['ydiff'] < 1).any():
        errors.append('y order of points error')

    if len(errors) > 0:
        return df, errors

    uvs = df.head(1).index.values[0]
    lvs = df.tail(1).index.values[0]
    uv = vertebrae.index(uvs)
    lv = vertebrae.index(lvs)
    c_arr = df[['x', 'y']].values.astype(int)

    # interpolate mid line
    f1 = ip.interp1d(c_arr[:, 1], c_arr[:, 0], kind='cubic')
    interp_line = [(int(f1(y)), y) for y in range(min(c_arr[:, 1]), max(c_arr[:, 1]))]

    # calculate angles of perpendicular lines
    a = np.zeros(len(c_arr))
    for i in range(1, len(c_arr) - 1):
        x1 = c_arr[i - 1, 0]
        x2 = c_arr[i + 1, 0]
        y1 = c_arr[i - 1, 1]
        y2 = c_arr[i + 1, 1]
        midX = (x1 + x2) // 2
        midY = (y1 + y2) // 2
        x3 = midX - y2 + y1  # perpendicular point
        y3 = midY + x2 - x1
        vangle = get_angle([midX, y3], [x3, y3], [midX, midY])
        a[i] = vangle

    # calculate COBB angle
    pa = argrelextrema(a, np.greater, order=2, mode='wrap')[0]
    na = argrelextrema(a, np.less, order=2, mode='wrap')[0]
    ai = np.sort(np.hstack([pa, na]))
    ai = np.delete(ai, np.where(np.diff(ai) == 1)[0])
    cobbs = []
    del_i = []
    for i in range(ai.shape[0] - 1):
        a_sum = abs(a[ai[i]]) + abs(a[ai[i + 1]])
        if a_sum > 10:
            cobbs.append(int(a_sum))
        else:
            del_i.append(i)
    if len(del_i) > 0:
        ai = np.delete(ai, del_i)

    # label Neutral-Vertebrae and COBB angle
    cvlist = []  # COBB vertebrae list = Name of end vertebrae
    cilist = []  # End vertebrae indices in CentroidList c_arr
    calist = []  # COBB angle list

    for i in range(len(ai) - 1):
        a1 = ai[i]
        a2 = ai[i + 1]
        cobb = cobbs[i]
        cilist.append((a1, a2))
        cvlist.append((vertebrae[uv + a1], vertebrae[uv + a2]))
        calist.append(cobb)

    data = {'UpperVertebra': uvs, 'LowerVertebra': lvs,
            'EndVertebrae': cvlist, 'EndVertebraeIndices': cilist, 'COBBAngles': calist,
            'VertebraeCentroids': c_arr, 'Spline': interp_line,
            'MeanConfidence': df['confidence'].mean(), 'MinConfidence': df['confidence'].min(), 'MaxConfidence': df['confidence'].max()}
    return data, errors

def beautifulSpline(d, cobbdata, features='', fontfile=FONT_FILE_SPLINE):
    """
    creates an annotated image which is saved in a given ImageDraw instance (d)
    takes features argument to include angles, upper and lower ends
    """
    try:
        font = ImageFont.truetype(fontfile, 15)
    except:
        return "Beautiful Spline Font loading error"
    try:
        points = np.array(cobbdata['Spline'])
        centroids = np.array(cobbdata['VertebraeCentroids'])
        ev = cobbdata['EndVertebrae']

        for i in range(-4, 5, 1):
            p = points + [i, 0]
            c = ImageColor.getrgb('hsl(45,50%,{}%)'.format(100 - (abs(i) * 18)))
            d.point(p.flatten().tolist(), fill=c)
    except:
        return "Beautiful Spline Construction error"
    try:
        for c in centroids:
            d.ellipse((c[0] - 5, c[1] - 5, c[0] + 5, c[1] + 5), outline='blue')
    except:
        return "Beautiful Spline Centroid error"
    try:
        if 'angles' in features:
            meanpositions = [int((vi[0] + vi[1]) / 2) for vi in cobbdata['EndVertebraeIndices']]
            i = 0
            for m in meanpositions:
                mpos = tuple([centroids[m][0] + 20, centroids[m][1] - 5])
                mtext = ev[i][0] + ' - ' + ev[i][1]
                mangle = cobbdata['COBBAngles'][i]
                d.multiline_text(mpos, mtext + '\n' + str(mangle) + '°', fill='yellow', font=font, anchor=None)
                i += 1
    except:
        return "Beautiful Spline Angle Annotation error"
    try:
        if 'ends' in features:
            mpos1 = tuple([centroids[0][0] - 20, centroids[0][1] - 5])
            mpos2 = tuple([centroids[-1][0] - 20, centroids[-1][1] - 5])
            mtext1 = cobbdata['UpperVertebra']
            mtext2 = cobbdata['LowerVertebra']
            d.text(mpos1, mtext1, fill='white', font=font, anchor=None)
            d.text(mpos2, mtext2, fill='white', font=font, anchor=None)
    except:
        return "Beautiful Spline EndVertebrae annotation error"


def getImgResized(pil_image, modelsize):
    imgsize = pil_image.size
    w = imgsize[0]
    h = imgsize[1]
    if (w != modelsize[0]) | (h != modelsize[1]):
        ratio = modelsize[1] / h
        resize_img = pil_image.resize((round(ratio * w), modelsize[1]))
        w = resize_img.size[0]
        if w > modelsize[0]:
            # if image is broader crop it to left,top =0, right, bottom = modelsize_height
            rpil_image = resize_img.crop(((w - modelsize[0]) // 2, 0, (w + modelsize[0]) // 2,
                                             modelsize[1]))
        else:
            # if image is thinner, paste it
            background = PIL.Image.new('RGB', modelsize)
            offset = (round(modelsize[0] - w) // 2, 0)
            background.paste(resize_img, offset)
            rpil_image = background
    else:
        rpil_image = pil_image
    return rpil_image

class CobbAngleDetector:
    def __init__(self, learn_model,modelsize=(500,500)):
        # hier den Pfad zum DL Model anpassen
        #net_folder = Path(modelpath)
        # das DL Model laden
        # hier die eventuell auftretenden Warnungen ignorieren
        #self.learn = load_learner(net_folder.parent, net_folder.name)
        self.learn=learn_model
        self.modelsize=modelsize
        self.errors=[]

    def fit(self, pil_image):
        #pil_image = opened Image via Pillow
        self.pil_image=getImgResized(pil_image, self.modelsize)
        self.annotated_image=self.pil_image
        img_tensor = T.ToTensor()(self.pil_image)
        self.fastai_image = Image(img_tensor)
        # predict vertebrae positions
        self.prediction = predict_vertebrae_position(self.fastai_image, self.learn)

    def generateCOBB(self):
        self.cobbdata, self.errors = prediction2CobbData(self.prediction)

    def generateAnnotatedImage(self, features='angles.ends'):
        w=self.pil_image.size[0]
        h=self.pil_image.size[1]
        if (w>0)&(h>0) & (len(self.errors)==0):
            COBBImg = PIL.Image.new('RGB', (w, h))
            d = ImageDraw.Draw(COBBImg)
            err = beautifulSpline(d, self.cobbdata, features=features)
            if err:
                self.errors.append(err)
            else:
                self.annotated_image=PIL.Image.blend(self.pil_image, COBBImg, 0.5)
                # add in for target size 500x500
                self.annotated_image=getImgResized(self.annotated_image,(500,500))