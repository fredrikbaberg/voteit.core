from betahaus.viewcomponent import view_action
from pyramid.renderers import render
from pyramid.traversal import find_interface

from voteit.core import _
from voteit.core.models.interfaces import IAgendaItem
from voteit.core.models.interfaces import IDiscussionPost
from voteit.core.models.interfaces import IProposal
from voteit.core.models.interfaces import IWorkflowAware
from voteit.core.security import ADD_DISCUSSION_POST
from voteit.core.security import ADD_PROPOSAL
from voteit.core.security import DELETE
from voteit.core.security import RETRACT 
from voteit.core.security import VIEW


@view_action('metadata_listing', 'state',
             permission = VIEW,
             interface = IWorkflowAware,
             renderer = "voteit.core:templates/snippets/inline_workflow.pt",
             priority = 10)
def meta_state(context, request, va, **kw):
    """ Note: moderator actions also uses this one.
    """
    response = dict(
        section_title = va.title,
        state_id  = context.wf_state,
        state_title = context.workflow.state_title,
        transitions = tuple(context.workflow.get_transitions(request)),
        context = context,
    )
    return render(va.kwargs['renderer'], response, request = request)


@view_action('metadata_listing', 'retract',
             permission = VIEW,
             interface = IWorkflowAware,
             priority = 20)
def meta_retract(context, request, va, **kw):
    if request.is_moderator:
        return
    if context.wf_state != 'published':
        return
    if not request.authenticated_userid in context.creators:
        return
    #Now for the 'expensive' stuff
    ai = find_interface(context, IAgendaItem)
    if not (request.has_permission(ADD_PROPOSAL, ai) and request.has_permission(RETRACT, context)):
        return
    url = request.resource_url(context, 'state', query = {'state': 'retracted'})
    return '<a role="button" class="btn btn-default btn-xs" href="%s"><span class="text-warning">%s</span></a> ' % \
        (url, request.localizer.translate(_(u'Retract')))


@view_action('metadata_listing', 'diff_view',
             permission = VIEW,
             interface = IProposal,
             title = _('Full paragraph'),
             priority = 22)
def diff_view(context, request, va, **kw):
    if request.meeting.diff_text_enabled and context.diff_text_para != None:
        url = request.resource_url(context, 'diff_view')
        return """<a data-open-modal data-modal-class="modal-lg" role="button"
            class="btn btn-default btn-xs" href="%s"><span class="text-primary">
            <span class="glyphicon glyphicon-transfer"/>
            %s</span></a>
        """ % (url, request.localizer.translate(va.title))


@view_action('metadata_listing', 'reply',
             title = _("Reply"),
             interface = IDiscussionPost,
             priority = 30,
             ai_perm = ADD_DISCUSSION_POST)
@view_action('metadata_listing', 'comment',
             title = _("Comment"),
             interface = IProposal,
             priority = 30,
             ai_perm = ADD_DISCUSSION_POST)
def meta_comment(context, request, va, **kw):
    """ Create a comment link
    """
    if not request.has_permission(va.kwargs['ai_perm'], request.agenda_item):
        return
    query = {'content_type': 'DiscussionPost',
             'tag': request.GET.getall('tag'),
             'reply-to': context.uid}
    data = {'role': 'button',
            'class': 'btn btn-default btn-xs',
            #'data-reply-to': context.uid,
            'data-external-popover-loaded': 'false',
            'data-reply-to': context.uid,
            'data-placement': 'bottom',
            'title': '',
            'href': request.resource_url(request.agenda_item, 'add', query = query),}
    out = """<a %s><span class="text-primary">%s</span></a> """ % \
        (" ".join(['%s="%s"' % (k, v) for (k, v) in data.items()]),
         request.localizer.translate(va.title))
    return out


@view_action('metadata_listing', 'delete',
             permission = DELETE,
             interface = IDiscussionPost,
             priority = 40)
def meta_delete(context, request, va, **kw):
    if not request.is_moderator:
        return u'<a href="%s" role="button" class="btn btn-default btn-xs"><span class="text-danger">%s %s</span></a> ' % \
            (request.resource_url(context, 'delete'),
             '<span class="glyphicon glyphicon-remove"></span>',
             request.localizer.translate(_("Delete")))


@view_action('metadata_listing', 'pick_poll',
             interface=IProposal,
             priority=25)
def pick_poll(context, request, va, **kw):
    if request.is_moderator:
        values = dict(agenda_item=request.agenda_item, context=context)
        return render("voteit.core:templates/snippets/pick_poll.pt", values, request=request)
