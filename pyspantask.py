#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Py-Span-Task is a simple application for testing working memory span.
"""

__author__    = "Titus von der Malsburg <malsburg@posteo.de>"
__copyright__ = "Copyright 2010, Titus von der Malsburg"
__license__   = "GPL v2"

import sys, os, re, math, time, random
import tkinter, tkinter.dnd, tkinter.filedialog
from tkinter.constants import PAGES, UNITS, NORMAL, RAISED, SUNKEN, HORIZONTAL, RIGHT, BOTH, LEFT, BOTTOM, TOP, NW, HIDDEN, X, Y, ALL, CENTER
from warnings import warn

def damerau_levenshtein(s1, s2, eq=None):
  """
  Compute the Damerau-Levenshtein distance between two sequences.
  """
  if not eq:
    eq = lambda s,t:s==t
  d = {}
  len1 = len(s1)
  len2 = len(s2)
  for i in range(-1,len1+1):
    d[(i,-1)] = i+1
  for j in range(-1,len2+1):
    d[(-1,j)] = j+1

  for i in range(0,len1):
    for j in range(0,len2):
      if eq(s1[i], s2[j]):
        cost = 0
      else:
        cost = 1
      d[(i,j)] = min(d[(i-1,j)] + 1,                 # deletion
                     d[(i,j-1)] + 1,                 # insertion
                     d[(i-1,j-1)] + cost)            # substitution
      if i>0 and j>0 and eq(s1[i], s2[j-1]) and eq(s1[i-1], s2[j]):
        d[(i,j)] = min (d[(i,j)], d[i-2,j-2] + cost) # transposition

  return d[len1-1,len2-1]

def calculate_score(s, t, allow_sloppy_spelling, heed_order):
  # Allow one typo: omission, addition, substitution of a character, or
  # transposition of two characters.
  if allow_sloppy_spelling:
    errors_allowed = 1
  else:
    errors_allowed = 0
  # Collect correctly recalled words:
  hits = []
  for w1 in s:
    for w2 in t:
      if damerau_levenshtein(w1,w2) <= errors_allowed:
        hits.append(w2)
        continue
  # Remove duplicates from list of hits (although duplicates should
  # not occur when the experiment is properly configured):
  seen = set()
  seen_add = seen.add
  hits = [x for x in hits if not (x in seen or seen_add(x))]

  if heed_order:
    # Subtract points for items recalled in incorrect order:
    correct = len(t) - damerau_levenshtein(hits, t)
  else:
    correct = len(hits)

  return correct

class MainFrame(tkinter.Frame):

  def __init__(self, master, *scripts, **opts):

    # build gui:
    tkinter.Frame.__init__(self, master, **opts)
    master.title("Py-Span-Task")

    self.scripts = list(scripts)
    self.opts = {}

    self.display_var = tkinter.StringVar(self, "")
    width = master.winfo_screenwidth()
    self.display = tkinter.Message(self, justify=LEFT, textvar=self.display_var,
                     font=(fontname, fontsize),
                     width=width-(width/10), bg="white")
    self.display.pack(fill=BOTH, expand=1)

    self.entry_var = tkinter.StringVar(self, "")
    self.entry = tkinter.Entry(self, font=(fontname, fontsize),
                               state="disabled",
                               textvar=self.entry_var)
    self.entry.pack(fill=X)
    self.entry.bind('<Return>', lambda e:self.key_pressed('<Return>'))

    self.bind('<space>', lambda e:self.key_pressed('<space>'))

    # Sometimes lexical closures suck:
    def event_handler_creator(frame, key):
      return lambda e:frame.key_pressed(key)

    for v in responses.values():
      self.bind(v, event_handler_creator(self, v))

    self.focus_set()

    self.key_pressed(None)

  def key_pressed(self, key):
    if self.scripts:
      self.scripts[0].next(self, key, **self.opts)
    else:
      sys.exit(0)

  def next_script(self, **opts):
    self.opts.update(opts)
    self.scripts.pop(0)

  def set_text(self, text, justify=None):
    if justify:
        self.display["justify"] = justify
    self.display_var.set(text)

class Text(object):

  def __init__(self, text, align=LEFT):
    self.text = text
    self.align = align

  def next(self, frame, key=None, **opts):
    frame.set_text(self.text, self.align)
    frame.next_script()

class PracticeProcessingItemsScript(object):

  def __init__(self, processing_items):
    self.processing_items = processing_items

    # Data strctures for collecting the results:
    self.number = 0
    self.correct = 0
    self.times = []

    self.next = self.show_element

  def show_element(self, frame, key=None, **opts):
    if key != None and key != "<space>":
      return
    element, self.desired_answer = [s.strip() for s in next(self.processing_items).split('\t')]
    self.times.append(time.time())
    frame.set_text(element)
    self.number += 1
    self.next = self.store_results

  def store_results(self, frame, key, **opts):
    if key not in responses.values():
      return
    self.next = lambda s,f,**o:None
    if key == responses[self.desired_answer]:
      self.correct += 1
      frame.set_text(practice_correct_response)
    else:
      frame.set_text(practice_incorrect_response)
    if self.number == practice_processing_items:
      frame.after(response_display_time, lambda:self.show_results(frame, **opts))
    else:
      frame.after(response_display_time, lambda:self.show_element(frame, **opts))

  def show_results(self, frame, **opts):
    self.times.append(time.time())

    frame.set_text(practice_summary % {
      "total":practice_processing_items,
      "correct":self.correct})

    time_out = int(1000 * (mean(diff(self.times[measure_time_after_trial:]))
          + time_out_factor * sd(diff(self.times[measure_time_after_trial:]))))

    frame.next_script(time_out=time_out, **opts)

class TestScript(object):

  def __init__(self, processing_items, target_items, levels, items_per_level,
               phase):

    self.processing_items = processing_items
    self.target_items = target_items
    self.phase = phase

    self.sets = list(levels * items_per_level)
    random.shuffle(self.sets)

    self.cur, self.cur_targets = self.next_set()

    # Data structures for collecting the results:
    self.set_no = 1
    self.correct = 0              # number of correctly verifies processing items
    self.times = []
    self.level = len(self.cur)
    self.seen_targets = []
    self.results = []             # list of lines for the results file
    self.proportion_recalled = [] # proportion of correctly recalled items

    self.next = self.show_element

  def next_set(self):
    size = self.sets.pop()
    return [next(self.processing_items) for x in range(size)], self.target_items.get_set(size)

  def show_element(self, frame, key=None, time_out=None, **opts):
    if key != None and key != "<space>":
      return
    opts.update({"time_out":time_out})
    element, self.desired_answer = self.cur.pop(0).split('\t')
    self.start_time = time.time()
    frame.set_text(element)
    self.after_id = frame.after(time_out, lambda:self.interrupt(frame, **opts))
    self.next = self.show_target

  def interrupt(self, frame, **opts):
    self.next = lambda s,f,**o:None
    frame.set_text(time_out_message)
    self.times.append(time.time() - self.start_time)
    ti = next(self.cur_targets)
    self.seen_targets.append(ti)
    if not self.cur:
      frame.after(target_display_time, lambda:self.finish_set(frame, **opts))
    else:
      frame.after(target_display_time, lambda:self.show_element(frame, **opts))

  def show_target(self, frame, key, **opts):
    if key not in responses.values():
      return
    frame.after_cancel(self.after_id)
    self.next = lambda s,f,**o:None
    self.times.append(time.time() - self.start_time)
    if key == responses[self.desired_answer]:
      self.correct += 1
    ti = next(self.cur_targets)
    self.seen_targets.append(ti)
    frame.set_text(ti)
    if not self.cur:
      frame.after(target_display_time, lambda:self.finish_set(frame, **opts))
    else:
      frame.after(target_display_time, lambda:self.show_element(frame, **opts))

  def prepare_for_element(self, frame, **opts):
    frame.set_text(next_message)
    self.next = self.show_element

  def finish_set(self, frame, **opts):
    frame.set_text("?")
    frame.entry.focus_set()
    frame.entry.configure(state="normal")
    self.next = self.store_results

  def store_results(self, frame, key, **opts):
    if key != "<Return>":
      return
    # Save working memory and processing performance:
    s = frame.entry_var.get().lower()
    s = s.replace(',', ' ')
    if single_letters:
        s = [c for c in s if not c in " \t"]  #identify characters as items even without spaces
    else:
        s = s.split()

    t = [x.lower() for x in self.seen_targets]

    recalled = calculate_score(s, t, allow_sloppy_spelling, heed_order)

    self.proportion_recalled.append(float(recalled) / float(self.level))

    print("trial:", self.phase, self.set_no)
    print("  presented:", ", ".join(t))
    print("  entered:", ", ".join(s))
    print("  correct:", recalled, "out of", self.level)

    self.results.append("%s\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t%s"
                        % (self.phase, self.set_no, self.level, recalled,
                           self.correct, int(1000*mean(self.times)),
                           int(1000*max(self.times)), " ".join(t), " ".join(s)))

    try:
      self.cur, self.cur_targets = self.next_set()
      self.set_no += 1
      self.correct = 0
      self.times = []
      self.level = len(self.cur)
      self.seen_targets = []
      frame.entry_var.set("")
      frame.focus_set()
      frame.entry.configure(state="disabled")
      self.prepare_for_element(frame, **opts)
    except:
      self.finish(frame, **opts)

  def finish(self, frame, results=None, **opts):
    if results:
      results.extend(self.results)
    else:
      results = self.results
    opts.update({"results":results})
    opts.update({"pcu":mean(self.proportion_recalled)})
    frame.entry_var.set("")
    frame.set_text(finished_message)
    frame.focus_set()
    frame.entry.configure(state="disabled")
    frame.next_script(**opts)

class GoodbyeScript(object):

  def next(self, frame, key=None, **opts):
    frame.set_text(good_bye_text)
    store_line("phase\tset.id\tnum.items\tcorrectly.recalled\tcorrectly.verified\tmean.rt\tmax.rt\tpresented.items\trecalled.items")
    store_line('\n'.join(opts["results"]))
    store_line("# Partial credit unit score (PCU): %.3f" % opts["pcu"])
    frame.next_script()

def shuffled_lines(filename):
  """
  Removes duplicate lines, iterates over the lines, shuffles them, and
  restarts iterating.
  """
  lines = list(set([l.strip() for l in open(filename, encoding='utf-8')]))
  while 1:
    random.shuffle(lines)
    for l in lines:
      yield l

class ShuffledItems:

  def __init__(self, filename):
    self.items = shuffled_lines(filename)

  def get_set(self, size):
    return (next(self.items) for i in range(size))

class RandomItems:

  def __init__(self, filename):
    self.items = list(set([l.decode("utf-8").strip() for l in file(filename)]))

  def get_set(self, size):
    return iter(random.sample(self.items, size))

def diff(l):
  """
  Given a sequence of numbers, this function returns a list containing
  the differences between each pair of consequtive numers.  If the
  original sequence has length n, the resulting list will have length
  n-1.
  """
  n = len(l)
  return [x-y for x,y in zip(l[1:], l[:n-1])]

def mean(l):
  """
  Calculate the arithmetic mean of a sequence of numbers.
  """
  if len(l) < 1:
    raise ValueError("The arithmetic mean of an empty list is undefined.")

  return float(sum(l))/len(l)

def sd(l):
  """
  Calculate the standard deviation of a sequence of numbers.
  """
  m = mean(l)
  return math.sqrt(sum([(m-x)**2 for x in l]) / len(l))

def store_line(s, mode='a'):
  """
  Appends the given string plus a newline character to the file
  containing the results.
  """
  with open(results_file, mode, encoding='utf-8') as fh:
    fh.write(s + '\n')

def request_subject_id():
  """
  Prompt the user to enter a subject ID and check if the input
  conforms with the required format.  If not ask again.
  """

  def center_window(size, window):
    window_width = size[
      0]  # Fetches the width you gave as arg. Alternatively window.winfo_width can be used if width is not to be fixed by you.
    window_height = size[
      1]  # Fetches the height you gave as arg. Alternatively window.winfo_height can be used if height is not to be fixed by you.
    window_x = int(
      (window.winfo_screenwidth() / 2) - (window_width / 2))  # Calculates the x for the window to be in the centre
    window_y = int(
      (window.winfo_screenheight() / 2) - (window_height / 2))  # Calculates the y for the window to be in the centre

    window_geometry = str(window_width) + 'x' + str(window_height) + '+' + str(window_x) + '+' + str(
      window_y)  # Creates a geometric string argument
    window.geometry(window_geometry)  # Sets the geometry accordingly.
    return

  window = tkinter.Tk()
  window.title('Subjetct ID')
  label = tkinter.Label(window, text="Please enter a subject id consisting of numbers letters:")

  sid_var = tkinter.StringVar()

  entry = tkinter.Entry(window, textvariable=sid_var)

  button = tkinter.Button(window, text="Confirm", command=window.destroy)

  label.pack()
  entry.pack()
  button.pack()

  center_window((500, 100), window)

  tkinter.mainloop()


  sid = sid_var.get()
  mo = re.match('[a-zA-Z0-9]+', sid)
  if mo and mo.group() == sid:
    return sid
  else:
    return request_subject_id()

def duplicates(s):
  """
  Returns a list containing the elements of s that occur more than
  once.
  """
  d = {}
  for i in s:
    d[i] = d.get(i, 0) + 1
  return [i for i,n in d.items() if n>1]

class ask_if_warnings(object):
  """
  This context manager monitors the contained code block for
  warnings.  If there was one or more, the user is asked whether a
  specified function should be executed.
  """

  def __init__(self, func, message):
    self._module = sys.modules['warnings']
    self._entered = False
    self._warned = False
    self._func = func
    self._message = message

  def __repr__(self):
    args = []
    if self._module is not sys.modules['warnings']:
      args.append("module=%r" % self._module)
    name = type(self).__name__
    return "%s(%s)" % (name, ", ".join(args))

  def __enter__(self):
    if self._entered:
        raise RuntimeError("Cannot enter %r twice" % self)
    self._entered = True
    self._showwarning = self._module.showwarning
    def showwarning(*args, **kwargs):
      self._warned = True
      self._showwarning(*args, **kwargs)
    self._module.showwarning = showwarning
    return None

  def __exit__(self, *exc_info):
    if not self._entered:
      raise RuntimeError("Cannot exit %r without entering first" % self)
    self._module.showwarning = self._showwarning
    if self._warned:
      print(self._message)
      print("y/n:")
      while 1:
        sid = sys.stdin.readline()[:-1]
        if sid=="n":
          self._func()
        elif sid=="y":
          break
        else:
          print("Please enter y or n.")

if __name__=="__main__":

  # Read configuration:

  if len(sys.argv) < 2:
    print("Usage: %s config_file [results_file]" % sys.argv[0])
    sys.exit(1)
  else:
    config_file = sys.argv[1]
  if len(sys.argv) < 3:
    results_file = request_subject_id() + ".tsv"
  else:
    results_file = sys.argv[2]

  # Check whether the output file already exists:

  while os.path.exists(results_file):
    print("A results file for this subject id already exists.")
    print("Do you want to overwrite it? (y/n)")
    if sys.stdin.readline().strip() == "y":
      break
    else:
      results_file = request_subject_id() + ".tsv"

  # Load and sanity check the configuration:

  exec(open(config_file).read())

  with ask_if_warnings(lambda:sys.exit(1), "There were warnings.  Do you want to proceed?"):

    # Make sure that all parameters are present in the configuration file:
    t = set("""fontname fontname processing_items_file target_items_file responses
      welcome_text instructions1 allow_sloppy_spelling practice_processing_items
      measure_time_after_trial heed_order pseudo_random_targets practice_levels
      practice_items_per_level practice_correct_response
      practice_incorrect_response practice_summary instructions2 instructions3
      levels items_per_level next_message finished_message
      time_out_factor time_out_message target_display_time response_display_time
      good_bye_text""".split())
    if set(dir()).intersection(t) != t:
      raise ValueError("Some settings are missing: "
                       + ', '.join(t.difference(set(dir()))))

    # If there is just one level specified in the
    # configuration file, we have to wrap it in a tuple:
    if type(practice_levels) != tuple:
      practice_levels = (practice_levels,)
    if type(levels) != tuple:
      levels = (levels,)

    # All levels should be integer values:
    if False in [type(x)==int for x in practice_levels]:
      raise ValueError("All values in practice_levels shoud be integer values.")
    if False in [type(x)==int for x in levels]:
      raise ValueError("All values in levels shoud be integer values.")

    # Check target items:

    # Check whether targets are unique:
    t = [l.strip() for l in open(target_items_file, encoding='utf-8')]
    if len(t)!=len(set(t)):
      warn("There are duplicates in the list of targets: "
           + ', '.join(duplicates(t)))

    # The number of target items must be larger than the size of the
    # largest level:
    if len(t) <= max(practice_levels + levels):
      raise ValueError("There are too few target items for the largest set size.")

    # Check whether the targets are single letters/numbers
    single_letters = all(len(x)==1 for x in t)

    # Warn if the number of targets is not resonably bigger than the
    # max level:
    if len(t) < 2*max(practice_levels + levels):
      warn("There are very few target items.  They might repeat too often.")

    # In case sloppy spelling is allowed, check if the target items have
    # a sufficient damerau levenshtein distance to be unambiguously
    # identifyable:
    if allow_sloppy_spelling:
      for i in range(0, len(t)):
        for j in range(i+1, len(t)):
          if damerau_levenshtein(t[i], t[j]) < 2:
            raise ValueError(("These target items are too similar to be used with sloppy spelling: %s, %s" % (t[i], t[j])).encode("utf-8"))

    # Check processing items:

    # Have enough practice trials for reliable time estimate:
    if practice_processing_items - measure_time_after_trial < 1:
      raise ValueError("Too few practice trials for getting a time estimate.")
    if practice_processing_items - measure_time_after_trial < 6:
      warn("Too few practice trials give you an unreliable estimate of the time needed by the participant to do the task.")

    # Have unique processing items:
    t = [l.strip() for l in open(processing_items_file, encoding='utf-8')]
    if len(t)!=len(set(t)):
      warn(("There are duplicates in the list of operations: "
           + ', '.join(duplicates(t))).encode("utf-8"))

    # Have enough processing items:
    no_targets = sum(practice_levels) * practice_items_per_level
    no_targets += sum(levels) * items_per_level
    if no_targets > len(set(t)):
      raise ValueError("Not enough verification items. Only %d instead of %d." % (
        len(set(t)), no_targets))

    # See that the resposes in the processing_items_file are the same
    # as those in the configuration:
    r = set([l.split("\t")[1] for l in t])
    if set(responses.keys()) != r:
      raise ValueError("There is a response other than y and n for at least one verification item.")

  # End sanity checks.

  store_line("# Py-span-task", 'w')
  store_line("# Written by Titus von der Malsburg <malsburg@posteo.de>")
  store_line("# https://github.com/tmalsburg/py-span-task")

  # Store important settings:

  store_line("# Settings:")
  store_line("# subject id = %s" % results_file.split(".")[0])
  store_line("# allow_sloppy_spelling = %s" % allow_sloppy_spelling)
  store_line("# heed_order = %s" % heed_order)
  store_line("# time_out_factor = %s" % time_out_factor)

  # Prepare material:

  if pseudo_random_targets:
    target_items = ShuffledItems(target_items_file)
  else:
    target_items = RandomItems(target_items_file)

  processing_items = shuffled_lines(processing_items_file)

  # Set up GUI and take off:

  root = tkinter.Tk()
  root.attributes('-fullscreen', True)
  main_frame = MainFrame(root,
                         Text(welcome_text, CENTER),
                         Text(instructions1),
                         PracticeProcessingItemsScript(processing_items),
                         Text(instructions2),
                         TestScript(processing_items, target_items,
                                    practice_levels, practice_items_per_level,
                                    "practice"),
                         Text(instructions3),
                         TestScript(processing_items, target_items, levels,
                                    items_per_level, "test"),
                         GoodbyeScript())
  main_frame.pack(fill=BOTH, expand=1)
  # Make it cover the entire screen:
  w, h = root.winfo_screenwidth(), root.winfo_screenheight()
  #root.overrideredirect(1)
  root.geometry("%dx%d+0+0" % (w, h))
  # root.focus_set()                        # <-- move focus to this widget
  root.bind("<Escape>", lambda e: e.widget.quit())
  root.mainloop()
