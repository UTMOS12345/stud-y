import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Card, Column


class KanbanTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.other = User.objects.create_user(username='o', email='o@o.com', password='pw12345!x')
        self.client.force_login(self.user)
        self.url = reverse('kanban')
        self.todo = Column.objects.create(user=self.user, name='To do', position=0)
        self.done = Column.objects.create(user=self.user, name='Done', position=1)
        self.theirs = Column.objects.create(user=self.other, name='Theirs')

    def card(self, title='A', column=None, position=0):
        return Card.objects.create(column=column or self.todo, title=title, position=position)

    def move(self, card, column, index):
        return self.client.post(reverse('kanban_move_card'),
                                json.dumps({'card': card, 'column': column, 'index': index}),
                                content_type='application/json')

    def titles(self, column):
        return list(column.cards.values_list('title', flat=True))


class BoardPageTests(KanbanTestCase):
    def test_new_user_gets_three_columns(self):
        Column.objects.filter(user=self.user).delete()
        response = self.client.get(self.url)
        self.assertEqual([c.name for c in response.context['columns']], ['To do', 'Doing', 'Done'])

    def test_marked_experimental_and_linked_from_the_sidebar(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Experimental')
        self.assertContains(response, f'href="{self.url}"')

    def test_only_your_board(self):
        Card.objects.create(column=self.theirs, title='Their secret')
        self.assertNotContains(self.client.get(self.url), 'Their secret')

    def test_titles_are_escaped(self):
        self.card('<script>x</script>')
        self.assertNotContains(self.client.get(self.url), '<script>x</script>')

    def test_query_count_does_not_grow_with_cards(self):
        for n in range(8):
            self.card(f'c{n}', position=n)
        with self.assertNumQueries(5):  # session, user, profile, columns, cards
            self.client.get(self.url)

    def test_needs_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)


class CardTests(KanbanTestCase):
    def test_new_cards_go_last(self):
        url = reverse('kanban_add_card', args=[self.todo.id])
        self.assertEqual(self.client.post(url, {'title': 'First'}).status_code, 201)
        response = self.client.post(url, {'title': 'Second'})
        self.assertIn('Second', response.json()['html'])
        self.assertEqual(self.titles(self.todo), ['First', 'Second'])

    def test_blank_title_is_refused(self):
        response = self.client.post(reverse('kanban_add_card', args=[self.todo.id]), {'title': '   '})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Card.objects.exists())

    def test_edit(self):
        card = self.card()
        response = self.client.post(reverse('kanban_edit_card', args=[card.id]),
                                    {'title': 'B', 'description': 'more', 'color': '#10B981'})
        self.assertEqual(response.status_code, 200)
        card.refresh_from_db()
        self.assertEqual((card.title, card.description, card.color), ('B', 'more', '#10B981'))

    def test_color_is_optional_but_checked(self):
        card = self.card()
        url = reverse('kanban_edit_card', args=[card.id])
        self.assertEqual(self.client.post(url, {'title': 'B', 'color': ''}).status_code, 200)
        self.assertEqual(self.client.post(url, {'title': 'B', 'color': 'red;x'}).status_code, 400)

    def test_edit_can_change_the_column(self):
        self.card('Old', self.done)
        card = self.card('New')
        response = self.client.post(reverse('kanban_edit_card', args=[card.id]), {'title': 'New', 'column': self.done.id})
        self.assertEqual(response.json()['column'], self.done.id)
        self.assertEqual(self.titles(self.done), ['Old', 'New'])

    def test_delete(self):
        card = self.card()
        self.assertEqual(self.client.post(reverse('kanban_delete_card', args=[card.id])).status_code, 200)
        self.assertFalse(Card.objects.exists())


class MoveTests(KanbanTestCase):
    def test_reorder_inside_a_column(self):
        a, b, c = self.card('a', position=0), self.card('b', position=1), self.card('c', position=2)
        self.assertEqual(self.move(c.id, self.todo.id, 0).status_code, 200)
        self.assertEqual(self.titles(self.todo), ['c', 'a', 'b'])

    def test_move_to_another_column_at_a_place(self):
        x, y = self.card('x', self.done, 0), self.card('y', self.done, 1)
        card = self.card('new')
        self.move(card.id, self.done.id, 1)
        self.assertEqual(self.titles(self.done), ['x', 'new', 'y'])
        self.assertEqual(self.titles(self.todo), [])

    def test_index_is_clamped(self):
        card = self.card('a')
        self.card('b', self.done)
        self.assertEqual(self.move(card.id, self.done.id, 99).status_code, 200)
        self.assertEqual(self.titles(self.done), ['b', 'a'])
        self.assertEqual(self.move(card.id, self.done.id, -5).status_code, 200)
        self.assertEqual(self.titles(self.done), ['a', 'b'])

    def test_bad_bodies(self):
        card = self.card()
        for body in ['[]', '{}', 'nope', json.dumps({'card': 'x', 'column': self.done.id, 'index': 0}),
                     json.dumps({'card': card.id, 'column': self.done.id, 'index': True})]:
            response = self.client.post(reverse('kanban_move_card'), body, content_type='application/json')
            self.assertEqual(response.status_code, 400, body)

    def test_cannot_touch_someone_elses_board(self):
        mine = self.card('mine')
        theirs = Card.objects.create(column=self.theirs, title='theirs')
        self.assertEqual(self.move(theirs.id, self.todo.id, 0).status_code, 404)
        self.assertEqual(self.move(mine.id, self.theirs.id, 0).status_code, 404)
        for name in ('kanban_edit_card', 'kanban_delete_card'):
            self.assertEqual(self.client.post(reverse(name, args=[theirs.id]), {'title': 'x'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('kanban_edit_card', args=[mine.id]),
                                          {'title': 'x', 'column': self.theirs.id}).status_code, 404)
        for name in ('kanban_rename_column', 'kanban_delete_column', 'kanban_add_card'):
            self.assertEqual(self.client.post(reverse(name, args=[self.theirs.id]), {'name': 'x', 'title': 'x'}).status_code, 404)

    def test_needs_post(self):
        self.assertEqual(self.client.get(reverse('kanban_move_card')).status_code, 405)


class ColumnTests(KanbanTestCase):
    def test_add_goes_last(self):
        self.assertEqual(self.client.post(reverse('kanban_add_column'), {'name': 'Later'}).status_code, 200)
        self.assertEqual(list(Column.objects.filter(user=self.user).values_list('name', flat=True)), ['To do', 'Done', 'Later'])

    def test_limit(self):
        for n in range(10):
            Column.objects.create(user=self.user, name=str(n))
        self.assertEqual(self.client.post(reverse('kanban_add_column'), {'name': 'x'}).status_code, 400)

    def test_rename(self):
        self.client.post(reverse('kanban_rename_column', args=[self.todo.id]), {'name': 'Next'})
        self.todo.refresh_from_db()
        self.assertEqual(self.todo.name, 'Next')

    def test_blank_name_is_refused(self):
        self.assertEqual(self.client.post(reverse('kanban_add_column'), {'name': ' '}).status_code, 400)

    def test_delete_takes_its_cards(self):
        self.card()
        self.assertEqual(self.client.post(reverse('kanban_delete_column', args=[self.todo.id])).status_code, 200)
        self.assertFalse(Card.objects.exists())

    def test_last_column_stays(self):
        self.client.post(reverse('kanban_delete_column', args=[self.todo.id]))
        response = self.client.post(reverse('kanban_delete_column', args=[self.done.id]))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Column.objects.filter(pk=self.done.pk).exists())
