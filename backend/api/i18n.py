from django.utils.translation import override


def render(text, params=None, lang='en'):
    with override(lang or 'en'):
        text = str(text)
        return text % params if params else text
