from BTrees.OOBTree import OOBTree
from arche.interfaces import IObjectAddedEvent
from arche.portlets import get_portlet_manager
from arche.security import get_acl_registry
from pyramid.httpexceptions import HTTPForbidden
from pyramid.traversal import find_root
from repoze.folder import unicodify
from zope.interface import implementer

from voteit.core import VoteITMF as _
from voteit.core import security
from voteit.core.models.arche_compat import createContent
from voteit.core.models.base_content import BaseContent
from voteit.core.models.interfaces import IAgendaItem
from voteit.core.models.interfaces import IMeeting
from voteit.core.models.workflow_aware import WorkflowAware
from voteit.core.models.security_aware import SecurityAware


@implementer(IMeeting)
class Meeting(BaseContent, SecurityAware, WorkflowAware):
    """ Meeting content type.
        See :mod:`voteit.core.models.interfaces.IMeeting`.
        All methods are documented in the interface of this class.
    """
    type_name = 'Meeting'
    type_title = _(u"Meeting")
    nav_visible = False
    add_permission = security.ADD_MEETING
    hide_meeting = False #Unless it's been set, don't show meeting
    nav_title = ""
    custom_mutators = {'copy_perms_and_users': 'copy_perms_and_users'}

    def __init__(self, data=None, **kwargs):
        """ When meetings are added, whoever added them should become moderator and voter.
            BaseContent will have added userid to creators attribute.
        """
        super(Meeting, self).__init__(data=data, **kwargs)
        if len(self.creators) and self.creators[0]:
            userid = self.creators[0]
            #We can't send the event here since the object isn't attached to the resource tree yet
            #When it is attached, an event will be sent.
            self.add_groups(userid, (security.ROLE_MODERATOR, ), event = False)

    @property
    def __acl__(self):
        acl = get_acl_registry()
        if self.get_workflow_state() == 'closed':
            return acl.get_acl('Meeting:closed')
        return acl.get_acl('Meeting:default')

    @property
    def order(self):
        if self._order is not None:
            return list(self._order)
        return self.data.keys()
    @order.setter
    def order(self, value):
        pool = list(self.data.keys())
        new_order = []
        for key in value:
            new_order.append(key)
            pool.remove(key)
        if pool:
            new_order.extend(pool)
        self._order = tuple([unicodify(x) for x in new_order])
        #Resort the agenda items too
        i = 1
        for obj in self.values():
            if not IAgendaItem.providedBy(obj):
                continue
            obj.set_field_appstruct({'order': i})
            i+=1

    @property
    def body(self): #arche compat
        return self.get_field_value('body', '')
    @body.setter
    def body(self, value):
        self.set_field_value('body', value)

    @property
    def start_time(self):
        return self.get_field_value('start_time')
    @start_time.setter
    def start_time(self, value):
        return self.set_field_value('start_time', value)

    @property
    def end_time(self):
        return self.get_field_value('end_time')
    @end_time.setter
    def end_time(self, value):
        return self.set_field_value('end_time', value)

    @property
    def meeting_mail_name(self): #arche compat
        return self.get_field_value('meeting_mail_name')
    @meeting_mail_name.setter
    def meeting_mail_name(self, value):
        self.set_field_value('meeting_mail_name', value)

    @property
    def meeting_mail_address(self): #arche compat
        return self.get_field_value('meeting_mail_address')
    @meeting_mail_address.setter
    def meeting_mail_address(self, value):
        self.set_field_value('meeting_mail_address', value)

    @property
    def public_description(self): #arche compat
        return self.get_field_value('public_description')
    @public_description.setter
    def public_description(self, value):
        self.set_field_value('public_description', value)

    @property
    def poll_notification_setting(self): #arche compat
        return self.get_field_value('poll_notification_setting', True)
    @poll_notification_setting.setter
    def poll_notification_setting(self, value):
        self.set_field_value('poll_notification_setting', value)

    @property
    def mention_notification_setting(self): #arche compat
        return self.get_field_value('mention_notification_setting', True)
    @mention_notification_setting.setter
    def mention_notification_setting(self, value):
        self.set_field_value('mention_notification_setting', value)

    @property
    def access_policy(self): #arche compat
        return self.get_field_value('access_policy')
    @access_policy.setter
    def access_policy(self, value):
        self.set_field_value('access_policy', value)

    @property
    def hide_proposal_states(self): #arche compat
        return self.get_field_value('hide_proposal_states', ('retracted', 'denied', 'unhandled'))
    @hide_proposal_states.setter
    def hide_proposal_states(self, value):
        self.set_field_value('hide_proposal_states', value)

    @property
    def invite_tickets(self):
        try:
            return self.__invite_tickets__
        except AttributeError:
            self.__invite_tickets__ = OOBTree()
            return self.__invite_tickets__

    def get_ticket_names(self, previous_invites = 0):
        assert isinstance(previous_invites, int)
        results = []
        for (name, ticket) in self.invite_tickets.items():
            if previous_invites < 0:
                continue
            if previous_invites >= len(ticket.sent_dates):
                results.append(name)
        return results

    def add_invite_ticket(self, email, roles, sent_by = None):
        if email in self.invite_tickets:
            return
        obj = createContent('InviteTicket', email, roles, sent_by = sent_by)
        obj.__parent__ = self
        self.invite_tickets[email] = obj
        return obj

    def copy_users_and_perms(self, name, event = True):
        root = find_root(self)
        origin = root[name]
        #value = origin.get_security()
        #self.set_security(value, event = event)
        self.local_roles.set_from_appstruct(origin.local_roles)


def closing_meeting_callback(context, info):
    """ Callback for workflow action. When a meeting is closed,
        raise an exception if any agenda item is ongoing.
    """
    #get_content returns a generator. It's "True" even if it's empty
    if tuple(context.get_content(iface=IAgendaItem, states=('ongoing', 'upcoming'))):
        err_msg = _(u"error_cant_close_meeting_with_ongoing_ais",
                    default = u"This meeting still has ongoing or upcoming Agenda items in it. You can't close it until they're closed.")
        raise HTTPForbidden(err_msg)

def add_default_portlets_meeting(meeting):
    manager = get_portlet_manager(meeting)
    if manager is not None:
        ai_polls = manager.add('agenda_item', 'ai_polls')
        ai_proposals = manager.add('agenda_item', 'ai_proposals')
        ai_proposals.settings = {'hide_proposal_states': ('retracted', 'denied', 'unhandled')}
        ai_discussions = manager.add('agenda_item', 'ai_discussions')
        agenda = manager.add('left', 'agenda')

def _add_portlets_meeting_subscriber(meeting, event):
    add_default_portlets_meeting(meeting)

def includeme(config):
    config.add_content_factory(Meeting, addable_to = 'Root')
    _MODERATOR_DEFAULTS = (security.VIEW,
                           security.EDIT,
                           security.MANAGE_GROUPS,
                           security.MODERATE_MEETING,
                           security.DELETE,
                           security.CHANGE_WORKFLOW_STATE,
                           security.ADD_INVITE_TICKET)
    aclreg = config.registry.acl
    default_acl = aclreg.new_acl('Meeting:default')
    default_acl.add(security.ROLE_ADMIN, security.REGULAR_ADD_PERMISSIONS)
    default_acl.add(security.ROLE_ADMIN, security.MANAGE_SERVER)
    default_acl.add(security.ROLE_ADMIN, _MODERATOR_DEFAULTS)
    default_acl.add(security.ROLE_MODERATOR, security.REGULAR_ADD_PERMISSIONS)
    default_acl.add(security.ROLE_MODERATOR, _MODERATOR_DEFAULTS)
    default_acl.add(security.ROLE_DISCUSS, security.ADD_DISCUSSION_POST)
    default_acl.add(security.ROLE_PROPOSE, security.ADD_PROPOSAL)
    default_acl.add(security.ROLE_VIEWER, security.VIEW)
    closed_acl = aclreg.new_acl('Meeting:closed')
    closed_acl.add(security.ROLE_ADMIN, (security.VIEW,
                                         security.MODERATE_MEETING,
                                         security.MANAGE_GROUPS,
                                         security.DELETE,
                                         security.CHANGE_WORKFLOW_STATE))
    closed_acl.add(security.ROLE_MODERATOR, (security.VIEW,
                                             security.MODERATE_MEETING,
                                             security.MANAGE_GROUPS,))
    closed_acl.add(security.ROLE_VIEWER, security.VIEW)
    config.add_subscriber(_add_portlets_meeting_subscriber, [IMeeting, IObjectAddedEvent])
