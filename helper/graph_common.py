#source TLE: https://github.com/cheran-senthil/TLE/blob/master/tle/util/graph_common.py
import os
import io
import discord
import time

from matplotlib import pyplot as plt

def get_current_figure_as_file():
    filename = os.path.join('temp_dir', f'tempplot_{time.time()}.png')
    plt.savefig(filename, facecolor=plt.gca().get_facecolor(), bbox_inches='tight', pad_inches=0.25)

    with open(filename, 'rb') as file:
        discord_file = discord.File(io.BytesIO(file.read()), filename='plot.png')

    os.remove(filename)
    return discord_file

def plot_rating_bg(ranks, MAX_SCORE = 10):
    ymin, ymax = plt.gca().get_ylim()
    bgcolor = plt.gca().get_facecolor()
    for rank in ranks:
        plt.axhspan(rank.low * MAX_SCORE / 100, rank.high * MAX_SCORE / 100, facecolor=rank.color_graph, alpha=0.8, edgecolor=bgcolor, linewidth=0.5)

    locs, labels = plt.xticks()
    for loc in locs:
        plt.axvline(loc, color=bgcolor, linewidth=0.5)
    plt.ylim(ymin, ymax)