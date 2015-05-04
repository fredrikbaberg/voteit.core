""" Portlets that by default will be rendered within the Agenda Item view.
    They can be rearranged or disabled by changing them within the meeting context.
"""
from __future__ import unicode_literals
from decimal import Decimal
from copy import copy

from arche.portlets import PortletType
from arche.utils import generate_slug
from arche.views.base import BaseView
from arche.views.base import DefaultAddForm
from pyramid.renderers import render
from pyramid.response import Response
from pyramid.traversal import resource_path
from repoze.catalog.query import Eq, NotAny, Any

from voteit.core import _
from voteit.core import security
from voteit.core.fanstaticlib import agenda_item_js
from voteit.core.helpers import get_docids_to_show
from voteit.core.models.interfaces import IAgendaItem
from voteit.core.models.interfaces import IProposal

#FIXME: Loading required resources for inline forms is still a problem.


class ListingPortlet(PortletType):
    schema_factory = None

    def render(self, context, request, view, **kwargs):
        if IAgendaItem.providedBy(context):
            agenda_item_js.need()
            query = {}
            tags = request.GET.getall('tag')
            if tags:
                query['tag'] = [x.lower() for x in tags]
            url = request.resource_url(context, self.view_name, query = query)
            response = {'portlet': self.portlet, 'view': view, 'load_url': url}
            return render(self.template, response, request = request)


class ProposalsPortlet(ListingPortlet):
    name = "ai_proposals"
    title = _("Proposals")
    template = "voteit.core:templates/portlets/proposals.pt"
    view_name = 'ai_proposals.json'

    def render(self, context, request, view, **kwargs):
        if IAgendaItem.providedBy(context):
            agenda_item_js.need()
            query = {}
            tags = request.GET.getall('tag')
            if tags:
                query['tag'] = [x.lower() for x in tags]
            url = request.resource_url(context, self.view_name, query = query)
            ai_state_titles = request.get_wf_state_titles(IProposal, 'Proposal')
            hidden_state_titles = ", ".join([ai_state_titles.get(x, x) for x in request.meeting.hide_proposal_states])
            response = {'portlet':
                        self.portlet,
                        'view': view,
                        'hidden_state_titles': hidden_state_titles,
                        'load_url': url}
            return render(self.template, response, request = request)


class DiscussionsPortlet(ListingPortlet):
    name = "ai_discussions"
    title = _("Discussion")
    template = "voteit.core:templates/portlets/discussions.pt"
    view_name = 'ai_discussion_posts.json'


class PollsPortlet(ListingPortlet):
    name = "ai_polls"
    title = _("Polls")
    template = "voteit.core:templates/portlets/polls.pt"
    view_name = '__ai_polls__'


class PollsInline(BaseView):

    def __call__(self):
        query = {
            'path': resource_path(self.context),
            'type_name': 'Poll',
            'sort_index': 'created',}
        response = {}
        response['contents'] = tuple(self.catalog_search(resolve = True, **query))
        response['vote_perm'] = security.ADD_VOTE
        return response

    def get_poll_filter_url(self, poll):
        tags = set()
        for prop in poll.get_proposal_objects():
            tags.add(prop.aid)
        return self.request.resource_url(self.context, 'ai_filter.json', query = {'tag': tags})

    def get_voted_estimate(self, poll):
        """ Returns an approx guess without doing expensive calculations.
            This method should rely on other things later on.

            Should only be called during ongoing or closed polls.
        """
        response = {'added': len(poll), 'total': 0}
        wf_state = poll.get_workflow_state()
        if wf_state == 'ongoing':
            response['total'] = len(poll.voters_mark_ongoing)
        elif wf_state == 'closed':
            response['total'] = len(poll.voters_mark_closed)
        if response['total'] != 0:
            try:
                response['percentage'] = int(round(100 * Decimal(response['added']) / Decimal(response['total']), 0))
            except ZeroDivisionError:
                response['percentage'] = 0
        else:
            response['percentage'] = 0
        return response


class StrippedInlineAddForm(DefaultAddForm):
    title = None
    response_template = ""
    update_selector = ""

    def before(self, form):
        super(StrippedInlineAddForm, self).before(form)
        form.widget.template = 'voteit_form_inline'
        form.use_ajax = True

    def _response(self, *args, **kw):
        return Response(self.render_template(self.response_template, **kw))

    def save_success(self, appstruct):
        factory = self.get_content_factory(self.type_name)
        obj = factory(**appstruct)
        name = generate_slug(self.context, obj.uid)
        self.context[name] = obj
        return self._response(update_selector = self.update_selector)

    def cancel(self, *args):
        return self._response()

    cancel_success = cancel_failure = cancel


class ProposalAddForm(StrippedInlineAddForm):
    response_template = 'voteit.core:templates/portlets/inline_add_button_prop.pt'
    formid = 'proposal_inline_add'
    update_selector = '#ai-proposals'


class DiscussionAddForm(StrippedInlineAddForm):
    response_template = 'voteit.core:templates/portlets/inline_add_button_disc.pt'
    update_structure_tpl = 'voteit.core:templates/snippets/js_update_structure.pt'
    update_selector = '#ai-discussions'

    @property
    def formid(self):
        if self.reply_to:
            return "discussion_add_reply_to_%s" % self.reply_to
        return "discussion_inline_add"

    @property
    def reply_to(self):
        return self.request.GET.get('reply-to')

    @property
    def form_options(self):
        options = dict(super(DiscussionAddForm, self).form_options)
        if self.reply_to:
            options.update({'css_class': 'deform discussion-reply-to'})
        return options

    def save_success(self, appstruct):
        factory = self.get_content_factory(self.type_name)
        obj = factory(**appstruct)
        name = generate_slug(self.context, obj.uid)
        self.context[name] = obj
        if not self.reply_to:
            return self._response(update_selector = self.update_selector)
        return Response(self.render_template(self.update_structure_tpl,
                                             hide_popover = '[data-reply-to="%s"]' % self.reply_to,
                                             scroll_to = '#ai-discussions .list-group-item:last',
                                             load_target = "%s [data-load-target]" % self.update_selector))

    def cancel(self, *args):
        if not self.reply_to:
            return self._response()
        return Response(self.render_template(self.update_structure_tpl,
                                             hide_popover = '[data-reply-to="%s"]' % self.reply_to))
    cancel_success = cancel_failure = cancel


def includeme(config):
    config.add_portlet_slot('agenda_item', title = _("Agenda Item portlets"), layout = 'horizontal')
    config.add_portlet(ProposalsPortlet)
    config.add_portlet(DiscussionsPortlet)
    config.add_portlet(PollsPortlet)
    config.add_view(ProposalAddForm,
                    context = IAgendaItem,
                    name = 'add',
                    request_param = "content_type=Proposal",
                    permission = security.ADD_PROPOSAL,
                    renderer = 'arche:templates/form.pt')
    config.add_view(DiscussionAddForm,
                    context = IAgendaItem,
                    name = 'add',
                    request_param = "content_type=DiscussionPost",
                    permission = security.ADD_DISCUSSION_POST,
                    renderer = 'arche:templates/form.pt')
    config.add_view(PollsInline,
                    name = '__ai_polls__',
                    context = IAgendaItem,
                    permission = security.VIEW,
                    renderer = 'voteit.core:templates/portlets/polls_inline.pt')
