import re
from gensim.models import KeyedVectors, Word2Vec
from os import path
import numpy as np
from sklearn.decomposition import PCA

gender_biased_word_pairs = [
    ("woman", "man"),
    ("daughter", "son"),
    ("mother", "father"),
    ("gal", "guy"),
    ("girl", "boy"),
    ("vagina", "penis"),
    ("feminine", "masculine"),
    ("ladies", "gentlemen"),
    ("wife", "husband"),
    ("female", "male"),
    ("girlfriend", "boyfriend"),
    ("queen", "king"),
    ("spokeswoman", "spokesman"),
]

gender_neutral_words = [
    #"who",
    #"what",
    #"where",
    #"the",
    #"it",
    "human"
]


class PcaBiasCalculator:
    def __init__(
            self,
            model_path=path.join(
                path.dirname(__file__), "../../data/gum_word2vec.model"
            ),
            biased_word_pairs=gender_biased_word_pairs,
            neutral_words=gender_neutral_words,
    ):
        self.model = Word2Vec.load(model_path)
        self.biased_word_pairs = biased_word_pairs
        self.neutral_words = neutral_words

        biased_pairs = [
            (self.model.wv[pair[0]], self.model.wv[pair[1]]) for pair in biased_word_pairs
        ]

        # female-male distance as biases. male-female as reversed_biases.
        biases = [pair[0] - pair[1] for pair in biased_pairs]
        reversed_biases = [pair[1] - pair[0] for pair in biased_pairs]

        # only keep 1 component
        self.pca = PCA(n_components=1)
        self.pca.fit(np.array(biases + reversed_biases))

        left_mean = np.mean(
            self.pca.transform(np.array([pair[0] for pair in biased_pairs]))
        )
        right_mean = np.mean(
            self.pca.transform(np.array([pair[1] for pair in biased_pairs]))
        )
        self.neutral_mean = np.mean(
            self.pca.transform(np.array([self.model.wv[word] for word in neutral_words]))
        )

        self.positive_mean = max(right_mean, left_mean)
        self.negative_mean = min(right_mean, left_mean)
        self.sign = 1 if right_mean > left_mean else -1

    def keys(self):
        return self.model.wv.vocab.keys()

    def detect_bias(self, raw_word):
        """
        Use PCA to find the gender bias vector, and determine bias based on position along the gender vector
        """
        # eliminate white spaces using underscore
        word = re.sub(r"\s+", "_", raw_word)
        if word not in self.model.wv:
            return None
        word_val = self.pca.transform(np.array([self.model.wv[word]]))[0][0]
        # rescaling word value so that the left/right average maps to 1 and -1, and neutral_mean maps to 0
        if word_val > self.neutral_mean:
            return self.sign * float(
                (word_val - self.neutral_mean)
                / (self.positive_mean - self.neutral_mean)
            )
        else:
            return self.sign * float(
                (self.neutral_mean - word_val)
                / (self.negative_mean - self.neutral_mean)
            )

