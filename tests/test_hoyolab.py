from datetime import datetime
from datetime import timezone

import langdetect
import pytest
from aiohttp import ClientSession
from pytest_mock import MockFixture

from hoyolabrssfeeds import errors
from hoyolabrssfeeds import hoyolab
from hoyolabrssfeeds import models
from .conftest import validate_hoyolab_post

# force consistent results
langdetect.DetectorFactory.seed = 42


# ---- FIXTURES ----

@pytest.fixture(params=[g for g in models.Game])
def game(request) -> models.Game:
    return request.param


@pytest.fixture(params=[c for c in models.FeedItemCategory])
def category(request) -> models.FeedItemCategory:
    return request.param


@pytest.fixture(params=[la for la in models.Language])
def language(request) -> models.Language:
    return request.param


# ---- TESTS ----

async def test_api_post_endpoint(client_session: ClientSession, game: models.Game):
    post_id = get_post_id(game)
    api = hoyolab.HoyolabNews(game)
    post = await api.get_post(client_session, post_id)

    validate_hoyolab_post(post, is_full_post=True)


async def test_api_list_endpoint(
        client_session: ClientSession,
        game: models.Game,
        category: models.FeedItemCategory
):
    api = hoyolab.HoyolabNews(game)
    news_list = await api.get_news_list(client_session, category, 2)

    assert type(news_list) is list
    assert len(news_list) > 0

    for post in news_list:
        validate_hoyolab_post(post, is_full_post=False)


@pytest.mark.xfail(reason='not accurate for all languages')
async def test_language(client_session: ClientSession, language: models.Language):
    # NOTE: The list endpoint is not checked due to insufficient text.
    # The text of the list endpoint is also not used for the feeds.

    api = hoyolab.HoyolabNews(models.Game.GENSHIN, language)

    # pure text post for a decent recognition
    post_id = 7156359
    post = await api.get_post(client_session, post_id)
    content = post['post']['content']

    # only use first letters of code if not chinese
    # https://github.com/Mimino666/langdetect
    expected = language.lower()
    if not expected.startswith('zh'):
        expected = expected.partition('-')[0]

    assert langdetect.detect(content) == expected


async def test_request_errors(client_session: ClientSession):
    api = hoyolab.HoyolabNews(models.Game.GENSHIN)

    # request error
    error_url = 'https://httpbin.org/status/500'
    with pytest.raises(errors.HoyolabApiError, match='Could not request'):
        await api._request(client_session, {}, error_url)

    # json decode error
    error_url = 'https://httpbin.org/html'
    with pytest.raises(errors.HoyolabApiError, match='Could not decode'):
        await api._request(client_session, {}, error_url)

    # unexpected response
    error_url = 'https://httpbin.org/json'
    with pytest.raises(errors.HoyolabApiError, match='Unexpected response'):
        await api._request(client_session, {}, error_url)

    # hoyolab error code
    error_url = 'https://bbs-api-os.hoyolab.com/community/post/wapi/getNewsList'
    with pytest.raises(errors.HoyolabApiError):
        await api._request(client_session, {}, error_url)


async def test_get_latest_item_metas(mocker: MockFixture, client_session):
    posts = [
        {
            'post': {
                'post_id': '42',
                'created_at': 1645564944
            },
            'last_modify_time': 0
        },
        {
            'post': {
                'post_id': '41',
                'created_at': 1645564942
            },
            'last_modify_time': 1645564943
        },
    ]

    mocked_news_list = mocker.patch(
        'hoyolabrssfeeds.hoyolab.HoyolabNews.get_news_list',
        spec=True,
        return_value=posts
    )

    api = hoyolab.HoyolabNews(models.Game.GENSHIN)
    metas = await api.get_latest_item_metas(client_session, models.FeedItemCategory.INFO, 2)

    expected = [
        models.FeedItemMeta(id=42, last_modified=datetime.fromtimestamp(1645564944, tz=timezone.utc)),
        models.FeedItemMeta(id=41, last_modified=datetime.fromtimestamp(1645564943, tz=timezone.utc)),
    ]

    mocked_news_list.assert_awaited()
    mocked_news_list.assert_called_with(models.FeedItemCategory.INFO, 2, client_session)

    assert metas == expected


async def test_get_feed_item(mocker: MockFixture, feed_item: models.FeedItem, client_session):
    post = {
        'post': {
            'post_id': str(feed_item.id),
            'subject': feed_item.title,
            'content': feed_item.content,
            'official_type': feed_item.category.value,
            'created_at': int(feed_item.published.timestamp())
        },
        'user': {
            'nickname': feed_item.author
        },
        'last_modify_time': int(feed_item.updated.timestamp()),
        'image_list': [
            {
                'url': str(feed_item.image)
            }
        ]
    }

    mocked_get_post = mocker.patch(
        'hoyolabrssfeeds.hoyolab.HoyolabNews.get_post',
        spec=True,
        return_value=post
    )

    api = hoyolab.HoyolabNews(models.Game.GENSHIN)
    fetched_item = await api.get_feed_item(client_session, feed_item.id)

    mocked_get_post.assert_awaited()
    mocked_get_post.assert_called_with(feed_item.id, client_session)

    assert fetched_item == feed_item


# ---- HELPER FUNCTIONS ----

def get_post_id(game: models.Game) -> int:
    post_ids = {
        models.Game.HONKAI: 4361615,
        models.Game.GENSHIN: 7156359,
        models.Game.THEMIS: 4283335,
        models.Game.STARRAIL: 3746616,
        models.Game.ZENLESS: 4729212
    }

    return post_ids[game]
