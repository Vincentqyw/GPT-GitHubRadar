import argparse
import logging
import time
from collections import namedtuple
from datetime import datetime

import pandas as pd
import yaml
from github import Github, GithubException
from github.GithubException import RateLimitExceededException

logging.basicConfig(format='[%(asctime)s %(levelname)s] %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S',
                    level=logging.INFO)

Topic = namedtuple('Topic', ['query', 'sort', 'order', 'created', 'data'])


class GitHubSearch:
    def __init__(self, config_path, github_token=None):
        self._config_path = config_path
        self._path_readme = None
        self._access_token = github_token
        self._contents = None
        self._g = None
        self._data_pack = {}
        # read config file
        self._read_config()
        self._create()

    def _create(self):
        # create a GitHub instance
        logging.info("create github instance")
        try:
            self._g = Github(self._access_token) if self._access_token else Github()
            user = self._g.get_user()
            print(f"User: {user.name}，login name: {user.login}")
        except GithubException as e:
            if e.status == 401:
                print("Token is invalid")
            else:
                print("Request error")
            self._g = Github()
        self.get_remaining_requests_info()

    def search_github(self, query, sort="stars", order="desc", created='>2022-01-01'):
        while True:
            try:
                # search for repositories containing the keyword 'slam' and sort by new stars
                repos = self._g.search_repositories(query=query, sort=sort,
                                                    order=order, created=created)  # NOLINT
                # create a list to hold repository data
                repo_list = []

                # loop through each repository in the search results and add data to repo_list
                for repo in repos[:self._contents[query]["topk"]]:
                    data = {
                        "Name": repo.name,
                        "Description": repo.description,
                        "URL": repo.html_url,
                        "Stars": repo.stargazers_count,
                        "Created": repo.created_at,
                        "Updated": repo.updated_at,
                        "Owner": repo.owner.login
                    }
                    repo_list.append(data)

                # create a dataframe from the repo_list
                df = pd.DataFrame(repo_list)

                # convert date columns to datetime format
                df["Created"] = pd.to_datetime(df["Created"])
                df["Updated"] = pd.to_datetime(df["Updated"])

                # format date columns as strings
                df["Created"] = df["Created"].dt.strftime("%Y-%m-%d-%H:%M:%S")
                df["Updated"] = df["Updated"].dt.strftime("%Y-%m-%d-%H:%M:%S")
                break
            except RateLimitExceededException as e:
                reset_time = self._g.get_rate_limit().core.reset.timestamp()
                remaining_requests = self._g.get_rate_limit.core.remaining

                sleep_time_seconds = reset_time - time.time()
                logging.error(
                    f"RateLimitExceededException: {e}, sleep {sleep_time_seconds} seconds, remaining_requests: {remaining_requests}")
                time.sleep(sleep_time_seconds)
        return df

    def write_to_markdown(self, file, data_frame, min_stars=10):
        # write the dataframe to a markdown file
        data_frame.iterrows()
        for _, row in data_frame.iterrows():
            # if row["Stars"] < min_stars:
            # print("skipping", row["Name"], "because it has ", row["Stars"], "stars")
            # continue
            file.write("| [{}]({}) | {} | {} | {} |\n".format(
                row["Name"], row["URL"], row["Description"], row["Stars"],
                row["Updated"]
            ))

    def write_header(self, file, topic, sort="stars", enable_title=True):
        # write the header for the markdown file
        if enable_title:
            file.write("## {}\n".format(topic.title()))
        file.write("- Sort by: {}\n\n".format(sort.title()))
        file.write("| Name | Description | Stars | Updated |\n")
        file.write("| --- | --- | --- | --- |\n")

    def write_outline(self, file):
        # Add: table of contents
        file.write("<details>\n")
        file.write("  <summary>Table of Contents</summary>\n")
        file.write("  <ol>\n")
        for keyword in self._data_pack.keys():
            kw = keyword.replace(' ', '-')
            file.write(f"    <li><a href=#{kw}>{keyword}</a></li>\n")
        file.write("  </ol>\n")
        file.write("</details>\n\n")

    def get_remaining_requests_info(self):
        # 获取 API 请求限制信息
        rate_limit = self._g.get_rate_limit()

        # 获取剩余 API 调用次数和恢复请求的秒数
        remaining_requests = rate_limit.core.remaining
        reset_timestamp = rate_limit.core.reset.timestamp()

        # 打印 API 请求数和恢复时间信息
        print(f'Remaining requests: {remaining_requests}')
        print(f'Reset time: {datetime.utcfromtimestamp(reset_timestamp)}')

    def search_topics(self):

        # search for repositories
        query_list = []
        df_list = []
        sort_list = []
        data_pack = dict()
        for query in self._contents:
            enabled = self._contents[query]["enabled"]
            if not enabled:
                continue
            sort = self._contents[query]["sort"]
            order = self._contents[query]["order"]
            created = self._contents[query]["created"]

            for sort_item in sort:
                logging.info(f"searching topic: {query}, sort: {sort_item}, order: {order}, created: {created}")
                # time.sleep(5)
                df = self.search_github(query, sort=sort_item, order=order, created=created)
                query_list.append(query)
                df_list.append(df)
                sort_list.append(sort_item)
            self._data_pack[query] = Topic(query, sort_list, order, created, df_list)

        # write to markdown file
        logging.info(f"write to markdown file {self._path_readme}")
        with open(self._path_readme, "w", encoding="utf-8") as file:
            self.write_outline(file)
            control = 0
            for query, df, sort_item in zip(query_list, df_list, sort_list):
                logging.info(f"process topic: {query}")
                self.write_header(file, query, sort_item, control % 2 == 0)
                self.write_to_markdown(file, df, 5)
                control += 1
            # TODO(vincentqin)：add a table of contents

    def _read_config(self):
        with open(self._config_path, 'r', encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self._path_readme = config["md_readme_path"]
        self._contents = config["keywords"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config_path', type=str, default='config.yaml',
                        help='configuration file path')
    parser.add_argument('--access_token', type=str, default='null',
                        help='github access token')
    args = parser.parse_args()

    github_search = GitHubSearch(args.config_path, args.access_token)
    github_search.search_topics()
