from betahaus.viewcomponent import render_view_group
from betahaus.viewcomponent import view_action
from pyramid.renderers import render
from zope.interface.interfaces import ComponentLookupError

from voteit.core import _
from voteit.core.security import DELETE
from voteit.core.security import EDIT
from voteit.core.models.interfaces import IAgendaItem
from voteit.core.models.interfaces import IMeeting
from voteit.core.models.interfaces import IPoll
from voteit.core.models.interfaces import IWorkflowAware
from voteit.core.views.components.metadata_listing import meta_state


@view_action('actionbar_main', 'voteit_wf',
             title = _("Workflow"),
             priority = 5,
             interface = IWorkflowAware,
             renderer = 'voteit.core:templates/snippets/workflow_menu.pt')
def wf_menu(context, request, va, **kw):
    return meta_state(context, request, va, **kw)


@view_action('context_actions', 'edit', title = _(u"Edit"),
             context_perm = EDIT, viewname = 'edit', priority=10)
@view_action('context_actions', 'edit_proposals',
             title = _(u"Edit picked proposals"),
             interface = IPoll,
             context_perm = EDIT,
             viewname = 'edit_proposals',
             priority=20)
def moderator_context_action(context, request, va, **kw):
    context_perm = va.kwargs.get('context_perm', None)
    if context_perm and not request.has_permission(context_perm, context):
        return
    url = request.resource_url(context, va.kwargs['viewname'])
    return """<li><a href="%s" class="%s">%s</a></li>""" % (url, va.kwargs['viewname'], request.localizer.translate(va.title))


@view_action('context_actions', 'delete', title = _(u"Delete"),
             context_perm = DELETE, viewname = 'delete',  priority=100)
def moderator_context_delete(context, request, va, **kw):
    """ This is already a part of the Arches context menu, so it shouldn't be shown in meetings or agenda items.
    """
    if IAgendaItem.providedBy(context) or IMeeting.providedBy(context):
        return
    return moderator_context_action(context, request, va, **kw)


@view_action('context_actions', 'poll_config', title = _(u"Poll settings"),
             interface = IPoll,  priority=30)
def poll_settings_context_action(context, request, va, **kw):
    try:
        schema = context.get_poll_plugin().get_settings_schema()
    except Exception: # pragma: no cover (When plugin has been removed)
        return
    if request.has_permission(EDIT, context) and schema:
        url = request.resource_url(context, 'poll_config')
        return """<li><a href="%s">%s</a></li>""" % (url, request.localizer.translate(_(u"Poll settings")))


@view_action('proposal_extras', 'enable_proposal_block', title = _(u"Block proposals"),
             interface = IAgendaItem, setting = 'proposal_block', enable = True)
@view_action('proposal_extras', 'disable_proposal_block', title = _(u"Enable proposals"),
             interface = IAgendaItem, setting = 'proposal_block', enable = False)
@view_action('discussion_extras', 'enable_discussion_block', title = _(u"Block discussion"),
             interface = IAgendaItem, setting = 'discussion_block', enable = True)
@view_action('discussion_extras', 'disable_discussion_block', title = _(u"Enable discussion"),
             interface = IAgendaItem, setting = 'discussion_block', enable = False)
def block_specific_perm_action(context, request, va, **kw):
    setting = va.kwargs['setting']
    enabled = context.get_field_value(setting, False)
    if va.kwargs['enable'] == enabled:
        return
    url = request.resource_url(context, '_toggle_block', query = {setting: int(va.kwargs['enable'])})
    return """<li><a href="%s">%s</a></li>""" % (url, request.localizer.translate(va.title))


@view_action('context_menus', 'proposal_extras')
@view_action('context_menus', 'discussion_extras')
def context_menus(context, request, va, **kw):
    if request.is_moderator:
        try:
            menu_items = render_view_group(context, request, va.name, as_type='list')
        except ComponentLookupError:
            menu_items = []
        if menu_items:
            response = {
                'menu_items': menu_items,
                'context': context,
            }
            return render('voteit.core:templates/menus/dropdown_actions.pt',
                          response,
                          request=request)
