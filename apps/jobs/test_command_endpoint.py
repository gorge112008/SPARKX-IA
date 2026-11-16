"""Human language interpretation is read-only and never grants execution authority."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import PortalAccount
from apps.ai_management.models import AIUsage
from apps.assistant.execution import agent_execution
from .models import Job, UIAction


class CommandEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='language-owner')
        self.portal = PortalAccount.objects.create(user=self.user)
        self.client.force_login(self.user)
        session = self.client.session
        session['portal_auth_version'] = 1
        session.save()
        self.url = reverse('events:romeo_interpret')

    def test_understanding_and_clarification_have_no_execution_or_model_side_effects(self):
        with patch('apps.assistant.provider._opener.open', side_effect=AssertionError('No network')), \
                patch('subprocess.Popen', side_effect=AssertionError('No shell')), \
                patch('apps.jobs.services.enqueue', side_effect=AssertionError('No job')):
            understood = self.client.post(self.url, {'command': 'Hola Gica, abre no sé el calendario por favor'})
            self.assertEqual(understood.status_code, 200)
            self.assertEqual(understood.json()['action'], 'calendar_open')
            ambiguous = self.client.post(self.url, {'command': 'abre'})
            self.assertEqual(ambiguous.json()['status'], 'clarify')
            self.assertIsNone(ambiguous.json()['action'])
            blocked = self.client.post(self.url, {'command': 'no abras el calendario'})
            self.assertNotEqual(blocked.json()['status'], 'understood')
        self.assertIn('no-store', understood['Cache-Control'])
        self.assertFalse(UIAction.objects.exists())
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_post_csrf_and_authentication_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        guest = Client()
        self.assertEqual(guest.post(self.url, {'command': 'calendario'}).status_code, 302)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.user)
        self.assertEqual(protected.post(self.url, {'command': 'calendario'}).status_code, 403)

    def test_social_paraphrases_use_the_ordinary_button_without_actions_or_models(self):
        for text in (
            '¿Puedes decirme la hora?', 'Puedes mandarle un saludo a Manu.',
            'Quiero saludar.', 'O buenas noches.', 'Buenos días',
            'muchas gracias', 'O k muchas gracias.', 'Listo, muchas gracias.',
            'Gracias por tu ayuda', 'no hay de qué',
            'graccias', 'oye te doy las graccias por ayudarme con esto',
            'perfecto de verdad muchas gracias Gica',
            'gracias por todo lo que me has ayudado', 'gracias por abrir calendario',
        ):
            with self.subTest(text=text):
                response = self.client.post(self.url, {'command': text})
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(set(data), {'status', 'action', 'query', 'message', 'options', 'catalog_version'})
                self.assertEqual((data['status'], data['action'], data['query'], data['options']), ('info', None, '', []))
                self.assertTrue(data['message'])
        search = self.client.post(self.url, {'command': 'Busca a Gracias'}).json()
        self.assertEqual((search['action'], search['query']), ('people_search', 'Gracias'))
        typo_name = self.client.post(self.url, {'command': 'Busca a Graccias'}).json()
        self.assertEqual((typo_name['action'], typo_name['query']), ('people_search', 'Graccias'))
        self.assertFalse(UIAction.objects.exists())
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_fresh_role_and_active_user_rechecked(self):
        self.portal.role = PortalAccount.Role.REVIEWER
        self.portal.save(update_fields=['role'])
        self.assertEqual(self.client.post(self.url, {'command': 'calendario'}).status_code, 403)
        self.assertEqual(self.client.post(self.url, {'command': 'puedes decirme la hora'}).status_code, 403)
        self.portal.role = PortalAccount.Role.ORGANIZER
        self.portal.save(update_fields=['role'])
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertIn(self.client.post(self.url, {'command': 'calendario'}).status_code, (302, 403))

    def test_normalized_destinations_are_read_only_and_person_data_stays_raw(self):
        for phrase, action in (
            ('caldenarios', 'calendar_open'), ('abre los calendarios', 'calendar_open'),
            ('evento', 'events_open'), ('directorios', 'directory_open'),
            ('pon temas claros', 'theme_light'), ('pon temas oscuros', 'theme_dark'),
        ):
            with self.subTest(phrase=phrase):
                data = self.client.post(self.url, {'command': phrase}).json()
                self.assertEqual((data['status'], data['action'], data['query']), ('understood', action, ''))
        for phrase, name in (
            ('busca a Caldenarios', 'Caldenarios'), ('busca a Evento', 'Evento'),
            ('busca a Ana Directorios Pérez', 'Ana Directorios Pérez'),
            ('busca en los directorios a José', 'José'),
        ):
            with self.subTest(phrase=phrase):
                data = self.client.post(self.url, {'command': phrase}).json()
                self.assertEqual((data['action'], data['query']), ('people_search', name))
        self.assertFalse(UIAction.objects.exists())
        self.assertFalse(Job.objects.exists())
        self.assertFalse(AIUsage.objects.exists())

    def test_agent_context_cannot_use_human_command_interpreter(self):
        with agent_execution():
            self.assertEqual(self.client.post(self.url, {'command': 'calendario'}).status_code, 403)

    def test_repeated_command_fields_rejected(self):
        response = self.client.post(self.url, {'command': ['calendario', 'directorio']})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(UIAction.objects.exists())

    def test_invalid_catalog_fails_without_any_action_or_text_echo(self):
        with patch('apps.jobs.command_language.interpret', side_effect=RuntimeError('invalid private config')):
            response = self.client.post(self.url, {'command': 'calendario'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private', response.content.decode())
        self.assertFalse(UIAction.objects.exists())

    def test_long_or_unicode_control_text_does_not_start_action(self):
        for command in ('abre calendario\u200b', 'a' * 301, 'abre calendario\n'):
            with self.subTest(command_length=len(command)):
                response = self.client.post(self.url, {'command': command})
                self.assertEqual(response.status_code, 200)
                self.assertNotEqual(response.json()['status'], 'understood')
        self.assertFalse(UIAction.objects.exists())
