from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from http import HTTPStatus

from ..models import Group, Post

User = get_user_model()


class PostsURLTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='test_user')
        cls.user_not_author = User.objects.create_user(
            username='test_user_not_author'
        )
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            group=cls.group,
            text='Тестовый пост тестового пользователя в тестовой группе',
        )

    def setUp(self):
        self.guest_client = Client()
        self.auth_client = Client()
        self.auth_client_not_author = Client()
        self.auth_client.force_login(PostsURLTests.user)
        self.auth_client_not_author.force_login(PostsURLTests.user_not_author)
        cache.clear()

    def test_urls_exists(self):
        """Проверяем доступность страниц приложения Posts."""
        group = PostsURLTests.group
        user = PostsURLTests.user
        post = PostsURLTests.post

        url_names = [
            '/',
            f'/group/{group.slug}/',
            f'/profile/{user.username}/',
            f'/posts/{post.pk}/',
        ]

        for address in url_names:
            with self.subTest(address=address):
                guest_response = self.guest_client.get(address, follow=True)
                auth_response = self.auth_client.get(address)

                self.assertEqual(guest_response.status_code, HTTPStatus.OK)
                self.assertEqual(auth_response.status_code, HTTPStatus.OK)

    def test_post_edit_url_exists(self):
        """
        Проверяем доступность страницы редактирования поста приложения Posts.
        """
        post = PostsURLTests.post
        address = reverse(
            'posts:post_edit',
            kwargs={'post_id': post.pk}
        )

        guest_response = self.guest_client.get(address)
        auth_response = self.auth_client.get(address)
        auth_not_author_response = (
            self.auth_client_not_author.get(address)
        )

        self.assertRedirects(
            guest_response,
            (reverse('users:login') + '?next=' + reverse(
                'posts:post_edit', kwargs={'post_id': self.post.pk}))
        )
        self.assertEqual(auth_response.status_code, HTTPStatus.OK)
        self.assertEqual(
            auth_not_author_response.url,
            reverse('posts:post_detail',
                    kwargs={'post_id': post.pk}
                    )
        )

    def test_create_post_url_exists(self):
        """Проверяем доступность страницы создания поста приложения Posts."""
        address = f'{"/create/"}'

        guest_response = self.guest_client.get(address)
        auth_response = self.auth_client.get(address)

        self.assertRedirects(
            guest_response,
            f'{"/auth/login/?next=/create/"}'
        )
        self.assertEqual(auth_response.status_code, HTTPStatus.OK)

    def test_404_error_return_for_unexisting_page(self):
        """
        Проверяем возврат ошибки 404 при запросе к несуществующей странице.
        """
        address = f'{"/something_page/"}'

        guest_response = self.guest_client.get(address, follow=True)
        auth_response = self.auth_client.get(address)

        self.assertEqual(guest_response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(auth_response.status_code, HTTPStatus.NOT_FOUND)

    def test_urls_uses_correct_template(self):
        """Проверяем шаблоны приложения Posts."""
        group = PostsURLTests.group
        user = PostsURLTests.user
        post = PostsURLTests.post
        url_templates_names = {
            '/': 'posts/index.html',
            f'/group/{group.slug}/': 'posts/group_list.html',
            f'/profile/{user.username}/': 'posts/profile.html',
            f'/posts/{post.pk}/': 'posts/post_detail.html',
            f'/posts/{post.pk}/edit/': 'posts/create_post.html',
            '/create/': 'posts/create_post.html',
        }
        for address, template in url_templates_names.items():
            with self.subTest(address=address):
                response = self.auth_client.get(address)
                self.assertTemplateUsed(response, template)
