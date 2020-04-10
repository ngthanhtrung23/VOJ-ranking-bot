from discord.ext import commands, tasks
import discord
import asyncio
import os
from helper import RankingDb
import json
from datetime import datetime
import time
from helper import discord_common
from helper import graph_common as gc
from helper.helper import DayFilter
from matplotlib import pyplot as plt
from typing import List
from helper import badge
BASE_PROBLEM_URL = 'https://codeforces.com/group/FLVn1Sc504/contest/{0}/problem/{1}'

WHILELIST_USER_IDs = ['328391']



def _plot_rating(resp, mark='o', labels: List[str] = None, MAX_SCORE=100):
    labels = [''] * len(resp) if labels is None else labels

    for user, label in zip(resp, labels):
        ratings, dates = [], []
        for rating, date in user:
            ratings.append(rating)
            dates.append(datetime.strptime(date, "%Y/%m/%d"))
        plt.plot(dates,
                 ratings,
                 linestyle='-',
                 marker=mark,
                 markersize=3,
                 markerfacecolor='white',
                 markeredgewidth=0.5,
                 label=label)

    gc.plot_rating_bg(badge.RATED_RANKS, MAX_SCORE)
    plt.gcf().autofmt_xdate()


def days_between(d1, d2=None):
    if d2 is None:
        d2 = datetime.today()
    d1 = datetime.strptime(d1, "%Y/%m/%d")
    return (d2 - d1).days

def to_message(p):
    # p[0][0] -> name
    # p[0][1] -> links
    # p[0][2] -> cnt_AC
    # p[1] -> result
    # p[2] -> DATE
    links = p[0][1].strip(',').split(',')
    links = list(map(lambda x: BASE_PROBLEM_URL.format(x.split('/')[0], x.split('/')[1]), links))
    msg = ""
    if len(links) == 1:
        msg = "[{0}]({1}) ".format(p[0][0], links[0])
    else:
        msg = p[0][0] + " "
        for i, link in enumerate(links):
            msg += "[link{0}]({1}) ".format(i + 1, link)
    diff = days_between(p[2])
    if diff == 1:
        msg += "(1 day ago)"
    elif diff > 1:
        msg += "({0} days ago)".format(diff)
    return msg


class Graph(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_handle(self, ctx, handle):
        if handle is None:
            handle = RankingDb.RankingDb.get_handle(ctx.author.id)
            if handle is None:
                await ctx.send(f'Handle for {ctx.author.mention} not found in database')
                return None
            return handle
        else:
            handle = handle.replace('!', '')
            if handle[0] == '<' and handle[-1] == '>':
                if len(handle) <= 3 or not handle[2:-1].isdigit():
                    await ctx.send(f'Handle {handle} is invalid.')
                    return None
                discord_id = handle[2:-1]
                handle = RankingDb.RankingDb.get_handle(discord_id)
                if handle is None:
                    await ctx.send(f'Handle for <@{discord_id}> not found in database')
                    return None
        return handle

    @commands.command(brief="List recent AC problems",
                      usage='[handle] [d>=[[dd]mm]yyyy] [d<[[dd]mm]yyyy]')
    async def stalk(self, ctx, *args):
        """
        Top 10 recent AC problems
        e.g. ;voj stalk CKQ d<16022020 d>=05062019
        """
        filt = DayFilter()
        handle = filt.parse(args)
        handle = await self.get_handle(ctx, handle)
        if handle is None:
            return
        problem_list = RankingDb.RankingDb.get_info_solved_problem(handle)
        problem_list = list(filter(lambda x: x[1] == 'AC' or (float(x[1]) >= 100 - 0.1), problem_list))
        problem_list = list(filter(lambda x: filt.filter(datetime.strptime(x[2], '%Y/%m/%d')), problem_list))
        if len(problem_list) == 0:
            await ctx.send('There are no submissions of user `{0}` within the specified parameters.'.format(handle))
            return
        problem_list = sorted(problem_list, key=lambda x: x[2], reverse=True)[:10]
        problem_list = list(map(lambda x: (RankingDb.RankingDb.get_problem_info(x[0]), x[1], x[2]), problem_list))

        msg = ''
        for p in problem_list:
            msg += to_message(p) + '\n'
        title = "Recently solved problems by " + handle

        embed = discord.Embed(title=title, description=msg)
        await ctx.send(embed=embed)

    def get_rating_change(self, handle):
        # problem id, result, date
        raw_subs = RankingDb.RankingDb.get_info_solved_problem(handle)
        raw_subs = list(filter(lambda x: (x[1] == 'AC') or (float(x[1]) <= 0.1), raw_subs))
        raw_subs = sorted(raw_subs, key=lambda x: x[2])

        problem_info = RankingDb.RankingDb.get_data('problem_info', limit=None)
        problem_points = {}
        for id, problem_name, links, cnt_AC in problem_info:
            point = 80 / (40 + int(cnt_AC))
            problem_points[int(id)] = point
        rating_changes = [(-1, -1)]
        rating = 0
        for problem_id, result, date in raw_subs:
            if rating_changes[-1][1] != date:
                rating_changes.append((0, date))
            if result == 'AC':
                result = 100
            rating += problem_points[int(problem_id)] * float(result) / 100
            rating_changes[-1] = (rating, date)
        return rating_changes[1:]

    @commands.command(brief="Show histogram of solved problems on CF.",
                      usage='[handle] [d>=[[dd]mm]yyyy] [d<[[dd]mm]yyyy]')
    async def hist(self, ctx, *args):
        """Shows the histogram of problems solved over time on Codeforces for the handles provided.
        e.g. ;voj hist CKQ d<16022020 d>=05062019
        """
        filt = DayFilter()
        handle = filt.parse(args)
        handle = await self.get_handle(ctx, handle)
        if handle is None:
            return
        raw_subs = RankingDb.RankingDb.get_info_solved_problem(handle)
        raw_subs = list(filter(lambda x: filt.filter(
            datetime.strptime(x[2], '%Y/%m/%d')), raw_subs))
        if len(raw_subs) == 0:
            await ctx.send('There are no submissions of user `{0}` within the specified parameters.'.format(handle))
            return
        subs = []
        types = ['AC', 'IC', 'PC']
        solved_by_type = {'AC': [], 'IC': [], 'PC': []}
        cnt = 0
        plt.clf()
        plt.xlabel('Time')
        plt.ylabel('Number solved')
        for problem_id, result, date in raw_subs:
            t = result
            if t != 'AC' and float(t) <= 0 + 0.01:
                t = 'IC'
            elif t != 'AC':
                t = 'PC'
            solved_by_type[t].append(date)

        all_times = [[datetime.strptime(date, '%Y/%m/%d')
                      for date in solved_by_type[t]] for t in types]
        labels = ['Accepted', 'Incorrect', 'Partial Result']
        colors = ['g', 'r', 'y']
        plt.hist(all_times, stacked=True, label=labels, bins=34, color=colors)
        total = sum(map(len, all_times))
        plt.legend(title=f'{handle}: {total}',
                   title_fontsize=plt.rcParams['legend.fontsize'])

        plt.gcf().autofmt_xdate()
        discord_file = gc.get_current_figure_as_file()
        embed = discord_common.cf_color_embed(
            title='Histogram of number of submissions over time')
        discord_common.attach_image(embed, discord_file)
        discord_common.set_author_footer(embed, ctx.author)
        await ctx.send(embed=embed, file=discord_file)

    @commands.command(brief="Show histogram of group's submissions.",
                      usage='[d>=[[dd]mm]yyyy] [d<[[dd]mm]yyyy]')
    async def group_hist(self, ctx, *args):
        """Shows the histogram of group's submissions.
        e.g. ;voj group_hist  d<16022020 d>=05062019
        """
        filt = DayFilter()
        handle = filt.parse(args)

        solved_info = RankingDb.RankingDb.get_data('solved_info', limit=None)
        raw_subs = []
        for user_id, problem_id, result, date in solved_info:
            if str(user_id) not in WHILELIST_USER_IDs:
                raw_subs.append((problem_id, result, date))

        raw_subs = list(filter(lambda x: filt.filter(datetime.strptime(x[2], '%Y/%m/%d')), raw_subs))
        if len(raw_subs) == 0:
            await ctx.send('There are no submissions within the specified parameters.')
            return
        subs = []
        types = ['AC', 'IC', 'PC']
        solved_by_type = {'AC': [], 'IC': [], 'PC': []}
        cnt = 0
        plt.clf()
        plt.xlabel('Time')
        plt.ylabel('Number solved')
        for problem_id, result, date in raw_subs:
            t = result
            if t != 'AC' and float(t) <= 0 + 0.01:
                t = 'IC'
            elif t != 'AC':
                t = 'PC'
            solved_by_type[t].append(date)

        all_times = [[datetime.strptime(date, '%Y/%m/%d')
                      for date in solved_by_type[t]] for t in types]
        labels = ['Accepted', 'Incorrect', 'Partial Result']
        colors = ['g', 'r', 'y']
        plt.hist(all_times, stacked=True, label=labels, bins=34, color=colors)
        total = sum(map(len, all_times))
        plt.legend(
            title=f'VNOI Group: {total}', title_fontsize=plt.rcParams['legend.fontsize'])

        plt.gcf().autofmt_xdate()
        discord_file = gc.get_current_figure_as_file()
        embed = discord_common.cf_color_embed(
            title='Histogram of number of submissions over time')
        discord_common.attach_image(embed, discord_file)
        discord_common.set_author_footer(embed, ctx.author)
        await ctx.send(embed=embed, file=discord_file)

    @commands.command(brief="Plot VOJ rating graph.",
                      usage='[handle] [d>=[[dd]mm]yyyy] [d<[[dd]mm]yyyy]')
    async def exp(self, ctx, *args):
        """
        Plots VOJ experience graph for the handle provided.
        e.g. ;voj exp CKQ d<16022020 d>=05062019
        """
        filt = DayFilter()
        handle = filt.parse(args)
        handle = await self.get_handle(ctx, handle)
        if handle is None:
            return
        if badge.MAX_SCORE == None:
            await ctx.send('Ranking has not been calculated yet.')
            return
        resp = self.get_rating_change(handle)
        resp = list(filter(lambda x: filt.filter(
            datetime.strptime(x[1], '%Y/%m/%d')), resp))
        if len(resp) == 0:
            await ctx.send('There are no submissions of user `{0}` within the specified parameters.'.format(handle))
            return
        plt.clf()
        _plot_rating([resp], MAX_SCORE=badge.MAX_SCORE)
        current_rating = resp[-1][0]
        rank_title = badge.point2rank(
            current_rating, badge.MAX_SCORE).title + " {:.3f}".format(current_rating)
        labels = [f'\N{ZERO WIDTH SPACE}{handle} ({rank_title})']
        plt.legend(labels, loc='upper left')
        min_rating = current_rating
        max_rating = current_rating
        for rating, date in resp:
            min_rating = min(min_rating, rating)
            max_rating = max(max_rating, rating)
        min_rating -= 5 * badge.MAX_SCORE / 100
        max_rating += 5 * badge.MAX_SCORE / 100
        if min_rating < 0:
            min_rating = 0

        discord_file = gc.get_current_figure_as_file()
        embed = discord_common.cf_color_embed(
            title='Experience graph in VNOI group')
        discord_common.attach_image(embed, discord_file)
        discord_common.set_author_footer(embed, ctx.author)
        await ctx.send(embed=embed, file=discord_file)

def setup(bot):
    bot.add_cog(Graph(bot))