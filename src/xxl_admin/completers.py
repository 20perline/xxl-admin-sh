from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    FuzzyWordCompleter,
    WordCompleter,
)
from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.document import Document


class MostRecentlyUsedFirstWordMixin:

    def __init__(self, max_words, words, *args, **kwargs):
        self.words = words
        self.max_words = max_words
        super().__init__(words, *args, **kwargs)

    def touch(self, word):
        """
        Make sure word is in the first place of the completer
        list.
        """
        if word in self.words:
            self.words.remove(word)
        else:
            if len(self.words) == self.max_words:
                self.words.pop()
        self.words.insert(0, word)

    def touch_words(self, words):
        for word in words:
            self.touch(word)


class MostRecentlyUsedFirstWordCompleter(MostRecentlyUsedFirstWordMixin, FuzzyWordCompleter):
    pass
