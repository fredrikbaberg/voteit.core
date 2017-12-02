# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from difflib import SequenceMatcher
import re

import colander
from BTrees.OOBTree import OOBTree
from arche.interfaces import IObjectUpdatedEvent
from arche.portlets import get_portlet_manager
from pyramid.decorator import reify
from zope.component import adapter
from zope.interface import implementer

from voteit.core.models.interfaces import IAgendaItem
from voteit.core.models.interfaces import IDiffText
from voteit.core.models.interfaces import IMeeting


@adapter(IAgendaItem)
@implementer(IDiffText)
class DiffText(object):

    def __init__(self, context):
        self.context = context

    @reify
    def data(self):
        try:
            return self.context._diff_text_data
        except AttributeError:
            self.context._diff_text_data = OOBTree()
            return self.context._diff_text_data

    @property
    def title(self):
        return self.data.get('title', '')
    @title.setter
    def title(self, value):
        self.data['title'] = value

    @property
    def text(self):
        return self.data.get('text', '')
    @text.setter
    def text(self, value):
        self.data['text'] = value

    @property
    def hashtag(self):
        return self.data.get('hashtag', '')
    @hashtag.setter
    def hashtag(self, value):
        self.data['hashtag'] = value

    def __call__(self, base_text, new_text, brief=False, no_deleted=False):
        ch = Changes(base_text, new_text)
        return ch.get_html(brief, no_deleted)

    def set_appstruct(self, appstruct):
        for (k, v) in appstruct.items():
            assert hasattr(self, k), "No such attribute: %s" % k
            setattr(self, k, v)

    def get_appstruct(self, schema):
        appstruct = {}
        for field in schema.children:
            if hasattr(self, field.name):
                val = getattr(self, field.name)
                if val in (None, ''):
                    val = colander.null
                appstruct[field.name] = val
        return appstruct

    def get_paragraphs(self):
        """ Split text into paragraphs. """
        output = []
        new_para = True
        for row in self.text.splitlines():
            row = row.strip()
            if row:
                if new_para:
                    output.append(row)
                else:
                    output[-1] += "\n"
                    output[-1] += row
                new_para = False
            else:
                new_para = True
        return output


def insert_diff_text_portlet(context, event):
    if event.changed and 'diff_text_enabled' in event.changed:
        manager = get_portlet_manager(context)
        current = manager.get_portlets('agenda_item', 'diff_text')
        if not context.diff_text_enabled:
            for portlet in current:
                manager.remove('agenda_item', portlet.uid)
        else:
            if not current:
                new_portlet = manager.add('agenda_item', 'diff_text')
                ai_slot = manager['agenda_item']
                current_order = list(ai_slot.keys())
                current_order.remove(new_portlet.uid)
                current_order.insert(0, new_portlet.uid)
                ai_slot.order = current_order


class ChangeGroup(object):
    WORD_CAP = 3
    LINE_CAP = 1
    CAP_FILL = ['[...]']
    first = False
    last = False

    def __init__(self, state, parts):
        self.state = state
        self.parts = parts

    def __len__(self):
        return len(self.parts)

    def brief_parts(self, joiner):
        cap = joiner == ' ' and self.WORD_CAP or self.LINE_CAP
        if self.state == 'equal' and len(self) > cap+1:
            if self.first:
                return self.CAP_FILL + self.parts[-cap:]
            elif self.last:
                return self.parts[:cap] + self.CAP_FILL
            elif len(self) > (cap * 2) + 1:
                return self.parts[:cap] + self.CAP_FILL + self.parts[-cap:]
        return self.parts

    def get_html(self, joiner, brief=False):
        txt = joiner.join(brief and self.brief_parts(joiner) or self.parts)
        if self.state == 'insert':
            return '<strong class="text-success">{0}</strong>'.format(txt)
        if self.state == 'delete':
            return '<strong><s class="text-danger">{0}</s></strong>'.format(txt)
        return txt


class Changes(object):
    whitespaces = re.compile('\s+')
    differ = SequenceMatcher()

    def __init__(self, orig, changed):
        # type: (str, str) -> None
        self.has_lines = '\n' in orig
        self.orig = self.split(orig)
        self.changed = self.split(self.has_lines and changed or changed.replace('\n', ' ⏎<br/> '))
        self.change_groups = list()
        self.do_compare()

    @property
    def joiner(self):
        return self.has_lines and '\n' or ' '

    def split(self, txt):
        return self.has_lines and txt.splitlines() or self.whitespaces.split(txt)

    def join(self, groups, brief, no_deleted):
        if no_deleted:
            groups = filter(lambda g: g.state != 'delete', groups)
        return self.joiner.join([cg.get_html(self.joiner, brief=brief) for cg in groups])

    def add_change_group(self, state, astart, aend, bstart, bend):
        if state == 'insert':
            parts = self.changed[bstart:bend]
        else:  # 'delete' och 'equal'
            parts = self.orig[astart:aend]
        self.change_groups.append(ChangeGroup(state, parts))

    def do_compare(self):
        self.differ.set_seqs(self.orig, self.changed)
        for opcode in self.differ.get_opcodes():
            state, positions = opcode[0], opcode[1:]
            if state == 'replace':
                self.add_change_group('delete', *positions)
                self.add_change_group('insert', *positions)
            else:
                self.add_change_group(*opcode)
        if self.change_groups:
            self.change_groups[0].first = True
            self.change_groups[-1].last = True

    def get_html(self, brief=False, no_deleted=False):
        return self.join(self.change_groups, brief, no_deleted)


def includeme(config):
    config.registry.registerAdapter(DiffText)
    config.add_subscriber(insert_diff_text_portlet, [IMeeting, IObjectUpdatedEvent])
