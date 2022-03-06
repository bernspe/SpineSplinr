import os

import numpy as np
import scipy.interpolate as ip
from PIL import Image, ImageDraw, ImageFont
from scipy.signal import argrelextrema

from SpineSplinr.settings import BASE_DIR

vertebrae = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T10', 'T11', 'T12', 'L1', 'L2', 'L3', 'L4','L5', 'S1']

def generateLine(pts):
    try:
        f1 = ip.interp1d(pts[:, 0], pts[:, 1], kind='cubic')  # einfache cubic Interpolation
        # interpolierte Linie
        defLine4 = [(y, int(f1(y))) for y in range(pts[0, 0], pts[-1, 0])]
        return defLine4
    except:
        print('Linie konnte nicht erstellt werden')
        return None


def optimizeWaistLine(wline, side, automode=True):
    waistbottom = None
    waisttop = None
    waist = None

    wl = np.sort(wline[0:-5], order='x')

    l = wline.shape[0]
    if (l < 5 and l > 0):
        return wline[0], wline[l // 2], wline[-1], wline
    elif l == 0:
        return None, None, None, None

    if side == 'left':
        waist = wl[-1]

        waist_ind = int(np.where(wline['y'] == waist[0])[0])
        if automode:
            if waist_ind > 0:
                waisttop = np.sort(wline[0:waist_ind], order='x')[0]
                waistbottom = np.sort(wline[waist_ind:l - 1], order='y')[-5]
                if waistbottom[1] > (waist[1] - 3):
                    # print('Left WaistBottom is X-oriented')
                    waistbottom = np.sort(wline[waist_ind:l - 1], order='x')[0]

            else:
                waisttop, waistbottom = None, None
        else:
            waisttop = np.sort(wline, order='y')[0]
            waistbottom = np.sort(wline, order='y')[-1]
    if side == 'right':
        waist = wl[0]
        waist_ind = int(np.where(wline['y'] == waist[0])[0])
        if automode:
            if waist_ind > 0:
                waisttop = np.sort(wline[0:waist_ind], order='x')[
                    -1]  # nimm den Punkt, der am weitesten draussen liegt
                waistbottom = np.sort(wline[waist_ind:l - 1], order='y')[-5]  # nimm den 5.untersten Punkt
                # print('WB X: %i, W X: %i'%(waistbottom[1],waist[1]))
                if waistbottom[1] < (waist[1] + 3):
                    # print('Right WaistBottom is X-oriented')
                    waistbottom = np.sort(wline[waist_ind:l - 1], order='x')[-1]
                # print(np.sort(wline[waist_ind:l-1], order='x'))
            else:
                waisttop, waistbottom = None, None
        else:
            waisttop = np.sort(wline, order='y')[0]
            waistbottom = np.sort(wline, order='y')[-1]

    # wline2=wline.view((int,2))
    if waistbottom is not None:
        optline = wline[wline['y'] < waistbottom[0]]
    else:
        optline = wline
    return tuple(map(lambda x: int(x), waisttop)), tuple(map(lambda x: int(x), waist)), tuple(
        map(lambda x: int(x), waistbottom)), optline

def get_angle(p0, p1=np.array([0, 0]), p2=None):
    if p2 is None:
        p2 = p1 + np.array([1, 0])
    v0 = np.array(p0) - np.array(p1)
    v1 = np.array(p2) - np.array(p1)
    angle = np.math.atan2(np.linalg.det([v0, v1]), np.dot(v0, v1))
    return np.degrees(angle)


def label_upright(resized_img,coords):
    w=resized_img.width
    draw = ImageDraw.Draw(resized_img)
    dtype = [('y', int), ('x', int)]
    result={}
    circle_radius=5

    linepts = {'left': [(item['y'], item['x']) for item in coords if (item['x'] < w // 2)],
               'right': [(item['y'], item['x']) for item in coords if (item['x'] > w // 2)]}
    waistpts = {}
    waistline = {}
    for s in ['left', 'right']:
        line = np.array(linepts[s], dtype=dtype)
        line = np.sort(line, order='y')
        wline = generateLine(line.view((int, 2)))
        waistline[s] = wline
        if wline is not None:
            p1, p2, p3, _ = optimizeWaistLine(np.array(wline, dtype=dtype), s, automode=False)
            for wp2 in wline:
                draw.ellipse(xy=(wp2[1]-circle_radius, wp2[0]-circle_radius, wp2[1]+circle_radius*2, wp2[0]+circle_radius*2),
                            fill=(0, 127, 0),
                            outline=(255, 255, 255),
                            width=1)
            for ps, pt in zip(['Waisttop', 'Waist', 'Waistbottom'], [p1, p2, p3]):
                if pt is not None:
                    draw.ellipse(xy=(pt[1]-circle_radius, pt[0]-circle_radius, pt[1] + circle_radius*2, pt[0] + circle_radius*2),
                                fill=(127,0, 0),
                                outline=(255, 255, 255),
                                width=1)
                waistpts[s + '_' + ps] = pt
    result['waistline'] = {k: [(coord[1], coord[0]) for coord in v] for (k, v) in waistline.items()}
    result['waistpoints'] = waistpts
    return resized_img,result

def label_bendforward(resized_img, coords):
    w=resized_img.width
    draw = ImageDraw.Draw(resized_img)
    fnt = ImageFont.truetype(os.path.join(BASE_DIR, "splineapp/acmesa.ttf"), 24)
    dtype = [('x', int), ('y', int)]
    result={}
    circle_radius=5

    linepts = {'left': [(item['x'], item['y']) for item in coords if (item['x'] < w // 2)],
               'right': [(item['x'], item['y']) for item in coords if (item['x'] > w // 2)]}

    print(linepts)

    humpline = {}
    humppt = {}
    for s in ['left', 'right']:
        hline = np.unique(np.array(linepts[s], dtype=dtype))
        hline = np.sort(hline, order='x')
        linearr = hline.view((int, 2))
        humpline[s] = linearr
        humpptidx = np.argmin(linearr[:, 1])  # find the topmost point
        humppt[s] = linearr[humpptidx]
        draw.ellipse(
            xy=(humppt[s][0] - circle_radius, humppt[s][1] - circle_radius, humppt[s][0] + circle_radius * 2, humppt[s][1] + circle_radius * 2),
            fill=(0, 127, 0),
            outline=(255, 255, 255),
            width=1)

    # get angle
    humpangle = get_angle(humppt['right'], humppt['left'], [humppt['right'][0], humppt['left'][1]])
    draw.line([tuple(humppt['left']), tuple(humppt['right'])], fill='blue', width=1)
    draw.text(tuple(humppt['right']), 'HA=%.2f' % humpangle, font=fnt, fill='blue')
    result['Humplines'] = {k: v.tolist() for (k, v) in humpline.items()}
    result['Humppts'] = {k: v.tolist() for (k, v) in humppt.items()}
    result['Humpangle'] = humpangle
    return resized_img, result

def label_xray_spline(resized_img, uv, lv,coords, manual_cobb):
    w=resized_img.width
    draw = ImageDraw.Draw(resized_img)
    fnt = ImageFont.truetype(os.path.join(BASE_DIR, "splineapp/acmesa.ttf"), 12)
    dtype = [('x', int), ('y', int)]
    circle_radius = 2
    result={}
    # sort the coords
    ca=[(item['x'], item['y']) for item in coords]
    vline = np.array(ca, dtype=dtype)
    vline = np.sort(vline, order='y')
    c_arr = vline.view((int, 2))
    # label vertebrae according to given upper and lower vertebra
    if c_arr[:, 0].shape[0] < (lv - uv):
        print('Lower Vertebra not specified. Only %i entries, expected %i' % (c_arr[:, 0].shape[0], lv - uv))
        return None, None
    else:
        draw.text((c_arr[0, 0] - 25, c_arr[0, 1]), vertebrae[uv], font=fnt, fill=(255, 255, 255))
        draw.text((c_arr[-1, 0] - 25, c_arr[-1, 1]), vertebrae[lv], font=fnt, fill=(255, 255, 255))
        result['upperVertebra'] = vertebrae[uv]
        result['lowerVertebra'] = vertebrae[lv]
    # interpolate mid line
    f1 = ip.interp1d(c_arr[:, 1], c_arr[:, 0], kind='cubic')
    interp_line = [(int(f1(y)), y) for y in range(min(c_arr[:, 1]), max(c_arr[:, 1]))]
    for pt in interp_line:
        draw.ellipse(
            xy=(pt[0] - circle_radius, pt[1] - circle_radius, pt[0] + circle_radius * 2, pt[1] + circle_radius * 2),
            fill=(0, 127, 0),
            outline=(255, 255, 255),
            width=1)
    for i in range(len(c_arr)):
        result[vertebrae[uv + i]] = c_arr[i].tolist()
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
        draw.line([(midX, midY), (x3, y3)], width=1)
        vangle = get_angle([midX, y3], [x3, y3], [midX, midY])
        a[i] = vangle
        draw.text((midX, midY), '%.1f' % vangle, font=fnt, fill=(255, 255, 255))
    # calculate COBB angle
    pa = argrelextrema(a, np.greater, order=2, mode='wrap')[0]
    na = argrelextrema(a, np.less, order=2, mode='wrap')[0]
    ai = np.sort(np.hstack([pa, na]))
    ai = np.delete(ai, np.where(np.diff(ai) == 1)[0])
    spline_angles = []
    del_i = []
    for i in range(ai.shape[0] - 1):
        a_sum = abs(a[ai[i]]) + abs(a[ai[i + 1]])
        if a_sum > 10:
            spline_angles.append(int(a_sum))
        else:
            del_i.append(i)
    if len(del_i) > 0:
        ai = np.delete(ai, del_i)
    # label Neutral-Vertebrae and COBB angle
    result['SPLINE_vertebrae'] = []
    result['SPLINE_angles'] = []
    for i in range(len(ai) - 1):
        a1 = ai[i]
        a2 = ai[i + 1]
        spline_angle = spline_angles[i]
        ypos = c_arr[a1][1] + (c_arr[a2][1] - c_arr[a1][1]) // 2
        xpos = int(c_arr[a2][0] + c_arr[a1][0]) // 2 + 30
        draw.text((xpos, ypos), 'SPLINE %s - %s: \n %i°' % (vertebrae[uv + a1], vertebrae[uv + a2], spline_angle), anchor='ls', font=fnt, fill=(255, 255, 255))
        result['SPLINE_vertebrae'].append((vertebrae[uv + a1], vertebrae[uv + a2]))
        result['SPLINE_angles'].append(spline_angle)

    #do the labelling with manual_cobb
    m_lines = manual_cobb['cobblines'] # line.start = [x,y], line.end = [x,y]
    m_angles = manual_cobb['cobbangles'] # angle.position = [x,y] angle.degree = String
    m_vert = manual_cobb['cobbvertebrae'] # vertebrae = [upper, lower], e.g. ['Th12','L4']

    result['COBB_vertebrae'] = []
    result['COBB_angles'] = []
    for l in m_lines:
        draw.line([(l['start'][0], l['start'][1]), (l['end'][0], l['end'][1])], fill=(128, 128, 255), width=3)
    for a,v in zip(m_angles,m_vert):
        draw.text((a['position'][0], a['position'][1]), 'COBB %s - %s: \n %s°'%(v[0],v[1],str(a['degree'])),anchor='rs', font=fnt, fill=(128, 128, 255))
        result['COBB_vertebrae'].append(v)
        result['COBB_angles'].append(a['degree'])

    return resized_img, result