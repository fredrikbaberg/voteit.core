from os.path import join
from pkg_resources import resource_filename
from copy import deepcopy

from deform import Form
from deform import ZPTRendererFactory
from deform.widget import RadioChoiceWidget
from deform.widget import RichTextWidget
from pyramid.i18n import get_localizer
from pyramid.threadlocal import get_current_request


DEFORM_TEMPLATE_DIR = resource_filename('deform', 'templates/')
CURRENT_PATH = resource_filename('voteit.core', '')
WIDGETS_PATH = join(CURRENT_PATH, 'views', 'templates', 'widgets')


def deform_translator(term):
    """ Special translator for deform templates. It doesn't register
        one as default, since it's framework agnostic.
    """
    return get_localizer(get_current_request()).translate(term)

def append_search_path(path):
    """ Add a search path to deform. This is the way to register
        custom widget templates.
    """
    current = list(Form.default_renderer.loader.search_path)
    current.append(path)
    Form.default_renderer.loader.search_path = tuple(current)

#Important for tests so we can restore deform to its original state
_OLD_RENDERER = deepcopy(Form.default_renderer)

def reset_deform(config=None):
    """ Reset deform to its original state. Run this in the tearDown part of tests, otherwise
        deform will still be patched. (This doesn't apply for tests run with nose, but with setuptools.)
        
        This will also clear search paths from deform.
    """
    Form.set_default_renderer(_OLD_RENDERER)

def includeme(config):
    """ Patch deform to use zpt_renderer as default with Pyramids
        translation mechanism activated.
        Also a good pluggable point for patching templates or other things.
        
        WARNING! This method patches global variables, which means that
        it will affect ALL tests after this method is included.
    """
    settings = config.registry.settings
    auto_reload = settings['pyramid.reload_templates']
    debug_templates = settings['pyramid.debug_templates']
    zpt_renderer = ZPTRendererFactory(DEFORM_TEMPLATE_DIR,
                                      translator = deform_translator,
                                      auto_reload = auto_reload,
                                      debug = debug_templates)
    Form.set_default_renderer(zpt_renderer)

    append_search_path(WIDGETS_PATH)

    #Patches for widget templates, so they actually display sane readonly templates
    RadioChoiceWidget.readonly_template = join(WIDGETS_PATH, 'readonly', 'radio_choice')

    #Patches for RichTextWidget templates to display a better editor 
    RichTextWidget.template = join(WIDGETS_PATH, 'richtext')
