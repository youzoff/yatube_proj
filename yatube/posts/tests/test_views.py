import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django import forms

from ..models import Group, Post, Follow

User = get_user_model()

TEST_POST_TEXT = 'Тестовый пост тестового пользователя.'
POSTS_ON_PAGE_1 = 10
POSTS_ON_PAGE_2 = 3
POSTS_COUNT = 13
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostsViewsTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='test_user')
        cls.group_1 = Group.objects.create(
            title='Тестовая группа 1',
            slug='test-slug-1',
            description='Тестовое описание группы 1',
        )
        cls.group_2 = Group.objects.create(
            title='Тестовая группа 2',
            slug='test-slug-2',
            description='Тестовое описание группы 2',
        )

        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )

        cls.post = Post.objects.create(
            author=cls.user,
            group=cls.group_1,
            text=TEST_POST_TEXT,
            image=uploaded,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.auth_client = Client()
        self.auth_client.force_login(self.user)
        cache.clear()

    def test_posts_urls_uses_correct_templates(self):
        """URL-адреса используют соответствующие шаблоны в приложении Posts."""
        group = self.group_1
        user = self.user
        post = self.post

        urls_templates_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse(
                'posts:group_list',
                kwargs={'slug': group.slug}
            ): 'posts/group_list.html',
            reverse(
                'posts:profile',
                kwargs={'username': user.username}
            ): 'posts/profile.html',
            reverse(
                'posts:post_detail',
                kwargs={'post_id': post.pk}
            ): 'posts/post_detail.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse(
                'posts:post_edit',
                kwargs={'post_id': post.pk}
            ): 'posts/create_post.html',
        }

        for url, template in urls_templates_names.items():
            with self.subTest(url=url):
                response = self.auth_client.get(url)
                self.assertTemplateUsed(response, template)

    def test_posts_main_pages_show_correct_context(self):
        """
        Шаблоны index, group_list, profile, post_detail
        сформированы с правильным контекстом.
        """
        group = self.group_1
        user = self.user
        post = self.post
        post_count = Post.objects.count()
        urls = (
            ('posts:index', None),
            ('posts:group_list', {'slug': group.slug}),
            ('posts:profile', {'username': user.username}),
            ('posts:post_detail', {'post_id': post.pk}),
        )
        for name, kwargs in urls:
            response = self.auth_client.get(reverse(name, kwargs=kwargs))
            if 'post_detail' in name:
                post_context = response.context['post']
            else:
                post_context = response.context['page_obj'][0]
            self.assertEqual(post_context, post)

            post_context_fields = {
                post_context.author.username: 'test_user',
                post_context.group.title: 'Тестовая группа 1',
                post_context.text: TEST_POST_TEXT,
                post_context.image: post.image,
                post_context.author.posts.count(): post_count,
            }
            for field, value in post_context_fields.items():
                with self.subTest(field=field):
                    self.assertEqual(field, value,
                                     f'Ошибка в контексте шаблона {name}')

    def test_posts_create_edit_pages_show_correct_context(self):
        """Шаблон create_post сформирован с правильным контекстом."""
        post = self.post
        urls = (
            ('posts:post_create', None),
            ('posts:post_edit', {'post_id': post.pk}),
        )
        for name, kwargs in urls:
            response = self.auth_client.get(reverse(name, kwargs=kwargs))
            form_fields = {
                'text': forms.fields.CharField,
                'group': forms.fields.ChoiceField,
            }

            for value, expected in form_fields.items():
                with self.subTest(value=value):
                    form_field = response.context.get('form').fields.get(value)
                    self.assertIsInstance(form_field, expected)

    def test_posts_correct_appear(self):
        """Проверка, что созданный пост появляется на нужных страницах."""
        group = self.group_1
        user = self.user
        post = self.post

        pages_names = (
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': group.slug}),
            reverse('posts:profile', kwargs={'username': user.username}),
        )
        for page in pages_names:
            with self.subTest(page=page):
                response = self.auth_client.get(page)
                context_posts = response.context['page_obj']
                self.assertIn(post, context_posts)

    def test_posts_correct_not_appear(self):
        """
        Проверка, что созданный пост не появляется
        в группе к которой он не принадлежит.
        """
        group = self.group_2
        post = self.post
        page = reverse('posts:group_list', kwargs={'slug': group.slug})
        response = self.auth_client.get(page)
        context_posts = response.context.get('page_obj')
        self.assertNotIn(post, context_posts)

    def test_posts_index_cache(self):
        """Проверка работы кэширования главной страницы."""
        index_url = reverse('posts:index')
        test_post = Post.objects.create(
            author=self.user,
            group=self.group_1,
            text=TEST_POST_TEXT,
        )
        response_1 = self.auth_client.get(index_url)
        test_post.delete()
        response_2 = self.auth_client.get(index_url)
        cache.clear()
        response_3 = self.auth_client.get(index_url)
        self.assertEqual(response_1.content, response_2.content)
        self.assertNotEqual(response_2.content, response_3.content)


class PaginatorViewsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='test_user')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание группы',
        )
        post_objs = (Post(
            author=cls.user,
            group=cls.group,
            text=f'Тестовый пост {i + 1}',
        ) for i in range(POSTS_COUNT))
        Post.objects.bulk_create(post_objs)

    def setUp(self):
        self.auth_client = Client()
        self.auth_client.force_login(self.user)
        cache.clear()

    def test_index_correct_paginator_work(self):
        """Проверка работы паджинатора в шаблонах приложения Posts."""
        group = self.group
        user = self.user
        urls = (
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': group.slug}),
            reverse('posts:profile', kwargs={'username': user.username}),
        )
        for url in urls:
            pages_posts = {
                url + '': POSTS_ON_PAGE_1,
                url + '?page=2': POSTS_ON_PAGE_2,
            }
            for page, posts_on_page in pages_posts.items():
                with self.subTest(page=page):
                    response = self.auth_client.get(page)
                    self.assertEqual(
                        len(response.context['page_obj']),
                        posts_on_page
                    )

    def test_paginator_show_correct_context(self):
        """Паджинатор формирует шаблоны с правильным контекстом."""
        group = self.group
        urls = (
            ('posts:index', None),
            ('posts:group_list', {'slug': group.slug}),
        )
        for name, kwargs in urls:
            response = self.auth_client.get(reverse(name, kwargs=kwargs))
            posts_context = response.context.get('page_obj')
            for post in posts_context:
                post_fields = {
                    post.author.username: 'test_user',
                    post.group.title: 'Тестовая группа',
                    post.text: f'Тестовый пост {post.id}',
                }
                for field, value in post_fields.items():
                    with self.subTest(field=field):
                        self.assertEqual(field, value)


class FollowTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='test_user')
        cls.author = User.objects.create_user(username='test_author')

    def setUp(self):
        self.auth_client = Client()
        self.auth_client.force_login(self.user)
        cache.clear()

    def test_posts_follow(self):
        """
        Авторизованный пользователь может
        подписаться на других пользователей.
        """
        follow_count_1 = Follow.objects.filter(
            user=self.user, author=self.author).count()
        self.auth_client.get(
            reverse(
                'posts:profile_follow',
                kwargs={'username': self.author.username}
            )
        )
        follow_count_2 = Follow.objects.filter(
            user=self.user, author=self.author).count()
        self.assertEqual(follow_count_1 + 1, follow_count_2)

    def test_posts_unfollow(self):
        """
        Авторизованный пользователь может
        отписаться от других пользователей.
        """
        Follow.objects.create(user=self.user, author=self.author)
        follow_count_1 = Follow.objects.filter(
            user=self.user, author=self.author).count()
        self.auth_client.get(
            reverse(
                'posts:profile_unfollow',
                kwargs={'username': self.author.username}
            )
        )
        follow_count_2 = Follow.objects.filter(
            user=self.user, author=self.author).count()
        self.assertEqual(follow_count_1 - 1, follow_count_2)

    def test_posts_follow_correct_appear(self):
        """
        Новая запись автора появляется
        только у тех пользователей, кто на него подписан.
        """
        post = Post.objects.create(
            author=self.author,
            text=TEST_POST_TEXT
        )
        url = reverse('posts:follow_index')

        response = self.auth_client.get(url)
        self.assertNotIn(post, response.context['page_obj'],
                         'Этого поста здесь быть не должно.')

        Follow.objects.create(user=self.user, author=self.author)
        response = self.auth_client.get(url)
        self.assertIn(post, response.context['page_obj'],
                      'Здесь должен быть пост автора.')

    def test_posts_follow_yourself(self):
        """Автор не может подписаться на самого себя."""
        self.auth_client.force_login(self.author)
        test_count_1 = Follow.objects.filter(
            user=self.author, author=self.author).count()

        self.auth_client.get(
            reverse(
                'posts:profile_follow',
                kwargs={'username': self.author.username}
            )
        )

        test_count_2 = Follow.objects.filter(
            user=self.author, author=self.author).count()
        self.assertEqual(test_count_1, test_count_2)
