![License](https://badgen.net/github/license/wiki-ST47/wiki-hist-search)
![Last Commit](https://badgen.net/github/last-commit/wiki-st47/wiki-hist-search)
[![Dependabot Status](https://api.dependabot.com/badges/status?host=github&repo=wiki-ST47/wiki-hist-search)](https://dependabot.com)
[![Total alerts](https://img.shields.io/lgtm/alerts/g/wiki-ST47/wiki-hist-search.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/wiki-ST47/wiki-hist-search/alerts/)

# History Search Tool for RevDel/Oversight
Helping find and remove sensitive data from revision histories

# Synopsis
This project is a web tool for Wikimedia ToolForge that searches through a
page's non-deleted revisions to find those which match a certain string or
regex. It returns that list, as well as links to easily delete those revisions.

# Project Status
This project is about 6 hours of work to package a Jupyter notebook that I spent
about 15 minutes on. It works, but there might be bugs or UI issues that I
haven't caught yet, and there are probably also more features to add.

Here are a few features that I might explore for the future:

- Search deleted pages/revisions as well
- Search relevant log entires

# Contributing
You can test most of this locally without even logging in to the wiki. If you
have an admin or oversighter account and want to test those features, you can
create an OAuth key and patch it in to the code that passes the OAuth creds to
pywikibot in hist\_search/views.py

To run the server, you'll want to do something like the following:

```
git clone https://github.com/wikimedia/pywikibot.git pywikibot/
./rebuild_venv.sh
source venv/bin/activate
npm install
PYTHONPATH=pywikibot/ PYWIKIBOT_NO_USER_CONFIG=1 ./manage.py runserver 0.0.0.0:9023
```

You will also need to create a file `conf/dev_settings` with the usual:

```
# Settings for dev

from conf.settings import *

ALLOWED_HOSTS = [
    '127.0.0.1',
]

DEBUG = True

SECRET_KEY = 'something random'

SOCIAL_AUTH_MEDIAWIKI_KEY = 'get these from metawiki'
SOCIAL_AUTH_MEDIAWIKI_SECRET = ''
SOCIAL_AUTH_MEDIAWIKI_URL = 'https://meta.wikimedia.org/w/index.php'
SOCIAL_AUTH_MEDIAWIKI_CALLBACK = 'http://127.0.0.1:9023/oauth/complete/mediawiki/'
```
