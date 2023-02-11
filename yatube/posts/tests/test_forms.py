import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Group, Post, Comment

User = get_user_model()

TEST_POST_TEXT = 'Тестовый пост'
TEST_POST_EDIT_TEXT = 'Изменённый тестовый пост'
TEST_COMMENT_TEXT = 'Тестовый комментарий под тестовым постом'
TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostsFormsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='test_user')
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

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.auth_client = Client()
        self.auth_client.force_login(PostsFormsTests.user)

    def test_posts_create_post(self):
        """Валидная форма создает запись в Post."""
        posts_count = Post.objects.count()

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

        form_data = {
            'text': TEST_POST_TEXT,
            'group': self.group.pk,
            'image': uploaded,
        }

        response = self.auth_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )

        self.assertRedirects(
            response,
            reverse('posts:profile', kwargs={'username': self.user.username})
        )
        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertTrue(
            Post.objects.filter(
                text=TEST_POST_TEXT,
                group=self.group,
                author=self.user,
                image='posts/small.gif',
            ).exists()
        )

    def test_posts_edit_post(self):
        """Валидная форма редактирует запись в Post."""
        posts_count = Post.objects.count()

        form_data = {
            'text': TEST_POST_EDIT_TEXT,
            'group': self.group.pk,
        }

        self.auth_client.post(
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk}),
            data=form_data,
        )

        self.assertEqual(Post.objects.count(), posts_count)
        self.assertEqual(
            Post.objects.get(pk=self.post.pk).text,
            TEST_POST_EDIT_TEXT
        )

    def test_posts_comments_by_auth_client(self):
        """Только авторизованный пользователь может оставлять комментарии."""
        comments_count = Comment.objects.count()
        guest_client = Client()
        form_data = {
            'text': TEST_COMMENT_TEXT,
        }
        page = reverse('posts:add_comment', kwargs={'post_id': self.post.pk})
        redirect_page = {
            'guest': reverse('users:login') + '?next=' + reverse(
                'posts:add_comment', kwargs={'post_id': self.post.pk}),
            'auth': reverse('posts:post_detail',
                            kwargs={'post_id': self.post.pk}),
        }

        guest_response = guest_client.post(page, data=form_data, follow=True)
        self.assertRedirects(guest_response, redirect_page['guest'])
        self.assertEqual(Comment.objects.count(), comments_count)

        auth_response = self.auth_client.post(
            page, data=form_data, follow=True
        )
        self.assertRedirects(auth_response, redirect_page['auth'])
        self.assertEqual(Comment.objects.count(), comments_count + 1)

        last_comment = auth_response.context['comments'][0]
        self.assertEqual(last_comment.text, form_data['text'])
        self.assertEqual(last_comment.post, self.post)
        self.assertEqual(last_comment.author, self.user)
