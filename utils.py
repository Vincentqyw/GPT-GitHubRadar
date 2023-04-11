import os
import pickle
from datetime import datetime, timedelta
from github import Github


class GithubCache:

    def __init__(self, cache_dir, cache_timeout=3600, github_token=None):
        self.cache_dir = cache_dir
        self.cache_timeout = cache_timeout
        self.github = Github(github_token) if github_token else Github()

    def get_cache_filename(self, query):
        return os.path.join(self.cache_dir, f"{query.lower().replace(' ', '_')}.cache")

    def read_cache(self, filename):
        try:
            with open(filename, 'rb') as f:
                cache = pickle.load(f)
                if datetime.now() <= cache['expires']:
                    return cache['result']
        except (FileNotFoundError, IOError, pickle.PickleError):
            pass
        return None

    def write_cache(self, filename, data, timeout):
        cache = {'result': data, 'expires': datetime.now() + timedelta(seconds=timeout)}
        with open(filename, 'wb') as f:
            pickle.dump(cache, f)

    def search_repositories(self, query, sort='stars', order='desc'):
        cache_filename = self.get_cache_filename(query)
        cache_result = self.read_cache(cache_filename)
        if cache_result:
            return cache_result

        result = self.github.search_repositories(query, sort=sort, order=order)
        self.write_cache(cache_filename, result, self.cache_timeout)
        return result
