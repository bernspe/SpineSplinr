from django.contrib.auth.models import Permission, Group
from sentry_sdk.utils import logger

from users import permissions

GROUP_PERMISSIONS=permissions.user_permissions_dict

def permission_names_to_objects(names):
    """
    Given an iterable of permission names (e.g. 'app_label.add_model'),
    return an iterable of Permission objects for them.  The permission
    must already exist, because a permission name is not enough information
    to create a new permission.
    """
    result = []
    for name in names:
        app_label, codename = name.split(".", 1)
        # Is that enough to be unique? Hope so
        try:
            result.append(Permission.objects.get(content_type__app_label=app_label,
                                                 codename=codename))
        except Permission.DoesNotExist:
            logger.exception("NO SUCH PERMISSION: %s, %s" % (app_label, codename))
            raise
    return result


def get_all_perm_names_for_group(group):
    # Return the set of permission names that the group should contain
    try:
        return GROUP_PERMISSIONS[group]
    except:
        logger.exception("Group not found: %s" % (group))
        return None


def create__or_update_groups():
    for group_name, perm_names in GROUP_PERMISSIONS.items():
        group, created = Group.objects.get_or_create(name=group_name)

        perms_to_add = permission_names_to_objects(get_all_perm_names_for_group(group_name))
        group.permissions.add(*perms_to_add)
        if not created:
            # Group already existed - make sure it doesn't have any perms we didn't want
            to_remove = set(group.permissions.all()) - set(perms_to_add)
            if to_remove:
                group.permissions.remove(*to_remove)
