# -*- coding:utf-8 -*-

from betahaus.viewcomponent import view_action
from pyramid.traversal import resource_path
from pyramid.traversal import find_resource
from pyramid.renderers import render

from voteit.core import VoteITMF as _
from voteit.core.security import DELETE

from voteit.core.htmltruncate import htmltruncate

def truncate(text, length=200):
    trunc_text = htmltruncate.truncate(text, length, u'…')
    
    return (trunc_text, text != trunc_text)

@view_action('discussions', 'listing')
def discussions_listing(context, request, va, **kw):
    """ Get discussions for a specific context """
    api = kw['api']

    def _show_delete(brain):
        #Do more expensive checks last!
        if not api.userid in brain['creators']:
            return
        obj = find_resource(api.root, brain['path'])
        return api.context_has_permission(DELETE, obj)

    path = resource_path(context)

    if request.GET.get('discussions', '') == 'all':
        limit = 0
    else:
        unread_count = api.search_catalog(path = path, content_type = 'DiscussionPost', unread = api.userid)[0]
        limit = 5
        if unread_count > limit:
            limit = unread_count

    query = dict(path = path,
                 content_type='DiscussionPost')
    #Returns tuple of (item count, iterator with docids)
    count = api.search_catalog(**query)[0]

    #New query with only limited number of results
    query['sort_index'] = 'created'
    query['reverse'] = True
    if limit:
        query['limit'] = limit
    docids = api.search_catalog(**query)[1]
    get_metadata = api.root.catalog.document_map.get_metadata
    results = []
    for docid in docids:
        #Insert the resolved docid first, since we need to reverse order again.
        results.insert(0, get_metadata(docid))
    response = {}
    response['discussions'] = tuple(results)
    if limit and limit < count:
        response['over_limit'] = count - limit
    else:
        response['over_limit'] = 0
    response['limit'] = limit
    response['api'] = api
    response['show_delete'] = _show_delete
    response['truncate'] = truncate 
    return render('../templates/discussions.pt', response, request = request)
