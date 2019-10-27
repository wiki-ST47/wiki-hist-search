from django import forms
import pywikibot


class SearchForm(forms.Form):
    wiki_url = forms.CharField(
        label="Path to the wiki",
        required=False,
    )
    page = forms.CharField(label="Page name to search")
    search = forms.CharField(
        label="Search query",
    )
    to_search = forms.IntegerField(
        label="Number of revisions to search",
        required=False,
    )
    start_id = forms.IntegerField(
        label="Start at Revision ID",
        required=False,
    )
    intent = forms.ChoiceField(
        label="Include RevDeled revisions?",
        choices=(("OS", "Yes"), ("RD", "No")),
        initial='OS',
    )
    case_insensitive = forms.ChoiceField(
        label="Case-insensitive searching?",
        choices=((True, "Yes"), (False, "No")),
        initial=True,
    )
    regex_search = forms.ChoiceField(
        label="Treat as RegEx?",
        choices=((True, "Yes"), (False, "No")),
        initial=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
