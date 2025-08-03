import re
import string


class SchemaFilter:
    @staticmethod
    def clean_string(text: str):
        text = text.lower() # all lowercase

        text = re.sub(r'\d+', '', text) # del digits

        # del punctuation
        translator = str.maketrans('', '', string.punctuation)
        text = text.translate(translator)

        return text


    @staticmethod
    def lexical_filtering(results: list[str], question: str) -> list:
        question: list = SF.clean_string(question).split()

        filtered = []
        for result in results:
            if any(word.lower() in question for word in result.split('_')):
                filtered.append(result)

        return filtered


# Class identificator
SF = SchemaFilter
