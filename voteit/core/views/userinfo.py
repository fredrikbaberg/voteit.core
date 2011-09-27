from pyramid.security import authenticated_userid, has_permission
from pyramid.exceptions import Forbidden
from pyramid.httpexceptions import HTTPFound
from pyramid.renderers import render
from pyramid.traversal import find_root
from pyramid.view import view_config
from webhelpers.html.converters import nl2br

from voteit.core import VoteITMF as _
from voteit.core.models.interfaces import IMeeting
from voteit.core.security import find_authorized_userids
from voteit.core.security import VIEW


USERINFO_TPL = 'templates/snippets/userinfo.pt'


@view_config(context=IMeeting, name="_userinfo", permission=VIEW, renderer=USERINFO_TPL)
def user_info(context, request):
    """ Special view to allow other meeting participants to see information about a user
        who's in the same meeting as them.
    """


    userid = authenticated_userid(request)
    if not userid:
        raise Forbidden("You're not allowed to access this view.")
    
    info_userid = request.GET.get('userid', None)
    if info_userid is None:
        raise ValueError("No userid specified")
    
    #Check if requested userid has permission in meeting
    if info_userid in find_authorized_userids(context, (VIEW,)):
        #User is allowed here, so do lookup
        root = find_root(context)
        user = root.users.get(info_userid)
    else:
        user = None

    response = {}
    response['user'] = user
    response['info_userid'] = info_userid
    response['nl2br'] = nl2br
    return response
