
def includeme(config):
    """ Include all models. """
    config.include('.agenda_item')
    config.include('.agenda_template')
    config.include('.agenda_templates')
    config.include('.catalog')
    config.include('.diff_text')
    config.include('.discussion_post')
    config.include('.evolver')
    config.include('.flash_messages')
    config.include('.invite_ticket')
    config.include('.meeting')
    config.include('.mention')
    config.include('.poll')
    config.include('.populator')
    config.include('.proposal')
    config.include('.proposal_ids')
    config.include('.read_names')
    config.include('.site')
    config.include('.user')
    config.include('.users')
    config.include('.vote')
    config.include('.workflow_aware')
