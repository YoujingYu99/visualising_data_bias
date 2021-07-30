import os
from os import path
from io import open
import pickle
from conllu import parse, parse_incr
import csv
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import urllib
import requests
import werkzeug
from werkzeug.utils import secure_filename
import spacy
from nltk.tokenize import RegexpTokenizer
from nltk.corpus import stopwords
from flask import url_for
from sklearn.preprocessing import MinMaxScaler
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import plotly.express as px
from matplotlib import cm
from matplotlib.cm import ScalarMappable
from wordcloud import WordCloud, ImageColorGenerator, STOPWORDS
from PIL import Image
import re
import cython
from gensim.models import phrases
from gensim import corpora, models, similarities
from sklearn.metrics.pairwise import cosine_similarity
from scipy import spatial
from statistics import mean
from gensim.models import Word2Vec, KeyedVectors
from string import ascii_letters, digits
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from gensim.test.utils import datapath

from .parse_sentence import parse_sentence, textify_tokens
from .PcaBiasCalculator import PcaBiasCalculator
from .PrecalculatedBiasCalculator import PrecalculatedBiasCalculator

# NLP bias detection
# if environ.get("USE_PRECALCULATED_BIASES", "").upper() == "TRUE":
#     print("using precalculated biases")
#     calculator = PrecalculatedBiasCalculator()
# else:
#     calculator = PcaBiasCalculator()

calculator = PrecalculatedBiasCalculator()

neutral_words = [
    "is",
    "was",
    "who",
    "what",
    "where",
    "the",
    "it",
]


def tsv_reader(path, file):
    """
    :param path: the path into amalgum dataset
    :param file: the file name in the folder: amalgum_genre_docxxx
    :return: a list of rows (lists containing words in sentences)
    """
    if not file.endswith('.tsv'):
        file += '.tsv'
    if os.path.exists(os.path.join(path, file)):
        tsv_file = open(os.path.join(path, file), encoding='utf-8')
        read_tsv = csv.reader(tsv_file, delimiter="\t")
        return read_tsv
    else:
        print(os.path.join(path, file))
        print('file not found')
        pass


def conllu_reader(path, file):
    """
    :param path: the path into amalgum dataset
    :param file: the file name in the folder: amalgum_genre_docxxx
    :return: a token list generator
    """
    file += '.conllu'
    if os.path.exists(os.path.join(path, file)):
        data_file = open(os.path.join(path, file), "r", encoding="utf-8")
        tokenlists = parse_incr(data_file)
        return tokenlists
    else:
        print(os.path.join(path, file))
        print('file not found')
        pass


def etree_reader(path, file):
    """
    :param path: the path into amalgum dataset
    :param file: the file name in the folder: amalgum_genre_docxxx
    :return: an element tree object
    """
    file += '.xml'
    if os.path.exists(os.path.join(path, file)):
        tree = ET.parse(os.path.join(path, file))
        return tree
    else:
        print(os.path.join(path, file))
        print('file not found')
        pass


def get_txt(file, path, save_path):
    """
    :param file: the file in the tsv folder
    :param path: the path of the file's parent directory
    :param save_path: the path to save the newly generated file
    :return: the plain text version of the file using the same name
    """
    f_read = tsv_reader(path, file)
    f_read = [x for x in f_read if x != []]
    f_out = []
    for row in f_read:
        line = row[0]
        if line.startswith('#Text='):
            f_out.append(line[6:])
    with open(os.path.join(save_path, file + '.txt'), 'w+', encoding='utf-8') as f:
        for line in f_out:
            f.write(line + '\n')
    f.close()
    if os.path.exists(os.path.join(save_path, file + '.txt')):
        print("writing completed: " + file)


def txt_list(path):
    """
    :param txt_dir: the path of the txt files to be extracted
    :return: a clean list containing the raw sentences
    """
    training_list = []
    txt_files = os.listdir(path)
    file_n = len(txt_files)
    print("{} files being processed".format(file_n))
    for file in txt_files:
        with open(os.path.join(path, file), "r", encoding='utf-8') as file_in:
            for line in file_in:
                # create word tokens as well as remove puntuation in one go
                rem_tok_punc = RegexpTokenizer(r'\w+')

                tokens = rem_tok_punc.tokenize(line)
                # convert the words to lower case
                words = [w.lower() for w in tokens]
                # Invoke all the english stopwords
                stop_word_list = set(stopwords.words('english'))
                # Remove stop words
                words = [w for w in words if not w in stop_word_list]

                training_list.append(words)

    return training_list


def tsv_txt(tsv_dir, txt_dir):
    """
    :param tsv_dir: the path of the tsv files
    :param txt_dir: the path of the txt files to be saved
    :return: extract all text from the tsv files and save to the txt directory
    """
    tsv_files = os.listdir(tsv_dir)
    file_n = len(tsv_files)
    print("{} files being processed".format(file_n))
    for file in tsv_files:
        file = file[:-4]
        get_txt(file, tsv_dir, txt_dir)


# Fetch Text From Url
def get_text_url(url):
    # page = urllib.request.urlopen(url)
    # soup = BeautifulSoup(page)
    page = requests.get(url).text
    soup = BeautifulSoup(page, 'lxml')
    fetched_text = ' '.join(map(lambda p: p.text, soup.find_all('p')))
    return fetched_text


# Fetch Text From Uploaded File
def get_text_file(corpora_file):
    # get filename
    filename = secure_filename(corpora_file.filename)
    fileDir = os.path.dirname(os.path.realpath('__file__'))

    # os.path.join is used so that paths work in every operating system
    save_user_path = os.path.join(fileDir, 'bias_visualisation_app\\data\\user_uploads')

    with open(os.path.join(save_user_path, filename), 'w+', encoding='utf-8') as f:
        for line in corpora_file:
            line = line.decode()

    return line


def list_to_dataframe(view_results, range=(-1, 1)):
    # put into a dataframe
    df = pd.DataFrame(view_results)
    # remove None
    df = df.dropna()
    # Normalise to -1 an 1
    scaler = MinMaxScaler(feature_range=range)
    df['bias'] = scaler.fit_transform(df[['bias']])

    return df


def generate_list(dataframe):
    token_list = dataframe['token'].to_list()
    value_list = dataframe['bias'].to_list()

    return token_list, value_list


def token_by_gender(token_list, value_list):
    # data
    # to convert lists to dictionary
    data = dict(zip(token_list, value_list))
    data = {k: v or 0 for (k, v) in data.items()}

    # separate into male and female dictionaries
    male_token = [k for (k, v) in data.items() if v > 0]
    female_token = [k for (k, v) in data.items() if v < 0]

    return male_token, female_token


def dict_by_gender(token_list, value_list):
    # convert lists to dictionary
    data = dict(zip(token_list, value_list))
    data = {k: v or 0 for (k, v) in data.items()}

    # separate into male and female dictionaries
    # sort from largest to smallest in each case
    male_dict = {k: v for (k, v) in data.items() if v > 0}
    male_dict = sorted(male_dict.items(), key=lambda x: x[1], reverse=True)
    female_dict = {k: v for (k, v) in data.items() if v < 0}
    female_dict = sorted(female_dict.items(), key=lambda x: x[1], reverse=True)

    return male_dict, female_dict


def save_obj(obj, name):
    save_dict_path = path.join(path.dirname(__file__), "..\\static\\", name)
    dict_path = save_dict_path + '.pkl'
    with open(dict_path, 'wb') as f:
        pickle.dump(obj, f)


def load_obj(name):
    save_dict_path = path.join(path.dirname(__file__), "..\\static\\")
    with open(save_dict_path + name + '.pkl', 'rb') as f:
        return pickle.load(f)


def generate_bias_values(input_data):
    objs = parse_sentence(input_data)
    results = []
    view_results = []
    for obj in objs:
        token_result = {
            "token": obj["text"],
            "bias": calculator.detect_bias(obj["text"]),
            "parts": [
                {
                    # "whitespace": token.whitespace_,
                    "pos": token.pos_,
                    "dep": token.dep_,
                    "ent": token.ent_type_,
                    "skip": token.pos_
                            in ["AUX", "ADP", "PUNCT", "SPACE", "DET", "PART", "CCONJ"]
                            or len(token) < 2
                            or token.text.lower() in neutral_words,
                }
                for token in obj["tokens"]
            ],
        }
        results.append(token_result)
    # copy results and only keep the word and the bias value
    token_result2 = results.copy()
    for item in token_result2:
        if "parts" in item.keys():
            del item['parts']
        else:
            continue
        view_results.append(item)

    view_df = list_to_dataframe(view_results)
    token_list, value_list = generate_list(view_df)
    male_dict, female_dict = dict_by_gender(token_list, value_list)

    save_obj(male_dict, m_dic)
    save_obj(female_dict, fm_dic)

    return view_results, view_df, (token_list, value_list)


def display_dataframe(m_dic, fm_dic):
    male_dictionary = load_obj(m_dic)
    male_dataframe = pd.DataFrame(male_dictionary.items(), columns=['Token', 'Bias Value'])
    female_dictionary = load_obj(fm_dic)
    female_dataframe = pd.DataFrame(female_dictionary.items(), columns=['Token', 'Bias Value'])







def bar_graph(dataframe, token_list, value_list):
    # set minus sign
    mpl.rcParams['axes.unicode_minus'] = False
    np.random.seed(12345)
    df = dataframe
    print(df)
    if len(token_list) > 15:
        set_x_tick = False
    else:
        set_x_tick = True

    plt.style.use('ggplot')
    plt.rcParams['font.family'] = ['sans-serif']
    plt.rcParams['font.sans-serif'] = ['SimHei']
    fig, ax = plt.subplots()

    # set up the colors
    cmap = mpl.colors.LinearSegmentedColormap.from_list('green_to_red', ['darkgreen', 'darkred'])
    df_mean = df.mean(axis=1)
    norm = plt.Normalize(df_mean.min(), df_mean.max())
    colors = cmap(norm(df_mean))

    ax.bar(
        token_list,
        value_list,
        yerr=df.std(axis=1) / np.sqrt(len(df.columns)),
        color=colors)
    fig.colorbar(ScalarMappable(cmap=cmap))

    ax.set_title('Word Bias Visualisation', fontsize=12)
    ax.set_xlabel('Word')
    ax.xaxis.set_visible(set_x_tick)
    ax.set_ylabel('Bias Value')
    plt.tight_layout()

    # save file to static
    bar_name = token_list[0] + token_list[-2]
    bar_name_ex = bar_name + '.png'
    save_img_path = path.join(path.dirname(__file__), "..\\static\\", bar_name)
    bar_path = save_img_path + '.png'
    plt.savefig(bar_path)
    plot_bar = url_for('static', filename=bar_name_ex)

    return plot_bar


# def bar_graph(token_list, value_list):
#     plt.rcParams['axes.unicode_minus'] = False
#
#
#     def autolable(rects):
#         for rect in rects:
#             height = rect.get_height()
#             if height >= 0:
#                 plt.text(rect.get_x() + rect.get_width() / 2.0 - 0.3, height + 0.02, '%.3f' % height)
#             else:
#                 plt.text(rect.get_x() + rect.get_width() / 2.0 - 0.3, height - 0.06, '%.3f' % height)
#                 plt.axhline(y=0, color='black')
#
#     # normalise
#     norm = plt.Normalize(-1, 1)
#     norm_values = norm(value_list)
#     map_vir = cm.get_cmap(name='viridis')
#     colors = map_vir(norm_values)
#     fig = plt.figure()
#     plt.subplot(111)
#     ax = plt.bar(token_list, value_list, width=0.5, color=colors, edgecolor='black')
#
#     sm = cm.ScalarMappable(cmap=map_vir, norm=norm)
#     sm.set_array([])
#     plt.colorbar(sm)
#     autolable(ax)
#
#     # save file to static
#     bar_name = token_list[0]
#     bar_name_ex = bar_name + '.png'
#     save_img_path = path.join(path.dirname(__file__), "..\\static\\", bar_name)
#     bar_path = save_img_path + '.png'
#     plt.savefig(bar_path)
#     plot_bar = url_for('static', filename=bar_name_ex)
#
#     return plot_bar


def transform_format(val):
    if val.any() == 0:
        return 255
    else:
        return val


def cloud_image(token_list, value_list):
    # data
    # to convert lists to dictionary
    data = dict(zip(token_list, value_list))
    data = {k: v or 0 for (k, v) in data.items()}

    # separate into male and female dictionaries
    male_data = {k: v for (k, v) in data.items() if v > 0}
    female_data = {k: v for (k, v) in data.items() if v < 0}

    # cloud
    cloud_color = "magma"
    cloud_bg_color = "white"
    # cloud_custom_font = False

    # transform mask
    # female_mask_path = path.join(path.dirname(__file__), "..\\static\\images", "female_symbol.png")
    # male_mask_path = path.join(path.dirname(__file__), "..\\static\\images", "male_symbol.png")
    #
    # female_cloud_mask = np.array(Image.open(female_mask_path))
    # male_cloud_mask = np.array(Image.open(male_mask_path))

    cloud_scale = 0.1
    cloud_horizontal = 1
    bigrams = True

    # Setting up wordcloud from previously set variables.
    female_wordcloud = WordCloud(collocations=bigrams, regexp=None,
                                 relative_scaling=cloud_scale, width=1000,
                                 height=500, background_color=cloud_bg_color, max_words=10000,
                                 contour_width=0,
                                 colormap=cloud_color)

    male_wordcloud = WordCloud(collocations=bigrams, regexp=None, relative_scaling=cloud_scale,
                               width=1000,
                               height=500, background_color=cloud_bg_color, max_words=10000,
                               contour_width=0,
                               colormap=cloud_color)

    try:
        female_wordcloud.generate_from_frequencies(female_data)

        # save file to static
        female_cloud_name = str(next(iter(female_data))) + 'femalecloud'
        female_cloud_name_ex = female_cloud_name + '.png'
        save_img_path = path.join(path.dirname(__file__), "..\\static\\", female_cloud_name)
        img_path = save_img_path + '.png'
        female_wordcloud.to_file(img_path)

        plot_female_cloud = url_for('static', filename=female_cloud_name_ex)

    except:
        # https: // www.wattpad.com / 729617965 - there % 27s - nothing - here - 3
        # https://images-na.ssl-images-amazon.com/images/I/41wjfr0wSsL.png
        print("Not enough words for female cloud!")
        plot_female_cloud = url_for('static', filename="nothing_here.jpg")

    try:
        male_wordcloud.generate_from_frequencies(male_data)

        # save file to static
        male_cloud_name = str(next(iter(male_data))) + 'malecloud'
        male_cloud_name_ex = male_cloud_name + '.png'
        save_img_path = path.join(path.dirname(__file__), "..\\static\\", male_cloud_name)
        img_path = save_img_path + '.png'
        male_wordcloud.to_file(img_path)

        plot_male_cloud = url_for('static', filename=male_cloud_name_ex)

    except:
        print("Not enough words for male cloud!")
        plot_male_cloud = url_for('static', filename="nothing_here.jpg")

    return plot_female_cloud, plot_male_cloud


def tsne_graph(token_list, iterations=3000, seed=20, title="TSNE Visualisation of Word-Vectors for Amalgum(Overall)"):
    """Creates a TSNE model and plots it"""

    # define word2vec model
    model_path = path.join(path.dirname(__file__), "../data/gum_word2vec.model")
    w2vmodel = Word2Vec.load(model_path)

    # manually define which words we want to explore
    my_word_list = []
    my_word_vectors = []

    words_to_explore = token_list

    for i in words_to_explore:
        try:
            if my_word_list not in my_word_list:
                my_word_vectors.append(w2vmodel.wv[i])
                my_word_list.append(i)
        except KeyError:
            continue

    tsne_model = TSNE(perplexity=5, n_components=2, init='pca', n_iter=iterations,
                      random_state=seed)
    new_values = tsne_model.fit_transform(my_word_vectors)

    x = []
    y = []
    for value in new_values:
        x.append(value[0])
        y.append(value[1])

    # save file to static
    tsne_name = token_list[0] + token_list[-2] + 'tsne'
    tsne_name_ex = tsne_name + '.jpg'
    save_img_path = path.join(path.dirname(__file__), "..\\static\\", tsne_name)
    tsne_path = save_img_path + '.jpg'

    plt.figure(figsize=(10, 10))
    for i in range(len(x)):
        plt.scatter(x[i], y[i])
        plt.annotate(my_word_list[i],
                     xy=(x[i], y[i]),
                     xytext=(5, 2),
                     textcoords='offset points',
                     ha='right',
                     va='bottom')
    plt.ylabel("TSNE Latent Dimension 1")
    plt.xlabel("TSNE Latent Dimension 2")
    plt.title(title)
    plt.savefig(tsne_path)
    plot_tsne = url_for('static', filename=tsne_name_ex)

    return plot_tsne


def tsne_graph_male(token_list, value_list, iterations=3000, seed=20, title="TSNE Visualisation(Male)"):
    """Creates a TSNE model and plots it"""

    # define word2vec model
    model_path = path.join(path.dirname(__file__), "../data/gum_word2vec.model")
    w2vmodel = Word2Vec.load(model_path)

    # manually define which words we want to explore
    my_word_list = []
    my_word_vectors = []

    words_to_explore = token_by_gender(token_list, value_list)[0]

    for i in words_to_explore:
        try:
            if my_word_list not in my_word_list:
                my_word_vectors.append(w2vmodel.wv[i])
                my_word_list.append(i)
        except KeyError:
            continue

    tsne_model = TSNE(perplexity=5, n_components=2, init='pca', n_iter=iterations,
                      random_state=seed)
    new_values = tsne_model.fit_transform(my_word_vectors)

    x = []
    y = []
    for value in new_values:
        x.append(value[0])
        y.append(value[1])

    # save file to static
    tsne_name = token_list[0] + token_list[-2] + 'tsne_male'
    tsne_name_ex = tsne_name + '.jpg'
    save_img_path = path.join(path.dirname(__file__), "..\\static\\", tsne_name)
    tsne_path = save_img_path + '.jpg'

    plt.figure(figsize=(10, 10))
    for i in range(len(x)):
        plt.scatter(x[i], y[i])
        plt.annotate(my_word_list[i],
                     xy=(x[i], y[i]),
                     xytext=(5, 2),
                     textcoords='offset points',
                     ha='right',
                     va='bottom')
    plt.ylabel("TSNE Latent Dimension 1")
    plt.xlabel("TSNE Latent Dimension 2")
    plt.title(title)
    plt.savefig(tsne_path)
    plot_tsne_male = url_for('static', filename=tsne_name_ex)

    return plot_tsne_male


def tsne_graph_female(token_list, value_list, iterations=3000, seed=20, title="TSNE Visualisation (Female)"):
    """Creates a TSNE model and plots it"""

    # define word2vec model
    model_path = path.join(path.dirname(__file__), "../data/gum_word2vec.model")
    w2vmodel = Word2Vec.load(model_path)

    # manually define which words we want to explore
    my_word_list = []
    my_word_vectors = []

    words_to_explore = token_by_gender(token_list, value_list)[1]

    for i in words_to_explore:
        try:
            if my_word_list not in my_word_list:
                my_word_vectors.append(w2vmodel.wv[i])
                my_word_list.append(i)
        except KeyError:
            continue

    tsne_model = TSNE(perplexity=5, n_components=2, init='pca', n_iter=iterations,
                      random_state=seed)
    new_values = tsne_model.fit_transform(my_word_vectors)

    x = []
    y = []
    for value in new_values:
        x.append(value[0])
        y.append(value[1])

    # save file to static
    tsne_name = token_list[0] + token_list[-2] + 'tsne_female'
    tsne_name_ex = tsne_name + '.jpg'
    save_img_path = path.join(path.dirname(__file__), "..\\static\\", tsne_name)
    tsne_path = save_img_path + '.jpg'

    plt.figure(figsize=(10, 10))
    for i in range(len(x)):
        plt.scatter(x[i], y[i])
        plt.annotate(my_word_list[i],
                     xy=(x[i], y[i]),
                     xytext=(5, 2),
                     textcoords='offset points',
                     ha='right',
                     va='bottom')
    plt.ylabel("TSNE Latent Dimension 1")
    plt.xlabel("TSNE Latent Dimension 2")
    plt.title(title)
    plt.savefig(tsne_path)
    plot_tsne_female = url_for('static', filename=tsne_name_ex)

    return plot_tsne_female


def pca_graph(token_list, title="PCA Visualisation of Word-Vectors for Amalgum"):
    """Creates a PCA model and plots it"""

    # define word2vec model
    model_path = path.join(path.dirname(__file__), "../data/gum_word2vec.model")
    w2vmodel = Word2Vec.load(model_path)

    # manually define which words we want to explore
    my_word_list = []
    my_word_vectors = []

    words_to_explore = token_list

    for i in words_to_explore:
        try:
            if my_word_list not in my_word_list:
                my_word_vectors.append(w2vmodel.wv[i])
                my_word_list.append(i)
        except KeyError:
            continue

    pca_model = PCA(n_components=2, svd_solver='full')
    new_values = pca_model.fit_transform(my_word_vectors)

    x = []
    y = []
    for value in new_values:
        x.append(value[0])
        y.append(value[1])

    # save file to static
    pca_name = token_list[0] + token_list[-2] + 'pca'
    pca_name_ex = pca_name + '.jpg'
    save_img_path = path.join(path.dirname(__file__), "..\\static\\", pca_name)
    pca_path = save_img_path + '.jpg'

    plt.figure(figsize=(10, 10))
    for i in range(len(x)):
        plt.scatter(x[i], y[i])
        plt.annotate(my_word_list[i],
                     xy=(x[i], y[i]),
                     xytext=(5, 2),
                     textcoords='offset points',
                     ha='right',
                     va='bottom')
    plt.ylabel("PCA Latent Dimension 1")
    plt.xlabel("PCA Latent Dimension 2")
    plt.title(title)
    plt.savefig(pca_path)
    plot_pca = url_for('static', filename=pca_name_ex)

    return plot_pca


def pca_graph_male(token_list, value_list, title="PCA Visualisation(Male)"):
    """Creates a PCA model and plots it"""

    # define word2vec model
    model_path = path.join(path.dirname(__file__), "../data/gum_word2vec.model")
    w2vmodel = Word2Vec.load(model_path)

    # manually define which words we want to explore
    my_word_list = []
    my_word_vectors = []

    words_to_explore = token_by_gender(token_list, value_list)[0]

    for i in words_to_explore:
        try:
            if my_word_list not in my_word_list:
                my_word_vectors.append(w2vmodel.wv[i])
                my_word_list.append(i)
        except KeyError:
            continue

    pca_model = PCA(n_components=2, svd_solver='full')
    new_values = pca_model.fit_transform(my_word_vectors)

    x = []
    y = []
    for value in new_values:
        x.append(value[0])
        y.append(value[1])

    # save file to static
    pca_name = token_list[0] + token_list[-2] + 'pca_male'
    pca_name_ex = pca_name + '.jpg'
    save_img_path = path.join(path.dirname(__file__), "..\\static\\", pca_name)
    pca_path = save_img_path + '.jpg'

    plt.figure(figsize=(10, 10))
    for i in range(len(x)):
        plt.scatter(x[i], y[i])
        plt.annotate(my_word_list[i],
                     xy=(x[i], y[i]),
                     xytext=(5, 2),
                     textcoords='offset points',
                     ha='right',
                     va='bottom')
    plt.ylabel("PCA Latent Dimension 1")
    plt.xlabel("PCA Latent Dimension 2")
    plt.title(title)
    plt.savefig(pca_path)
    plot_pca_male = url_for('static', filename=pca_name_ex)

    return plot_pca_male


def pca_graph_female(token_list, value_list, title="PCA Visualisation(Female)"):
    """Creates a PCA model and plots it"""

    # define word2vec model
    model_path = path.join(path.dirname(__file__), "../data/gum_word2vec.model")
    w2vmodel = Word2Vec.load(model_path)

    # manually define which words we want to explore
    my_word_list = []
    my_word_vectors = []

    words_to_explore = token_by_gender(token_list, value_list)[1]

    for i in words_to_explore:
        try:
            if my_word_list not in my_word_list:
                my_word_vectors.append(w2vmodel.wv[i])
                my_word_list.append(i)
        except KeyError:
            continue

    pca_model = PCA(n_components=2, svd_solver='full')
    new_values = pca_model.fit_transform(my_word_vectors)

    x = []
    y = []
    for value in new_values:
        x.append(value[0])
        y.append(value[1])

    # save file to static
    pca_name = token_list[0] + token_list[-2] + 'pca_female'
    pca_name_ex = pca_name + '.jpg'
    save_img_path = path.join(path.dirname(__file__), "..\\static\\", pca_name)
    pca_path = save_img_path + '.jpg'

    plt.figure(figsize=(10, 10))
    for i in range(len(x)):
        plt.scatter(x[i], y[i])
        plt.annotate(my_word_list[i],
                     xy=(x[i], y[i]),
                     xytext=(5, 2),
                     textcoords='offset points',
                     ha='right',
                     va='bottom')
    plt.ylabel("PCA Latent Dimension 1")
    plt.xlabel("PCA Latent Dimension 2")
    plt.title(title)
    plt.savefig(pca_path)
    plot_pca_female = url_for('static', filename=pca_name_ex)

    return plot_pca_female

# p = 'bias_visualisation_app/data/amalgum/amalgum_balanced/tsv'
# p1 = 'bias_visualisation_app/data/amalgum/amalgum_balanced/txt'
#
# tsv_txt(p, p1)
