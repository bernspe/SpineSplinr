import os
from datetime import datetime, timezone
from io import BytesIO

import qrcode
from django.core.files.base import ContentFile
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Frame

from SpineSplinr.settings import INVITED_USER_URL, USER_INVITATION_DIR
from urllib.parse import urlencode

class UserQRCode:
    def __init__(self,useremail=None, username=None, notify=None):
        # notify sends a websocket message to the username when QRCode was used to log in
        self.qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        suffix= {}
        if useremail:
            suffix['email'] = useremail
        if username:
            suffix['username'] = username
        if notify:
            suffix['notify']=notify
        self.qr.add_data(INVITED_USER_URL + '?'+urlencode(suffix))
        self.qr.make(fit=True)

    def getQRCode(self):
        """
        obtain the QR Code in PIL Image format
        :return:
        """
        return self.qr.make_image(fill_color="black", back_color="white")

    def getQRCodeAsContentFile(self):
        buffer = BytesIO()
        img=self.getQRCode()
        img.save(stream=buffer, format='PNG')
        return ContentFile(buffer.getvalue())


class PdfFile:
    filename=''

    def __init__(self, recipient_name='', recipient_email='', recipient_password='startpass', recipient=[], recipient_username=None ,sender='', buffer=None):
        if not os.path.exists(USER_INVITATION_DIR):
            os.mkdir(USER_INVITATION_DIR)
        self.filename="/einladung_%s.pdf"%recipient_name.split(' ')[0]
        self.logo="images/skolioselogo.png"
        if buffer:
            self.c=canvas.Canvas(buffer)
        else:
            self.c = canvas.Canvas(USER_INVITATION_DIR+self.filename)
        self.to=recipient
        self.to_name=recipient_name
        self.to_username=recipient_username
        self.fr=sender
        self.to_email=recipient_email
        self.to_password=recipient_password

    def pageHeading(self):
        textobject = self.c.beginText()
        textobject.setTextOrigin(3*cm,28*cm)
        textobject.setFont("Helvetica-Oblique", 20)
        textobject.textLine(text="skoliosekinder.de")
        self.c.drawText(textobject)
        self.c.drawImage(self.logo, 16*cm, 21*cm,preserveAspectRatio=True, width=3.5*cm,)
        p = self.c.beginPath()
        p.moveTo(cm, 27.5*cm)
        p.lineTo(15*cm, 27.5*cm)
        self.c.drawPath(p, stroke=1, fill=1)

    def adress(self):
        textobject = self.c.beginText()
        textobject.setTextOrigin(2.5*cm,25*cm)
        textobject.setFont("Helvetica", 12)
        textobject.textLines(stuff=self.to_name+"\n"+self.to)
        self.c.drawText(textobject)

    def subject(self):
        textobject = self.c.beginText()
        textobject.setTextOrigin(2.5*cm,20*cm)
        textobject.setFont("Helvetica-Bold", 12)
        textobject.textLine(text="Einladung")
        self.c.drawText(textobject)

    def date(self):
        textobject = self.c.beginText()
        textobject.setTextOrigin(15*cm,21.5*cm)
        textobject.setFont("Helvetica", 10)
        textobject.textLine(text=datetime.now().replace(tzinfo=timezone.utc).strftime("%d.%m.%Y"))
        self.c.drawText(textobject)

    def body(self):
        styles = getSampleStyleSheet()
        styleN = styles['BodyText']
        styleH = styles['Heading2']
        story = []
        # add some flowables
        story.append(Paragraph("Hallo %s"%self.to_name.split(' ')[0], styleH))
        if len(self.fr)>0:
            story.append(Paragraph("%s und ich möchten Dich gern bei skoliosekinder.de begrüßen."%self.fr,
                               styleN))
        else:
            story.append(Paragraph("Wir möchten Dich gern bei skoliosekinder.de begrüßen.",
                               styleN))
        s=''
        with open('templates/pdf_body1.ml','r') as file:
            s=file.read().replace('\n', '')
        story.append(Paragraph(s,styleN))
        story.append(Paragraph("Deine Anmeldedaten", styleH))
        story.append(Paragraph("Anmeldename (Pseudo-Email, von uns vergeben - muss in echte Email-Adresse geändert werden): <strong>%s"%self.to_email+"</strong>",styleN, bulletText="\x80"))
        story.append(Paragraph(
            "Du kannst im Browser <strong>skoliosekinder.de</strong> eingeben und dich dann per Login anmelden. Ein Passwort benötigst du für den ersten Login nicht.",
            styleN, bulletText="\x80"))
        story.append(Paragraph(
            "Oder du nutzt den QR Code mit Smartphone oder Tablet:",
            styleN, bulletText="\x80"))
        #story.append(Paragraph("Passwort (Startpasswort, muss bei der ersten Anmeldung geändert werden): <strong>%s"%self.to_password+"</strong>", styleN, bulletText="\x80"))
        if self.to_username:
            qr = UserQRCode(username=self.to_username)
        else:
            qr = UserQRCode(useremail=self.to_email)
        qrimg=qr.getQRCode()

        f = Frame(2.5*cm, 2*cm, 16 * cm, 16 * cm, showBoundary=0)
        f.addFromList(story, self.c)
        self.c.drawInlineImage(qrimg, 8 * cm, 2 * cm, width=3*cm,height=3*cm)

    def makePdf(self):
        self.c.showPage()
        self.c.save()

    def build(self):
        try:
            self.pageHeading()
            self.adress()
            self.date()
            self.subject()
            self.body()
            self.makePdf()
            return True,self.filename
        except Exception as e:
            return False,e