
from django.core.management.base import BaseCommand
import pandas as pd
from users.models import Userrole

def add2Model(row):
    r = row.to_dict()
    try:
        role=Userrole.objects.filter(role=r['role'])
        if len(role)==1:
            role.update(**r)
            print('Updated: {}'.format(role))
        if len(role)==0:
            role = Userrole.objects.create(**r)
            print('Created role: {}'.format(role))
    except Exception as e:
        print(str(e))

class Command(BaseCommand):
    help = 'Updates and creates role specifications for users'

    def handle(self, *args, **options):
        df = pd.read_excel('initialdata/roles.xls')
        df2 = df.filter(like='translation')
        df=df.drop(columns=df2.columns)
        df2.rename(lambda x: x.split('_')[1], axis=1,inplace=True)
        df['translations']=df2.to_dict(orient='records')
        modelbatch=[]
        for row in df.iterrows():
            print('Calling add2model for {}'.format(row[0]))
            add2Model(row[1])
            #d=row[1].to_dict()
            #modelbatch.append(Userrole(role=d['role'], translations=d['translations'], category=d['category'], proof=d['proof'], consents=d['consents']))
        #Userrole.objects.bulk_create(modelbatch,len(modelbatch))