import unittest

from pyramid import testing
from zope.interface.verify import verifyObject
import transaction

from voteit.core.testing import testing_sql_session


class MessagesTests(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        self.session = testing_sql_session(self.config)
        self.config.include('pyramid_zcml')
        self.config.load_zcml('voteit.core:configure.zcml')        

    def tearDown(self):
        testing.tearDown()
        transaction.abort() #To cancel any commit to the sql db

    def _import_class(self):
        from voteit.core.models.message import Messages
        return Messages

    def _add_mock_data(self, obj):
        data = (
            ('m1', 'test', 'alert', None, None,),
            ('m1', 'test', 'log', 'm1', None,),
            ('m1', 'test', 'like', 'p1', 'robin',),
            ('m1', 'test', 'alert', 'v1', 'robin',),
            ('m1', 'test', 'log', 'p1', None,),
            ('m1', 'test', 'log', 'v1', None,),
         )
        for (meetinguid, message, tag, contextuid, userid) in data:
            obj.add(meetinguid, message, tag, contextuid, userid)

    def test_verify_obj_implementation(self):
        from voteit.core.models.interfaces import IMessages
        obj = self._import_class()(self.session)
        self.assertTrue(verifyObject(IMessages, obj))

    def test_add(self):
        obj = self._import_class()(self.session)
        meetinguid = 'a1'
        message = 'aa-bb'
        tags = 'log'
        contextuid = 'a1'
        userid = 'robin'
        obj.add(meetinguid, message, tags, contextuid, userid)

        from voteit.core.models.message import Message
        query = self.session.query(Message).filter_by(userid=userid)

        self.assertEqual(len(query.all()), 1)
        result_obj = query.all()[0]
        self.assertEqual(result_obj.userid, userid)
        self.assertEqual(result_obj.meetinguid, meetinguid)
        self.assertEqual(result_obj.message, message)
        #FIXME: thid doesn't work
        #self.assertEqual(result_obj.tags, tags)

    def test_retrieve_user_messages(self):
        obj = self._import_class()(self.session)
        self._add_mock_data(obj)

        self.assertEqual(len(obj.retrieve_messages('m1', contextuid='v1')), 2)
        
    def test_mark_read(self):
        obj = self._import_class()(self.session)
        meetinguid = 'a1'
        message = 'aa-bb'
        tags = 'log'
        contextuid = 'a1'
        userid = 'robin'
        obj.add(meetinguid, message, tags, contextuid, userid)
        
        from voteit.core.models.message import Message
        # to get the id of the message
        msg = self.session.query(Message).filter(Message.userid==userid).first()

        obj.mark_read(msg.id, userid)

        query = self.session.query(Message).filter(Message.id==msg.id).filter(Message.userid==userid)
        self.assertEqual(len(query.all()), 1)
        result_obj = query.all()[0]
        self.assertEqual(result_obj.id, msg.id)
        self.assertEqual(result_obj.userid, userid)
        self.assertEqual(result_obj.unread, False)

