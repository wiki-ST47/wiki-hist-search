from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import render
from hist_search.forms import SearchForm
import pywikibot
import requests.utils
import re
import urllib.parse


def index(request):
    context = {}
    context['form'] = SearchForm()
    return render(request, 'index.html', context)


def docs(request):
    context = {}
    context['form'] = SearchForm()
    return render(request, 'docs.html', context)


def search(request):
    context = {}
    form = SearchForm(request.GET)
    context['form'] = form
    if form.is_valid():
        # Clear out any old data just in case
        pywikibot.config.authenticate = {}

        # Load up the site
        site_kwargs = {'code': 'en', 'fam': 'wikipedia'}
        wiki_url = form.cleaned_data.get('wiki_url')
        base_url = f"https://{wiki_url}/wiki/"
        if wiki_url:
            site_kwargs = {'url': base_url}
        try:
            site = pywikibot.Site(**site_kwargs)
        except pywikibot.exceptions.SiteDefinitionError:
            form.add_error('wiki_url',
                f"Unable to find this wiki. Please check the domain and "
                f"try again. You provided {wiki_url}, so we expected "
                f"{base_url} to be recognized by pywikibot - but it "
                f"wasn't."
            )
            return render(request, 'index.html', context)

        # Set up authentication
        if request.user.is_authenticated:
            # TODO If it is possible to have more than one auth, we should try
            # all of them, or clear them out somehow.
            auths = request.user.social_auth.all()
            auth = auths[0]
            sitebasename = requests.utils.urlparse(site.base_url('')).netloc
            pywikibot.config.authenticate[sitebasename] = (
                settings.SOCIAL_AUTH_MEDIAWIKI_KEY,
                settings.SOCIAL_AUTH_MEDIAWIKI_SECRET,
                auth.extra_data['access_token']['oauth_token'],
                auth.extra_data['access_token']['oauth_token_secret'],
            )
            userinfo = site.getuserinfo(force=True)
            if userinfo['name'] != request.user.username:
                auth.delete()
                pywikibot.config.authenticate = {}
                messages.error(request, "We weren't able to log in to the "
                               "wiki. If you need more revisions or to scan "
                               "deleted revisions, please log in again.")
                logout(request)

        revs_kwargs = {'rvdir': False, 'content': True}
        revs_kwargs['startid'] = form.cleaned_data.get('start_id', None)
        if form.cleaned_data.get('to_search'):
            revs_kwargs['total'] = total = form.cleaned_data.get('to_search')
        else:
            revs_kwargs['total'] = total = 200

        try:
            page = pywikibot.Page(site, form.cleaned_data['page'])
            # Adapted from Page.revisions(), which doesn't pass the args I need
            page.site.loadrevisions(page, **revs_kwargs)
            revisions = (page._revisions[rev] for rev in
                         sorted(page._revisions, reverse=True)[:total])
            context['revisions'] = revisions
        except pywikibot.exceptions.NoPage as e:
            form.add_error('page',
                f"Unable to find this page. {e.title} does not exist."
            )
            return render(request, 'index.html', context)

        # Actually perform the searching
        revlist = []
        last_revid = None
        active_rev_flag = active_es_flag = False
        active_rev_track = active_es_track = None
        revdel_rev_string = revdel_es_string = ''
        revdel_rev_count = revdel_es_count = 0
        intent = form.cleaned_data.get('intent')
        search = form.cleaned_data.get('search')
        if form.cleaned_data.get('regex_search'):
            re_args = []
            if form.cleaned_data.get('case_insensitive'):
                re_args.append(re.IGNORECASE)
            def string_compare(search, text):
                return re.search(search, text)
        else:
            if form.cleaned_data.get('case_insensitive'):
                def string_compare(search, text):
                    return search.lower() in text.lower()
            else:
                def string_compare(search, text):
                    return search.lower() in text.lower()

        return_matches = form.cleaned_data.get('return_matches', False)

        for rev in revisions:
            revd = {}
            text = page.getOldVersion(rev.revid)

            revdeled_rev = rev.texthidden and (rev.suppressed or intent != 'OS')
            revdeled_es = rev.commenthidden and (rev.suppressed or intent != 'OS')
            match_rev = text and string_compare(search, text)
            match_es = rev.comment and string_compare(search, rev.comment)
            if match_rev and not revdeled_rev:
                revdel_rev_count += 1
                if not active_rev_flag:
                    active_rev_flag = True
                    active_rev_track = rev.revid
            else:
                if active_rev_flag:
                    active_rev_flag = False
                    new_string = f"{last_revid}..{active_rev_track}"
                    if revdel_rev_string:
                        revdel_rev_string = '|' + revdel_rev_string
                    revdel_rev_string = new_string + revdel_rev_string
            if match_es and not revdeled_es:
                revdel_es_count += 1
                if not active_es_flag:
                    active_es_flag = True
                    active_es_track = rev.revid
            else:
                if active_es_flag:
                    active_es_flag = False
                    new_string = f"{last_revid}..{active_es_track}"
                    if revdel_es_string:
                        revdel_es_string = '|' + revdel_es_string
                    revdel_es_string = new_string + revdel_es_string

            revd['match_rev'] = match_rev
            revd['rev_handled'] = revdeled_rev
            revd['texthidden'] = rev.texthidden
            revd['match_es'] = match_es
            revd['es_handled'] = revdeled_es
            revd['commenthidden'] = rev.commenthidden
            revd['suppressed'] = rev.suppressed
            revd['rev'] = rev
            if (not return_matches) or match_rev or match_es:
                revlist.append(revd)

            last_revid = rev.revid

        page_name_encoded = urllib.parse.quote(form.cleaned_data.get('page').replace(' ', '_'))
        context['revlist'] = revlist
        indexphp = 'https:' + site.siteinfo['server'] + site.siteinfo['script']
        context['rev_url'] = f"{indexphp}?title={page_name_encoded}&action=history&limit={total}&revdel_select={revdel_rev_string}"
        context['es_url'] = f"{indexphp}?title={page_name_encoded}&action=history&limit={total}&revdel_select={revdel_es_string}"
        context['log_url'] = f"{indexphp}?title=Special:Log&type=create&page={page_name_encoded}"
        context['rev_count'] = revdel_rev_count
        context['es_count'] = revdel_es_count
        context['indexphp'] = indexphp

        # Clean up
        pywikibot.config.authenticate = {}

        return render(request, 'hist_search/search.html', context)

    return render(request, 'index.html', context)
