from functools import lru_cache

from django.conf import settings


# Fill is used for filling in some fields with sensible defaults
from toolz import merge
MESSAGE_GROUP_FILL = {
    'is_preference': True,
    'use_preference': None,
    'preference_defaults': {
        'app_push': True,
        'email': True,
        'sms': None,
        'web_push': None
    },
    'message_keys': []
}

CONFIG_DEFAULTS = {
    # Message groups are used to organize the messages and provide preferences and their defaults
    'MESSAGE_GROUPS': [
        {
            'id': 'default',
            'label': 'News and Updates',
            'description': 'General news and updates.',
            'message_keys': ['default']
        }
    ],
    # Callable that returns the Firebase push notification key so that a user can be sent pushes, or None
    # if one doesn't exist for the user.
    'APP_PUSH_NOTIFICATION_KEY_GETTER': None,
    'BACKENDS': {
        'APP_PUSH': 'inbox.core.app_push.backends.locmem.AppPushBackend'
    },
    'TESTING_MEDIUM_OUTPUT_PATH': None,
    'DISABLE_NEW_DATA_SILENT_APP_PUSH': False,
    'MESSAGE_CREATE_FAIL_SILENTLY': True,
    'HOOKS_MODULE': None
}


def deep_merge(a, b):
    """ Merge two dictionaries recursively. """
    def merge_values(k, v1, v2):
        if isinstance(v1, dict) and isinstance(v2, dict):
            return k, deep_merge(v1, v2)
        else:
            return k, v2
    a_keys = set(a.keys())
    b_keys = set(b.keys())
    pairs = [merge_values(k, a[k], b[k]) for k in a_keys & b_keys] \
            + [(k, a[k]) for k in a_keys - b_keys] \
            + [(k, b[k]) for k in b_keys - a_keys]
    return dict(pairs)


@lru_cache()
def get_config():
    USER_CONFIG = getattr(settings, "INBOX_CONFIG", {})
    CONFIG = CONFIG_DEFAULTS.copy()
    CONFIG.update(USER_CONFIG)

    for k, message_group in enumerate(CONFIG['MESSAGE_GROUPS']):
        CONFIG['MESSAGE_GROUPS'][k] = deep_merge(MESSAGE_GROUP_FILL, message_group)

    return CONFIG
