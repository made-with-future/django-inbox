import os

from django.utils import timezone
from inbox.constants import MessageMedium

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(PROJECT_DIR)

SECRET_KEY = 'fake-key'

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',

    'inbox',
    'tests',
]

ROOT_URLCONF = 'tests.urls'

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'inbox',
        'USER': 'inbox',
        'PASSWORD': 'password',
        'HOST': 'db',
        'PORT': ''
    },
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
    },
]

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/a/static/'

INBOX_CONFIG = {
    # Message groups are used to organize the messages and provide preferences and their defaults
    'MESSAGE_GROUPS': [
        {
            'id': 'default',
            'label': 'Updates',
            'description': 'General news and updates.',
            'preference_defaults': {
                'email': True,
                'sms': None
            },
            'message_keys': ['default', 'hook_fails_throws_exception'],
            'skip_email': ['hook_fails_throws_exception']
        },
        {
            'id': 'inbox_only',
            'label': 'Inbox Only',
            'description': 'Inbox only messages.',
            'is_preference': False,
            'preference_defaults': {
                "app_push": None,
                "email": None,
                "sms": None,
                "web_push": None
            },
            'message_keys': ['welcome', 'key_with_no_template']
        },
        {
            'id': 'account_updated',
            'label': 'Account Updated',
            'description': 'When you update your account.',
            'message_keys': ['new_account', 'account_updated']
        },
        {
            "id": "friend_requests",
            "label": "Friend Requests",
            "description": "Receive reminders about friend requests.",
            "preference_defaults": {
                "app_push": True,
                "email": True,
                "sms": True,
                "web_push": True
            },
            "message_keys": ["new_friend_request", "friend_request_accepted"]
        },
        {
            'id': 'important_updates',
            'label': 'Important Updates',
            'description': "Receive notifications about important updates.",
            'preference_defaults': {
                'app_push': True,
                'email': True
            },
            'message_keys': ['important_update']
        },
        {
            'id': 'push_only_group',
            'label': 'Push only group',
            'description': "Receive notifications about push only.",
            'preference_defaults': {
                'app_push': True,
                'email': None
            },
            'message_keys': ['push_only']
        },
        {
            'id': 'group_with_all_mediums_off',
            'label': 'Group with All Mediums Off',
            'description': "This group should not show up in preferences.",
            'preference_defaults': {
                'app_push': None,
                'email': None,
                'web_push': None,
                'sms': None
            },
            'message_keys': ['all_mediums_off']
        },
        {
            'id': 'group_with_skip_push',
            'label': 'Group with skip push',
            'description': "This group has one key that won't send an app push.",
            'preference_defaults': {
                'app_push': True,
                'email': True
            },
            'message_keys': ['group_with_skip_push', 'group_with_skip_push_2', 'group_with_skip_push_3'],
            'skip_app_push': ['group_with_skip_push_2', 'group_with_skip_push_3'],
            'skip_email': ['group_with_skip_push_3']
        }
    ],
    'BACKENDS': {
        'APP_PUSH': 'inbox.core.app_push.backends.locmem.AppPushBackend',
        'APP_PUSH_CONFIG': {
            'GOOGLE_FCM_SERVER_KEY': 'abc'
        }
    },
    'TESTING_MEDIUM_OUTPUT_PATH': None,
    'HOOKS_MODULE': 'tests.hooks',
    'MAX_AGE_BEYOND_SEND_AT': timezone.timedelta(days=2),
}

GOOGLE_FCM_SENDER_ID = '12345'
GOOGLE_FCM_SERVER_KEY = '678910'

AUTH_USER_MODEL = 'tests.User'
