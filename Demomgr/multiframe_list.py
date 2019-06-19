'''ONLY TESTED ON WINDOWS 7 64 bit, Tcl v8.5'''
#TODO: Make configurable.
from tkinter import *
from operator import itemgetter
from math import floor

__version__ = "1.5"
__author__ = "Square789"

_DEFAULT = {"NAME":"egg",
			"BLANK":"",
			"SORTERMODE":False,
			"WIDTH":None,
			"FRMTFUNC" : None,}

_DEF_OPT = {"columns":1,
			"names":[],
			"sort":0,
			"sorters":[],
			"widths":[],
			"formatters":[],}

ALL = "all" #NOTE: tkinter has an ALL constant with the same value. Keeping this for readability.
COLUMN = "column"
ROW = "row"
BORDERWIDTH = 2
ENTRYHEIGHT = 16

_RIGHTCLICKBTN = 3

class idLabel(Label): # Labels are a subclass that hold some additional values regarding their column
	def __init__(self, parent, id_, *args, **kwargs):
		self.id = id_
		self.sortstate = 0

		super().__init__(parent, *args, **kwargs)

class Multiframe(Frame):
	'''Instantiates a multiframe tkinter based list
	parameters:
	master - parent object, should be default tkinter root or a tkinter.Frame object

	keyword arguments:
	columns: Number of columns to display
	names: List titling the columns: ["Egg", "Spam"]
	sort: 0:No labels sort; 1: All labels sort; 2: specify param sorters in the argument sorters: [True, False, True]
	widths: Set columns to fixed lengths; if none will expand as normally : [None, 10, None, 20, 5]
	formatters: A list of functions that formats list data for each element in a row. This is especially useful for i. e. dates, where you want to be able to sort by a unix timestamp but still be able to have the dates in a human-readable format :[None, self.dateformat]

	shadowdata: The shadowdata is an array always kept parallel to the current state of the Multiframe-Listbox. It is used by the sorting function to sort the list automatically; if you however want to display information in another fashion than to sort it by, specify formatters and call self.format() once all input has been made.
	shadowdata should always containt values you can directly sort.

	The list broadcasts the Virtual event "<<MultiframeSelect>>" to its parent whenever something is selected.
	The list broadcasts the Virtual event "<<MultiframeRightclick>>" to its parent whenever a right click is performed or the context menu button is pressed.'''
	def __init__(self, master, **options):

		super().__init__(master)

		self.master = master

		self.options = _DEF_OPT.copy()
		self.currentsely = None
		self.currentselx = None
		self.lastx = None
		self.lasty = None

		self.scrollbar = Scrollbar(self, command = self.__scrollallbar)

		self.frames = []
		self.shadowdata = [] #"shadow"-values that the sorting function uses. Great for dates etc.

		self.length = 0

		self.options.update(options) #user-defined options here
		self.options = dict( zip( ([k for k in self.options]), ( map(lambda a, b: list(a) if b else a, [self.options[k] for k in self.options], [isinstance(self.options[k], tuple) for k in self.options])) ) )#one liner lol, converts every tuple to a list, leaving anything that isn't a tuple untouched.

		if len(self.options["names"]) < self.options["columns"]:
			for i in range(self.options["columns"] - len(self.options["names"])):
				self.options["names"].append(_DEFAULT["NAME"]) # Fill up listbox names with default if user specified too little/none

		if len(self.options["sorters"]) < self.options["columns"]:
			for i in range(self.options["columns"] - len(self.options["sorters"])):
				self.options["sorters"].append(_DEFAULT["SORTERMODE"])

		if len(self.options["widths"]) < self.options["columns"]:
			for i in range(self.options["columns"] - len(self.options["widths"])):
				self.options["widths"].append(_DEFAULT["WIDTH"])

		if len(self.options["formatters"]) < self.options["columns"]:
			for i in range(self.options["columns"] - len(self.options["formatters"])):
				self.options["formatters"].append(_DEFAULT["FRMTFUNC"])

		for i in range(self.options["columns"]): #This for loop adds the elements to the main Frame and configures them
			self.shadowdata.append([])
			self.frames.append([])
			self.frames[i].append(Frame(self))																#[0] is frame
			self.frames[i].append(Listbox(self.frames[i][0], exportselection = False) )						#[1] is listbox
			self.frames[i].append(idLabel(self.frames[i][0], i, text=self.options["names"][i], anchor = W))	#[2] is label
			if self.options["widths"][i]:
				self.frames[i][0].config(width = self.options["widths"][i])
				self.frames[i][1].config(width = self.options["widths"][i])
				self.frames[i][2].config(width = self.options["widths"][i])
			def _handler0(event, self=self, button=_RIGHTCLICKBTN, currow = i, fromclick=False):#This sort of code might get me to commit die one day.
				return self.__setindex(event, button, currow, fromclick)
			def _handler1(event, self=self, button=1, currow=i, fromclick=True):
				return self.__setindex(event, button, currow, fromclick)
			def _handler2(event, self=self, button=_RIGHTCLICKBTN, currow=i, fromclick=True):
				return self.__setindex(event, button, currow, fromclick)
			self.frames[i][1].bind("<KeyPress-App>", _handler0) #https://infohost.nmt.edu/tcc/help/pubs/tkinter/web/extra-args.html
			self.frames[i][1].bind("<<ListboxSelect>>", _handler1)
			self.frames[i][1].bind("<Button-" + str(_RIGHTCLICKBTN) + ">", _handler2)
			self.frames[i][1].config(yscrollcommand=self.__scrollalllistbox)
			if not self.options["sort"] == 0:
				if self.options["sort"] == 2:
					if self.options["sorters"][i]:
						self.frames[i][2].bind("<Button-1>", self.__sort)
				else:
					self.frames[i][2].bind("<Button-1>", self.__sort)
			self.frames[i][2].pack(expand=0, fill=X, side=TOP) 				#pack label
			self.frames[i][1].pack(expand=1, fill=BOTH, side=LEFT)			#pack listbox
			expandop = 0
			if not self.options["widths"][i]:
				expandop = 1
			self.frames[i][0].pack(expand=expandop, fill=BOTH, side=LEFT)	#pack frame

		self.scrollbar.pack(fill=Y,expand=0,side=LEFT)

#====USER METHODS====

	def appendrow(self, data):
		'''data: The row contents as list/tuple. shadowdata will be the same.'''
		for i in range(len(data)):
			try:
				self.frames[i][1].insert(END, data[i])
				self.shadowdata[i].append(data[i])
			except IndexError:
				self.length += 1
				return
		for i in range(self.options["columns"] - len(data)):
			self.frames[i + len(data)][1].insert(END, _DEFAULT["BLANK"])
			self.shadowdata[i + len(data)].append(_DEFAULT["BLANK"])
		self.length += 1

	def setdata(self, data, mode = "row"):
		'''This function has two mode parameters: "row" and "column". It will set the data (list of lists/tuples) of the listbox, clearing it beforehand.'''
		if mode == "row":
			self.clear()
			for i in data:
				self.appendrow(i)
			self.length = len(data)
		elif mode == "column":
			#validate
			ln = len(data[0])
			if all([len(i) == ln for i in data]) == True: #check if all lists are the same length
				self.clear()
				for i in range(len(data)):
					for j in data[i]:
						self.frames[i][1].insert(END, j)
						self.shadowdata[i].append(j)
				self.length = ln
		if self.currentsely == None: return
		if self.currentsely > self.length - 1:
			self.currentsely = self.length - 1
		if self.currentsely < 0:
			self.currentsely = None

	def setcolumn(self, index, data, overrideval = False, modshdat = True):
		'''This function will set the contents of the column at index to data, data being a list/tuple of values. overrideval: No validation. Use with care!'''
		if not overrideval:
			#validate
			if len(data) != len(self.frames[index][1].get(0, END)):
				return
			#validation end
		self.frames[index][1].delete(0, END)
		for i in range(len(data)):
			self.frames[index][1].insert(END, data[i])
		if modshdat:
			self.shadowdata[index] = data

	def setcell(self, x, y, data):
		'''Sets the cell in row x at y to data(str)'''
		scroll = False
		if self.frames[x][1].yview()[1] == 1.0:
			scroll = True
		self.frames[x][1].delete(y)
		self.frames[x][1].insert(y, data)
		self.shadowdata[x][y] = data
		if scroll: self.__scrollalllistbox(self.frames[x][1].yview()[1], 1.0)

	def removerow(self, index=None):
		'''Will delete a row at index.'''
		if index == None or index > (self.length - 1):
			return
		for i in range(self.options["columns"]):
			self.frames[i][1].delete(index)
			self.shadowdata[i].pop(index)
		self.length -= 1
		if self.currentsely > (self.length - 1):
			self.currentsely = self.length - 1
		if self.currentsely < 0:
			self.currentsely = None

	def clear(self):
		'''Clears the multiframe-list.'''
		for i in range(self.options["columns"]):
			self.frames[i][1].delete(0, END)
			self.shadowdata[i] = []
		self.length = 0
		self.currentselx = None
		self.currentsely = None

	def getselectedcell(self):
		'''Returns the currently selected cell as a tuple of length 2: (0, 0) starting in the top left corner; The two values may also be None.'''
		return (self.currentselx, self.currentsely)

	def getlastclick(self):
		'''Returns the coordinates in the listbox the last click was made in as a tuple. May consist of int or None.'''
		return (self.lastx, self.lasty)

	def getlen(self):
		'''Returns length of the multiframe-list'''
		return self.length

	def getrows(self, start, end = None):
		'''This function will return the contents of the multiframe-list from index start to end. If end is omitted, will only get the start row. If start is "all" (ALL), will return entire listbox contents.'''
		valuelist = []
		if end:
			getrange = end - start + 1
		else:
			getrange = 1
		if start == "all":
			getrange = len(self.frames[0][1].get(0,END))
			start = 0
		for i in range(getrange):
			valuelist.append([])
			for j in range(self.options["columns"]):
				valuelist[i].append(self.frames[j][1].get(i + start))
		else:
			return valuelist

	def getcolumn(self, index):
		'''Will return the contents of the column at index.'''
		return self.frames[index][1].get(0,END)

	def getcell(self, x, y):
		'''Returns element y in column x'''
		return self.frames[x][1].get(y)

	def getshadowdata(self, mode = "row"):
		'''Returns the shadowdata; mode: "row" or "column"'''
		res = []
		if mode == "row":
			if len(self.shadowdata) == 0:
				return
			for i in range(len(self.shadowdata[0])):#Assuming the shadowdata isn't broken and all lists have same length
				res.append([])
				for j in range(len(self.shadowdata)):
					res[i].append(self.shadowdata[j][i])
		elif mode == "column":
			res = self.shadowdata
		else: return
		return res

	def format(self):
		'''Format the entire list based on the functions in self.options["formatters"]. Call this after all input has been performed.'''
		for i in range(self.options["columns"]):
			if not self.options["formatters"][i]:
				pass
			else:
				self.setcolumn(i, [self.options["formatters"][i](j) for j in self.getcolumn(i)], True, False)

#====INTERNAL METHODS====

	def __setindex(self, event, button, rowindex, fromclick):
		'''Called by listboxes; GENERATES EVENT, sets the current index.'''
		if self.length == 0: return
		try:
			if button == _RIGHTCLICKBTN and fromclick:
				offset = event.widget.yview()[0] * self.length
				tosel = int(floor((event.y + - BORDERWIDTH) / ENTRYHEIGHT) + offset)
				if tosel < 0: return
				if tosel >= self.length: tosel = self.length - 1
				event.widget.selection_clear(0, END)
				event.widget.selection_set(tosel)
			sel = event.widget.curselection()[0]
			for i in self.frames:
				i[1].selection_clear(0, END)
				i[1].selection_set(sel)
				i[1].activate(sel)
			self.currentsely = sel
			self.currentselx = rowindex
			self.lastx = event.x
			self.lasty = event.y
			self.master.event_generate("<<MultiframeSelect>>", when = "tail")
			if button == _RIGHTCLICKBTN:
				self.master.event_generate("<<MultiframeRightclick>>", when = "tail")
		except Exception:
			pass

	def __scrollallbar(self, a, b, c = None): #c only appears when holding mouse and scrolling on the scrollbar
		'''Bound to the scrollbar; Will scroll listboxes'''
		if c:
			for i in range(self.options["columns"]):
				self.frames[i][1].yview(a, b, c)
		else:
			for i in range(self.options["columns"]):
				self.frames[i][1].yview(a, b)

	def __scrollalllistbox(self, a, b):
		'''Bound to all listboxes so that they will scroll the other ones and scrollbar.'''
		for i in range(self.options["columns"]):
			self.frames[i][1].yview_moveto(a)
		self.scrollbar.set(a, b)

	def __sort(self, event):
		'''This function will sort the list'''
		if len(self.frames) != 0:
			scroll = self.frames[0][1].yview()[0]
		id_ = event.widget.id
		sstate = event.widget.sortstate
		rev = False
		if sstate == 1: rev = True
		for i, j in enumerate(self.frames):
			if i == id_:
				j[2].sortstate = abs(sstate-1)
				continue
			j[2].sortstate = 0
		tmpshd = self.getshadowdata()
		content = sorted(tmpshd, key=itemgetter(id_), reverse=rev)
		self.setdata(content)
		self.format()
		self.__scrollalllistbox(scroll, 1.0)

if __name__ == "__main__":
	from random import randint
	def test():
		def priceconv(data):
			return str(data) + "$"
		root = Tk()
		mf = Multiframe(root, columns=5, names=("Name","Age","Author","Price","Length"), sort = 2, sorters=(True, True, False, False, True), widths = (None, 5, None, 10), formatters=(None, None, None, priceconv))
		for i in range(10):
			mf.appendrow((randint(0,100), randint(0,100), randint(0,100), randint(0,100), randint(0,100), randint(0,100), "Hello!", 9))
		mf.format()
		mf.pack(expand=1, fill=BOTH)
		addbutton = Button(root, text="Add", command=lambda: mf.appendrow((randint(0,100), randint(0,100), randint(0,100), randint(0,100), randint(0,100), randint(0,100), "eight", 9)))
		removebutton = Button(root, text="Remove", command=lambda: mf.removerow(mf.getselectedcell()[1]) )
		clearbutton = Button(root, text="Clear", command = mf.clear)
		getindexbutton = Button(root, text="Get selected cell", command = lambda: print(mf.getselectedcell()))
		getbutton = Button(root, text="Get", command=lambda: print(mf.getrows(mf.getselectedcell()[1])))
		getlenbutton = Button(root, text="Get length", command = lambda: print(mf.getlen()))
		setclmbtn = Button(root, text="Setclm", command= lambda: mf.setcolumn(2, (1,3,4,"5",9,"hi")))
		getshdw = Button(root, text = "Get SD", command = lambda: print(mf.getshadowdata()))
		getdat = Button(root, text = "Get D", command = lambda: print(mf.getrows(ALL)))
		addbutton.pack(fill = X, side = LEFT)
		removebutton.pack(fill = X, side = LEFT)
		getbutton.pack(fill = X, side = LEFT)
		getindexbutton.pack(fill = X, side = LEFT)
		clearbutton.pack(fill = X, side = LEFT)
		getlenbutton.pack(fill = X, side = LEFT)
		setclmbtn.pack(fill = X, side = LEFT)
		getshdw.pack(fill = X, side = LEFT)
		getdat.pack(fill = X, side = LEFT)
		root.mainloop()
	try:
		import traceback
		test()
	except Exception as e:
		print(str(e) + "\n\nMore info:\n======\n")
		traceback.print_exc()
		input()
		quit()
	import os
	if os.path.exists(os.path.join(os.getcwd(), "co")):
		import shutil
		shutil.copy2(os.path.join(os.getcwd(), "multiframe_list.py"), os.path.join(os.getcwd(), "Demomgr","multiframe_list.py"))