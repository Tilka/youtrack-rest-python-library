# mapping for default google code project
import googleCode

print "Use dolphin_emu mapping scheme"

# TODO: configure in YouTrack which of these are open/closed
googleCode.STATES = {
        'New':              'New',
        'Accepted':         'Accepted',
        'Started':          'Started',
        'Questionable':     'Questionable',
        'FixedInPR':        'Fixed in pull request',
        'Fixed':            'Fixed',
        'Invalid':          'Invalid',
        'Duplicate':        'Duplicate',
        'WontFix':          'Won\'t fix',
        'UserIsBadAtGames': 'User is bad at games',
}

googleCode.TYPES = {
        'Type-Defect':      'Defect',
        'Type-Enhancement': 'Enhancement',
        'Type-Task':        'Task',
        'Type-Patch':       'Patch',
        'Type-Other':       'Other',
}

googleCode.PRIORITIES = {
        'Priority-Low':      '0', # typo?
        'Priority-Medium':   '3',
        'Priority-High':     '2',
        'Priority-Critical': '1',
}

googleCode.FIELD_NAMES = {
        'owner':     'Assignee',
        'status':    'State',
        'Milestone': 'Fix versions',
        'Component': 'Subsystem',
}

googleCode.FIELD_TYPES = {
        'Assignee':     'user[1]',
        'Fix versions': 'version[*]',
        'Priority':     'enum[1]',
        'State':        'state[1]',
        'Subsystem':    'ownedField[1]',
        'Type':         'enum[1]',
}
