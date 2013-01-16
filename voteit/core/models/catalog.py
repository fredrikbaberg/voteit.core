from calendar import timegm

from repoze.catalog.indexes.field import CatalogFieldIndex
from repoze.catalog.indexes.keyword import CatalogKeywordIndex
from repoze.catalog.indexes.path import CatalogPathIndex
from repoze.catalog.indexes.text import CatalogTextIndex
from zope.interface import implements
from zope.component import adapts
from zope.component import getAdapter
from zope.component import queryAdapter
from zope.component.interfaces import ComponentLookupError
from pyramid.traversal import find_resource
from pyramid.traversal import find_root
from pyramid.traversal import resource_path
from pyramid.security import principals_allowed_by_permission

from voteit.core.models.interfaces import IAgendaItem
from voteit.core.models.interfaces import IMeeting
from voteit.core.models.interfaces import IUserTags
from voteit.core.models.interfaces import ICatalogMetadataEnabled
from voteit.core.models.interfaces import ISecurityAware
from voteit.core.models.interfaces import IWorkflowAware
from voteit.core.models.interfaces import ICatalogMetadata
from voteit.core.models.interfaces import IUnread
from voteit.core.models.interfaces import IDiscussionPost
from voteit.core.models.interfaces import IPoll
from voteit.core.models.interfaces import IProposal
from voteit.core.security import NEVER_EVER_PRINCIPAL
from voteit.core.security import VIEW
from voteit.core.security import find_authorized_userids


SEARCHABLE_TEXT_INDEXES = ('title',
                           'description',)


class CatalogMetadata(object):
    """ An adapter to fetch metadata for the catalog.
        See :mod:`voteit.core.models.interfaces.ICatalogMetadata`.
    """
    #FIXME: Each metadata should be its own adapter instead
    #otherwise we can't make this pluggable
    #Refactor!
    implements(ICatalogMetadata)
    adapts(ICatalogMetadataEnabled)
    special_indexes = {IAgendaItem:'get_agenda_item_specific',
                       IWorkflowAware:'get_workflow_specific',
                       IPoll:'get_poll_specific',
                       IProposal: 'get_proposal_specific'}
    
    def __init__(self, context):
        self.context = context

    def __call__(self):
        """ Return a dict of metadata values for an object. """
        results = {
            'name': self.context.__name__,
            'title': get_title(self.context, None),
            'created': self.context.created, #Exception, since the get_created method returns unixtime
            'creators': get_creators(self.context, ()),
            'path': get_path(self.context, None),
            'content_type': get_content_type(self.context, None),
            'workflow_state': get_workflow_state(self.context, None),
            'uid': get_uid(self.context, None),
            'like_userids': get_like_userids(self.context, ()),
            'tags': get_tags(self.context, ()),
        }

        #Use special metadata?
        for (iface, method_name) in self.special_indexes.items():
            if iface.providedBy(self.context):
                method = getattr(self, method_name)
                method(results)

        return results

    def get_agenda_item_specific(self, results):
        """ Specific for Agenda items. """
        results['discussion_count'] = len(self.context.get_content(content_type='Discussion'))
        results['poll_count'] = len(self.context.get_content(content_type='Poll'))
        results['proposal_count'] = len(self.context.get_content(content_type='Proposal'))
        results['order'] = get_order(self.context, 0)

    def get_workflow_specific(self, results):
        """ Specific for workflow aware items. """
        results['workflow_state'] = get_workflow_state(self.context, None)

    def get_poll_specific(self, results):
        """ Specific for polls. """
        results['voted_userids'] = get_voted_userids(self.context, ())

    def get_proposal_specific(self, results):
        results['aid'] = get_aid(self.context, u'')
        results['aid_int'] = get_aid_int(self.context, 0)

def update_indexes(catalog, reindex=True):
    """ Add or remove indexes. If reindex is True, also reindex all content if
        an index has been added or removed.
        Will return a set of indexes changed regardless.
    """
    
    indexes = {
        'title': CatalogFieldIndex(get_title),
        'sortable_title': CatalogFieldIndex(get_sortable_title),
        'description': CatalogFieldIndex(get_description),
        'uid': CatalogFieldIndex(get_uid),
        'aid': CatalogFieldIndex(get_aid),
        'aid_int': CatalogFieldIndex(get_aid_int),
        'content_type': CatalogFieldIndex(get_content_type),
        'workflow_state': CatalogFieldIndex(get_workflow_state),
        'path': CatalogPathIndex(get_path),
        'creators': CatalogKeywordIndex(get_creators),
        'created': CatalogFieldIndex(get_created),
        'allowed_to_view': CatalogKeywordIndex(get_allowed_to_view),
        'view_meeting_userids': CatalogKeywordIndex(get_view_meeting_userids),
        'searchable_text' : CatalogTextIndex(get_searchable_text),
        'start_time' : CatalogFieldIndex(get_start_time),
        'end_time' : CatalogFieldIndex(get_end_time),
        'unread': CatalogKeywordIndex(get_unread),
        'like_userids': CatalogKeywordIndex(get_like_userids),
        'voted_userids': CatalogKeywordIndex(get_voted_userids),
        'order': CatalogFieldIndex(get_order),
        'tags': CatalogKeywordIndex(get_tags),
    }
    
    changed_indexes = set()
    
    # remove indexes
    for name in catalog.keys():
        if name not in indexes:
            del catalog[name]            

    # add indexes
    for name, index in indexes.iteritems():
        if name not in catalog:
            catalog[name] = index
            if reindex:
                changed_indexes.add(name)
    
    if reindex:
        reindex_indexes(catalog)

    return changed_indexes


def reindex_indexes(catalog):
    """ Warning! This will only update things that already are in the catalog! """
    root = find_root(catalog)
    for path, docid in catalog.document_map.address_to_docid.items():

        obj = find_resource(root, path)
        reindex_object(catalog, obj)
        

def index_object(catalog, obj):
    """ Index an object and add metadata. """
    #Check if object already exists
    if catalog.document_map.docid_for_address(resource_path(obj)) is not None:
        reindex_object(catalog, obj)
        return

    obj_id = catalog.document_map.add(resource_path(obj))
    catalog.index_doc(obj_id, obj)
    
    #Add metadata
    if ICatalogMetadataEnabled.providedBy(obj):
        metadata = getAdapter(obj, ICatalogMetadata)()
        metadata['docid'] = obj_id
        catalog.document_map.add_metadata(obj_id, metadata)


def reindex_object(catalog, obj, indexes = (), metadata = True):
    """ Reindex an object and update metadata.
        It's possible to not update metadata and to only update some indexes.
    """
    obj_id = catalog.document_map.docid_for_address(resource_path(obj))
    if obj_id is None:
        #This is a special case when an object that isn't indexed tries to be reindexed
        #Note that indexes and metadata parameter is ignored in that case
        index_object(catalog, obj) #Do reindex instead
        return

    if not indexes:
        catalog.reindex_doc(obj_id, obj)
    else:
        for index in indexes:
            catalog[index].reindex_doc(obj_id, obj)

    #Add metadata
    if metadata and ICatalogMetadataEnabled.providedBy(obj):
        metadata = getAdapter(obj, ICatalogMetadata)()
        metadata['docid'] = obj_id
        catalog.document_map.add_metadata(obj_id, metadata)


def unindex_object(catalog, obj):
    """ Remove an index and its metadata. """
    obj_id = catalog.document_map.docid_for_address(resource_path(obj))
    catalog.unindex_doc(obj_id)

    #Remove metadata
    if ICatalogMetadataEnabled.providedBy(obj):
        catalog.document_map.remove_metadata(obj_id)


def reindex_object_security(catalog, obj):
    """ Update security information in the catalog.
        Will update all contained objects as well.
    """
    reindex_object(catalog, obj)
    #Recurse
    #FIXME: We may want to only touch the security related index here, and no metadata.
    for contained in obj.values():
        if ISecurityAware.providedBy(contained):
            reindex_object_security(catalog, contained)

def resolve_catalog_docid(catalog, root, docid):
    """ Takes a catalog docid and returns object that was indexed.
        This method should only be used when it's really necessary to have the object,
        since it will make it slower to retrieve objects.
    """
    path = catalog.document_map.address_for_docid(docid)
    if path is None:
        return ValueError("Nothing found in catalog with docid '%s'" % docid) # pragma : no cover
    return find_resource(root, path)

def metadata_for_query(catalog, **kwargs):
    """ Get metadata objects and return them. Shorthand for looking up
        metadata from a query result.
    """
    num, docids = catalog.search(**kwargs)
    metadata = [catalog.document_map.get_metadata(x) for x in docids]
    return tuple(metadata)


#Indexes
def get_title(object, default):
    """ Return objects title. """
    return object.title

def get_sortable_title(object, default):
    """ Sortable title is a lowercased version of the title. """
    title = object.title
    if not title:
        return default
    return object.title.lower()

def get_description(object, default):
    """ Objects description. """
    return object.description

def get_uid(object, default):
    """ Objects unique id. """
    return object.uid

def get_aid(object, default):
    """ Objects automatic id. """
    if IProposal.providedBy(object):
        return object.get_field_value('aid', default)
    return default

def get_aid_int(object, default):
    if IProposal.providedBy(object):
        return object.get_field_value('aid_int', default)
    return default

def get_content_type(object, default):
    """ Objects content_type name. """
    return object.content_type

def get_workflow_state(object, default):
    """ Return workflow state, if this object has workflow enabled. """
    if not IWorkflowAware.providedBy(object):
        return default
    return object.get_workflow_state()

def get_path(object, default):
    """ Physical path of object. """
    return resource_path(object)

def get_creators(object, default):
    """ Return a tuple of all the objects creators. """
    if object.creators:
        return tuple(object.creators)
    return default

def get_created(object, default):
    """ The created time is stored in the catalog as unixtime.
        See the time.gmtime and calendar.timegm Python modules for more info.
        http://docs.python.org/library/calendar.html#calendar.timegm
        http://docs.python.org/library/time.html#time.gmtime
    """
    return timegm(object.created.timetuple())

def get_allowed_to_view(object, default):
    """ Return a list of all roles allowed to view this object. """
    principals = principals_allowed_by_permission(object, VIEW)
    if not principals:
        # An empty value tells the catalog to match anything, whereas when
        # there are no principals with permission to view we want for there
        # to be no matches.
        principals = [NEVER_EVER_PRINCIPAL,]
    return principals

def get_view_meeting_userids(object, default):
    """ Userids that are allowed to view a meeting. Only index meeting contexts. """
    if not IMeeting.providedBy(object):
        return default
    try:
        userids = find_authorized_userids(object, [VIEW])
        return userids and userids or default
    except ComponentLookupError: # pragma : no cover
        #This is to avoid having security fixture for each catalog test.
        return default

def get_searchable_text(object, default):
    """ Searchable text is basically all textfields that should be
        searchable appended to each other.
    """
    text = u''
    for index in SEARCHABLE_TEXT_INDEXES:
        res = getattr(object, index, None)
        if res:
            text += u' %s' % res
    text = text.strip()
    return text and text or default

def get_start_time(object, default):
    """ UNIX timestamp from start_time. """
    value = object.get_field_value('start_time', default)
    if value and value != default:
        return timegm(value.timetuple())
    return default

def get_end_time(object, default):
    """ UNIX timestamp from end_time. """
    value = object.get_field_value('end_time', default)
    if value and value != default:
        return timegm(value.timetuple())
    return default

def get_unread(object, default):
    """ All userids who have this object as unread. """
    unread = queryAdapter(object, IUnread)
    if not unread:
        return default
    userids = unread.get_unread_userids()
    if userids:
        return userids
    return default

def get_like_userids(object, default):
    """ Returns all userids who 'like' something.
        We only use like for Discussions and Proposals.
        Warning! An empty list doesn't update the catalog.
        If default is returned to an index, it will cause that index to remove index,
        which is the correct behaviour for the catalog.
    """
    if IDiscussionPost.providedBy(object) or IProposal.providedBy(object):
        user_tags = getAdapter(object, IUserTags)
        likes = user_tags.userids_for_tag('like')
        if likes:
            return likes
        
    return default
    
def get_voted_userids(object, default):
    """ Returns all userids who voted in a poll.
        Warning! An empty list doesn't update the catalog.
        If default is returned to an index, it will cause that index to remove index,
        which is the correct behaviour for the catalog.
    """
    if not IPoll.providedBy(object):
        return default
    voted_userids = object.get_voted_userids()
    return voted_userids and voted_userids or default

def get_order(object, default):
    """ Return order, if object has that field. """
    return object.get_field_value('order', default)

def get_tags(object, default):
    """ We only use tags for Discussions and Proposals.
        Warning! An empty list doesn't update the catalog.
        If default is returned to an index, it will cause that index to remove index,
        which is the correct behaviour for the catalog.
    """
    if IDiscussionPost.providedBy(object) or IProposal.providedBy(object):
        return tuple(object.get_tags(default))
    return default


def includeme(config):
    """ Register metadata adapter. """
    config.registry.registerAdapter(CatalogMetadata, (ICatalogMetadataEnabled,), ICatalogMetadata)

