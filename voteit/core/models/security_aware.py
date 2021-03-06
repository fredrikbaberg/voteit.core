from arche.events import ObjectUpdatedEvent
from arche.resources import LocalRolesMixin
from pyramid.location import lineage
from zope.component.event import objectEventNotify
from zope.interface import implementer

from voteit.core.models.interfaces import ISecurityAware
from voteit.core import security


NON_INHERITED_GROUPS = ('role:Owner',)

ROLES_NAMESPACE = 'role:'
GROUPS_NAMESPACE = 'group:'
NAMESPACES = (ROLES_NAMESPACE, GROUPS_NAMESPACE, )


@implementer(ISecurityAware)
class SecurityAware(LocalRolesMixin):
    """ This is a compatibility-class for arche
    """

    def get_groups(self, principal):
        groups = set()
        for location in lineage(self):
            location_groups = location.local_roles
            try:
                if self is location:
                    groups.update(location_groups[principal])
                else:
                    #FIXME: non inherited groups from Arche
                    groups.update([x for x in location_groups[principal] if x not in NON_INHERITED_GROUPS])
            except KeyError:
                continue
        return tuple(groups)

    def check_groups(self, groups):
        self._check_groups(groups)
        adjusted_groups = set()
        for group in groups:
            adjusted_groups.add(group)
            deps = security.ROLE_DEPENDENCIES.get(group, None)
            if deps is None:
                continue
            adjusted_groups.update(set(deps))
        return adjusted_groups

    def add_groups(self, principal, groups, event = True):
        groups = set(groups)
        groups.update(self.get_groups(principal))
        #Delegate check and set to set_groups
        self.set_groups(principal, groups, event = event)

    def del_groups(self, principal, groups, event = True):
        if isinstance(groups, basestring):
            groups = set([groups])
        else:
            groups = set(groups)
        current = set(self.get_groups(principal))
        new_groups = current - groups
        #Delegate check and set to set_groups
        self.set_groups(principal, new_groups, event = event)

    def set_groups(self, principal, groups, event = True):
        changed = False
        if not groups:
            if principal in self.local_roles:
                del self.local_roles[principal]
                changed = True
        else:
            adjusted_groups = self.check_groups(groups)
            if adjusted_groups != set(self.get_groups(principal)):
                self.local_roles[principal] = tuple(adjusted_groups)
                changed = True
        if changed and event:
            self._notify()

    def get_security(self):
        userids_and_groups = []
        for userid in self.local_roles.keys():
            userids_and_groups.append({'userid': userid,
                                       'groups': self.get_groups(userid)})
        return tuple(userids_and_groups)

    def set_security(self, value, event = True):
        submitted_userids = [x['userid'] for x in value]
        current_userids = self.local_roles.keys()
        for userid in current_userids:
            if userid not in submitted_userids:
                del self.local_roles[userid]
        for item in value:
            self.set_groups(item['userid'], item['groups'], event = False)
        if event:
            self._notify()

    def _notify(self):
        #Only update specific index?
        objectEventNotify(ObjectUpdatedEvent(self))

    def _check_groups(self, groups):
        for group in groups:
            if not group.startswith(NAMESPACES):
                raise ValueError('Groups need to start with either "group:" or "role:"')
