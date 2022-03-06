from datetime import timedelta
from itertools import islice

import pandas as pd
from django.utils.timezone import now
from oauth2_provider.admin import AccessToken, Application
from users.models import User


def create_users(apps, schema_editor):
    # We can't import the Person model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    df=pd.read_excel('fakedata.xls')
    app = Application.objects.get(name="Splinr")
    batch_size=len(df)
    objs=(User(email=df['email'].iloc[i], first_name=df['first_name'].iloc[i], last_name=df['last_name'].iloc[i],
          date_of_birth=df['date_of_birth'].iloc[i], sex=df['sex'].iloc[i], username=df['username'].iloc[i],
          role=df['role'].iloc[i]) for i in range(batch_size))
    while True:
        batch = list(islice(objs, batch_size))
        if not batch:
            break
        User.objects.bulk_create(batch, batch_size)
    for i in range(batch_size):
        user=User.objects.get(username=df['username'].iloc[i])
        user.set_password(df['password'].iloc[i])
        AccessToken.objects.get_or_create(user=user,
                                          application=app,
                                          expires=now() + timedelta(days=365),
                                          token=df['accesstoken'].iloc[i])