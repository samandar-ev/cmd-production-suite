from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Client, Project, User


class ProjectRulesTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('boss', password='x', role='OWNER')
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.client_obj = Client.objects.create(client_name='Acme', contact_person='A')

    def test_owner_can_be_project_manager(self):
        r = self.api.post(
            '/api/v1/projects/',
            {'name': 'P', 'client': self.client_obj.id, 'project_manager': self.owner.id},
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.data)

    def test_delete_only_from_archive(self):
        p = Project.objects.create(name='P', client=self.client_obj, status='active')
        r = self.api.delete(f'/api/v1/projects/{p.id}/')
        self.assertEqual(r.status_code, 400)
        self.assertTrue(Project.objects.filter(pk=p.pk).exists())
        self.api.patch(f'/api/v1/projects/{p.id}/', {'status': 'archived'}, format='json')
        self.assertEqual(self.api.delete(f'/api/v1/projects/{p.id}/').status_code, 204)
        self.assertFalse(Project.objects.filter(pk=p.pk).exists())


class NoteTemplatesTest(TestCase):
    def test_anyone_saves_note_templates_but_only_author_deletes(self):
        ed = User.objects.create_user('ed', password='x', role='EDITOR')
        vg = User.objects.create_user('vg', password='x', role='VIDEOGRAPHER')
        a, b = APIClient(), APIClient()
        a.force_authenticate(ed)
        b.force_authenticate(vg)
        r = a.post(
            '/api/v1/templates/',
            {'name': 'My edit checklist', 'type': 'note', 'content_json_or_text': '- [ ] Colour'},
            format='json',
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(b.get('/api/v1/templates/?type=note').data), 1)
        self.assertEqual(b.delete(f'/api/v1/templates/{r.data["id"]}/').status_code, 403)
        self.assertEqual(a.delete(f'/api/v1/templates/{r.data["id"]}/').status_code, 204)
        self.assertEqual(
            a.post(
                '/api/v1/templates/', {'name': 'C', 'type': 'contract', 'content_json_or_text': 'x'}, format='json'
            ).status_code,
            403,
        )
