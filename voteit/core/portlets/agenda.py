from __future__ import unicode_literals

from arche.portlets import PortletType
from arche.views.base import BaseView
from pyramid.renderers import render
from pyramid.traversal import resource_path
import colander
from pyramid.decorator import reify

from voteit.core.models.interfaces import IAgendaItem, IUserUnread
from voteit.core.models.interfaces import IMeeting
from voteit.core import _
from voteit.core.fanstaticlib import data_loader


class AgendaPortlet(PortletType):
    name = "agenda"
    schema_factory = None
    title = _("Agenda")

    def render(self, context, request, view, **kwargs):
        if request.meeting:
            data_loader.need()
            ai_name = IAgendaItem.providedBy(context) and context.__name__ or ''
            response = {'title': self.title,
                        'portlet': self.portlet,
                        'view': view,
                        'load_url': request.resource_url(request.meeting, '__agenda_items__', query = {'ai_name': ai_name})}
            return render("voteit.core:templates/portlets/agenda.pt",
                          response,
                          request = request)


class AgendaInlineView(BaseView):

    def __call__(self):
        response = {}
        states = ['ongoing', 'upcoming', 'closed']
        if self.request.is_moderator:
            states.append('private')
        response['states'] = states
        response['state_titles'] = self.request.get_wf_state_titles(IAgendaItem, 'AgendaItem')
        response['meeting_path'] = self.meeting_path = resource_path(self.request.meeting)
        ai_name = self.request.GET.get('ai_name', None)
        if ai_name:
            self.ai_path = "%s/%s" % (self.meeting_path, ai_name)
        else:
            self.ai_path = None
        return response

    def get_ais(self, state):
        results = []
        catalog = self.request.root.catalog
        unread_types = ('Proposal', 'DiscussionPost')
        user_unread = IUserUnread(self.request.profile)
        for docid in catalog.search(path = self.meeting_path,
                                    type_name = 'AgendaItem',
                                    workflow_state = state)[1]:
            try:
                meta = dict(self.request.root.document_map.get_metadata(docid))
            except KeyError:
                meta = {}
            for utype in unread_types:
                meta['unread_%s' % utype.lower()] = user_unread.get_count(meta['uid'], utype)
            results.append(meta)
        #Sort meta
        ai_order = self.context.order
        def _sorter(meta):
            try:
                return ai_order.index(meta['__name__'])
            except (ValueError, KeyError):
                return len(ai_order)
        return sorted(results, key=_sorter)

    def in_current_context(self, context_path):
        if self.ai_path:
            path = self.ai_path.split('/')
            context_path = context_path.split('/')
            if len(path) > len(context_path):
                path = path[0:len(context_path)]
            return path == context_path


def includeme(config):
    config.add_view(AgendaInlineView,
                    name = '__agenda_items__',
                    context = IMeeting,
                    renderer = 'voteit.core:templates/portlets/agenda_inline.pt')
    config.add_portlet(AgendaPortlet)
