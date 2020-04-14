from time import sleep
from unittest.mock import MagicMock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from freezegun import freeze_time
import responses

from inbox import settings as inbox_settings
from inbox import signals
from inbox.core import app_push

from inbox.models import Message, MessageLog
from inbox.utils import process_new_messages
from tests.models import DeviceGroup
from tests.schema import message_preferences, messages
from tests.test import TestCase

User = get_user_model()


class DeviceGroupTests(TestCase):
    fixtures = ['users']

    def setUp(self):
        super(DeviceGroupTests, self).setUp()

        self.user_1 = User.objects.get(email='testuser+1@pre.haus')

    def _get_message_preferences(self, user_id):
        return self.client.get(f'/api/v1/users/{user_id}/message_preferences')

    def test_device_group_on_user(self):
        self.assertIsInstance(self.user_1.device_group, DeviceGroup)

    def test_register_device_without_auth(self):
        response = self.post('/api/v1/users/1/devices', {'registration_token': 'abcdef123'})
        self.assertHTTP401(response)

    @responses.activate
    def test_register_device(self):
        user_id = 1
        user = User.objects.get(pk=user_id)
        self.client.force_login(user)

        # Mock the response from Google
        responses.add(responses.POST, 'https://fcm.googleapis.com/fcm/notification',
                      json={'notification_key': '0987654321poiuytrewq'})

        response = self.post(f'/api/v1/users/{user_id}/devices', {'registration_token': 'abcdef123'})
        self.assertHTTP201(response)
        self.assertEqual(user.device_group.notification_key_name, '9N')

    @responses.activate
    def test_register_and_remove_device(self):
        user_id = 1
        user = User.objects.get(pk=user_id)
        self.client.force_login(user)

        # Mock the response from Google
        responses.add(responses.POST, 'https://fcm.googleapis.com/fcm/notification',
                      json={'notification_key': '0987654321poiuytrewq'})

        registration_token = 'abcdef123'
        response = self.post(f'/api/v1/users/{user_id}/devices', {'registration_token': 'abcdef123'})
        self.assertHTTP201(response)

        # Mock the response from Google
        responses.add(responses.POST, 'https://fcm.googleapis.com/fcm/notification',
                      json={'notification_key': '0987654321poiuytrewq'})

        response = self.delete(f'/api/v1/devices/{registration_token}')
        self.assertHTTP204(response)

    @responses.activate
    def test_update_user_that_generates_inbox_message(self):
        inbox_settings.get_config.cache_clear()

        user_id = 1
        user = User.objects.get(pk=user_id)
        self.client.force_login(user)

        handler = MagicMock()
        signals.unread_count.connect(handler, sender=Message)

        response = self.patch(f'/api/v1/users/{user_id}', {'first_name': 'Test'})
        self.assertHTTP200(response)

        sleep(1)

        # Verify there's an update_account message in Inbox and in model directly
        response = self.get(f'/api/v1/users/{user_id}/messages')
        self.assertHTTP200(response)
        self.validate_list(response, messages)
        self.assertTrue(len(response.data['results']), 1)
        self.assertFalse(response.data['results'][0]['is_read'])

        message = Message.objects.filter(user_id=user_id)
        self.assertTrue(len(message), 1)

        future_send_at = timezone.now() + timezone.timedelta(days=3)
        with freeze_time(future_send_at):
            response = self.get(f'/api/v1/users/{user_id}/messages')
            self.assertHTTP200(response)
            self.assertTrue(len(response.data['results']), 2)

            self.assertEqual(response.data['results'][0]['id'], '2')
            self.assertFalse(response.data['results'][0]['is_read'])
            self.assertEqual(response.data['results'][0]['subject'], 'Account Updated Subject')
            self.assertEqual(response.data['results'][0]['body'], 'Account updated body.')
            self.assertEqual(response.data['results'][0]['group'], 'account_updated')
            self.assertIsNone(response.data['results'][0]['data'])

            self.assertEqual(response.data['results'][1]['id'], '1')
            self.assertFalse(response.data['results'][1]['is_read'])
            self.assertEqual(response.data['results'][1]['subject'], 'Account Updated Subject')
            self.assertEqual(response.data['results'][1]['body'], 'Account updated body.')
            self.assertEqual(response.data['results'][1]['group'], 'account_updated')
            self.assertIsNone(response.data['results'][1]['data'])

            # Assert the signal was called only once with the args
            handler.assert_called_with(signal=signals.unread_count, count=2, sender=Message)

            # Mark them as read
            response = self.post(f'/api/v1/users/{user_id}/messages/read')
            self.assertHTTP200(response)

            # Assert the signal was called only once with the args
            handler.assert_called_with(signal=signals.unread_count, count=0, sender=Message)

            response = self.get(f'/api/v1/users/{user_id}/messages')
            self.assertHTTP200(response)
            self.assertTrue(len(response.data['results']), 2)

            self.assertTrue(response.data['results'][0]['is_read'])
            self.assertTrue(response.data['results'][1]['is_read'])

        # Verify there are message logs for both of these messages
        message_logs = MessageLog.objects.filter(message__user_id=user_id)

        self.assertEqual(len(message_logs), 4)

        process_new_messages()

        self.assertEqual(len(app_push.outbox), 1)
        self.assertEqual(len(mail.outbox), 1)

        app_push.outbox = []
        mail.outbox = []

        with freeze_time(future_send_at):
            process_new_messages()

            self.assertEqual(len(app_push.outbox), 1)
            self.assertEqual(len(mail.outbox), 1)

    def test_message_preferences_from_different_user(self):
        user_id = 1
        user = User.objects.get(pk=user_id)
        self.client.force_login(user)

        response = self.client.get(f'/api/v1/users/2/message_preferences')
        self.assertHTTP403(response)

    def test_message_preferences(self):
        user_id = 1
        user = User.objects.get(pk=user_id)
        self.client.force_login(user)

        # Case 1
        # Update default message preference
        response = self._get_message_preferences(user.pk)
        self.validate(response.data, message_preferences)
        response.data['results'][0]['app_push'] = False
        response = self.client.put(f'/api/v1/users/{user.pk}/message_preferences', response.data)
        self.assertHTTP200(response)
        self.assertFalse(response.data['results'][0]['app_push'])
        self.assertTrue(response.data['results'][0]['email'])
        self.assertTrue(response.data['results'][1]['app_push'])

        # Case 2
        # Update default message preference with mediums that don't exist, shouldn't error, but also not get stored
        response.data['results'][0]['app_push'] = False
        response.data['results'][0]['tester'] = False
        response = self.client.put(f'/api/v1/users/{user.pk}/message_preferences', response.data)
        self.assertHTTP200(response)
        self.assertFalse(response.data['results'][0]['app_push'])
        self.assertTrue(response.data['results'][0]['email'])
        self.assertTrue(response.data['results'][1]['app_push'])
        self.assertFalse('tester' in response.data['results'][0])

        # Case 3
        # Make sure it's actually in the DB that way
        res_user = User.objects.get(pk=user.pk)
        self.assertFalse('tester' in res_user.message_preferences.groups[0])

        # Add preference that isn't valid (eg no id in defaults)
        response.data['results'].append({
            'id': 'fake',
            'app_push': True
        })
        response = self.client.put(f'/api/v1/users/{user.pk}/message_preferences', response.data)
        self.assertHTTP200(response)

        for group in response.data['results']:
            self.assertNotEqual(group['id'], 'fake')
        res_user = User.objects.get(pk=user.pk)
        for group in res_user.message_preferences._groups:
            self.assertNotEqual(group['id'], 'fake')

        # Case 4
        # Reverse order before saving and make sure comes back in the correct order (as defined by defaults)
        response = self.client.get(f'/api/v1/users/{user.pk}/message_preferences')
        response.data['results'].reverse()
        response = self.client.put(f'/api/v1/users/{user.pk}/message_preferences', response.data)
        self.assertHTTP200(response)
        self.assertEqual(response.data['results'][0]['id'], 'default')
        self.assertEqual(response.data['results'][1]['id'], 'account_updated')
        self.assertEqual(response.data['results'][2]['id'], 'friend_requests')
        self.assertEqual(response.data['results'][3]['id'], 'important_updates')

        # We use lru_cache on INBOX_CONFIG, clear it out
        inbox_settings.get_config.cache_clear()
        # Then override the INBOX_CONFIG setting, we'll add a new message group and see it we get the expected return
        INBOX_CONFIG = settings.INBOX_CONFIG.copy()
        MESSAGE_GROUPS = INBOX_CONFIG['MESSAGE_GROUPS'].copy()
        MESSAGE_GROUPS.append({
            'id': 'test_1',
            'label': 'Test 1',
            'description': 'Test 1 description.',
            'is_preference': True,
            'use_preference': None,
            'preference_defaults': {
                'app_push': True,
                'email': True,
                'sms': None,
                'web_push': None
            },
            'message_keys': ['test_1']
        })
        INBOX_CONFIG['MESSAGE_GROUPS'] = MESSAGE_GROUPS
        with self.settings(INBOX_CONFIG=INBOX_CONFIG):
            response = self._get_message_preferences(user.pk)
            self.assertEqual(response.data['results'][4]['id'], 'test_1')
            self.assertTrue(response.data['results'][4]['app_push'])
            self.assertTrue(response.data['results'][4]['email'])

        # Then override the INBOX_CONFIG setting, we'll add a new message group to the front
        #  and see it we get the expected return
        inbox_settings.get_config.cache_clear()
        MESSAGE_GROUPS.insert(0, {
            'id': 'test_2',
            'label': 'Test 2',
            'description': 'Test 2 description.',
            'is_preference': True,
            'use_preference': None,
            'preference_defaults': {
                'app_push': True,
                'email': False,
                'sms': None,
                'web_push': None
            },
            'message_keys': ['test_2']
        })
        INBOX_CONFIG['MESSAGE_GROUPS'] = MESSAGE_GROUPS
        with self.settings(INBOX_CONFIG=INBOX_CONFIG):
            response = self._get_message_preferences(user.pk)
            self.assertEqual(response.data['results'][0]['id'], 'test_2')
            self.assertTrue(response.data['results'][0]['app_push'])
            self.assertFalse(response.data['results'][0]['email'])
            self.assertEqual(response.data['results'][5]['id'], 'test_1')
            self.assertTrue(response.data['results'][5]['app_push'])
            self.assertTrue(response.data['results'][5]['email'])

        # Verify it wasn't saved to user, since user didn't save/update it
        user.refresh_from_db()

        # The _groups property is the actual underlying field on the table
        self.assertTrue(user.message_preferences._groups[0]['id'], 'default')
        self.assertTrue(user.message_preferences._groups[3]['id'], 'important_updates')
        self.assertTrue(len(user.message_preferences._groups), 4)

        for group in user.message_preferences._groups:
            self.assertNotEqual(group['id'], 'test_1')
            self.assertNotEqual(group['id'], 'test_2')

        # Now remove a setting and verify it doesn't come back on endpoint but is still stored on user after saving
        #  we do this so that a preference that is brought back and a user had chosen to enable/disable it we'd still
        #  have their old preference.
        inbox_settings.get_config.cache_clear()
        INBOX_CONFIG['MESSAGE_GROUPS'] = [INBOX_CONFIG['MESSAGE_GROUPS'][0]]
        with self.settings(INBOX_CONFIG=INBOX_CONFIG):
            response = self.client.get(f'/api/v1/users/{user.pk}/message_preferences')
            self.assertEqual(response.data['results'][0]['id'], 'test_2')
            self.assertTrue(response.data['results'][0]['app_push'])
            self.assertFalse(response.data['results'][0]['email'])
            self.assertTrue(len(response.data['results']), 1)

        # Verify it wasn't saved to user, since user didn't save/update it
        user.refresh_from_db()

        # The _groups property is the actual underlying field on the table
        self.assertTrue(user.message_preferences._groups[0]['id'], 'default')
        self.assertTrue(user.message_preferences._groups[3]['id'], 'important_updates')
        self.assertTrue(len(user.message_preferences._groups), 4)

        for group in user.message_preferences._groups:
            self.assertNotEqual(group['id'], 'test_1')
            self.assertNotEqual(group['id'], 'test_2')

        inbox_settings.get_config.cache_clear()
        with self.settings(INBOX_CONFIG=INBOX_CONFIG):
            # Now save the single message group we have, it should still keep the old ones and include the new one even
            #  though they won't be returned in the API
            response = self.client.put(f'/api/v1/users/{user.pk}/message_preferences', response.data)
            self.assertHTTP200(response)
            self.assertEqual(response.data['results'][0]['id'], 'test_2')
            self.assertTrue(response.data['results'][0]['app_push'])
            self.assertFalse(response.data['results'][0]['email'])
            self.assertEqual(len(response.data['results']), 1)

            # Fetch it, verify the fetch is correct as well
            response = self.client.get(f'/api/v1/users/{user.pk}/message_preferences')
            self.assertHTTP200(response)
            self.assertEqual(response.data['results'][0]['id'], 'test_2')
            self.assertTrue(response.data['results'][0]['app_push'])
            self.assertFalse(response.data['results'][0]['email'])
            self.assertEqual(len(response.data['results']), 1)

        # Verify it was saved to user
        user.refresh_from_db()

        # The _groups property is the actual underlying field on the table
        # Verify that label and description aren't stored in the DB for the user
        self.assertEqual(list(user.message_preferences._groups[0]).sort(), ['id', 'app_push', 'email'].sort())
        self.assertTrue(user.message_preferences._groups[0]['id'], 'test_2')
        self.assertTrue(user.message_preferences._groups[4]['id'], 'important_updates')
        self.assertTrue(len(user.message_preferences._groups), 5)

        for group in user.message_preferences._groups:
            self.assertNotEqual(group['id'], 'test_1')

    def test_message_preference_medium(self):
        user_id = 1
        user = User.objects.get(pk=user_id)
        self.client.force_login(user)

        # Case 1
        # Update default message preference
        response = self._get_message_preferences(user.pk)
        self.validate(response.data, message_preferences)
        message_preference = response.data['results'][0]
        response = self.client.put(f'/api/v1/users/{user.pk}/message_preferences/{message_preference["id"]}/app_push',
                                   False)
        self.assertHTTP200(response)
        self.assertFalse(response.data)
        response = self.client.put(f'/api/v1/users/{user.pk}/message_preferences/{message_preference["id"]}/app_push',
                                   True)
        self.assertHTTP200(response)
        self.assertTrue(response.data)

        response = self.client.put(f'/api/v1/users/{user.pk}/message_preferences/{message_preference["id"]}/fake',
                                   True)
        self.assertHTTP400(response)

        response = self.client.put(f'/api/v1/users/{user.pk}/message_preferences/fake/app_push',
                                   True)
        self.assertHTTP400(response)
