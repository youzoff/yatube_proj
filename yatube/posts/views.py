import core.views as cv

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.cache import cache_page

from .forms import PostForm, CommentForm
from .models import Post, Group, User, Follow

POST_ON_PAGE = 10
POST_ON_PROFILE = 10
CHAR_IN_POST = 200


@cache_page(1 * 20, key_prefix='index_page')
def index(request):
    page_obj = cv.page_paginator(request, Post.objects.all(), POST_ON_PAGE)
    context = {
        'page_obj': page_obj,
        'char_br': CHAR_IN_POST,
    }
    return render(request, 'posts/index.html', context)


def group_posts(request, slug):
    group = get_object_or_404(Group, slug=slug)
    page_obj = cv.page_paginator(request, group.posts.all(), POST_ON_PAGE)
    context = {
        'group': group,
        'page_obj': page_obj,
        'char_br': CHAR_IN_POST,
    }
    return render(request, 'posts/group_list.html', context)


def profile(request, username):
    author = get_object_or_404(User, username=username)
    page_obj = cv.page_paginator(request, author.posts.all(), POST_ON_PROFILE)
    following = False
    if request.user.is_authenticated:
        following = (Follow.objects.filter(
            user=request.user, author=author).exists())
    context = {
        'author': author,
        'page_obj': page_obj,
        'char_br': CHAR_IN_POST,
        'following': following,
    }
    return render(request, 'posts/profile.html', context)


def post_detail(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST or None)
    comments = post.comments.all()
    is_edit = True if post.author == request.user else False
    context = {
        'post': post,
        'is_edit': is_edit,
        'form': form,
        'comments': comments,
    }
    return render(request, 'posts/post_detail.html', context)


@login_required
def post_create(request):
    if request.method == 'POST':
        form = PostForm(
            request.POST or None,
            files=request.FILES or None
        )
        if form.is_valid():
            temp_form = form.save(commit=False)
            temp_form.author = request.user
            temp_form.save()
            return redirect('posts:profile', temp_form.author)
        return render(request, 'posts/create_post.html', {'form': form})

    form = PostForm()
    return render(request, 'posts/create_post.html', {'form': form})


@login_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author != request.user:
        return redirect('posts:post_detail', post_id)
    form = PostForm(
        request.POST or None,
        files=request.FILES or None,
        instance=post
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('posts:post_detail', post_id)
    context = {
        'form': form,
        'is_edit': True,
        'post': post,
    }
    return render(request, 'posts/create_post.html', context)


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('posts:post_detail', post_id=post_id)


@login_required
def follow_index(request):
    posts = Post.objects.filter(author__following__user=request.user)
    page_obj = cv.page_paginator(request, posts, POST_ON_PAGE)
    context = {
        'page_obj': page_obj,
        'char_br': CHAR_IN_POST,
    }
    return render(request, 'posts/follow.html', context)


@login_required
def profile_follow(request, username):
    author = get_object_or_404(User, username=username)
    user = request.user
    following_exists = Follow.objects.filter(
        author=author,
        user=user
    ).exists()
    if user != author and not following_exists:
        Follow.objects.create(
            user=request.user,
            author=author
        )
    return redirect('posts:profile', username)


@login_required
def profile_unfollow(request, username):
    author = get_object_or_404(User, username=username)
    Follow.objects.get(user=request.user, author=author).delete()
    return redirect('posts:profile', username)
