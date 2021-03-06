from zope.interface import implements
from zope.component import adapts
from pyramid.response import Response

from voteit.core.models.interfaces import IPoll
from voteit.core.models.interfaces import IPollPlugin
from voteit.core.models.vote import Vote


class PollPlugin(object):
    """ Base class for poll plugins. Subclass this to make your own.
        It's not usable by itself, since it doesn't implement the required interfaces.
        See :mod:`voteit.core.models.interfaces.IPollPlugin` for documentation.
    """
    implements(IPollPlugin)
    adapts(IPoll)
    name = 'BasePollPlugin'
    title = 'BasePollPlugin'
    description = 'Subclass this to make a usable PollPlugin'

    # Use this to determine if poll is applicable
    multiple_winners = False
    # Position in listing, lower number is better
    priority = 3
    proposals_min = 1
    proposals_max = None

    # Default: Check min/max proposals and if multiple winners is needed.
    @classmethod
    def check_applicable(cls, proposals=None, winners=1, random_timebreaks=True):
        # type: (int, int, bool) -> bool
        if proposals is not None:
            if cls.proposals_min and cls.proposals_min > proposals:
                return False
            if cls.proposals_max and proposals > cls.proposals_max:
                return False
        if winners > 1 and not cls.multiple_winners:
            return False
        return True

    def __init__(self, context):
        self.context = context

    def get_vote_schema(self):
        """ Return the schema of how a vote should be structured.
            This is used to render a voting form.
        """
        raise NotImplementedError("Must be provided by subclass") # pragma : no cover
    
    def get_vote_class(self):
        """ Get the vote class to use for this poll. Normally it's the
            voteit.core.models.vote.Vote class.
        """
        return Vote # pragma : no cover

    def get_settings_schema(self):
        """ Get an instance of the schema used to render a form for editing settings.
            If this is None, this poll method doesn't have any settings.
        """
        return None # pragma : no cover

    def handle_close(self):
        """ Handle closing of the poll.
        """
        raise NotImplementedError("Must be provided by subclass") # pragma : no cover

    def render_result(self, view):
        """ Return rendered html with result display. Called by the poll view
            when the poll has finished.
        """
        raise NotImplementedError("Must be provided by subclass") # pragma : no cover

    def change_states_of(self):
        """ This gets called when a poll has finished.
            It returns a dictionary with proposal uid as key and new state as value.
            Like: {'<uid>':'approved', '<uid>', 'denied'}
            It's not required to do, but if it isn't done, the proposals won't change state
            and you have to do it manually.
            It's not required to return anything.
        """
        return {} # pragma : no cover

    def render_raw_data(self):
        """ Return rendered html with raw data from this poll.
            It should consist of ballot information.
            It can either be anonymous, or actually show the userids of the ones
            that voted. That's just a matter of taste.
            The point with this view is to enable others to run
            a poll to verify the result.
            
            The method needs to return an instance of either:
            - pyramid.renderers.render
            - pyramid.response.Response
        """
        return Response(unicode(self.context.ballots))
