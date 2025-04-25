import os
import importlib.resources
import json
import shutil
import subprocess
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as tk_fid
import tkinter.messagebox as tk_msg
import typing as t

import multiframe_list.multiframe_list as mfl
from schema import SchemaError

from demomgr import constants as CNST
from demomgr import context_menus
from demomgr.config import Config
from demomgr.demo_info import DemoInfo
from demomgr.dialogues import *
from demomgr.explorer import open_explorer
from demomgr.helpers import build_date_formatter, convertunit
from demomgr import platforming
from demomgr.style_helper import StyleHelper
from demomgr.threadgroup import ThreadGroup, THREADGROUPSIG
from demomgr.threads import THREADSIG, ThreadFilter, ThreadReadFolder, ReadDemoMetaThread
from demomgr.tk_widgets import DmgrEntry, KeyValueDisplay, HeadedFrame, purge_commands


__version__ = "1.11.1"
__author__ = "Square789"


class DemoOp():
	__slots__ = ("name", "cmd", "button", "fit_for_selection_size")

	def __init__(
		self,
		name: str,
		cmd: t.Callable[[], None],
		button: t.Optional[tk.Button],
		fit_for_selection_size: t.Callable[[int], bool],
	) -> None:
		self.name = name
		self.cmd = cmd
		self.button = button
		self.fit_for_selection_size = fit_for_selection_size

	def __iter__(self):
		yield self.name
		yield self.cmd
		yield self.button
		yield self.fit_for_selection_size


class MainApp():
	def __init__(self) -> None:
		"""
		Initializes values, variables, reads config, checks for firstrun,
		applies UI style, sets up interface, then shows main window.
		"""
		self.root = tk.Tk()
		self.root.withdraw()

		self.RCB = platforming.get_rightclick_btn()

		self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
		self.root.wm_title(f"Demomgr v{__version__}")

		self.demooperations = (
			DemoOp("Play...", self._playdem, None, lambda s: s == 1),
			DemoOp("Delete/Copy/Move...", self._copy_move_delete_demos, None, lambda s: s > 0),
			# DemoOp("Rename...", self._rename, None, lambda s: s == 1),
			DemoOp("Manage bookmarks...", self._managebookmarks, None, lambda s: s == 1),
			DemoOp("Reveal in file manager...", self._open_file_manager, None, lambda _: True),
		)

		self.cfgpath = platforming.get_cfg_storage_path()
		self.curdir: t.Optional[str] = None
		self.spinboxvar = tk.StringVar()

		self.after_handle_statusbar = self.root.after(0, lambda: True)

		# Threading setup
		self.threadgroups = {
			"filter_select": ThreadGroup(ThreadFilter, self.root),
			"demometa": ThreadGroup(ReadDemoMetaThread, self.root),
			"fetchdata": ThreadGroup(ThreadReadFolder, self.root),
			"filter": ThreadGroup(ThreadFilter, self.root),
		}

		self.threadgroups["filter_select"].register_finalize_method(
			self._finalization_filter_select
		)
		self.threadgroups["fetchdata"].register_finalize_method(self._finalization_fetchdata)

		self.threadgroups["filter_select"].build_cb_method(self._after_callback_filter_select)
		self.threadgroups["demometa"].build_cb_method(self._after_callback_demoinfo)
		self.threadgroups["fetchdata"].build_cb_method(self._after_callback_fetchdata)
		self.threadgroups["filter"].build_cb_method(self._after_callback_filter)

		# startup routine
		if os.path.exists(self.cfgpath):
			self.cfg = self.getcfg()
		else:
			# see if an old (pre-1.10.1) config exists and migrate it
			old_cfgpath = platforming.get_old_cfg_storage_path()
			if os.path.exists(old_cfgpath):
				try:
					os.makedirs(os.path.dirname(self.cfgpath), exist_ok = True)
					shutil.move(old_cfgpath, self.cfgpath)
				except OSError as exc:
					tk_msg.showerror("Demomgr - Error", f"Error migrating config: {exc}")
					self.quit_app(False)
					return
				try:
					os.rmdir(os.path.dirname(old_cfgpath))
				except OSError:
					# Weird, since it may mean the dir is not empty. Just ignore it then.
					# The dir will be left like that forever but, as a wise man once said,
					# that's showbiz.
					pass
				self.cfg = self.getcfg()
			else:
				self.cfg = Config.get_default()

		if self.cfg is None:
			return

		try:
			quieres = importlib.resources.read_binary("demomgr.ui_themes", CNST.ICON_FILENAME)
			icon = tk.PhotoImage(data = quieres)
			self.root.tk.call("wm", "iconphoto", self.root._w, "-default", icon)
		except Exception as e:
			pass

		# load style (For FirstRun)
		self.ttkstyle = ttk.Style() # Used later-on too.
		# Fallback that is different depending on the platform.
		self._DEFAULT_THEME = self.ttkstyle.theme_use()
		self._applytheme()

		if self.cfg.first_run:
			fr_dialog = FirstRun(self.root)
			fr_dialog.show()
			if fr_dialog.result.state != DIAGSIG.SUCCESS:
				self.quit_app(False)
				return
			self.cfg.first_run = False

		self._setupgui()
		context_menus.decorate_root_window(self.root)

		ctxmen_name = platforming.get_contextmenu_btn()
		for class_tag in ("TEntry", "TCombobox"):
			self.root.bind_class(
				class_tag,
				f"<Button-{self.RCB}><ButtonRelease-{self.RCB}>",
				context_menus.entry_cb
			)
			# This interrupts the event seq above
			self.root.bind_class(
				class_tag,
				f"<Button-{self.RCB}><Leave><ButtonRelease-{self.RCB}>",
				lambda _: None
			)
			if ctxmen_name is not None:
				self.root.bind_class(
					class_tag, f"<KeyPress-{ctxmen_name}>", context_menus.entry_cb
				)

		last_path = self.cfg.demo_paths[0] if self.cfg.demo_paths else None
		if self.cfg.last_path is not None and 0 <= self.cfg.last_path < len(self.cfg.demo_paths):
			last_path = self.cfg.demo_paths[self.cfg.last_path]
		self.curdir = last_path
		self.spinboxvar.set("" if self.curdir is None else self.curdir)
		self.reloadgui()
		# All subsequent changes to the spinbox will call
		# self._spinboxsel -> self.reloadgui, and update main view.
		self.spinboxvar.trace("w", self._spinboxsel)

		self.root.deiconify() # end startup; show UI
		self.root.focus()

	def _setupgui(self) -> None:
		"""Sets up UI inside of self.root widget."""
		self.mainframe = ttk.Frame(self.root, padding = (5, 3, 5, 3))

		self.mainframe.grid_columnconfigure(0, weight = 10)
		self.mainframe.grid_columnconfigure(1, weight = 15)
		self.mainframe.grid_rowconfigure(3, weight = 2)
		self.mainframe.grid_rowconfigure(4, weight = 1)

		self.filterentry_var = tk.StringVar()

		widgetframe0 = ttk.Frame(self.mainframe) # Directory Selection, Settings/About
		widgetframe1 = ttk.Frame(self.mainframe) # Filtering / Cleanup by filter
		widgetframe2 = ttk.Frame(self.mainframe) # Buttons here interact with the currently selected demo
		self.listboxframe = ttk.Frame(self.mainframe)
		demoinfframe = HeadedFrame(self.mainframe, hlabel_conf = {"text": "Demo information"})
		dirinfframe = HeadedFrame(self.mainframe, hlabel_conf = {"text": "Directory information"})
		self.statusbar = ttk.Frame(self.mainframe, padding = (1, 2, 1, 1), style = "Statusbar.TFrame")

		dirinfframe.internal_frame.grid_columnconfigure(0, weight = 1)
		dirinfframe.internal_frame.grid_rowconfigure((1, 2), weight = 1)

		demoinfframe.internal_frame.grid_columnconfigure(0, weight = 1)
		demoinfframe.internal_frame.grid_rowconfigure(1, weight = 1)

		# Hardcoded weights that approximately relate to the length of each of the column's strings
		self.listbox = mfl.MultiframeList(
			self.listboxframe,
			inicolumns = (
				{"name": "Name", "col_id": "col_filename", "sort": True,
					"weight": round(1.5 * mfl.WEIGHT), "dblclick_cmd": lambda _: self._playdem()},
				{"name": "Killstreaks", "col_id": "col_ks", "sort": True,
					"weight": round(0.2 * mfl.WEIGHT),
					"formatter": lambda i: len(i.killstreak_peaks) if i is not None else "?",
					"sortkey": lambda i: len(i.killstreak_peaks) if i is not None else -1},
				{"name": "Bookmarks", "col_id": "col_bm", "sort": True,
					"weight": round(0.2 * mfl.WEIGHT),
					"formatter": lambda i: len(i.bookmarks) if i is not None else "?",
					"sortkey": lambda i: len(i.bookmarks) if i is not None else -1,
					"dblclick_cmd": lambda _: self._managebookmarks()},
				{"name": "Creation time", "col_id": "col_ctime", "sort": True,
					"weight": round(0.9 * mfl.WEIGHT),
					"formatter": build_date_formatter(self.cfg.date_format)},
				{"name": "Size", "col_id": "col_filesize", "sort": True,
					"weight": round(0.42 * mfl.WEIGHT), "formatter": convertunit}
			),
			rightclickbtn = self.RCB,
			resizable = True,
			reorderable = True,
		)

		self.pathsel_spinbox = ttk.Combobox(widgetframe0, state = "readonly")
		self.pathsel_spinbox.config(values = tuple(self.cfg.demo_paths))
		self.pathsel_spinbox.config(textvariable = self.spinboxvar)

		rempathbtn = ttk.Button(widgetframe0, text = "Remove demo path", command = self._rempath)
		addpathbtn = ttk.Button(widgetframe0, text = "Add demo path...", command = self._addpath)
		settingsbtn = ttk.Button(widgetframe0, text = "Settings...", command = self._opensettings)

		self.demo_header_kvd = KeyValueDisplay(
			demoinfframe.internal_frame, self.ttkstyle,
			inipairs = ({"id_": v, "name": v} for v in CNST.HEADER_HUMAN_NAMES.values()),
			width = 240, height = 80,
		)
		self.demoeventmfl = mfl.MultiframeList(
			demoinfframe.internal_frame,
			inicolumns = (
				{"name": "Type", "col_id": "col_type", "sort": True, "minsize": 40},
				{"name": "Tick", "col_id": "col_tick", "sort": True, "minsize": 30},
				{"name": "Value", "col_id": "col_value", "sort": False},
			),
			rightclickbtn = self.RCB,
			listboxheight = 5,
			selection_type = mfl.SELECTION_TYPE.SINGLE,
		)

		self.directory_inf_kvd = KeyValueDisplay(
			dirinfframe.internal_frame, self.ttkstyle, inipairs = (
				{"id_": "l_amount", "name": "Amount of demos"},
				{"id_": "l_totalsize", "name": "Size of demos", "formatter": convertunit},
			), width = 240, height = 60,
		)

		filterlabel = ttk.Label(widgetframe1, text = "Filter: ")
		self.filterentry = DmgrEntry(
			widgetframe1, CNST.FILTERSTR_MAX, textvariable = self.filterentry_var
		)
		self.filterentry.bind("<Return>", self._filter)
		self.filterbtn = ttk.Button(widgetframe1, text = "Apply filter", command = self._filter)
		self.resetfilterbtn = ttk.Button(
			widgetframe1, text = "Clear filter / Refresh", command = self.reloadgui
		)
		self.filter_select_btn = ttk.Button(
			widgetframe1, text = "Select by filter", command = self._filter_select
		)

		demo_op_label = ttk.Label(widgetframe2, text = "Selection:")
		for i, (s, cmd, _, _) in enumerate(self.demooperations):
			btn = ttk.Button(widgetframe2, text = s, command = cmd, state = tk.DISABLED)
			self.demooperations[i].button = btn

		self.statusbarlabel = ttk.Label(self.statusbar, text = "Ready.", style = "Statusbar.TLabel")

		#widget geometry mgmt here
		#widgetframe0
		self.pathsel_spinbox.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = (0, 3))
		rempathbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		addpathbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		settingsbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (3, 0))
		widgetframe0.grid(column = 0, row = 0, columnspan = 2, sticky = "ew", pady = 5)

		#widgetframe1
		filterlabel.pack(side = tk.LEFT, fill = tk.X, expand = 0)
		self.filterentry.pack(side = tk.LEFT, fill = tk.X, expand = 1, padx = 3)
		self.filterbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		self.resetfilterbtn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = 3)
		self.filter_select_btn.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (3, 0))
		widgetframe1.grid(column = 0, row = 1, columnspan = 2, sticky = "ew", pady = 5)

		#widgetframe2
		demo_op_label.pack(side = tk.LEFT, padx = (0, 5))
		for op in self.demooperations:
			op.button.pack(side = tk.LEFT, fill = tk.X, expand = 0, padx = (0, 6))
		widgetframe2.grid(column = 0, row = 2, columnspan = 2, sticky = "ew", pady = 5)

		#listbox
		self.listboxframe.grid_columnconfigure(0, weight = 1, minsize = 500)
		self.listboxframe.grid_rowconfigure(0, weight = 1)
		self.listbox.grid(column = 0, row = 0, sticky = "nesw")
		self.listboxframe.grid(column = 0, row = 3, rowspan = 2, sticky = "nesw")

		#demoinfframe
		self.demoeventmfl.grid(sticky = "nesw", padx = 5, pady = 5)
		self.demo_header_kvd.grid(sticky = "nesw", padx = 5, pady = (0, 5))
		demoinfframe.grid(column = 1, row = 3, sticky = "nesw", padx = 5)

		#dirinfframe
		self.directory_inf_kvd.grid(sticky = "nesw", padx = 5, pady = 5)
		dirinfframe.grid(column = 1, row = 4, sticky = "nesw", padx = 5, pady = (5, 0))

		#Statusbar
		self.statusbarlabel.pack(anchor = tk.W)
		self.statusbar.grid(column = 0, row = 5, columnspan = 2, sticky = "ew")

		#Main frame
		self.mainframe.pack(expand = 1, fill = tk.BOTH, side = tk.TOP, anchor = tk.NW)

		self.listbox.bind("<<MultiframeSelect>>", self._mfl_select_callback)
		self.listbox.bind("<<MultiframeRightclick>>", self._mfl_rc_callback)

		# # This will force the root window's dimensions to its initially requested one.
		# # Prevents irritating resize of the window for long paths that get written to the
		# # statusbar.
		# self.root.update()
		# self.root.wm_geometry(self.root.wm_geometry())

		# You know, it's actually much easier to just not put the paths onto the statusbar, so
		# I did that instead lul

	def quit_app(self, save_cfg: bool = True) -> None:
		for g in self.threadgroups.values():
			g.cancel_after() # Calling first to cancel running after callbacks asap
		for g in self.threadgroups.values():
			g.join_thread(finalize = False)
		if save_cfg:
			if self.curdir in self.cfg.demo_paths:
				self.cfg.last_path = self.cfg.demo_paths.index(self.curdir)
			self.writecfg()

		purge_commands(self.root)
		# Sometimes, TclErrors are produced on closing. Since the program always happens
		# to close fine though, suppress them. Maybe start logging stuff sometime.
		try:
			self.root.destroy()
		except tk.TclError as e:
			pass
		try:
			self.root.quit()
		except tk.TclError as e:
			pass

	def _mfl_rc_callback(self, event: tk.Event) -> None:
		context_menus.multiframelist_cb(event, self.listbox, self.demooperations)

	def _mfl_select_callback(self, event: tk.Event) -> None:
		self._config_action_buttons()
		# NOTE: After removing/deleting demos, an event will be fired with a then-empty
		# selection, which fills the demo event screen confusingly with the next demo's
		# event data/header. Prevent that with the if.
		if self.listbox.selection:
			self._updatedemowindow()

	def _config_action_buttons(self, force_disable = False) -> None:
		"""
		Reconfigs the state of action buttons based on the current
		selection as well as whether a valid directory is selected.
		"""
		disable = self.curdir is None or force_disable
		sel_len = len(self.listbox.selection)
		for (_, _, btn, fit_for_sel) in self.demooperations:
			state = tk.DISABLED if disable or not fit_for_sel(sel_len) else tk.NORMAL
			btn.configure(state = state)

	def _opensettings(self) -> None:
		"""Opens settings, acts based on results"""
		dialog = Settings(
			self.root,
			cfg = self.cfg,
			remember = self.cfg.ui_remember["settings"],
		)
		dialog.show()
		if dialog.result.state == DIAGSIG.GLITCHED:
			return

		self.cfg.ui_remember["settings"] = dialog.result.remember

		if dialog.result.state != DIAGSIG.SUCCESS:
			return

		# what a hardcoded piece of garbage, there must be better ways
		if self.cfg.date_format != dialog.result.data["date_format"]:
			self.listbox.config_column(
				"col_ctime", formatter = build_date_formatter(dialog.result.data["date_format"])
			)
		self.cfg.update(dialog.result.data)
		self.reloadgui()
		self._applytheme()

	def _open_file_manager(self) -> None:
		"""
		Opens file manager in the current directory.
		"""
		if self.curdir is None:
			return

		if self.cfg.file_manager_mode is CNST.FILE_MANAGER_MODE.WINDOWS_EXPLORER:
			try:
				open_explorer(
					self.curdir,
					[self.listbox.get_cell("col_filename", i) for i in sorted(self.listbox.selection)]
				)
			except OSError as e:
				tk_msg.showerror(
					"Demomgr - Error", f"Error launching explorer: {e}", parent = self.root
				)

		elif self.cfg.file_manager_mode is CNST.FILE_MANAGER_MODE.USER_DEFINED:
			if self.cfg.file_manager_path is None:
				tk_msg.showinfo(
					"Demomgr",
					"No file manager specified, please do so in Settings > Paths.",
					parent = self.root
				)
				return

			final_args = []
			for arg, is_template in self.cfg.file_manager_launchcmd:
				if not is_template:
					final_args.append(arg)
					continue

				if arg == "D":
					# Shouldn't be possible to get here when it's None, but better be safe
					final_args.append(self.curdir if self.curdir is not None else "")
				elif arg == "S" or arg == "s":
					d = self.listbox.get_column("col_filename")
					if self.listbox.selection:
						final_args.extend(d[i] for i in self.listbox.selection)
					elif arg == "s":
						final_args.append("")

			try:
				subprocess.Popen([self.cfg.file_manager_path] + final_args)
			except FileNotFoundError:
				tk_msg.showinfo(
					"Demomgr - Error", "File manager executable not found.", parent = self.root
				)
			except OSError as e:
				tk_msg.showerror(
					"Demomgr - Error", f"Error launching file manager: {e}", parent = self.root
				)

	def _playdem(self) -> None:
		"""
		Opens play dialog for the currently selected demo.
		"""
		if not self.listbox.selection:
			return

		index = next(iter(self.listbox.selection))
		demo_info = self.listbox.get_cell("col_ks", index)
		dialog = Play(
			self.root,
			demo_dir = self.curdir,
			info = DemoInfo(
				self.listbox.get_cell("col_filename", index),
				[] if demo_info is None else demo_info.killstreaks,
				[] if demo_info is None else demo_info.bookmarks,
			),
			cfg = self.cfg,
			style = self.ttkstyle,
			remember = self.cfg.ui_remember["launch_tf2"],
		)
		dialog.show()
		if dialog.result.state == DIAGSIG.GLITCHED:
			return
		self.cfg.ui_remember["launch_tf2"] = dialog.result.remember

	def _copy_move_delete_demos(self) -> None:
		"""
		Opens a bulk operator dialog on the selected demos and applies
		its return values.
		"""
		if not self.listbox.selection:
			return

		file_idx_map = {
			self.listbox.get_cell("col_filename", i): i
			for i in self.listbox.selection
		}
		dialog = BulkOperator(
			self.root,
			demodir = self.curdir,
			files = [
				x for i, x in enumerate(self.listbox.get_column("col_filename"))
				if i in self.listbox.selection
			],
			cfg = self.cfg,
			styleobj = self.ttkstyle,
			remember = self.cfg.ui_remember["bulk_operator"],
		)
		dialog.show()
		if dialog.result.state == DIAGSIG.GLITCHED:
			return

		self.cfg.ui_remember["bulk_operator"] = dialog.result.remember

		if dialog.result.state != DIAGSIG.SUCCESS:
			return

		# Processed demos are gone when they were deleted/moved. Update only necessary then.
		if dialog.result.data["operation"] != CNST.BULK_OPERATION.COPY:
			if not self.cfg.lazy_reload:
				self.reloadgui()
				return

			to_remove = [file_idx_map[file] for file in dialog.result.data["processed_files"]]
			self.directory_inf_kvd.set_value(
				"l_amount",
				self.directory_inf_kvd.get_value("l_amount") - len(to_remove)
			)
			self.directory_inf_kvd.set_value(
				"l_totalsize",
				self.directory_inf_kvd.get_value("l_totalsize") - sum(
					self.listbox.get_cell("col_filesize", index) for index in to_remove
				)
			)
			self.listbox.remove_rows(to_remove)
			self._updatedemowindow(clear = True)

	# def _rename(self) -> None:
	# 	"""Opens the rename dialog"""
	# 	if not self.listbox.selection:
	# 		return

	# 	index = next(iter(self.listbox.selection))
	# 	target = self.listbox.get_cell("col_filename", index)
	# 	dialog = Rename(self.root, self.cfg, self.curdir, target)
	# 	dialog.show()
	# 	if dialog.result.state != DIAGSIG.SUCCESS:
	# 		return

	# 	if not self.cfg.lazy_reload:
	# 		self.reloadgui()
	# 	else:
	# 		self.listbox.set_cell("col_filename", index, dialog.result.data)

	def _managebookmarks(self) -> None:
		"""Offers dialog to manage a demo's bookmarks."""
		if not self.listbox.selection:
			return

		index = next(iter(self.listbox.selection))
		demo_name = self.listbox.get_cell("col_filename", index)
		path = os.path.join(self.curdir, demo_name)
		info = self.listbox.get_cell("col_bm", index)
		dialog = BookmarkSetter(
			self.root,
			targetdemo = path,
			bm_dat = None if info is None else info.bookmarks,
			styleobj = self.ttkstyle,
			cfg = self.cfg,
		)
		dialog.show()
		if dialog.result.state != DIAGSIG.SUCCESS:
			return

		if not self.cfg.lazy_reload:
			self.reloadgui()
			return

		if self.cfg.data_grab_mode == CNST.DATA_GRAB_MODE.NONE.value:
			return

		container_state = dialog.result.data["containers"][self.cfg.data_grab_mode - 1]
		if container_state is None:
			return

		if container_state:
			# FIXME The DemoInfo object is stored both in col_bm and col_ks, so the change is
			# visible in both. See multiframe_list issue #7
			info = self.listbox.get_cell("col_bm", index)
			if info is None:
				info = DemoInfo(demo_name, [], dialog.result.data["bookmarks"])
				# This is nasty, info needs to be inserted here
				self.listbox.set_cell("col_ks", index, info)
				self.listbox.set_cell("col_bm", index, info)
			else:
				info.bookmarks = dialog.result.data["bookmarks"]
		else:
			# Container doesn't exist anymore; the info is now None.
			self.listbox.set_cell("col_ks", index, None)
			self.listbox.set_cell("col_bm", index, None)
		self.listbox.format(("col_bm", "col_ks"), (index, ))
		self._updatedemowindow(no_io = True)

	def _applytheme(self) -> None:
		"""
		Looks at self.cfg, attempts to apply an interface theme using a
		StyleHelper.
		"""
		if self.cfg.ui_theme == "_DEFAULT":
			self.root.tk.call("ttk::setTheme", self._DEFAULT_THEME)
			return

		try:
			theme_tuple = CNST.THEME_PACKAGES[self.cfg.ui_theme]
		except KeyError:
			tk_msg.showerror("Demomgr - Error", "Cannot find Tcl theme, using default.")
			return

		try:
			stylehelper = StyleHelper(self.root)
			with \
				importlib.resources.path("demomgr.ui_themes", theme_tuple[0]) as tcl_p, \
				importlib.resources.path("demomgr.ui_themes", theme_tuple[2]) as dir_p \
			:
				theme_path = str(tcl_p.absolute())
				imgdir = str(dir_p.absolute())
				stylehelper.load_image_dir(imagedir = imgdir, filetypes = ("png", ), imgvarname = "IMG")
				stylehelper.load_theme(theme_path, theme_tuple[1])

		except tk.TclError as error:
			tk_msg.showerror("Demomgr - Error", f"A Tcl error occurred:\n{error}")
		except OSError as error:
			tk_msg.showerror(
				"Demomgr - Error",
				f"The theme file was not found or a permission problem occurred:\n{error}"
			)

	def _updatedemowindow(self, clear: bool = False, no_io: bool = False) -> None:
		"""
		Renews contents of demo information windows.
		When `clear` is set to `True`, just clears the associated
		widgets and returns.
		If `no_io` is set to `True`, will not start a DemoMeta thread.
		"""
		index = self.listbox.get_active_cell()[1]
		if clear or not no_io:
			self.demo_header_kvd.clear()
		self.demoeventmfl.clear()
		if clear or index is None:
			return

		info = self.listbox.get_cell("col_ks", index)
		if info is not None:
			for events, name in (
				(info.killstreak_peaks, "Killstreak"),
				(info.bookmarks, "Bookmark"),
			):
				for event in events:
					self.demoeventmfl.insert_row({
						"col_type": name,
						"col_tick": event.tick,
						"col_value": str(event.value),
					})

		if not self.cfg.preview_demos or no_io:
			return

		demname = self.listbox.get_cell("col_filename", index)
		# In case of a super slow drive, this will hang in order to
		# prevent multiple referenceless threads going wild in the demo directory
		self.threadgroups["demometa"].join_thread()
		self.threadgroups["demometa"].start_thread(
			target_demo_path = os.path.join(self.curdir, demname)
		)

	def _after_callback_demoinfo(self, sig: THREADSIG, *args) -> None:
		"""
		Loop worker for the demo_info thread.
		Updates demo info window with I/O-obtained information.
		(Incomplete, requires `self`-dependent decoration in __init__())
		"""
		if sig.value < 0x100: # Finish
			return THREADGROUPSIG.FINISHED
		elif sig is THREADSIG.RESULT_HEADER:
			if args[0] is None:
				for v in CNST.HEADER_HUMAN_NAMES.values():
					self.demo_header_kvd.set_value(v, "?")
			else:
				for k, v in args[0].items():
					if k in CNST.HEADER_HUMAN_NAMES:
						self.demo_header_kvd.set_value(CNST.HEADER_HUMAN_NAMES[k], str(v))
			return THREADGROUPSIG.CONTINUE
		elif sig is THREADSIG.RESULT_FS_INFO:
			return THREADGROUPSIG.CONTINUE

	def reloadgui(self) -> None:
		"""
		Re-fetches the current directory's contents, cancelling all
		running threads, clearing all information displays and then
		starting the fetchdata thread.
		If the current directory is `None`, will display a message on
		the status bar instead of starting the fetchdata thread.
		"""
		for g in self.threadgroups.values():
			g.cancel_after()
		self.listbox.clear()
		self.directory_inf_kvd.clear()
		self._config_action_buttons(force_disable = True)
		self._updatedemowindow(clear = True)
		for g in self.threadgroups.values():
			g.join_thread(finalize = False)
		if self.curdir is None:
			self.setstatusbar(
				"No directories registered. Click \"Add demo path...\" to get started!"
			)
		else:
			self.threadgroups["fetchdata"].start_thread(targetdir = self.curdir, cfg = self.cfg)

	def _after_callback_fetchdata(self, sig: THREADSIG, *args) -> None:
		"""
		Loop worker for the after callback decorator stub.
		Grabs thread signals from the fetchdata queue and
		acts accordingly.
		(Incomplete, requires `self`-dependent decoration in __init__())
		"""
		if sig.is_finish_signal():
			return THREADGROUPSIG.FINISHED
		elif sig is THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*args)
		elif sig is THREADSIG.RESULT_DEMODATA:
			data = args[0]
			if data is not None:
				self.directory_inf_kvd.set_value("l_amount", len(data["col_filename"]))
				self._display_demo_data(data)
				self._config_action_buttons()
		return THREADGROUPSIG.CONTINUE

	def _finalization_fetchdata(self, *_) -> None:
		self.directory_inf_kvd.set_value(
			"l_totalsize", sum(self.listbox.get_column("col_filesize"))
		)

	def _filter_select(self) -> None:
		"""
		Starts the filter-select thread after disabling the invoking button.
		"""
		if self.filterentry_var.get() == "":
			return
		self.filter_select_btn.config(text = "Select by filter", state = tk.DISABLED)
		self.threadgroups["filter_select"].start_thread(
			filterstring = self.filterentry_var.get(),
			curdir = self.curdir,
			silent = True,
			cfg = self.cfg,
		)

	def _after_callback_filter_select(self, sig: THREADSIG, *args) -> None:
		"""
		Loop worker for the after callback decorator stub.
		Grabs thread signals from the filter-select queue and acts
		accordingly, making a selection once the thread is done.
		(Incomplete, requires `self`-dependent decoration in __init__())
		"""
		if sig.is_finish_signal():
			self.filter_select_btn.config(text = "Select by filter", state = tk.NORMAL)
			return THREADGROUPSIG.FINISHED
		elif sig is THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*args[0])
			return THREADGROUPSIG.CONTINUE
		elif sig is THREADSIG.RESULT_DEMODATA:
			return THREADGROUPSIG.HOLDBACK

	def _finalization_filter_select(self, sig: THREADSIG, *args) -> None:
		if sig is None:
			return
		if sig is not THREADSIG.RESULT_DEMODATA: # weird
			return

		filtered_files = set(args[0]["col_filename"])
		col_data = self.listbox.get_column("col_filename")
		new_selection = [i for i, name in enumerate(col_data) if name in filtered_files]

		self.listbox.set_selection(new_selection)

	def _filter(self, *_) -> None:
		"""Starts a filtering thread and configures the filtering button."""
		if not self.filterentry_var.get() or self.curdir is None:
			return
		self.filterbtn.config(text = "Stop Filtering", command = self._stopfilter)
		self.filterentry.unbind("<Return>")
		self.resetfilterbtn.config(state = tk.DISABLED)
		self.threadgroups["filter"].start_thread(
			filterstring = self.filterentry_var.get(),
			curdir = self.curdir,
			silent = False,
			cfg = self.cfg,
		)

	def _stopfilter(self) -> None:
		"""
		Stops the filtering thread by calling the threadgroup's join method.
		As this invokes the after callback, button states will be reverted.
		"""
		self.threadgroups["filter"].join_thread()

	def _after_callback_filter(self, sig: THREADSIG, *args) -> None:
		"""
		Loop worker for the after handler callback stub.
		Grabs elements from the filter queue and updates the statusbar with
		the filtering progress. If the thread is done, fills listbox with new
		dataset.
		(Incomplete, requires `self`-dependent decoration in __init__())
		"""
		if sig.is_finish_signal(): # Finish
			if sig is THREADSIG.ABORTED:
				self.setstatusbar("", 0)
			self.resetfilterbtn.config(state = tk.NORMAL)
			self.filterbtn.config(text = "Apply Filter", command = self._filter)
			self.filterentry.bind("<Return>", self._filter)
			self._updatedemowindow(clear = True)
			return THREADGROUPSIG.FINISHED
		elif sig is THREADSIG.INFO_STATUSBAR:
			self.setstatusbar(*args[0])
			return THREADGROUPSIG.CONTINUE
		elif sig is THREADSIG.RESULT_DEMODATA:
			self._display_demo_data(args[0])
			return THREADGROUPSIG.CONTINUE

	def _display_demo_data(self, data: t.Dict) -> None:
		"""
		Sets the main listbox to display demo data as delivered by the
		ReadFolder and Filter thread. Mutates `data` before feeding it
		to the listbox.
		"""
		di = data.pop("col_demo_info")
		data["col_bm"] = data["col_ks"] = di
		self.listbox.set_data(data)
		self.listbox.format()

	def _spinboxsel(self, *_) -> None:
		"""
		Observer callback to self.spinboxvar; is called whenever
		self.spinboxvar (so the combobox) is updated.
		Also triggered by self._rempath.
		Kicks off the process of reading the current directory.
		"""
		selpath = self.spinboxvar.get() or None
		if selpath != self.curdir:
			self.curdir = selpath
			self.reloadgui()

	def setstatusbar(self, data: str, timeout: t.Optional[int] = None) -> None:
		"""
		Sets the statusbar text to `data`, resetting it to a default
		after `timeout` msecs, or keeping it indefinitely if `timeout`
		is None.
		"""
		self.statusbarlabel.after_cancel(self.after_handle_statusbar)
		self.statusbarlabel.config(text = str(data))
		if timeout is not None:
			self.after_handle_statusbar = self.statusbarlabel.after(
				timeout, lambda: self.setstatusbar(CNST.STATUSBARDEFAULT)
			)

	def _addpath(self) -> None:
		"""
		Offers a directory selection dialog and writes the selected
		directory path to config after validating.
		"""
		dirpath = tk_fid.askdirectory(title = "Select the folder containing your demos.")
		# askdirectory can return empty tuples if it feels like it
		if type(dirpath) is not str or not dirpath:
			return
		if dirpath in self.cfg.demo_paths:
			return
		self.cfg.demo_paths.append(dirpath)
		self.pathsel_spinbox.config(values = tuple(self.cfg.demo_paths))
		self.spinboxvar.set(dirpath)

	def _rempath(self) -> None:
		"""
		Removes the current directory from the registered directories,
		automatically moves to another one or sets the current directory
		to `None` if none are available anymore.
		"""
		if not self.cfg.demo_paths:
			return
		popindex = self.cfg.demo_paths.index(self.curdir)
		self.cfg.demo_paths.pop(popindex)
		if len(self.cfg.demo_paths) > 0:
			self.spinboxvar.set(self.cfg.demo_paths[(popindex - 1) % len(self.cfg.demo_paths)])
		else:
			self.spinboxvar.set("")
		self.pathsel_spinbox.config(values = tuple(self.cfg.demo_paths))

	def writecfg(self) -> None:
		"""
		Writes the `Config` in `self.cfg` to self.cfgpath, converted to JSON.
		On write error, opens the CfgError dialog, blocking until the issue is
		fixed.
		"""
		write_ok = False
		cfg_dir = os.path.dirname(self.cfgpath) # self.cfgpath ends in a file, should be ok
		while not write_ok:
			try:
				if not os.path.exists(cfg_dir):
					# exist_ok is unnecessary but as long as it gets created, whatever
					os.makedirs(cfg_dir, exist_ok = True)
				with open(self.cfgpath, "w", encoding = "utf-8") as handle:
					handle.write(self.cfg.to_json())
				write_ok = True
			except OSError as error:
				dialog = CfgError(self.root, cfgpath = self.cfgpath, error = error, mode = 1)
				dialog.show()
				if dialog.result.data == 0: # Retry
					pass
				elif dialog.result.data == 1: # Config replaced by dialog
					pass
				elif dialog.result.data == 2 or dialog.result.state == DIAGSIG.GLITCHED: # Quit
					self.quit_app(False)
					return

	def getcfg(self) -> t.Optional[Config]:
		"""
		Gets config from self.cfgpath and returns it. On error, blocks
		until program is closed, config is replaced or fixed.
		If the user chose to quit demomgr after an error, this method will
		return `None`.
		"""
		cfg = None
		while cfg is None:
			try:
				with open(self.cfgpath, "r", encoding = "utf-8") as f:
					cfg = Config(json.load(f))
			except (OSError, json.decoder.JSONDecodeError, SchemaError, TypeError) as exc:
				dialog = CfgError(self.root, cfgpath = self.cfgpath, error = exc, mode = 0)
				dialog.show()
				if dialog.result.data == 0: # Retry
					pass
				elif dialog.result.data == 1: # Config replaced by dialog
					pass
				elif dialog.result.data == 2 or dialog.result.state == DIAGSIG.GLITCHED: # Quit
					self.quit_app(False)
					return None
		return cfg
