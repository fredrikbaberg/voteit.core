from __future__ import unicode_literals

import colander
import deform
from betahaus.pyracont.decorators import schema_factory
from betahaus.pyracont.factories import createSchema
from pyramid.httpexceptions import HTTPFound

from voteit.core.models.access_policy import AccessPolicy
from voteit.core import VoteITMF as _
from voteit.core import security


class ImmediateAP(AccessPolicy):
    """ Grant access for specific permissions immediately if a user requests it.
        No moderator approval requred. This is for very public meetings.
    """
    name = 'public'
    title = _("Public access")
    description = _("public_access_description",
                    default = "Users will be granted the permissions you select without prior moderator approval. This is for public meetings.")

    def schema(self):
        return colander.Schema(title = _("Would you like to participate?"),
                               description = _("Clicking request access will grant you access right away!"))

    def handle_success(self, view, appstruct):
        rolesdict = dict(security.STANDARD_ROLES)
        roles = self.context.get_field_value('immediate_access_grant_roles')
        self.context.add_groups(view.api.userid, roles)
        view.api.flash_messages.add(_("Access granted - welcome!"))
        return HTTPFound(location = view.api.meeting_url)

    def config_schema(self):
        return createSchema('ImmediateAPConfigSchema')

    def handle_config_success(self, view, appstruct):
        self.context.set_field_appstruct(appstruct)
        view.api.flash_messages.add(view.default_success)
        return HTTPFound(location = view.api.meeting_url)


@schema_factory('ImmediateAPConfigSchema', title = _("Configure immediate access policy"))
class ImmediateAPConfigSchema(colander.Schema):
    immediate_access_grant_roles = colander.SchemaNode(
        deform.Set(),
        title = _("Roles"),
        description = _("immediate_ap_schema_grant_description",
                        default = "Users will be granted these roles IMMEDIATELY upon requesting access."),
        default = (security.ROLE_VIEWER,),
        widget = deform.widget.CheckboxChoiceWidget(values=security.STANDARD_ROLES,),
    )


def includeme(config):
    config.registry.registerAdapter(ImmediateAP, name = ImmediateAP.name)
