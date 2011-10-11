from datetime import timedelta
from datetime import datetime
import pytz

from pyramid.i18n import get_locale_name
from pyramid.threadlocal import get_current_request
from babel.dates import format_date
from babel.dates import format_time
from babel.dates import format_datetime
from zope.interface import implements

from voteit.core.models.interfaces import IDateTimeUtil
from voteit.core import VoteITMF as _


class DateTimeUtil(object):
    """ Handle conversion and printing of date and time.
        See IDateTimeUtil
    """
    implements(IDateTimeUtil)
    locale = None
    timezone_name = None

    def __init__(self, locale='en', timezone_name='Europe/Stockholm'):
        self.set_locale(locale)
        self.timezone = pytz.timezone(timezone_name)

    def set_locale(self, value):
        self.locale = value

    def d_format(self, value, format='short'):
        """ Format the given date in the given format.
            Will also convert to current timezone from utc.
        """
        localtime = self.utc_to_tz(value)
        return format_date(localtime, format=format, locale=self.locale)

    def t_format(self, value, format='short'):
        localtime = self.utc_to_tz(value)
        return format_time(localtime, format=format, locale=self.locale)
    
    def dt_format(self, value, format='short'):
        """ Format the given datetime in the given format.
            Will also convert to current timezone from utc.
        """
        localtime = self.utc_to_tz(value)
        return format_datetime(localtime, format=format, locale=self.locale)

    def tz_to_utc(self, datetime):
        """Convert the provided datetime object from local to UTC.

        The datetime object is expected to have the timezone specified in
        the timezone attribute.
        """
        utc = pytz.utc
        return datetime.astimezone(utc)

    def utc_to_tz(self, datetime):
        """Convert the provided datetime object from UTC to local.

        The resulting localized datetime object will have the timezone
        specified in the timezone attribute.
        """

        return self.timezone.normalize(datetime.astimezone(self.timezone))

    def localize(self, datetime, tz=None):
        """Localize a naive datetime to the provided timezone.

        If no timezone is provided, the current selected one is used.
        
        Example usage:
        from datetime.datetime import now
        #Regular python datetime:
        now_dt = now()
        #Converted to datetime that cares about a specific locale:
        self.localize(now_dt)
        """

        if tz is None:
            tz = self.timezone

        return tz.localize(datetime)

    def localnow(self, tz=None):
        """Get the current datetime localized to the specified timezone.
        If no timezone is specified, the current selected one is used.
        """
        naive_now = datetime.now()

        if tz is None:
            tz = self.timezone

        return self.localize(naive_now, tz)

    def utcnow(self):
        return utcnow()

    def relative_time_format(self, time):
        """ Get a datetime object or a int() Epoch timestamp and return a
            pretty string like 'an hour ago', 'Yesterday', '3 months ago',
            'just now', etc
        """
        time = self.tz_to_utc(time)
        now = self.utcnow()
        if type(time) is int:
            diff = now - datetime.fromtimestamp(time)
        elif isinstance(time, datetime):
            diff = now - time 
        elif not time:
            diff = now - now #Haha :)
        second_diff = diff.seconds
        day_diff = diff.days

        if day_diff < 0:
            return ''

        if day_diff == 0:
            if second_diff < 10:
                return _("Just now")
            if second_diff < 60:
                return _("${diff} seconds ago", mapping={'diff': str(second_diff)})
            if second_diff < 120:
                return  _("1 minute ago")
            if second_diff < 3600:
                return _("${diff} minutes ago", mapping={'diff': str(second_diff / 60)})
            if second_diff < 7200:
                return _("1 hour ago")
            if second_diff < 86400:
                return _("${diff} hours ago", mapping={'diff': str(second_diff / 3600)})

        #If it's longer than 7 days, just run the regular localization
        return self.dt_format(time)


def utcnow():
    """Get the current datetime localized to UTC.

    The difference between this method and datetime.utcnow() is
    that datetime.utcnow() returns the current UTC time but as a naive
    datetime object, whereas this one includes the UTC tz info."""

    naive_utcnow = datetime.utcnow()
    return pytz.utc.localize(naive_utcnow)


def includeme(config):
    locale = config.registry.settings['default_locale_name']
    timezone_name = config.registry.settings['default_timezone_name']
    util = DateTimeUtil(locale, timezone_name)
    config.registry.registerUtility(util, IDateTimeUtil)
