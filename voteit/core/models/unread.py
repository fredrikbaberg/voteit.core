from BTrees.Length import Length
from BTrees.OOBTree import OOBTree
from BTrees.OOBTree import OOSet
from arche.compat import IterableUserDict
from pyramid.location import lineage
from six import string_types

from voteit.core.models.interfaces import IAgendaItem
from voteit.core.models.interfaces import IMeeting


#Keep this during migrations. Remove 2018
class UserUnread(IterableUserDict):
    container_ifaces = (IAgendaItem,)
    counter_ifaces = (IMeeting,)

    def __init__(self, context):
        self.context = context
        self.data = getattr(context, '_unread', {})
        self.unread_counter = getattr(context, '_unread_counter', {})

    def __setitem__(self, key, value):
        if not isinstance(self.data, OOBTree):
            self.data = self.context._unread = OOBTree()
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]
        if key in self.unread_counter:
            del self.unread_counter[key]

    def _find_container(self, obj):
        for obj in lineage(obj):
            if self._is_container(obj):
                return obj

    def _is_container(self, obj):
        for iface in self.container_ifaces:
            if iface.providedBy(obj):
                return True

    def _is_counter_context(self, obj):
        for iface in self.counter_ifaces:
            if iface.providedBy(obj):
                return True

    def _find_counter(self, obj):
        for obj in lineage(obj):
            if self._is_counter_context(obj):
                return obj

    def add(self, context):
        container = self._find_container(context)
        assert container
        if container.uid not in self:
            self[container.uid] = OOBTree()
        if context.type_name not in self[container.uid]:
            type_uids = self[container.uid][context.type_name] = OOSet()
        else:
            type_uids = self[container.uid][context.type_name]
        if context.uid not in type_uids:
            type_uids.add(context.uid)
            #counter_context = self._find_counter(container)
            #self._update_counter(counter_context.uid, context.type_name, 1)
            return context

    def remove(self, context):
        container = self._find_container(context)
        assert container
        if container is context:
            return self.remove_container(container.uid)
        return self.remove_uids(container, [context.uid])

    def remove_container(self, container):
        """ Remove container and return all contained uids that were removed. """
        if isinstance(container, string_types):
            container_uid = container
        else:
            container_uid = container.uid
        removed = set()
        for curr in self.get(container_uid, {}).values():
            removed.update(curr)
        del self[container_uid]
        return removed

    def remove_uids(self, container, uids):
        removed = {}
        if isinstance(uids, string_types):
            uids = [uids]
        if isinstance(container, string_types):
            container_uid = container
        else:
            container_uid = container.uid
        for (type_name, curr) in self.get(container_uid, {}).items():
            for uid in uids:
                if uid in curr:
                    curr.remove(uid)
                    if type_name not in removed:
                        removed[type_name] = set()
                    removed[type_name].add(uid)
        #if removed:
        #    counter_context = self._find_counter(container)
        #    for (type_name, uids) in removed.items():
        #        self._update_counter(counter_context.uid, type_name, -len(uids))
        return removed

    def get_count(self, container_uid, type_name):
        return len(self.get(container_uid, {}).get(type_name, ()))

    def get_uids(self, container_uid, type_name):
        try:
            return frozenset(self[container_uid][type_name])
        except KeyError:
            return ()

    # def _update_counter(self, counter_uid, type_name, val):
    #     if not isinstance(self.unread_counter, OOBTree):
    #         self.unread_counter = self.context._unread_counter = OOBTree()
    #     if counter_uid not in self.unread_counter:
    #         self.unread_counter[counter_uid] = OOBTree()
    #     if type_name not in self.unread_counter[counter_uid]:
    #         self.unread_counter[counter_uid][type_name] = Length()
    #     self.unread_counter[counter_uid][type_name].change(val)

    def get_unread_count(self, counter_uid, type_name):
        try:
            return self.unread_counter[counter_uid][type_name]()
        except KeyError:
            return 0

    def __bool__(self):
        return True
    __nonzero__ = __bool__
