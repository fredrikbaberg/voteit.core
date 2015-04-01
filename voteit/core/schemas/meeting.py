# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import colander
import deform
from repoze.workflow import get_workflow

from voteit.core import VoteITMF as _
from voteit.core import security 
from voteit.core.models.interfaces import IAccessPolicy
from voteit.core.models.interfaces import IPollPlugin
from voteit.core.models.interfaces import IProposal
from voteit.core.schemas.common import NAME_PATTERN
from voteit.core.validators import html_string_validator
from voteit.core.validators import richtext_validator


@colander.deferred
def poll_plugins_choices_widget(node, kw):
    request = kw['request']
    plugin_choices = [(x.name, x.factory.title) for x in request.registry.registeredAdapters() if x.provided == IPollPlugin]
    return deform.widget.CheckboxChoiceWidget(values = plugin_choices)

@colander.deferred
def deferred_access_policy_widget(node, kw):
    request = kw['request']
    choices = [(x.name, x.factory) for x in request.registry.registeredAdapters() if x.provided == IAccessPolicy]
    return deform.widget.RadioChoiceWidget(values = choices,
                                           template = "object_radio_choice",
                                           readonly_template = "readonly/object_radio_choice")

@colander.deferred
def deferred_copy_perms_widget(node, kw):
    context = kw['context']
    request = kw['request']
    view = kw['view']
    choices = [('', _("<Don't copy>"))]
    for meeting in view.root.get_content(content_type = 'Meeting'):
        if request.has_permission(security.MODERATE_MEETING, meeting):
            choices.append((meeting.__name__, "%s (%s)" % (meeting.title, meeting.__name__)))
    return deform.widget.SelectWidget(values=choices)

@colander.deferred
def deferred_current_user_mail(node, kw):
    request = kw['request']
    if request.profile:
        return request.profile.email

@colander.deferred
def _deferred_current_fullname(node, kw):
    request = kw['request']
    if request.profile:
        return request.profile.title


class EditMeetingSchema(colander.Schema):
    title = colander.SchemaNode(colander.String(),
        title = _("Title"),
        description = _("meeting_title_description",
                        default="Set a title for the meeting that separates it from previous meetings"),
        validator = html_string_validator,)
    meeting_mail_name = colander.SchemaNode(colander.String(),
        title = _("Name of the contact person for this meeting"),
        default = _deferred_current_fullname,
        validator = colander.Regex(regex = NAME_PATTERN,
                                   msg = _("name_pattern_error",
                                         default = "Must be at least 3 chars + only alphanumeric characters allowed")),)
    meeting_mail_address = colander.SchemaNode(colander.String(),
        title = _("Contact email for this site"),
        default = deferred_current_user_mail,
        validator = colander.All(colander.Email(msg = _("Invalid email address.")), html_string_validator,),)
    description = colander.SchemaNode(colander.String(),
        title = _("Short description"),
        description = _("short_description_text",
                        default = "Shows up in search results and similar. One sentence is enough. "
                        "You don't need to add it if you don't want to."),
        missing = "",
        validator = html_string_validator)
    body = colander.SchemaNode(colander.String(),
        title = _("Participants description"),
        description = _("meeting_description_description",
                        default="This is only visible to participants, so don't put information on how to register here. "
                            "Displayed on the first page of the meeting. You can include things "
                            "like information about the meeting, how to contact the moderator and your logo."),
        missing = "",
        widget = deform.widget.RichTextWidget(options = (('theme', 'advanced'),)),
        validator = richtext_validator,)
    public_description = colander.SchemaNode(
        colander.String(),
        title = _("Public presentation"),
        description = _("meeting_public_description_description",
                        default="The public description is visible on the request access "
                            "page and to not yet logged in visitors."),
        missing = "",
        widget = deform.widget.RichTextWidget(options = (('theme', 'advanced'),)),
        validator = richtext_validator,)
    mention_notification_setting = colander.SchemaNode(colander.Bool(),
        title = _("Send mail to mentioned users."),
        default = True,
        missing = True,
        tab = 'advanced',)
    poll_notification_setting = colander.SchemaNode(colander.Bool(),
        title = _("Send mail to voters when a poll starts."),
        default = True,
        missing = True,
        tab = 'advanced',)
    hide_meeting = colander.SchemaNode(colander.Bool(),
        title = _("Hide meeting from listings"),
        description = _("hide_meeting_description",
                        default = "Users won't be able to find it unless they have a link to it."),
        tab = 'advanced',
        default = False,
        missing = False)
    nav_title = colander.SchemaNode(colander.String(),
         title = _("Navigation bar title"),
         description = _("In case you want another title in the navigation bar"),
         missing = "",
         tab = 'advanced')


class AddMeetingSchema(EditMeetingSchema):
    copy_users_and_perms = colander.SchemaNode(colander.String(),
                                               title = _("Copy users and permissions from a previous meeting."),
                                               description = _("You can only pick meeting where you've been a moderator."),
                                               widget = deferred_copy_perms_widget,
                                               default = "",
                                               missing = "",
                                               tab = 'advanced')


class AccessPolicyMeetingSchema(colander.MappingSchema):
    access_policy = colander.SchemaNode(colander.String(),
        title = _("Meeting access policy"),
        widget = deferred_access_policy_widget,
        default = "invite_only",)


class MeetingPollSettingsSchema(colander.Schema):
    poll_plugins = colander.SchemaNode(colander.Set(),
                                       title = _("mps_poll_plugins_title",
                                                 default = "Available poll methods within this meeting"),
                                       description = _("mps_poll_plugins_description",
                                                       default="Only poll methods selected here will be available withing the meeting. "
                                                               "If nothing is selected, only the servers default poll method will be available."),
                                       missing=set(),
                                       widget = poll_plugins_choices_widget,)


@colander.deferred
def hide_proposal_states_widget(node, kw):
    request = kw['request']
    wf = get_workflow(IProposal, 'Proposal')
    state_values = []
    
    for info in wf._state_info(IProposal): #Public API goes through permission checker
        item = [info['name']]
        item.append(info['title'])
        state_values.append(item)
    return deform.widget.CheckboxChoiceWidget(values = state_values)


class AgendaItemProposalsPortletSchema(colander.Schema):
    hide_proposal_states = colander.SchemaNode(colander.Set(),
                                               title = _("Hide"),
                                               description = _("hide_proposal_states_description",
                                                               default = "Proposals in these states will be hidden by "
                                                               "default but can be shown by pressing "
                                                               "the link below the other proposals."),
                                               widget = hide_proposal_states_widget,
                                               default = ('retracted', 'denied', 'unhandled'),)


def includeme(config):
    config.add_content_schema('Meeting', AddMeetingSchema, 'add')
    config.add_content_schema('Meeting', EditMeetingSchema, 'edit')
    config.add_content_schema('Meeting', MeetingPollSettingsSchema, 'meeting_poll_settings')
    config.add_content_schema('Meeting', AccessPolicyMeetingSchema, 'access_policy')
