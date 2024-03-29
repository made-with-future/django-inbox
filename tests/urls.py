from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, re_path

from inbox.cron import view_process_new_messages, view_process_new_message_logs
from inbox.views import MessageViewSet, NestedMessagesViewSet, MessagePreferencesViewSet
from rest_framework_extensions.routers import ExtendedSimpleRouter

from tests.views import UserViewSet, UserDeviceViewSet, DeviceViewSet

urlpatterns = []

router = ExtendedSimpleRouter(trailing_slash=False)
router.register(r'devices', DeviceViewSet, basename='devices')
users_router = router.register(r'users', UserViewSet)
users_router.register(r'devices', UserDeviceViewSet,
                      basename='users_devices', parents_query_lookups=['user'])
users_router.register(r'messages', NestedMessagesViewSet, basename='users_messages', parents_query_lookups=['user'])

messages_router = router.register(r'messages', MessageViewSet, basename='messages')

router.register(r'message[-_]preferences', MessagePreferencesViewSet, basename='messagepreferences')

urlpatterns = [
    re_path(r'^api/(?P<version>v1)/', include(router.urls)),
    re_path(r'^cron/process_new_messages$', view_process_new_messages),
    re_path(r'^cron/process_new_message_logs$', view_process_new_message_logs),
]

urlpatterns += staticfiles_urlpatterns()
