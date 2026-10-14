from django.test import TestCase
from rest_framework.test import APIClient

from api.models import User


class WorkflowTest(TestCase):
    def test_full_workflow(self):
        def c(u):
            a = APIClient()
            a.force_authenticate(u)
            return a

        owner = User.objects.create_user('o', password='x', role='OWNER')
        pm = User.objects.create_user('p', password='x', role='PROJECT_MANAGER')
        vg = User.objects.create_user('v', password='x', role='VIDEOGRAPHER')
        ed = User.objects.create_user('e', password='x', role='EDITOR')
        owner_api, pm_api, V, E = c(owner), c(pm), c(vg), c(ed)
        res = owner_api.post(
            '/api/v1/users/',
            {'username': 'n', 'first_name': 'N', 'password': 'pw12345!', 'role': 'EDITOR', 'email': 'n@x.io'},
            format='json',
        )
        assert res.status_code == 201, res.data
        assert User.objects.get(username='n').check_password('pw12345!')
        assert 'password' not in res.data
        res = E.patch('/api/v1/users/me/', {'first_name': 'Ed', 'role': 'OWNER', 'password': 'newpw'}, format='json')
        ed.refresh_from_db()
        assert ed.first_name == 'Ed' and ed.role == 'EDITOR' and ed.check_password('newpw')
        assert owner_api.delete(f'/api/v1/users/{owner.id}/').status_code == 400
        assert (
            pm_api.post('/api/v1/clients/', {'client_name': 'Acme', 'contact_person': 'A'}, format='json').status_code
            == 403
        )
        cl = owner_api.post('/api/v1/clients/', {'client_name': 'Acme', 'contact_person': 'A'}, format='json')
        assert cl.status_code == 201, cl.data
        pr = pm_api.post(
            '/api/v1/projects/',
            {'client': cl.data['id'], 'name': 'Launch', 'status': 'active', 'service_fee': 1000},
            format='json',
        )
        assert pr.status_code == 201, pr.data
        assert pr.data['project_manager'] == pm.id and pr.data['client_name'] == 'Acme'
        assert V.post('/api/v1/projects/', {'client': cl.data['id'], 'name': 'x'}, format='json').status_code == 403
        pid = pr.data['id']
        it = pm_api.post(
            '/api/v1/content-items/',
            {
                'project': pid,
                'title': 'Reel 1',
                'content_type': 'Reel',
                'platform': 'Instagram',
                'assigned_videographer': vg.id,
                'assigned_editor': ed.id,
                'status': 'approved',
            },
            format='json',
        )
        assert it.status_code == 201, it.data
        iid = it.data['id']
        assert it.data['editor_name'] == 'Ed' and it.data['status'] == 'planned'
        tk = pm_api.post(
            '/api/v1/tasks/',
            {
                'project': pid,
                'content_item': iid,
                'title': 'Edit reel',
                'task_type': 'Edit',
                'assigned_to': ed.id,
                'due_date': '2020-01-01T00:00:00Z',
                'status': 'completed',
            },
            format='json',
        )
        assert tk.status_code == 201, tk.data
        assert tk.data['status'] == 'not_started' and tk.data['is_overdue']
        tid = tk.data['id']
        assert (
            E.post('/api/v1/tasks/', {'project': pid, 'title': 'x', 'task_type': 'x'}, format='json').status_code == 403
        )
        m = pm_api.get('/api/v1/dashboards/metrics/').data
        assert m['overdue_tasks'] == 1 and m['pipeline']['planned'] == 1, m

        for who in (pm_api, owner_api, E):
            assert who.patch(f'/api/v1/tasks/{tid}/', {'status': 'completed'}, format='json').status_code in (400, 403)
            assert who.patch(f'/api/v1/content-items/{iid}/', {'status': 'approved'}, format='json').status_code in (
                400,
                403,
            )
        assert pm_api.patch(f'/api/v1/tasks/{tid}/', {'title': 'Edit the reel'}, format='json').status_code == 200
        assert E.post(f'/api/v1/content-items/{iid}/submit/', {'submission_note': 'x'}, format='json').status_code in (
            404,
            405,
        )
        assert pm_api.post(
            f'/api/v1/content-items/{iid}/review/', {'action': 'approve'}, format='json'
        ).status_code in (
            404,
            405,
        )
        assert E.post(f'/api/v1/tasks/{tid}/submit/', {'submission_note': 'x'}, format='json').status_code in (404, 405)
        assert pm_api.post(f'/api/v1/tasks/{tid}/start/').status_code == 403
        assert E.post(f'/api/v1/tasks/{tid}/start/').data['status'] == 'in_progress'
        assert E.post(f'/api/v1/tasks/{tid}/start/').status_code == 409
        assert (
            pm_api.post(
                f'/api/v1/content-items/{iid}/publish/', {'post_url': 'https://instagram.com/p/1'}, format='json'
            ).status_code
            == 400
        )
        assert (
            E.post(
                '/api/v1/comments/', {'entity_type': 'ContentItem', 'entity_id': iid, 'message': 'hi'}, format='json'
            ).status_code
            == 201
        )
        assert pm_api.get(f'/api/v1/comments/?entity_type=ContentItem&entity_id={iid}').data[0]['author_name'] == 'Ed'
        assert E.post('/api/v1/notifications/mark_all_read/').status_code == 200
        assert not any(not n['is_read'] for n in E.get('/api/v1/notifications/').data)
        sr = E.get('/api/v1/dashboards/search/?q=reel').data
        assert sr['content_items'] and not sr['clients'], sr
        rep = owner_api.get('/api/v1/dashboards/reports/')
        assert rep.status_code == 200 and sum(rep.data['now']['pipeline'].values()) == 1
        assert pm_api.get('/api/v1/dashboards/reports/').status_code == 403
        assert pm_api.get('/api/v1/contracts/').status_code == 403
        assert (
            owner_api.post('/api/v1/contracts/', {'project': pid, 'contract_number': 'C-1'}, format='json').data[
                'client_name'
            ]
            == 'Acme'
        )


class OrdersAndChatTest(TestCase):
    def test_orders_and_chat(self):
        from api.models import Client, Project, Task

        def c(u):
            a = APIClient()
            a.force_authenticate(u)
            return a

        pm = User.objects.create_user('p', password='x', role='PROJECT_MANAGER', first_name='Pat')
        ed = User.objects.create_user('e', password='x', role='EDITOR', first_name='Eve')
        other = User.objects.create_user('o', password='x', role='EDITOR', email='secret@x.io')
        client = Client.objects.create(client_name='Acme', contact_person='A', email='ceo@acme.io')
        proj = Project.objects.create(
            client=client, name='Launch', project_manager=pm, service_fee=9000, goals='secret goals'
        )
        hidden = Project.objects.create(client=client, name='Other', project_manager=pm)
        mine = Task.objects.create(project=proj, title='Edit reel', task_type='Edit', assigned_to=ed)
        theirs = Task.objects.create(project=proj, title='Other edit', task_type='Edit', assigned_to=other)
        Task.objects.create(project=hidden, title='Hidden', task_type='Edit', assigned_to=other)
        E, pm_api = c(ed), c(pm)

        projects = E.get('/api/v1/projects/').data
        assert [p['name'] for p in projects] == ['Launch'], projects
        assert 'service_fee' not in projects[0] and 'goals' not in projects[0]
        assert [t['title'] for t in E.get('/api/v1/tasks/').data] == ['Edit reel']
        assert E.get(f'/api/v1/tasks/{theirs.id}/').status_code == 404
        assert 'secret@x.io' not in str(E.get('/api/v1/users/').data)
        assert E.get('/api/v1/clients/').data == []

        assert E.post(f'/api/v1/tasks/{mine.id}/start/').status_code == 200
        assert (
            E.patch(f'/api/v1/tasks/{mine.id}/', {'due_date': '2030-01-01T00:00:00Z'}, format='json').status_code == 403
        )
        assert E.patch(f'/api/v1/tasks/{mine.id}/', {'status': 'completed'}, format='json').status_code in (400, 403)

        assert (
            pm_api.post(
                f'/api/v1/chats/{mine.id}/messages/', {'body': 'Deadline moved to Friday'}, format='json'
            ).status_code
            == 201
        )
        assert E.get('/api/v1/chats/unread/').data['unread'] == 1
        assert E.get('/api/v1/tasks/').data[0]['unread_messages'] == 1
        assert E.get(f'/api/v1/chats/{mine.id}/messages/').data[0]['sender_name'] == 'Pat'
        assert E.get('/api/v1/chats/unread/').data['unread'] == 0
        E.post(f'/api/v1/chats/{mine.id}/messages/', {'body': 'OK!'}, format='json')
        threads = pm_api.get('/api/v1/chats/').data
        assert threads[0]['unread'] == 1 and threads[0]['with_name'] == 'Eve' and threads[0]['last_message'] == 'OK!', (
            threads
        )
        assert E.post(f'/api/v1/chats/{theirs.id}/messages/', {'body': 'hi'}, format='json').status_code == 404
        assert E.post(f'/api/v1/chats/{mine.id}/messages/', {'body': '  '}, format='json').status_code == 400

        assert (
            E.post('/api/v1/task-checklist-items/', {'task': mine.id, 'text': 'Color grade'}, format='json').status_code
            == 201
        )
        assert (
            E.post('/api/v1/task-checklist-items/', {'task': theirs.id, 'text': 'x'}, format='json').status_code == 403
        )


class OwnerOnlyBusinessDataTest(TestCase):
    def test_pm_sees_only_assigned_and_no_costs(self):
        from api.models import Client, Project

        def c(u):
            a = APIClient()
            a.force_authenticate(u)
            return a

        owner = User.objects.create_user('ow', password='x', role='OWNER')
        pm = User.objects.create_user('pm', password='x', role='PROJECT_MANAGER')
        mine = Client.objects.create(client_name='Mine', contact_person='A')
        other = Client.objects.create(client_name='Other', contact_person='B')
        Project.objects.create(client=mine, name='P1', project_manager=pm, service_fee=5000)
        Project.objects.create(client=other, name='P2', service_fee=9000)
        owner_api, pm_api = c(owner), c(pm)

        assert [x['client_name'] for x in owner_api.get('/api/v1/clients/').data] == ['Mine', 'Other']
        assert [x['client_name'] for x in pm_api.get('/api/v1/clients/').data] == ['Mine']
        assert pm_api.get(f'/api/v1/clients/{other.id}/').status_code == 404
        assert (
            pm_api.post('/api/v1/clients/', {'client_name': 'New', 'contact_person': 'x'}, format='json').status_code
            == 403
        )
        assert pm_api.patch(f'/api/v1/clients/{mine.id}/', {'client_name': 'Renamed'}, format='json').status_code == 403

        projects = pm_api.get('/api/v1/projects/').data
        assert [p['name'] for p in projects] == ['P1'] and 'service_fee' not in projects[0]
        assert owner_api.get('/api/v1/projects/').data[0]['service_fee'] is not None
        res = pm_api.post('/api/v1/projects/', {'client': mine.id, 'name': 'P3', 'service_fee': 1}, format='json')
        assert res.status_code == 201 and Project.objects.get(name='P3').service_fee is None
        assert 'revenue' not in pm_api.get('/api/v1/dashboards/metrics/').data
        assert pm_api.get('/api/v1/contracts/').status_code == 403
        assert pm_api.get('/api/v1/dashboards/reports/').status_code == 403
        assert not pm_api.get('/api/v1/dashboards/search/?q=other').data['clients']


class WorkspaceCalendarTest(TestCase):
    def test_workspace_and_calendar(self):
        from api.models import Client, ContentItem, Notification, Project, Task

        def c(u):
            a = APIClient()
            a.force_authenticate(u)
            return a

        pm = User.objects.create_user('pm', password='x', role='PROJECT_MANAGER')
        pm2 = User.objects.create_user('pm2', password='x', role='PROJECT_MANAGER')
        ed = User.objects.create_user('ed', password='x', role='EDITOR')
        cl = Client.objects.create(client_name='Acme', contact_person='A')
        proj = Project.objects.create(client=cl, name='Launch', project_manager=pm)
        pm_api, P2, E = c(pm), c(pm2), c(ed)

        page = pm_api.post(
            '/api/v1/workspace-pages/', {'project': proj.id, 'title': 'Brief', 'body': '# Goals'}, format='json'
        )
        assert page.status_code == 201, page.data
        assert P2.get('/api/v1/workspace-pages/').data == []
        assert P2.post('/api/v1/workspace-pages/', {'project': proj.id, 'title': 'x'}, format='json').status_code == 403
        assert E.post('/api/v1/workspace-pages/', {'project': proj.id, 'title': 'x'}, format='json').status_code == 403
        assert E.post('/api/v1/workspace-pages/', {'title': 'My notes'}, format='json').status_code == 201
        assert [p['title'] for p in E.get('/api/v1/workspace-pages/').data] == ['My notes']
        assert (
            pm_api.patch(
                f'/api/v1/workspace-pages/{page.data["id"]}/', {'body': '# Goals\n- grow'}, format='json'
            ).data['updated_by']
            == pm.id
        )

        todo = pm_api.post(
            '/api/v1/workspace-todos/',
            {'project': proj.id, 'title': 'Pick music', 'assignee': ed.id, 'due_date': '2030-01-10', 'priority': 1},
            format='json',
        ).data
        assert Notification.objects.filter(recipient_user=ed, type='todo').exists()
        assert [t['title'] for t in E.get('/api/v1/workspace-todos/?view=mine').data] == ['Pick music']
        assert E.patch(f'/api/v1/workspace-todos/{todo["id"]}/', {'title': 'hack'}, format='json').status_code == 403
        done = E.patch(f'/api/v1/workspace-todos/{todo["id"]}/', {'completed': True}, format='json').data
        assert done['completed'] and done['completed_at']
        assert E.delete(f'/api/v1/workspace-todos/{todo["id"]}/').status_code == 403
        mine = E.post(
            '/api/v1/workspace-todos/', {'title': 'Back up drive', 'due_date': '2030-01-11'}, format='json'
        ).data
        assert E.post('/api/v1/workspace-todos/', {'title': 'x', 'assignee': pm.id}, format='json').status_code == 400
        assert mine['id'] not in [t['id'] for t in pm_api.get('/api/v1/workspace-todos/').data]

        ev = E.post(
            '/api/v1/calendar-events/',
            {
                'title': 'Gear check',
                'start': '2030-01-09T09:00:00Z',
                'end': '2030-01-09T10:00:00Z',
                'attendees': [pm.id],
            },
            format='json',
        ).data
        assert ev['attendees'] == [ed.id]
        shoot = pm_api.post(
            '/api/v1/calendar-events/',
            {
                'project': proj.id,
                'title': 'Studio shoot',
                'start': '2030-01-12T08:00:00Z',
                'end': '2030-01-12T12:00:00Z',
                'attendees': [ed.id],
            },
            format='json',
        )
        assert shoot.status_code == 201 and Notification.objects.filter(recipient_user=ed, type='event').exists()
        assert E.patch(f'/api/v1/calendar-events/{shoot.data["id"]}/', {'title': 'x'}, format='json').status_code == 403
        assert (
            pm_api.post(
                '/api/v1/calendar-events/',
                {'title': 'bad', 'start': '2030-01-12T08:00:00Z', 'end': '2030-01-11T08:00:00Z'},
                format='json',
            ).status_code
            == 400
        )

        Task.objects.create(
            project=proj, title='Edit reel', task_type='Edit', assigned_to=ed, due_date='2030-01-15T10:00:00Z'
        )
        ContentItem.objects.create(
            project=proj,
            title='Reel',
            content_type='Reel',
            platform='Instagram',
            target_publish_date='2030-01-20T10:00:00Z',
        )
        feed = lambda cl: sorted(
            (i['type'], i['title']) for i in cl.get('/api/v1/calendar/?start=2030-01-01&end=2030-01-31').data
        )
        assert feed(pm_api) == [
            ('event', 'Studio shoot'),
            ('order', 'Edit reel'),
            ('publish', 'Publish: Reel'),
            ('todo', 'Pick music'),
        ], feed(pm_api)
        assert feed(E) == [
            ('event', 'Gear check'),
            ('event', 'Studio shoot'),
            ('order', 'Edit reel'),
            ('todo', 'Back up drive'),
            ('todo', 'Pick music'),
        ], feed(E)
        assert feed(P2) == []
        orders = [i for i in E.get('/api/v1/calendar/?start=2030-01-01&end=2030-01-31').data if i['type'] == 'order']
        assert orders[0]['can_move'] is False
        assert pm_api.get('/api/v1/calendar/?start=2030-01-01&end=2030-06-01').status_code == 400


class HealthCheckTest(TestCase):
    def test_health_page_never_touches_the_database(self):
        with self.assertNumQueries(0):
            r = self.client.get('/health/')
        self.assertEqual((r.status_code, r.content), (200, b'ok'))
