from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import render
from hist_search.forms import SearchForm
import itertools
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
    return render(request, 'docs.html', context)


def tools(request):
    context = {}
    return render(request, 'tools.html', context)


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

        indexphp = 'https:' + site.siteinfo['server'] + site.siteinfo['script']
        context['indexphp'] = indexphp

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

        intent = form.cleaned_data.get('intent')
        username_mode = form.cleaned_data.get('verify_hidden_user')
        if username_mode:
            username = form.cleaned_data.get('search')
            user = pywikibot.User(site, username)
            # TODO This check is disabled because apparently it returns false for suppressed users
            # even if you have viewsuppressed right
#            if not user.isRegistered():
#                form.add_error('search',
#                    f"User does not exist on this wiki, or you do not "
#                    f"have the ability to see it."
#                )
#                return render(request, 'index.html', context)

            log_entries_actor = site.logevents(user=user)
            log_entries_target = site.logevents(page=user)
            log_entries_talk_target = site.logevents(page=user.toggleTalkPage())
            log_entry_ids_seen = []
            log_entry_data = []
            for log_entry in itertools.chain(log_entries_actor, log_entries_target,
                                             log_entries_talk_target):
                logid = log_entry.data['logid']
                if logid in log_entry_ids_seen:
                    continue
                log_entry_ids_seen.append(logid)

                le = {}
                le['is_log'] = True
                le['match_user'] = log_entry.data['user'] == user.username
                le['match_target'] = user.username in log_entry.data['title']
                le['match_comment'] = user.username in log_entry.data['comment']
                le['user_hidden'] = 'userhidden' in log_entry.data or 'suppress' == log_entry.data['type']
                le['target_hidden'] = 'actionhidden' in log_entry.data or 'suppress' == log_entry.data['type']
                le['comment_hidden'] = 'commenthidden' in log_entry.data or 'suppress' == log_entry.data['type']
                le['suppressed'] = 'suppressed' in log_entry.data or 'suppress' == log_entry.data['type']
                le['le'] = log_entry
                le['timestamp'] = log_entry.data['timestamp']
                le['title'] = log_entry.data['title']
                le['user'] = log_entry.data['user']
                le['user_handled'] = le['user_hidden'] and (le['suppressed'] or intent != 'OS')
                le['target_handled'] = le['target_hidden'] and (le['suppressed'] or intent != 'OS')
                le['comment_handled'] = le['comment_hidden'] and (le['suppressed'] or intent != 'OS')
                le['change_visibility'] = f"{indexphp}?action=historysubmit&type=logging&ids[{logid}]=1&revisiondelete=1"
                log_entry_data.append(le)
            log_entry_data.sort(key=lambda x:x['le'].data['logid'], reverse=True)

            # AbuseFilter
            afl_argsets = [
                {'afluser': user.username},
                {'afltitle': user.title()},
                {'afltitle': user.toggleTalkPage().title()},
            ]
            afl_ids_seen = []
            for afl_args in afl_argsets:
                aflog = site._generator(pywikibot.data.api.ListGenerator, 'abuselog')
                aflog.request.update(afl_args)
                aflog.request['aflprop'] = 'ids|user|title|action|result|timestamp|details|hidden'
                for afl_entry in aflog:
                    logid = afl_entry['id']
                    if logid in afl_ids_seen:
                        continue
                    afl_ids_seen.append(logid)

                    le = {}
                    le['is_log'] = True
                    le['is_afl'] = True
                    le['filter_id'] = afl_entry['filter_id']
                    le['match_user'] = afl_entry['user'] == user.username
                    le['match_target'] = user.username in afl_entry['title']
                    le['match_comment'] = (afl_entry['details'] and (
                        ('summary' in afl_entry['details'] and user.username in afl_entry['details']['summary']) or
                        ('new_wikitext' in afl_entry['details'] and user.username in afl_entry['details']['new_wikitext'])))
                    le['user_hidden'] = 'hidden' in log_entry.data
                    le['target_hidden'] = 'hidden' in log_entry.data
                    le['comment_hidden'] = 'hidden' in log_entry.data
                    le['suppressed'] = 'hidden' in log_entry.data
                    le['le'] = afl_entry
                    le['timestamp'] = afl_entry['timestamp']
                    le['format_timestamp'] = pywikibot.Timestamp.fromISOformat(afl_entry['timestamp'])
                    le['title'] = afl_entry['title']
                    le['user'] = afl_entry['user']
                    le['user_handled'] = le['user_hidden'] and (le['suppressed'] or intent != 'OS')
                    le['target_handled'] = le['target_hidden'] and (le['suppressed'] or intent != 'OS')
                    le['comment_handled'] = le['comment_hidden'] and (le['suppressed'] or intent != 'OS')
                    le['change_visibility'] = f"{indexphp}?title=Special:AbuseLog&hide={logid}"
                    log_entry_data.append(le)

            contribs = site.usercontribs(user=user)
            pages = {}
            # Right now, we're just building a list of pages and the first time they were edited by
            # this user.
            for edit in contribs:
                title = edit['title']
                timestamp = edit['timestamp']
                if title not in pages or timestamp < pages['title']:
                    pages[title] = timestamp
            # Extra pages to check the whole history
            pages[user.title()] = None
            pages[user.toggleTalkPage().title()] = None

            for pagetitle, timestamp in pages.items():
                page = pywikibot.Page(site, pagetitle)
                try:
                    revisions = page.revisions(endtime=timestamp, content=True)
                    for rev in revisions:
                        le = {}
                        le['is_rev'] = True
                        le['match_user'] = rev['user'] == user.username
                        le['match_text'] = user.username in rev['text']
                        le['match_comment'] = user.username in rev['comment']
                        le['user_hidden'] = rev['userhidden']
                        le['text_hidden'] = rev['texthidden']
                        le['comment_hidden'] = rev['commenthidden']
                        le['suppressed'] = rev['suppressed']
                        le['rev'] = rev
                        le['title'] = page.title()
                        le['timestamp'] = str(rev['timestamp'])
                        le['format_timestamp'] = rev['timestamp']
                        le['user_handled'] = le['user_hidden'] and (le['suppressed'] or intent != 'OS')
                        le['text_handled'] = le['text_hidden'] and (le['suppressed'] or intent != 'OS')
                        le['comment_handled'] = le['comment_hidden'] and (le['suppressed'] or intent != 'OS')
                        le['change_visibility'] = f"{indexphp}?title={page.title()}&action=revisiondelete&type=revision&ids[{rev['revid']}]=1"
                        if le['match_user'] or le['match_text'] or le['match_comment']:
                            log_entry_data.append(le)
                except pywikibot.exceptions.NoPage:
                    pass

                deletedrevs = list(site.deletedrevs(titles=page, end=timestamp, content=True))
                if deletedrevs:
                    for rev in deletedrevs[0]['revisions']:
                        le = {}
                        le['is_rev'] = True
                        le['is_deleted'] = True
                        le['match_user'] = rev['user'] == user.username
                        le['match_text'] = user.username in rev['slots']['main']['*']
                        le['match_comment'] = user.username in rev['comment']
                        le['user_hidden'] = 'userhidden' in rev
                        le['text_hidden'] = 'texthidden' in rev['slots']['main']
                        le['comment_hidden'] = 'commenthidden' in rev
                        le['suppressed'] = 'suppressed' in rev
                        le['rev'] = rev
                        le['title'] = page.title()
                        le['timestamp'] = rev['timestamp']
                        le['format_timestamp'] = pywikibot.Timestamp.fromISOformat(rev['timestamp'])
                        le['user_handled'] = le['user_hidden'] and (le['suppressed'] or intent != 'OS')
                        le['text_handled'] = le['text_hidden'] and (le['suppressed'] or intent != 'OS')
                        le['comment_handled'] = le['comment_hidden'] and (le['suppressed'] or intent != 'OS')
                        le['change_visibility'] = f"{indexphp}?target={page.title()}&action=revisiondelete&type=revision&ids[{rev['revid']}]=1"
                        if le['match_user'] or le['match_text'] or le['match_comment']:
                            log_entry_data.append(le)

            # Clean up
            pywikibot.config.authenticate = {}

            log_entry_data.sort(key=lambda x:x['timestamp'], reverse=True)
            context['revlist'] = log_entry_data

            return render(request, 'hist_search/search_username.html', context)
        else:
            revs_kwargs = {'rvdir': False, 'content': True}
            revs_kwargs['startid'] = form.cleaned_data.get('start_id', None)
            if form.cleaned_data.get('to_search'):
                revs_kwargs['total'] = total = form.cleaned_data.get('to_search')
            else:
                revs_kwargs['total'] = total = 200

            pagename = form.cleaned_data['page']
            if not pagename:
                form.add_error('page',
                    f"Page name missing. This field is required, unless "
                    f"you select the 'Verify that a username is fully "
                    f"hidden' option."
                )
                return render(request, 'index.html', context)
            is_contribs = False
            if pagename.startswith('Special:Contributions/'):
                username = pagename.replace('Special:Contributions/', '')
                context['username'] = username

                revisions = site.usercontribs(user=username, total=total)
                context['revisions'] = revisions
                is_contribs = True
            else:
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
            search = form.cleaned_data.get('search')
            if form.cleaned_data.get('regex_search'):
                re_kwargs = {}
                if form.cleaned_data.get('case_insensitive'):
                    re_kwargs['flags'] = re.IGNORECASE
                def string_compare(search, text):
                    return re.search(search, text, **re_kwargs)
            else:
                if form.cleaned_data.get('case_insensitive'):
                    def string_compare(search, text):
                        return search.lower() in text.lower()
                else:
                    def string_compare(search, text):
                        return search.lower() in text.lower()

            return_matches = form.cleaned_data.get('return_matches', False)

            if is_contribs:
                # Build a list of pages with content now, more efficient that way
                pagelist = {}
                revs_kwargs = {'content': True, 'total': total, 'user': username}
                pages_needed = [rev['title'] for rev in revisions]
                for pagename in pages_needed:
                    page = pywikibot.Page(site, pagename)
                    page.site.loadrevisions(page, **revs_kwargs)
                    pagelist[pagename] = page
                matching_pages = {}

            for rev in revisions:
                revd = {}
                if is_contribs:
                    revd['title'] = rev['title']
                    page = pagelist[rev['title']]
                    rev = page._revisions[rev['revid']]

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

                if is_contribs and (match_rev or match_es):
                    if revd['title'] in matching_pages:
                        matching_pages[revd['title']]['count'] += 1
                        if rev.timestamp < matching_pages[revd['title']]['first']:
                            matching_pages[revd['title']]['first'] = rev.timestamp
                        if rev.timestamp > matching_pages[revd['title']]['last']:
                            matching_pages[revd['title']]['last'] = rev.timestamp
                    else:
                        matching_pages[revd['title']] = {
                            'title': revd['title'],
                            'first': rev.timestamp,
                            'last': rev.timestamp,
                            'count': 1,
                        }

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
            if is_contribs:
                context['matching_pages'] = matching_pages
                query = request.META['QUERY_STRING']
                context['qparams'] = re.sub(r'&?page=[^&]+', '', query)
            if not is_contribs:
                query = request.META['QUERY_STRING']
                query = re.sub(r'&?start_id=[^&]*', '', query)
                context['continue'] = query + '&start_id=' + str(last_revid)
            context['rev_url'] = f"{indexphp}?title={page_name_encoded}&action=history&limit={total}&revdel_select={revdel_rev_string}"
            context['es_url'] = f"{indexphp}?title={page_name_encoded}&action=history&limit={total}&revdel_select={revdel_es_string}"
            context['log_url'] = f"{indexphp}?title=Special:Log&type=create&page={page_name_encoded}"
            context['rev_count'] = revdel_rev_count
            context['es_count'] = revdel_es_count

            # Clean up
            pywikibot.config.authenticate = {}

            return render(request, 'hist_search/search.html', context)

    return render(request, 'index.html', context)
