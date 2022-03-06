from django.apps import AppConfig

#from users.utils import create__or_update_groups


class SplineappConfig(AppConfig):
    name = 'splineapp'

    def ready(self):
        pass
        #create__or_update_groups()


