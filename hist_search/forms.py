from django import forms


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
    case_insensitive = forms.TypedChoiceField(
        label="Case-insensitive searching?",
        choices=((True, "Yes"), (False, "No")),
        initial=True,
        coerce=lambda x: x == 'True',
    )
    regex_search = forms.TypedChoiceField(
        label="Treat as RegEx?",
        choices=((True, "Yes"), (False, "No")),
        initial=True,
        coerce=lambda x: x == 'True',
    )
    return_matches = forms.TypedChoiceField(
        label="Only return matching rows?",
        choices=((True, "Yes"), (False, "No")),
        initial=False,
        coerce=lambda x: x == 'True',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
