import uuid
from unittest.mock import MagicMock

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from faker import Faker
from freezegun import freeze_time

from inbox import settings as inbox_settings
from inbox import signals
from inbox.constants import MessageLogStatus, MessageLogStatusReason
from inbox.core import app_push
from inbox.models import Message, MessageMedium, MessageLog
from inbox.test.utils import InboxTestCaseMixin
from inbox.utils import process_new_messages, process_new_message_logs

User = get_user_model()
Faker.seed()
fake = Faker()


class MessageTestCase(InboxTestCaseMixin, TestCase):

    user = None

    def setUp(self):
        super().setUp()
        email = fake.ascii_email()
        self.user = User.objects.create(email=email, email_verified_on=timezone.now().date(), username=email)
        self.user.device_group.notification_key = 'fake-notification_key'
        self.user.device_group.save()

        inbox_settings.get_config.cache_clear()

    def test_can_save_message(self):

        message = Message.objects.create(user=self.user, key='default')

        self.assertEqual(message.user.email, self.user.email)
        self.assertEqual(message.group, {'id': 'default', 'label': 'Updates', 'data': {}})
        self.assertEqual(message.key, 'default')

    def test_cannot_save_message_with_same_message_id_more_than_once(self):

        message = Message.objects.create(user=self.user, key='default', message_id='test', fail_silently=False)

        self.assertEqual(message.user.email, self.user.email)
        self.assertEqual(message.group, {'id': 'default', 'label': 'Updates', 'data': {}})
        self.assertEqual(message.key, 'default')

        with self.assertRaises(ValidationError) as context:
            Message.objects.create(user=self.user, key='default', message_id='test', fail_silently=False)

    def test_can_save_multiple_messages_with_null_message_id(self):

        message = Message.objects.create(user=self.user, key='default', fail_silently=False)

        self.assertEqual(message.user.email, self.user.email)
        self.assertEqual(message.group, {'id': 'default', 'label': 'Updates', 'data': {}})
        self.assertEqual(message.key, 'default')
        self.assertIsNone(message.message_id)

        Message.objects.create(user=self.user, key='default', fail_silently=False)

    def test_unread_count_signal_gets_proper_data(self):
        handler = MagicMock()
        signals.unread_count.connect(handler, sender=Message)

        # Do what it takes to trigger the signal
        Message.objects.create(user=self.user, key='default')

        process_new_messages()
        process_new_message_logs()

        # Assert the signal was called only once with the args
        handler.assert_called_once_with(signal=signals.unread_count, count=1, sender=Message, user=self.user)

        # Do what it takes to trigger the signal
        Message.objects.create(user=self.user, key='default')

        process_new_messages()
        process_new_message_logs()

        # Assert the signal was called only once with the args
        handler.assert_called_with(signal=signals.unread_count, count=2, sender=Message, user=self.user)

    def test_unread_count_signal_gets_proper_data_after_mark_read(self):

        handler = MagicMock()
        signals.unread_count.connect(handler, sender=Message)

        # Do what it takes to trigger the signal
        Message.objects.create(user=self.user, key='default')
        Message.objects.create(user=self.user, key='default')
        Message.objects.create(user=self.user, key='default')

        process_new_messages()
        process_new_message_logs()

        # Assert the signal was called only once with the args
        handler.assert_called_with(signal=signals.unread_count, count=3, sender=Message, user=self.user)

        handler = MagicMock()
        signals.unread_count.connect(handler, sender=Message)

        Message.objects.mark_all_read(self.user.id)

        # Assert the signal was called only once with the args
        handler.assert_called_once_with(signal=signals.unread_count, count=0, sender=Message, user=self.user)

    def test_save_message_with_key_not_in_a_group(self):
        # We use lru_cache on INBOX_CONFIG, clear it out
        inbox_settings.get_config.cache_clear()
        # Then override the INBOX_CONFIG setting, we'll add a new message group and see it we get the expected return
        INBOX_CONFIG = settings.INBOX_CONFIG.copy()
        INBOX_CONFIG['MESSAGE_CREATE_FAIL_SILENTLY'] = False
        with self.settings(INBOX_CONFIG=INBOX_CONFIG):
            with self.assertRaises(ValidationError) as context:
                Message.objects.create(user=self.user, key='key_not_in_a_group')

            self.assertTrue('"key_not_in_a_group" does not exist in any group.' in context.exception.messages[0])

        inbox_settings.get_config.cache_clear()

    def test_save_message_with_invalid_key(self):

        # We use lru_cache on INBOX_CONFIG, clear it out
        inbox_settings.get_config.cache_clear()
        # Then override the INBOX_CONFIG setting, we'll add a new message group and see it we get the expected return
        INBOX_CONFIG = settings.INBOX_CONFIG.copy()
        INBOX_CONFIG['MESSAGE_CREATE_FAIL_SILENTLY'] = False
        with self.settings(INBOX_CONFIG=INBOX_CONFIG):
            with self.assertRaises(ValidationError) as context:
                Message.objects.create(user=self.user, key='key_with_no_template')

            self.assertTrue('Subject template for "key_with_no_template" does not exist.' in context.exception.messages[0])

        inbox_settings.get_config.cache_clear()

        # Verify that you can adjust fail_silently on a per call basis
        with self.assertRaises(ValidationError) as context:
            Message.objects.create(user=self.user, key='key_with_no_template', fail_silently=False)

        self.assertTrue('Subject template for "key_with_no_template" does not exist.' in context.exception.messages[0])

    def test_create_message_verify_log_exists(self):

        self.assertEqual(MessageLog.objects.count(), 0)

        message = Message.objects.create(user=self.user, key='default')

        message_logs = MessageLog.objects.filter(message=message)

        used = []
        for k, message_log in enumerate(message_logs):
            # Tested this way because order can change
            self.assertTrue(message_log.medium in (MessageMedium.EMAIL, MessageMedium.APP_PUSH) and message_log.medium not in used)
            self.assertEqual(message.pk, message_log.message_id)
            used.append(message_log.medium)

    def test_defined_message_id_exists(self):

        self.assertEqual(MessageLog.objects.count(), 0)

        now_str = timezone.now().strftime('%Y%m%d')
        test_message_id = f'default_{self.user.pk}_{now_str}'
        Message.objects.create(user=self.user, key='default', message_id=test_message_id)

        existing_message_ids, missing_message_ids = Message.objects.exists(test_message_id)

        self.assertEqual(existing_message_ids, set([test_message_id]))
        self.assertEqual(missing_message_ids, set())

        existing_message_ids, missing_message_ids = Message.objects.exists([test_message_id, '123'])

        self.assertEqual(existing_message_ids, set([test_message_id]))
        self.assertEqual(missing_message_ids, set(['123']))

    def test_create_message_process_message_logs(self):

        self.assertEqual(MessageLog.objects.count(), 0)

        Message.objects.create(user=self.user, key='default')

        process_new_messages()
        process_new_message_logs()

        self.assertEqual(len(app_push.outbox), 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_create_message_for_unverified_user_empty_outbox(self):

        email = fake.ascii_email()
        user = User.objects.create(email=email, username=email)
        user.device_group.notification_key = 'fake-notification_key'
        user.device_group.save()

        self.assertEqual(MessageLog.objects.count(), 0)

        message = Message.objects.create(user=user, key='default')

        process_new_messages()
        process_new_message_logs()

        self.assertEqual(len(app_push.outbox), 2)
        self.assertEqual(len(mail.outbox), 0)

        message.refresh_from_db()

        self.assertTrue(message.is_logged)

    def test_create_message_process_message_logs_user_has_push_off(self):

        groups = self.user.message_preferences.groups.copy()
        groups[0]['app_push'] = False
        self.user.message_preferences.groups = groups
        self.user.message_preferences.save()

        self.assertEqual(MessageLog.objects.count(), 0)

        message = Message.objects.create(user=self.user, key='default')

        process_new_messages()

        # Verify two message log entries
        self.assertTrue(len(message.logs.all()), 2)

        process_new_message_logs()

        self.assertEqual(len(app_push.outbox), 1)
        self.assertEqual(len(mail.outbox), 1)

        for message_log in message.logs.all():
            if message_log.medium == MessageMedium.APP_PUSH:
                self.assertTrue(message_log.status, MessageLogStatus.NOT_SENDABLE)
            if message_log.medium == MessageMedium.EMAIL:
                self.assertTrue(message_log.status, MessageLogStatus.SENT)

    def test_verify_app_push_template_falls_back(self):

        self.assertEqual(MessageLog.objects.count(), 0)

        Message.objects.create(user=self.user, key='push_only')

        process_new_messages()

    def test_create_message_fail_silently(self):

        message = Message.objects.create(user=self.user)

        self.assertIsNone(message)

    def test_message_is_cancelled_before_sending_but_schedules_future(self):
        message = Message.objects.create(user=self.user, key='new_account', fail_silently=False)

        messages_count = Message.objects.count()
        self.assertEqual(messages_count, 1)

        process_new_messages()
        process_new_message_logs()

        message_logs_count = MessageLog.objects.count()
        messages_count = Message.objects.count()
        message = Message.objects.get(pk=message.id)
        self.assertTrue(message.is_hidden)

        self.assertEqual(message_logs_count, 0)
        self.assertEqual(messages_count, 2)

    def test_message_scheduled_for_future_doesnt_send_unread_push(self):
        email = fake.ascii_email()
        user = User.objects.create(email=email, email_verified_on=timezone.now().date(), username=email)
        user.device_group.notification_key = 'abcdef'
        user.device_group.save()

        self.assertEqual(len(app_push.outbox), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(MessageLog.objects.count(), 0)

        future_at = timezone.now() + timezone.timedelta(days=1)

        Message.objects.create(user=user, key='default', send_at=future_at)

        process_new_messages()
        process_new_message_logs()

        self.assertEqual(len(app_push.outbox), 0)
        self.assertEqual(len(mail.outbox), 0)

        # Grab message logs with app_push, verify status and failure reason
        message_logs = MessageLog.objects.filter(message__user=user)
        self.assertEqual(len(message_logs), 0)

        with freeze_time(future_at + timezone.timedelta(seconds=30)):
            process_new_messages()
            process_new_message_logs()

            self.assertEqual(len(app_push.outbox), 2)
            self.assertEqual(len(mail.outbox), 1)

    def test_message_send_to_group_that_has_app_push_and_email_but_skips_app_push_on_one_key(self):
        # this message key in the group has app push and email
        message = Message.objects.create(user=self.user, key='group_with_skip_push', fail_silently=False)

        messages_count = Message.objects.count()
        self.assertEqual(messages_count, 1)

        process_new_messages()
        process_new_message_logs()

        message_logs_count = MessageLog.objects.count()
        messages_count = Message.objects.count()
        message = Message.objects.get(pk=message.id)
        self.assertFalse(message.is_hidden)

        self.assertEqual(message_logs_count, 2)
        self.assertEqual(messages_count, 1)

        # this message key in the group has no app push
        message = Message.objects.create(user=self.user, key='group_with_skip_push_2', fail_silently=False)

        messages_count = Message.objects.count()
        self.assertEqual(messages_count, 2)

        process_new_messages()
        process_new_message_logs()

        message_logs_count = MessageLog.objects.count()
        messages_count = Message.objects.count()
        message = Message.objects.get(pk=message.id)
        self.assertFalse(message.is_hidden)

        self.assertEqual(message_logs_count, 3)
        self.assertEqual(messages_count, 2)

    def test_message_send_to_group_that_has_all_mediums_skipped_so_they_appear_only_in_inbox(self):
        # this message key in the group has app push and email
        message = Message.objects.create(user=self.user, key='group_with_skip_push_3', fail_silently=False)

        messages_count = Message.objects.count()
        self.assertEqual(messages_count, 1)

        process_new_messages()
        process_new_message_logs()

        message = Message.objects.get(pk=message.id)
        self.assertFalse(message.is_hidden)
        message_logs_count = MessageLog.objects.count()
        messages_count = Message.objects.count()

        self.assertEqual(message_logs_count, 0)
        self.assertEqual(messages_count, 1)

    def test_create_message_user_without_app_push_notification_key(self):
        email = fake.ascii_email()
        user = User.objects.create(email=email, email_verified_on=timezone.now().date(), username=email)

        self.assertEqual(MessageLog.objects.count(), 0)

        Message.objects.create(user=user, key='default')

        process_new_messages()
        process_new_message_logs()

        self.assertEqual(len(app_push.outbox), 0)
        self.assertEqual(len(mail.outbox), 1)

        # Grab message log with app_push, verify status and failure reason
        message_log = MessageLog.objects.filter(message__user=user, medium=MessageMedium.APP_PUSH).first()

        self.assertGreater(message_log.updated_at, message_log.created_at)
        self.assertEqual(message_log.status, MessageLogStatus.NOT_SENDABLE)
        self.assertEqual(message_log.status_reason, MessageLogStatusReason.MISSING_ID.label)

    def test_create_message_inbox_only_welcome(self):
        email = fake.ascii_email()
        user = User.objects.create(email=email, email_verified_on=timezone.now().date(), username=email)
        user.device_group.notification_key = 'abcdef'
        user.device_group.save()

        self.assertEqual(MessageLog.objects.count(), 0)

        Message.objects.create(user=user, key='welcome')

        # Unread count isn't sent until the message is processed
        self.assertEqual(len(app_push.outbox), 0)

        process_new_messages()
        process_new_message_logs()

        self.assertEqual(len(app_push.outbox), 1)
        self.assertEqual(len(mail.outbox), 0)

        # Grab message logs with app_push, verify status and failure reason
        messages = Message.objects.filter(user=user)
        self.assertTrue(len(messages), 1)

        message = messages[0]

        self.assertTrue(message.is_logged)
        self.assertEqual(message.subject, 'Welcome to Django Inbox')
        self.assertEqual(message.body, 'Django Inbox is a library, welcome.')

    def test_legacy_uuid4_message_id_clearing(self):
        """
        We previously stored unset message_id as uuid4, but we wanted a better way to lookup which messages had no
        message id set without adding a field, so switched to storing as null. This method just verified that Django
        is accurate at looking up uuid4 by pattern and setting to null so that our migration to the new null method
        can be successful.
        :return:
        """
        inbox = __import__('inbox')
        clear_message_id_uuid4 = getattr(inbox.migrations, '0009_message_id_default_clear_prev_uuid4').clear_message_id_uuid4

        uuid4 = uuid.uuid4()

        message = Message.objects.create(user=self.user, key='default', message_id=uuid4, fail_silently=False)

        # Insert a second message that isn't uuid4 so that we can make sure it isn't cleared out
        message_2 = Message.objects.create(user=self.user, key='default', message_id='placebo', fail_silently=False)

        self.assertEqual(message.message_id, str(uuid4))

        message = Message.objects.filter(message_id__iregex=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}').first()

        message = Message.objects.get(pk=message.pk)
        self.assertEqual(message.message_id, str(uuid4))

        message_2 = Message.objects.get(pk=message_2.pk)
        self.assertEqual(message_2.message_id, 'placebo')

        clear_message_id_uuid4(apps, None)

        message = Message.objects.get(pk=message.pk)
        self.assertIsNone(message.message_id)

        message_2 = Message.objects.get(pk=message_2.pk)
        self.assertEqual(message_2.message_id, 'placebo')

    def test_maintenance_max_age(self):

        messages = Message.objects.filter(user=self.user)

        self.assertEqual(len(messages), 0)

        Message.objects.create(user=self.user, key='default', fail_silently=False)

        messages = Message.objects.filter(user=self.user)

        self.assertEqual(len(messages), 1)

    def test_mailchimp_header_on_email_message(self):

        self.assertEqual(MessageLog.objects.count(), 0)

        Message.objects.create(user=self.user, key='default')

        process_new_messages()
        process_new_message_logs()

        self.assertEqual(mail.outbox[0].extra_headers, {'X-MC-Tags': 'default',
                                                        'X-SMTPAPI': '{"category": "default"}',
                                                        'X-Mailgun-Tag': 'default'})

    def test_hook_fails_catches_exception(self):

        self.assertEqual(MessageLog.objects.count(), 0)

        Message.objects.create(user=self.user, key='hook_fails_throws_exception', fail_silently=False)

        messages = Message.objects.filter(user=self.user)
        self.assertEqual(len(messages), 1)
        self.assertFalse(messages[0].is_logged)

        process_new_messages()

        message_logs = MessageLog.objects.filter(message__user=self.user)
        self.assertEqual(len(message_logs), 1)
        self.assertEqual(message_logs[0].status, MessageLogStatus.NEW)

        self.assertRaises(Exception, process_new_message_logs)

        message_logs = MessageLog.objects.filter(message__user=self.user)
        self.assertEqual(len(message_logs), 1)
        self.assertEqual(message_logs[0].status, MessageLogStatus.FAILED)

        # Running process_new_message_logs again shouldn't raise an error
        process_new_message_logs()

    def test_send_at_not_in_range_does_not_send(self):

        self.assertEqual(MessageLog.objects.count(), 0)
        now = timezone.now()

        message = Message.objects.create(user=self.user, key='default', fail_silently=False,
                                         send_at=now + timezone.timedelta(days=1))

        future_at = message.send_at + timezone.timedelta(days=7)

        with freeze_time(future_at):
            process_new_messages()
            process_new_message_logs()

            self.assertEqual(len(mail.outbox), 0)
            self.assertEqual(len(app_push.outbox), 1)

    def test_send_at_in_range_does_send(self):

        self.assertEqual(MessageLog.objects.count(), 0)
        now = timezone.now()

        message = Message.objects.create(user=self.user, key='default', fail_silently=False,
                                         send_at=now + timezone.timedelta(days=1))

        future_at = message.send_at + timezone.timedelta(days=1)

        with freeze_time(future_at):
            process_new_messages()
            process_new_message_logs()

            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(len(app_push.outbox), 2)

    def test_send_at_in_range_is_none_does_send(self):
        # Django doesn't give a good way to override settings when the setting
        #  is a dictionary, so we'll update the dictionary and then reset it
        #  at the end.
        inbox_config = settings.INBOX_CONFIG
        original_value = inbox_config.get('MAX_AGE_BEYOND_SEND_AT')
        inbox_config['MAX_AGE_BEYOND_SEND_AT'] = None
        with override_settings(INBOX_CONFIG=inbox_config):
            self.assertEqual(MessageLog.objects.count(), 0)
            now = timezone.now()

            message = Message.objects.create(user=self.user, key='default', fail_silently=False,
                                             send_at=now + timezone.timedelta(days=1))

            future_at = message.send_at + timezone.timedelta(days=30)

            with freeze_time(future_at):
                process_new_messages()
                process_new_message_logs()

                self.assertEqual(len(mail.outbox), 1)
                self.assertEqual(len(app_push.outbox), 2)

        # Reset as to not break other tests
        inbox_config['MAX_AGE_BEYOND_SEND_AT'] = original_value
