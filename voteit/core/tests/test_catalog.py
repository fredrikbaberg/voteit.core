import unittest
from datetime import datetime

from pyramid import testing
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.security import remember, principals_allowed_by_permission
from zope.interface.verify import verifyObject
from zope.component.event import objectEventNotify

from voteit.core.app import register_content_types
from voteit.core.app import register_catalog_metadata_adapter
from voteit.core.bootstrap import bootstrap_voteit
from voteit.core.models.interfaces import IContentUtility
from voteit.core.interfaces import IObjectUpdatedEvent
from voteit.core.events import ObjectUpdatedEvent
from voteit.core.testing import testing_sql_session
from voteit.core import security
from voteit.core.security import groupfinder


authn_policy = AuthTktAuthenticationPolicy(secret='sosecret',
                                           callback=groupfinder)
authz_policy = ACLAuthorizationPolicy()


class CatalogTestCase(unittest.TestCase):
    """ Class for registering test setup and some helper methods.
        This doesn't actually run any tests.
    """
    def setUp(self):
        self.config = testing.setUp()
        ct = """
    voteit.core.models.meeting
    voteit.core.models.site
    voteit.core.models.user
    voteit.core.models.users
        """
        self.config.registry.settings['content_types'] = ct
        register_content_types(self.config)
        register_catalog_metadata_adapter(self.config)

        testing_sql_session(self.config) #To register session utility   
        self.config.scan('voteit.core.subscribers.catalog')

        self.root = bootstrap_voteit(registry=self.config.registry, echo=False)
        self.query = self.root.catalog.query
        self.get_metadata = self.root.catalog.document_map.get_metadata
        self.content_types = self.config.registry.getUtility(IContentUtility)
        self.config.include('pyramid_zcml')
        self.config.load_zcml('voteit.core:configure.zcml')

    def tearDown(self):
        testing.tearDown()

    def _add_mock_meeting(self):
        obj = self.content_types['Meeting'].type_class()
        obj.title = 'Testing catalog'
        obj.uid = 'simple_uid'
        obj.creators = ['demo_userid']
        obj.add_groups('demo_userid', (security.ROLE_OWNER,))
        obj.add_groups('admin', (security.ROLE_ADMIN, security.ROLE_MODERATOR,))
        self.root['meeting'] = obj
        return obj


class CatalogTests(CatalogTestCase):
    def test_indexed_on_add(self):
        title_index = self.root.catalog['title']
        title_count = title_index.documentCount()
        meeting = self.content_types['Meeting'].type_class()
        meeting.title = 'hello world'
        
        self.root['meeting'] = meeting
        
        self.assertEqual(title_index.documentCount(), title_count + 1)

    def test_unindexed_on_remove(self):
        title_index = self.root.catalog['title']
        title_count = title_index.documentCount()

        meeting = self.content_types['Meeting'].type_class()
        meeting.title = 'hello world'
        
        self.root['meeting'] = meeting
        
        self.assertEqual(title_index.documentCount(), title_count + 1)
        
        del self.root['meeting']
        self.assertEqual(title_index.documentCount(), title_count)
        
    def test_reindexed_on_update(self):
        meeting = self.content_types['Meeting'].type_class()
        meeting.title = 'hello world'
        self.root['meeting'] = meeting
        
        query = self.query
        self.assertEqual(query("title == 'hello world'")[0], 1)
        
        self.root['meeting'].title = 'me and my little friends'
        #We'll have to kick the subscriber manually
        objectEventNotify(ObjectUpdatedEvent(self.root['meeting']))
        
        self.assertEqual(query("title == 'hello world'")[0], 0)
        self.assertEqual(query("title == 'me and my little friends'")[0], 1)

    def test_update_indexes_when_index_removed(self):
        meeting = self.content_types['Meeting'].type_class()
        meeting.title = 'hello world'
        self.root['meeting'] = meeting
        
        catalog = self.root.catalog
        catalog['nonexistent_index'] = catalog['title'] #Nonexistent should be removed
        del catalog['title'] #Removing title index should recreate it
        
        self.failUnless(catalog.get('nonexistent_index'))
        
        from voteit.core.models.catalog import update_indexes
        update_indexes(catalog, reindex=False)
        
        self.failIf(catalog.get('nonexistent_index'))
        self.failUnless(catalog.get('title'))
    
    def test_reindex_indexes(self):
        meeting = self.content_types['Meeting'].type_class()
        meeting.title = 'hello world'
        self.root['meeting'] = meeting
        catalog = self.root.catalog
        
        #Catalog should return the meeting on a search
        self.assertEqual(self.query("title == 'hello world'")[0], 1)
        
        #If the meeting title changes, no subscriber will be fired here...
        meeting.title = "Goodbye cruel world"
        #...but when reindexed it should work
        from voteit.core.models.catalog import reindex_indexes
        reindex_indexes(catalog)
        
        self.assertEqual(self.query("title == 'Goodbye cruel world'")[0], 1)

    def test_reindex_object_security(self):
        from voteit.core.models.catalog import reindex_object_security
        
        self.config.setup_registry(authentication_policy=authn_policy,
                                   authorization_policy=authz_policy)
        
        catalog = self.root.catalog
        obj = self._add_mock_meeting()
        
        #Owners are not allowed to view meetings. It's exclusive for Admins / Moderators right now
        self.assertEqual(self.query("allowed_to_view in any('role:Admin',) and path == '/meeting'")[0], 1)
        self.assertEqual(self.query("allowed_to_view in any('role:Participant',) and path == '/meeting'")[0], 0)        
        self.assertEqual(self.query("allowed_to_view in any('role:Viewer',) and path == '/meeting'")[0], 0)        
        
        self.config.testing_securitypolicy(userid='some_user',
                                           permissive=True)
        request = testing.DummyRequest()
        obj.set_workflow_state(request, 'inactive')
        
        self.config.setup_registry(authentication_policy=authn_policy,
                                   authorization_policy=authz_policy)
        reindex_object_security(catalog, obj)

        self.assertEqual(self.query("allowed_to_view in any('role:Participant',) and path == '/meeting'")[0], 1)        
        self.assertEqual(self.query("allowed_to_view in any('role:Viewer',) and path == '/meeting'")[0], 1)        


class CatalogIndexTests(CatalogTestCase):
    """ Make sure indexes work as expected. """

    def test_title(self):
        self._add_mock_meeting()
        self.assertEqual(self.query("title == 'Testing catalog'")[0], 1)
    
    def test_sortable_title(self):
        self._add_mock_meeting()
        self.assertEqual(self.query("sortable_title == 'testing catalog'")[0], 1)

    def test_uid(self):
        self._add_mock_meeting()
        self.assertEqual(self.query("uid == 'simple_uid'")[0], 1)

    def test_content_type(self):
        self._add_mock_meeting()
        self.assertEqual(self.query("content_type == 'Meeting'")[0], 1)

    def test_workflow_state(self):
        self._add_mock_meeting()
        self.assertEqual(self.query("workflow_state == 'private'")[0], 1)

    def test_path(self):
        self._add_mock_meeting()
        self.assertEqual(self.query("path == '/meeting'")[0], 1)

    def test_creators(self):
        self._add_mock_meeting()
        self.assertEqual(self.query("creators in any('demo_userid',)")[0], 1)

    def test_created(self):
        """ created actually stores unix-time. Note that it's very
            likely that all objects are added within the same second.
        """
        obj = self._add_mock_meeting()
        from datetime import datetime
        from calendar import timegm
        meeting_unix = timegm(obj.created.timetuple())
        
        self.assertEqual(self.query("created == %s and path == '/meeting'" % meeting_unix)[0], 1)
        qy = ("%s < created < %s and path == '/meeting'" % (meeting_unix-1, meeting_unix+1))
        self.assertEqual(self.query(qy)[0], 1)

    def test_allowed_to_view(self):
        self.config.setup_registry(authentication_policy=authn_policy,
                                   authorization_policy=authz_policy)
        obj = self._add_mock_meeting()
        
        #Owners are not allowed to view meetings. It's exclusive for Admins / Moderators right now
        self.assertEqual(self.query("allowed_to_view in any('role:Owner',) and path == '/meeting'")[0], 0)
        self.assertEqual(self.query("allowed_to_view in any('role:Admin',) and path == '/meeting'")[0], 1)
        self.assertEqual(self.query("allowed_to_view in any('role:Moderator',) and path == '/meeting'")[0], 1)


class CatalogMetadataTests(CatalogTestCase):
    """ Test metadata creation. This test also covers catalog subscribers.
    """
    
    def test_title(self):
        self._add_mock_meeting()
        result = self.query("title == 'Testing catalog'")
        doc_id = result[1][0] #Layout is something like: (1, set([123]))
        metadata = self.get_metadata(doc_id)
        
        self.assertTrue('title' in metadata)
        self.assertEqual(metadata['title'], 'Testing catalog')        
        
    def test_created(self):
        """ created actually stores unix-time. Note that it's very
            likely that all objects are added within the same second.
            The metadata is regular datetime though.
        """
        obj = self._add_mock_meeting()
        result = self.query("title == 'Testing catalog'")
        doc_id = result[1][0]
        metadata = self.get_metadata(doc_id)
        
        self.assertEqual(obj.created, metadata['created'])
        self.assertTrue(isinstance(metadata['created'], datetime))
