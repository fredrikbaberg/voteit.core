from betahaus.viewcomponent import view_action
from pyramid.renderers import render
from pyramid.traversal import find_interface

from voteit.core.models.interfaces import IInviteTicket
from voteit.core.models.interfaces import IMeeting
from voteit.core.models.interfaces import IUser


@view_action('email', 'request_password', interface = IUser)
def request_password_body(context, request, va, **kw):
    """ Body for request password email """
    response = dict(
        pw_link = kw['pw_link'],
        context = context,
    )
    return render('../templates/email/request_password.pt', response, request = request)

@view_action('email', 'invite_ticket', interface = IInviteTicket)
def invite_ticket(context, request, va, **kw):
    """ Render invite ticket email html.
        Uses ticket as a context.
    """
    meeting = find_interface(context, IMeeting)
    response = {}
    form_url = "%sticket" % request.resource_url(meeting)
    response['access_link'] = form_url + '?email=%s&token=%s' % (context.email, context.token)
    response['message'] = context.message
    return render('../templates/email/invite_ticket_email.pt', response, request = request)
