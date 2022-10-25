import asyncio
from platform import system
import argparse
from pathlib import Path
from typing import Optional

from .configs import FeedConfigLoader
from .feeds import GameFeedCollection


async def create_feeds(config_path: Optional[Path] = None):
    # fallback path defined in config loader if no path given
    config_loader = FeedConfigLoader(config_path)

    if not config_loader.path.exists():
        await config_loader.create_default_config_file()
        print('Default config file created at "{}"!'.format(config_loader.path))
        return

    feed_configs = await config_loader.get_all_feed_configs()

    game_feed = GameFeedCollection.from_configs(feed_configs)
    await game_feed.create_feeds()


def cli():
    if system() == "Windows":
        # default policy not working on windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    arg_parser = argparse.ArgumentParser(
        prog="hoyolab-rss-feeds", description="Generate Hoyolab RSS feeds."
    )

    arg_parser.add_argument(
        "-c", "--config-path", help="path to the TOML config file", type=Path
    )

    args = arg_parser.parse_args()

    asyncio.run(create_feeds(args.config_path))


if __name__ == "__main__":
    cli()
