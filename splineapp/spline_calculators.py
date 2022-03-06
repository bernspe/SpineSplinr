from PIL import Image, ImageDraw, ImageFont
import numpy as np
import scipy.interpolate as ip
import math
import os
from SpineSplinr.settings import BASE_DIR

# Euclidean distance.
def euc_dist(pt1,pt2):
    return math.sqrt((pt2[0]-pt1[0])*(pt2[0]-pt1[0])+(pt2[1]-pt1[1])*(pt2[1]-pt1[1]))

def _c(ca,i,j,P,Q):
    if ca[i,j] > -1:
        return ca[i,j]
    elif i == 0 and j == 0:
        ca[i,j] = euc_dist(P[0],Q[0])
    elif i > 0 and j == 0:
        ca[i,j] = max(_c(ca,i-1,0,P,Q),euc_dist(P[i],Q[0]))
    elif i == 0 and j > 0:
        ca[i,j] = max(_c(ca,0,j-1,P,Q),euc_dist(P[0],Q[j]))
    elif i > 0 and j > 0:
        ca[i,j] = max(min(_c(ca,i-1,j,P,Q),_c(ca,i-1,j-1,P,Q),_c(ca,i,j-1,P,Q)),euc_dist(P[i],Q[j]))
    else:
        ca[i,j] = float("inf")
    return ca[i,j]

""" Computes the discrete frechet distance between two polygonal lines
Algorithm: http://www.kr.tuwien.ac.at/staff/eiter/et-archive/cdtr9464.pdf
P and Q are arrays of 2-element arrays (points)
"""
def frechetDist(P,Q):
    ca = np.ones((len(P),len(Q)))
    ca = np.multiply(ca,-1)
    return _c(ca,len(P)-1,len(Q)-1,P,Q)





# getting the angle of 3 points (corner = p1), points = [x,y]
def get_angle(p0, p1=np.array([0, 0]), p2=None):
    if p2 is None:
        p2 = p1 + np.array([1, 0])
    v0 = np.array(p0) - np.array(p1)
    v1 = np.array(p2) - np.array(p1)
    angle = np.math.atan2(np.linalg.det([v0, v1]), np.dot(v0, v1))
    return np.degrees(angle)


# returns the mean curvature of a line in 2D
def getCurvature(l):
    dx_dt = np.gradient(l[:, 0])
    dy_dt = np.gradient(l[:, 1])
    d2x_dt2 = np.gradient(dx_dt)
    d2y_dt2 = np.gradient(dy_dt)
    curvature = np.abs(d2x_dt2 * dy_dt - dx_dt * d2y_dt2) / (dx_dt * dx_dt + dy_dt * dy_dt) ** 1.5
    return np.mean(curvature), np.amax(curvature), curvature


# flip the y part of a line downside up and reduce start to 0
def flipline(pl):
    start = pl[0, 1]
    for i in range(pl.shape[0]):
        pl[i, 1] = (start - pl[i, 1])
    return pl

def getMinLineLength(waistlines):
    wl = waistlines['left']
    wr = waistlines['right']
    ll = wl[-1][1]-wl[0][1]
    rl = wr[-1][1]-wr[0][1]
    return min(ll,rl)

# Waistlines auf ein Koordinatensystem übertragen 90° gedreht und übereinandergeflippt
# die Linien werden auf linelength trunkiert
def getTransformedWaistLines(waistlines,linelength):
    lines=[]
    for (linetype,waistline) in zip(['left','right'],[waistlines['left'],waistlines['right']]):
        pl = np.array(waistline)
        ptsl = np.rot90(pl).T
        if linetype == 'left':
            start = ptsl[0, 1]
            ptsl[:, 1] -= start
        if linetype == 'right':
            ptsl = flipline(ptsl)
        #truncate the lines
        ptsl=ptsl[0:int(linelength)]
        lines.append(ptsl)
    return lines

# Frechet Distanz zwischen zwei Linien berechnen
def getfrechetDistanceBetweenLines(transformedwaistlines):
    return frechetDist(transformedwaistlines[0],transformedwaistlines[1])

# Die Linien auf der y-Achse hin und herschieben, bis die Frechet-Distanz minimiert ist
def getFrechetOptimizedTransformedWaistLines(transformedwaistlines, window=20):
    frechets=[]
    for y in range(0-window//2,window//2):
        twl=np.copy(transformedwaistlines[1])
        twl[:,1]+=y
        frechets.append(getfrechetDistanceBetweenLines([transformedwaistlines[0],twl]))
    min_frechet = min(frechets)
    idx=frechets.index(min_frechet)
    y_transformer = 0-window//2+idx
    transformedwaistlines[1][:,1]+=y_transformer
    return transformedwaistlines,min_frechet

# der Abstand zwischen den Linien wird quadriert und aufsummiert
def getSumOfSquaresBetweenOptimizedTransformedLines(transformedwaistlines):
    return np.sum((transformedwaistlines[0][:,1]-transformedwaistlines[1][:,1])**2)
# returns the area under the rotated waistline, partitionned into n chunks, limited to the shoulderdistance

def getAreasUnderLine(waistline, shoulderdistance, linetype='left', n=4):
    areas = []
    pl = np.array(waistline)
    ptsl = np.rot90(pl).T
    if linetype == 'left':
        start = ptsl[0, 1]
        ptsl[:, 1] -= start
    if linetype == 'right':
        ptsl = flipline(ptsl)
    f1 = ip.interp1d(ptsl[:, 0], ptsl[:, 1], kind='cubic')  # einfache cubic Interpolation
    # interpolierte Linie
    iline = [(y, int(f1(y))) for y in range(ptsl[0, 0], ptsl[-1, 0])]
    a = np.array(iline)[:shoulderdistance, :]
    teiler = shoulderdistance / n
    for i in range(n):
        areas.append(np.trapz(a[int(i * teiler):int((i + 1) * teiler), 1]))
    return np.array(areas)



class WaistCalculator():
    result={}

    def __init__(self, waistlines=None, targetImg=None, annotate=True):
        self.prediction=waistlines # enthält left and right points
        self.img=targetImg
        self.annotate=annotate

    def do_waistline_manipulation(self,factor=0.8):
        self.transformedWaistLines = getTransformedWaistLines(self.prediction,self.shoulderdistance*factor)
        self.transformedWaistLines,self.frechetDistance = getFrechetOptimizedTransformedWaistLines(self.transformedWaistLines)
        self.squaredDiffs = getSumOfSquaresBetweenOptimizedTransformedLines(self.transformedWaistLines)
        self.transformedWaistLinesArray.append(self.transformedWaistLines)
        fd=self.frechetDistance/self.shoulderdistance*100
        sd=self.squaredDiffs/(self.shoulderdistance**2)
        self.frechetDistanceArray.append(fd)
        self.squaredDiffsArray.append(sd)
        return fd,sd

    # liefert Images mit den eingezeichneten Waistlines zurück, optional mit Beschriftung der Curvature und eingezeichneten Angle-Linien
    # im anglecontainer werden die nach rechts offenen Winkel zurückgegeben
    # im curvaturecontainer die Krümmungen der Linien als List of Dict(left,right)
    def getLabeledImage(self, zoomfactor=1):
        annotate = self.annotate
        draw = ImageDraw.Draw(self.img)
        fnt = ImageFont.truetype(os.path.join(BASE_DIR, "splineapp/acmesa.ttf"), 12)

        self.shoulderdistance = self.prediction['right'][0][0] - self.prediction['left'][0][0]
        self.shoulderheightdifference = (self.prediction['right'][0][1] - self.prediction['left'][0][1]) / self.shoulderdistance

        wply = np.array(self.prediction['left'])[np.argmax(np.array(self.prediction['left']), axis=0)[0]][1]
        wpry = np.array(self.prediction['right'])[np.argmin(np.array(self.prediction['right']), axis=0)[0]][1]
        self.waistpointheightdifference = (wpry - wply) / self.shoulderdistance

        shoulder_y = max(self.prediction['right'][0][1],self.prediction['left'][0][1])
        mid_x = self.prediction['left'][0][0] + (self.shoulderdistance//2)
        if (annotate):
            draw.line([(self.prediction['left'][0][0],shoulder_y), (self.prediction['right'][0][0],shoulder_y)], fill='blue', width=1)
            draw.line([(mid_x,shoulder_y), (mid_x,shoulder_y+self.shoulderdistance)], fill='blue',width=1)
            draw.text((mid_x-70,shoulder_y+int(0.3*self.shoulderdistance)),'Fr-Dist', font=fnt, fill='blue')
            draw.text((mid_x +10, shoulder_y + int(0.3 * self.shoulderdistance)), 'Sq-Dist', font=fnt, fill='blue')
        minDistance=getMinLineLength(self.prediction)/ self.shoulderdistance
        self.transformedWaistLinesArray=[]
        self.frechetDistanceArray=[]
        self.squaredDiffsArray=[]
        # die Länge der Waistlines muss minimal 50% der Schulterdistanz betragen, ansonsten bleibt die ergebnisliste leer
        for m in [0.5,0.6,0.7,0.8,0.9,1.0]:
            if minDistance>m:
                fd,sqd=self.do_waistline_manipulation(factor=m)
                if (annotate):
                    draw.line([(mid_x-10, shoulder_y+ int(m*self.shoulderdistance)), (mid_x+10, shoulder_y + int(m*self.shoulderdistance))], fill='blue', width=1)
                    textptl= '%.2f'%(fd)
                    textptr= '%.2f'%(sqd)
                    draw.text((mid_x-50, shoulder_y+ int(m*self.shoulderdistance)), textptl, font=fnt, fill='blue')
                    draw.text((mid_x+20, shoulder_y+ int(m*self.shoulderdistance)), textptr, font=fnt,
                              fill='blue')

        self.areadifference = getAreasUnderLine(self.prediction['right'], self.shoulderdistance,
                                            linetype='right') - getAreasUnderLine(self.prediction['left'],
                                                                                  self.shoulderdistance, linetype='left')
        self.areadifference /= self.shoulderdistance

        self.angles = np.zeros(len(self.prediction['left']), dtype=float)
        i = 0
        for pl, pr in zip(self.prediction['left'], self.prediction['right']):
            lpt = (pl[0] * zoomfactor, pl[1] * zoomfactor)
            rpt = (pr[0] * zoomfactor, pr[1] * zoomfactor)
            # only for debugging and/or predicted
            # cv2.circle(i2, lpt, 4, (255, 255, 255), -1)
            # cv2.circle(i2, rpt, 4, (255, 255, 255), -1)
            interval = lpt[1] % 5 # only print every 5th line
           # angles sind die nach rechts offenen Winkel von Punkt zu Punkt auf der WaistLine
            self.angles[i] = get_angle([pr[0], pr[1]], [pl[0], pl[1]], [pr[0], pl[1]])
            i += 1

        curvl, curvl_max,curvature_left = getCurvature(np.array(self.prediction['left']))
        curvr, curvr_max,curvature_right = getCurvature(np.array(self.prediction['right']))
        self.curvatures={'left': curvl, 'right': curvr, 'left_max': curvl_max, 'right_max': curvr_max, 'left_curvature':curvature_left, 'right_curvature':curvature_right}

        self.annotatedImg=self.img
        self.result = {'MaxWaistAngle': max(self.angles),
                             'MinWaistAngle': min(self.angles),
                             'CurvatureDifference': abs(self.curvatures['left'] - self.curvatures['right']),
                             'CurvatureMaxDifference': abs(self.curvatures['left_max'] - self.curvatures['right_max']),
                             'ShoulderHeightDifference': self.shoulderheightdifference,
                             'WaistPointHeightDifference': self.waistpointheightdifference,
                             'WaistAreaDifferences': self.areadifference.tolist(),
                            'FrechetDistances':self.frechetDistanceArray,
                            'SquaredDistances':self.squaredDiffsArray}


