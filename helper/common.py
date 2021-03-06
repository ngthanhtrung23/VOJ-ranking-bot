from datetime import datetime
from discord.ext import commands
from helper import RankingDb
import json
class FilterError(commands.CommandError):
    pass
class ParamParseError(FilterError):
    pass

def time_format(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return days, hours, minutes, seconds


def pretty_time_format(seconds):
    days, hours, minutes, seconds = time_format(seconds)
    timespec = [
        (days, 'day', 'days'),
        (hours, 'hour', 'hours'),
        (minutes, 'minute', 'minutes'),
        (seconds, 'second', 'seconds')
    ]
    timeprint = [(cnt, singular, plural) for cnt, singular, plural in timespec if cnt]

    def format_(triple):
        cnt, singular, plural = triple
        return f'{cnt} {singular if cnt == 1 else plural}'

    return ' '.join(map(format_, timeprint))

def parse_date(arg):
    try:
        if len(arg) == 8:
            fmt = '%d%m%Y'
        elif len(arg) == 6:
            fmt = '%m%Y'
        elif len(arg) == 4:
            fmt = '%Y'
        else:
            raise ValueError
        return datetime.strptime(arg, fmt)
    except ValueError:
        raise ParamParseError(f'{arg} is an invalid date argument')

class DayFilter():
    def __init__(self):
        self.low = datetime.strptime("2000", "%Y")
        self.hi = datetime.strptime("3000", "%Y")
    def filter(self, date):
        return self.low <= date and date < self.hi
    
    def parse(self, args):
        args = list(set(args))
        handle = None
        for arg in args:
            if arg[0:2] == 'd<':
                self.hi = min(self.hi, parse_date(arg[2:]))
            elif arg[0:3] == 'd>=':
                self.low = max(self.low, parse_date(arg[3:]))
            else:
                handle = arg
        return handle

async def get_handle(ctx, handle):
    if handle is None:
        handle = RankingDb.RankingDb.get_handle(ctx.author.id)
        if handle is None:
            await ctx.send(f'Không tìm thấy nick của {ctx.author.mention} trong dữ liệu. Xin hãy dùng command ;voj identify nick_cf')
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
                await ctx.send(f'Không tìm thấy nick của <@{discord_id}> trong dữ liệu.')
                return None
    return handle
SPOJ_CNT_AC = json.load(open('database/spoj_cnt_ac.json'))
problem_points = None
def get_problem_points(force=False):
    global problem_points
    if problem_points != None and not force:
        return problem_points
    problem_info = RankingDb.RankingDb.get_data('problem_info', limit=None)
    problem_points = {}
    for id, problem_name, links, cnt_AC in problem_info:
        name = problem_name[:problem_name.find('-')].strip()
        spoj_cnt = 0
        if name in SPOJ_CNT_AC:
            spoj_cnt = SPOJ_CNT_AC[name]
        point = 200 / (100 + int(cnt_AC) + spoj_cnt)
        problem_points[int(id)] = point
    return problem_points