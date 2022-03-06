"""
Create permission groups
Create permissions (read only) to models for a set of groups
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission

grouppermdict= {
    'Validated User': [
         'auth.view_permission',
         'caserooms.add_caseroom',
         'caserooms.add_caseroomentry',
         'caserooms.change_caseroom',
         'caserooms.change_caseroomentry',
         'caserooms.delete_caseroom',
         'caserooms.delete_caseroomentry',
         'caserooms.view_caseroom',
         'caserooms.view_caseroomentry',
         'oauth2_provider.add_accesstoken',
         'oauth2_provider.delete_accesstoken',
         'oauth2_provider.view_accesstoken',
         'splineapp.add_spinesplinemodel',
         'splineapp.change_spinesplinemodel',
         'splineapp.delete_spinesplinemodel',
         'splineapp.view_spinesplinemodel',
         'users.add_consent',
         'users.add_contribution',
         'users.add_cost',
         'users.change_consent',
         'users.change_contribution',
         'users.change_cost',
         'users.change_user',
         'users.delete_consent',
         'users.delete_contribution',
         'users.delete_cost',
         'users.delete_user',
         'users.view_consent',
         'users.view_contribution',
         'users.view_cost',
         'users.view_user'
    ],
    'Non validated User': [
        'auth.view_permission',
        'oauth2_provider.add_accesstoken',
        'oauth2_provider.delete_accesstoken',
        'oauth2_provider.view_accesstoken',
        'users.add_consent',
        'users.change_consent',
        'users.change_user',
        'users.delete_consent',
        'users.delete_user',
        'users.view_consent',
        'users.view_user'
    ],
    'Staff': [
         'auth.add_permission',
         'auth.change_permission',
         'auth.delete_permission',
         'auth.view_permission',
         'caserooms.add_caseroom',
         'caserooms.add_caseroomentry',
         'caserooms.change_caseroom',
         'caserooms.change_caseroomentry',
         'caserooms.delete_caseroom',
         'caserooms.delete_caseroomentry',
         'caserooms.view_caseroom',
         'caserooms.view_caseroomentry',
         'contenttypes.add_contenttype',
         'contenttypes.change_contenttype',
         'contenttypes.delete_contenttype',
         'contenttypes.view_contenttype',
         'guardian.add_groupobjectpermission',
         'guardian.add_userobjectpermission',
         'guardian.change_groupobjectpermission',
         'guardian.change_userobjectpermission',
         'guardian.delete_groupobjectpermission',
         'guardian.delete_userobjectpermission',
         'guardian.view_groupobjectpermission',
         'guardian.view_userobjectpermission',
         'oauth2_provider.add_accesstoken',
         'oauth2_provider.change_accesstoken',
         'oauth2_provider.delete_accesstoken',
         'oauth2_provider.view_accesstoken',
         'splineapp.add_spinesplinemodel',
         'splineapp.change_spinesplinemodel',
         'splineapp.delete_spinesplinemodel',
         'splineapp.view_spinesplinemodel',
         'users.add_consent',
         'users.add_consentcontent',
         'users.add_contribution',
         'users.add_cost',
         'users.add_user',
         'users.add_userproof',
         'users.change_consent',
         'users.change_consentcontent',
         'users.change_contribution',
         'users.change_cost',
         'users.change_user',
         'users.change_userproof',
         'users.delete_consent',
         'users.delete_consentcontent',
         'users.delete_contribution',
         'users.delete_cost',
         'users.delete_user',
         'users.delete_userproof',
         'users.view_consent',
         'users.view_consentcontent',
         'users.view_contribution',
         'users.view_cost',
         'users.view_user',
         'users.view_userproof'
    ]

}

class Command(BaseCommand):
    help = 'Creates read only default permission groups for users'

    def handle(self, *args, **options):
        for k,v in grouppermdict.items():
            new_group, created = Group.objects.get_or_create(name=k)
            for permission in v:
                app_label=permission.split('.')[0]
                model_name=permission.rsplit('_')[-1]
                permstring=permission.split('.')[1]
                print('Getting Content Type for app {} and model {} with permstring {}'.format(app_label,model_name,permstring))
                content_type = ContentType.objects.get(app_label=app_label, model=model_name)
                print("Creating {}".format(permission))
                try:
                    model_add_perm = Permission.objects.get(codename=permstring, content_type=content_type)
                except Permission.DoesNotExist:
                    logging.warning("**** Permission not found with name '{}'.".format(permission))
                    continue

                new_group.permissions.add(model_add_perm)

        print("Created default group and permissions.")