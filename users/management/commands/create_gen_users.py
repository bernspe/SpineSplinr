from django.core.management import BaseCommand

from SpineSplinr.settings import GEN_STAFF_USER
from users.models import User, Userrole


class Command(BaseCommand):
    help = 'Creates read only default permission groups for users'

    def handle(self, *args, **options):
        r=Userrole.objects.get(role='Support')
        u,c=User.objects.update_or_create(**GEN_STAFF_USER)
        u.roles.add(r)
        if c:
            print('User %s was created.'%u.get_full_name())
        else:
            print('User %s already existed and was updated. '%u.get_full_name())