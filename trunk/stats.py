import email
import calendar
import heapq
import time

from Cheetah.Template import Template
from pygooglechart import StackedVerticalBarChart, Axis

_Y_AXIS_SPACE = 32
_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", 
    "Oct", "Nov", "Dec"]

def _GetYearRange(date_range):
  start, end = date_range
  start_year = time.localtime(start).tm_year
  end_year = time.localtime(end).tm_year
  return range(start_year, end_year + 1)

def _GetDisplaySize(bytes):
  megabytes = bytes/(1 << 20)
  
  if megabytes:
    if bytes % (1 << 20) == 0:
      return "%dM" % (bytes/(1 << 20))
    else:
      return "%.2fM" % (float(bytes)/float(1 << 20))
  
  kilobytes = bytes/(1 << 10)
  
  if kilobytes:
    if bytes % (1 << 10) == 0:
      return "%dK" % (bytes/(1 << 10))
    else:
      return "%.2fK" % (float(bytes)/float(1 << 10))

  return str(bytes)
  
class Stat(object):
  _IdIndex = 0

  def __init__(self):
    self.id = "stat-%d" % Stat._IdIndex
    Stat._IdIndex += 1

class ChartStat(Stat):
  def __init__(self):
    Stat.__init__(self)
    
  def _GetRescaledData(self, data, data_max):
    # Use the extended encoding if we don't have too many data points
    if data_max:
      rescaled_max = len(data) > 1500 and 61 or 4095
      scaling_factor = float(rescaled_max) / float(data_max)
    else:
      scaling_factor = 0
    
    scaled_data = []
    
    for point in data:
      scaled_data.append(int(float(point) * scaling_factor))
    
    return scaled_data
  
  def _GetRescaledMax(self, max):
    if max > 200:
      if max % 100:
        return max + (100 - (max % 100))
      else:
        return max
    else:
      if max % 10:
        return max + (10 - (max % 10))
      else:
        return max

class BucketStat(ChartStat):
  def __init__(self, bucket_count, title, width, height):
    Stat.__init__(self) 
    
    self.__buckets = [0] * bucket_count
    self.__max = 0
    
    self.__title = title
    self.__width = width
    self.__height = height
  
  def ProcessMessageInfo(self, message_info):
    bucket = self._GetBucket(message_info)
    
    if bucket is None: return
    
    self.__buckets[bucket] += 1
    
    v = self.__buckets[bucket]
    if v > self.__max:
      self.__max = v
   
  def GetHtml(self):
    max = self._GetRescaledMax(self.__max)
    w = self.__width
    h = self.__height
    
    # We don't really care about StackedVerticalBarChart vs. 
    # GroupedVerticalBarChart since we just have one data-set, but only the
    # stacked graph seems to respect the bar spacing option
    chart = StackedVerticalBarChart(w, h)

    # Compute bar width so that it fits in the overall graph width.
    bucket_width = (w - _Y_AXIS_SPACE)/len(self.__buckets)
    bar_width = bucket_width * 4/5
    space_width = bucket_width - bar_width

    chart.set_bar_width(bar_width)
    chart.set_bar_spacing(space_width)
    
    chart.add_data(self._GetRescaledData(self.__buckets, max))
    chart.set_axis_range(Axis.LEFT, 0, max)
    chart.set_axis_labels(Axis.BOTTOM, self._GetBucketLabels())
    
    # We render the title in the template instead of in the chart, to give
    # stat collections and individual stats similar appearance
    
    t = Template(
        file="templates/bucket-stat.tmpl",
        searchList = {
          "id": self.id,
          "title": self.__title,
          "width": w,
          "height": h,
          "chart_url": chart.get_url()
        })
    return str(t)

class TimeOfDayStat(BucketStat):
  def __init__(self, title):
    BucketStat.__init__(self, 24, '%s by time of day' % title, 400, 200)
  
  def _GetBucket(self, message_info):
    return message_info.GetDate().tm_hour

  def _GetBucketLabels(self):
    return ['Midnight', '', '', '', '', '',
            '6 AM', '', '', '', '', '',
            'Noon', '', '', '', '', '',
            ' 6 PM', '', '', '', '', '']

class DayOfWeekStat(BucketStat):
  def __init__(self, title):
    BucketStat.__init__(self, 7, '%s by day of week' % title, 300, 200)

  
  def _GetBucket(self, message_info):
    # In the time tuple Monday is 0, but we want Sunday to be 0
    return (message_info.GetDate().tm_wday + 1) % 7
    
    
  def _GetBucketLabels(self):
    return ['S', 'M', 'T', 'W', 'T', 'F', 'S']

class YearStat(BucketStat):
  def __init__(self, date_range, title):
    self.__years = _GetYearRange(date_range)

    width = _Y_AXIS_SPACE + 30 * len(self.__years)
    
    BucketStat.__init__(
        self, len(self.__years), "%s by year" % title, width, 200)
    
  def _GetBucket(self, message_info):
    return message_info.GetDate().tm_year - self.__years[0]
  
  def _GetBucketLabels(self):
    return [str(x) for x in self.__years]
    
class MonthStat(BucketStat):
  def __init__(self, year):
    self.__year = year
    # No title is necessary, since the stat collection provides one
    BucketStat.__init__(self, 12, None, 300, 200)

  def _GetBucket(self, message_info):
    date = message_info.GetDate()
    
    if date.tm_year == self.__year:
      return date.tm_mon - 1
    else:
      return None
      
  def _GetBucketLabels(self):
    return _MONTH_NAMES

class DayStat(BucketStat):
  def __init__(self, year, month):
    self.__year = year
    self.__month = month
    self.__days_in_month = calendar.monthrange(year, month)[1]
    # No title is necessary, since the stat collection provides one
    BucketStat.__init__(
        self, 
        self.__days_in_month,
        None, 
        500,
        200)
        
  def _GetBucket(self, message_info):
    date = message_info.GetDate()
    
    if date.tm_year == self.__year and date.tm_mon == self.__month:
      return date.tm_mday - 1
    else:
      return None
      
  def _GetBucketLabels(self):
    return [str(d) for d in range(1, self.__days_in_month + 1)]

class SizeBucketStat(BucketStat):
  _SIZE_BUCKETS = [
    0,
    1 << 9,
    1 << 10,
    1 << 11,
    1 << 12,
    1 << 13,
    1 << 14,
    1 << 15,
    1 << 16,
    1 << 17,
    1 << 18,
    1 << 19,
    1 << 20,
    1 << 21,
    1 << 22,
    1 << 23,
  ]
  
  def __init__(self, title):
    BucketStat.__init__(
      self,
      len(SizeBucketStat._SIZE_BUCKETS),
      "%s message sizes" % title,
      500,
      200)

  def _GetBucket(self, message_info):
    size = message_info.size
    
    for i in reversed(xrange(0, len(SizeBucketStat._SIZE_BUCKETS))):
      if size >= SizeBucketStat._SIZE_BUCKETS[i]:
        return i
  
  def _GetBucketLabels(self):
    return [_GetDisplaySize(s) for s in SizeBucketStat._SIZE_BUCKETS]

class SizeFormatter(object):
  def __init__(self):
    self.header = "Size"
    self.css_class = "size"
  
  def Format(self, message_info):
    return _GetDisplaySize(message_info.size)

class SubjectSenderFormatter(object):
  _NAME_CACHE = {}

  def __init__(self):
    self.header = "Message"
    self.css_class = "message"
  
  def Format(self, message_info):
    name, address = email.utils.parseaddr(message_info.headers["from"])
    
    cache = SubjectSenderFormatter._NAME_CACHE
    
    if address in cache:
      if not name or len(cache[address]) > len(name):
        name = cache[address]
    
    if name:
      cache[address] = name
    else:
      name = address
      
    full_subject = subject = message_info.headers["subject"]
    if len(subject) > 50:
      subject = subject[0:50] + "..."

    t = Template(
        file="templates/subject-sender-formatter.tmpl",
        searchList = {
          "subject": subject,
          "full_subject": full_subject,
          "address": address,
          "name": name,
        });
    return str(t)    

_SizeHeapMap = lambda m: m
_SizeHeapIndex = lambda m: m.size

class TableStat(Stat):
  _TABLE_SIZE = 40
  
  def __init__(self, title, map_func, index_func, formatters):
    Stat.__init__(self)
    self.__title = title
    self.__heap = []
    self.__map_func = map_func
    self.__index_func = index_func
    self.__formatters = formatters

  def ProcessMessageInfo(self, message_info):
    obj = self.__map_func(message_info)
    index = self.__index_func(obj)
    
    pair = [index, obj]
    if len(self.__heap) < TableStat._TABLE_SIZE:
      heapq.heappush(self.__heap, pair)
    else:
      min_pair = self.__heap[0]
      if pair[0] > min_pair[0]:
        heapq.heapreplace(self.__heap, pair)

  def GetHtml(self):
    sorted = self.__heap
    sorted.sort(reverse=True)
  
    t = Template(
        file="templates/table-stat.tmpl",
        searchList = {
          "id": self.id,
          "title": self.__title,
          "formatters": self.__formatters,
          "objs": [obj for index, obj in sorted]
        })
    return str(t)

class SizeTableStat(TableStat):
  def __init__(self, title):
    TableStat.__init__(
        self,
        "%s top messages by size" % title,
        lambda m: m, # identity mapping function
        lambda m: m.size,  # use size as index
        [SubjectSenderFormatter(), SizeFormatter()])

class StatCollection(Stat):
  def __init__(self, title):
    Stat.__init__(self)
    self.title = title
    self.__stat_refs = []
    
  def ProcessMessageInfo(self, message_info):
    for stat_ref in self.__stat_refs:
      stat_ref.stat.ProcessMessageInfo(message_info)

  def _AddStatRef(self, stat, title):
    self.__stat_refs.append(StatRef(stat, title))
    
  def GetHtml(self):
    t = Template(
        file="templates/stat-collection.tmpl", 
        searchList = {"collection": self, "stat_refs": self.__stat_refs})
    return str(t)

class StatRef(object):
  def __init__(self, stat, title):
    self.stat = stat
    self.title = title

class MonthStatCollection(StatCollection):
  def __init__(self, date_range, title):
    StatCollection.__init__(self, "%s by month for " % title)
    
    for year in _GetYearRange(date_range):
      self._AddStatRef(MonthStat(year), "%s" % year)
      
class DayStatCollection(StatCollection):
  def __init__(self, date_range, title):
    StatCollection.__init__(self, "%s by month for " % title)
    
    for year in _GetYearRange(date_range):
      for month in range(1, 13):
        self._AddStatRef(
            DayStat(year, month), 
            "%s %s" % (year, _MONTH_NAMES[month - 1]))
            
class StatGroup(Stat):
  def __init__(self, *args):
    Stat.__init__(self)
    self.__stats = args
  
  def ProcessMessageInfo(self, message_info):
    for stat in self.__stats:
      stat.ProcessMessageInfo(message_info)
  
  def GetHtml(self):
    t = Template(
        file="templates/stat-group.tmpl", 
        searchList = {"stats": self.__stats})
    return str(t)
    
class TitleStat(Stat):
  _TIME_FORMAT = "%B %d %Y"
  
  def __init__(self, date_range, title):
    Stat.__init__(self)
    
    start_sec, end_sec = date_range
    self.__start = time.strftime(
        TitleStat._TIME_FORMAT, time.localtime(start_sec))
    self.__end = time.strftime(
        TitleStat._TIME_FORMAT, time.localtime(end_sec))
    
    self.__title = title
    
    self.__message_count = 0
  
  def ProcessMessageInfo(self, message_info):
    self.__message_count += 1
  
  def GetHtml(self):
    t = Template(
        file="templates/title-stat.tmpl",
        searchList = {
          "title": self.__title,
          "start": self.__start,
          "end": self.__end,
          "message_count": self.__message_count,
        })
    return str(t)