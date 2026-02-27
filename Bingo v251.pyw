import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sqlite3
import os
import subprocess
import configparser
from datetime import datetime

# --- CONFIGURATION ---
APP_PATH = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_PATH, 'config.ini')

# ==========================================
#   PART 1: DATABASE MANAGER
# ==========================================
class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name
        self.check_and_migrate_db()

    def check_and_migrate_db(self):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(info)")
            columns = [row[1] for row in cursor.fetchall()]
            if "sort_order" not in columns:
                cursor.execute("ALTER TABLE info ADD COLUMN sort_order INTEGER")
                cursor.execute("UPDATE info SET sort_order = id")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Database migration warning: {e}")

    def fetch_data(self):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM info ORDER BY sort_order ASC")
            data = cursor.fetchall()
            conn.close()
            return data
        except sqlite3.Error:
            return []

    def get_record_by_url(self, url):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM info WHERE URL = ?", (url,))
        row = cursor.fetchone()
        conn.close()
        return row

    def swap_rows(self, id1, id2):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT sort_order FROM info WHERE id=?", (id1,))
            res1 = cursor.fetchone()
            cursor.execute("SELECT sort_order FROM info WHERE id=?", (id2,))
            res2 = cursor.fetchone()
            if res1 and res2:
                order1, order2 = res1[0], res2[0]
                cursor.execute("UPDATE info SET sort_order=? WHERE id=?", (order2, id1))
                cursor.execute("UPDATE info SET sort_order=? WHERE id=?", (order1, id2))
                conn.commit()
        except Exception as e: print(f"Swap error: {e}")
        finally: conn.close()

    def move_to_top(self, record_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MIN(sort_order) FROM info")
            min_val = cursor.fetchone()[0]
            new_val = (min_val - 1) if min_val is not None else 0
            cursor.execute("UPDATE info SET sort_order=? WHERE id=?", (new_val, record_id))
            conn.commit()
        except Exception as e: print(f"Top error: {e}")
        finally: conn.close()

    def move_to_bottom(self, record_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(sort_order) FROM info")
            max_val = cursor.fetchone()[0]
            new_val = (max_val + 1) if max_val is not None else 0
            cursor.execute("UPDATE info SET sort_order=? WHERE id=?", (new_val, record_id))
            conn.commit()
        except Exception as e: print(f"Bottom error: {e}")
        finally: conn.close()

    def update_record(self, record_id, **kwargs):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        columns = self.get_columns()
        set_clause = ', '.join([f"{col} = ?" for col in kwargs.keys() if col in columns])
        query = f"UPDATE info SET {set_clause} WHERE id = ?"
        cursor.execute(query, list(kwargs.values()) + [record_id])
        conn.commit()
        conn.close()

    def update_multiple_tags(self, record_ids, tags):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        placeholders = ', '.join(['?'] * len(record_ids))
        query = f"UPDATE info SET Searchwords = ? WHERE id IN ({placeholders})"
        cursor.execute(query, [tags] + list(record_ids))
        conn.commit()
        conn.close()

    def add_record(self, **kwargs):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        columns = self.get_columns()
        valid_kwargs = {k: v for k, v in kwargs.items() if k in columns}
        if "sort_order" in columns and "sort_order" not in valid_kwargs:
            cursor.execute("SELECT MAX(sort_order) FROM info")
            max_val = cursor.fetchone()[0] or 0
            valid_kwargs["sort_order"] = max_val + 1
        cols = ', '.join(valid_kwargs.keys())
        placeholders = ', '.join(['?' for _ in valid_kwargs])
        cursor.execute(f"INSERT INTO info ({cols}) VALUES ({placeholders})", list(valid_kwargs.values()))
        conn.commit()
        conn.close()

    def delete_record(self, record_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM info WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()

    def get_columns(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(info)")
        cols = [row[1] for row in cursor.fetchall()]
        conn.close()
        return cols

# ==========================================
#   PART 2: MAIN APPLICATION (GUI)
# ==========================================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Bingo Search v2.5.1")
        self.root.geometry("300x500")
        self.root.configure(bg='#2c2f33')
        self.root.attributes("-topmost", True)

        self.is_docked = False
        self.current_state = "expanded"
        self.dock_x = 0
        self.visible_margin = 8
        self.after_id = None

        self.data_copy = []
        self.db_manager = None
        self.file_path = None
        self.last_mtime = 0
        self.favorites = {}

        self.show_window()
        self.load_config()
        self.monitor_database_changes()

    def show_window(self):
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.style.configure("Treeview", background="black", foreground="white", fieldbackground="black", font=("Helvetica", 10, "bold"))
        self.style.configure("Treeview.Heading", background="gray", foreground="black", font=("Helvetica", 12, "bold"))
        self.style.map('Treeview', background=[('selected', 'green')], foreground=[('selected', 'white')])

        # Search field
        search_frame = tk.Frame(self.root, bg='#2c2f33')
        search_frame.pack(pady=10, padx=10, fill=tk.X)
        tk.Label(search_frame, text="Search:", font=("Arial", 10, "bold"), fg="white", bg='#2c2f33').pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Arial", 11))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.search_entry.bind("<KeyRelease>", self.filter_treeview)

        # Treeview (Extended selection)
        self.tree = ttk.Treeview(self.root, columns=("Col1", "Col2", "Col3"), show="headings", selectmode="extended")
        self.tree.heading("Col2", text="Description")
        self.tree.column("Col1", width=0, stretch=False)
        self.tree.column("Col3", width=0, stretch=False)
        self.tree.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)

        self.tree.bind("<Double-1>", lambda e: self.start_program())
        self.tree.bind("<Button-3>", self.show_popup_menu)
        self.tree.bind('<Control-v>', self.on_paste)

        # KEYBOARD BINDINGS FOR MOVE UP/DOWN
        self.tree.bind('<Control-Up>', self.move_up_keyboard)
        self.tree.bind('<Control-Down>', self.move_down_keyboard)

        self.root.bind("<Enter>", self.on_mouse_enter)
        self.root.bind("<Leave>", self.on_mouse_leave)

        # Menus
        self.menu = tk.Menu(self.root)
        self.root.config(menu=self.menu)

        self.file_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Open Database", command=self.open_database)
        self.file_menu.add_command(label="Create New Database", command=self.create_new_database)
        self.file_menu.add_separator()

        self.dock_var = tk.BooleanVar(value=False)
        self.file_menu.add_checkbutton(label="Auto-Dock Window", variable=self.dock_var, command=self.toggle_dock)

        self.file_menu.add_separator()
        self.file_menu.add_command(label="Add to Favorites", command=self.add_to_favorites)
        self.file_menu.add_command(label="Exit", command=self.root.destroy)

        self.favorites_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Favorites", menu=self.favorites_menu)

        # Bottom panel
        bottom_frame = tk.Frame(self.root, bg='#2c2f33')
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.bottom_label = tk.Label(bottom_frame, text="No database", bg='#2c2f33', fg="#aaaaaa", font=("Arial", 8))
        self.bottom_label.pack(side=tk.LEFT, padx=10, pady=2)
        self.dock_check = tk.Checkbutton(bottom_frame, text="Auto-Dock", variable=self.dock_var, command=self.toggle_dock, bg='#2c2f33', fg="white", selectcolor="black", activebackground='#2c2f33')
        self.dock_check.pack(side=tk.RIGHT, padx=10)

        self.popup_menu = tk.Menu(self.root, tearoff=0)

    # --- DOCKING ---
    def toggle_dock(self):
        self.is_docked = self.dock_var.get()
        if self.is_docked:
            self.dock_x = self.root.winfo_x()
            self.collapse()
        else:
            self.expand()

    def expand(self):
        if self.after_id: self.root.after_cancel(self.after_id); self.after_id = None
        if self.current_state == "collapsed":
            self.root.geometry(f"+{self.dock_x}+{self.root.winfo_y()}")
            self.root.attributes("-alpha", 1.0)
            self.current_state = "expanded"

    def collapse(self):
        if self.is_docked and self.current_state == "expanded":
            hidden_x = self.dock_x - self.root.winfo_width() + self.visible_margin
            self.root.geometry(f"+{hidden_x}+{self.root.winfo_y()}")
            self.root.attributes("-alpha", 0.01)
            self.current_state = "collapsed"

    def on_mouse_enter(self, event):
        if self.is_docked: self.expand()

    def on_mouse_leave(self, event):
        if self.is_docked:
            if self.after_id: self.root.after_cancel(self.after_id)
            self.after_id = self.root.after(250, self._delayed_collapse)

    def _delayed_collapse(self):
        mx, my = self.root.winfo_pointerxy()
        wx, wy = self.root.winfo_x(), self.root.winfo_y()
        ww, wh = self.root.winfo_width(), self.root.winfo_height()
        if not (wx <= mx <= wx + ww and wy <= my <= wy + wh):
            self.collapse()
        self.after_id = None

    # --- POPUP MENU ---
    def show_popup_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item and item not in self.tree.selection():
            self.tree.selection_set(item)

        selection = self.tree.selection()
        if not selection: return

        self.popup_menu.delete(0, tk.END)

        if len(selection) == 1:
            self.popup_menu.add_command(label="Edit", command=lambda: self.add_item("edit"))
            self.popup_menu.add_command(label="Go", command=self.start_program)
            self.popup_menu.add_separator()
            self.popup_menu.add_command(label="Move to Top", command=lambda: self.move_item("top"))
            self.popup_menu.add_command(label="Move to Bottom", command=lambda: self.move_item("bottom"))
        else:
            self.popup_menu.add_command(label=f"Set Common Tag ({len(selection)})", command=self.set_common_tags)
            self.popup_menu.add_separator()
            self.popup_menu.add_command(label="Move to Top", command=lambda: self.move_item("top"))
            self.popup_menu.add_command(label="Move to Bottom", command=lambda: self.move_item("bottom"))

        self.popup_menu.add_separator()
        self.popup_menu.add_command(label="Move Up", command=lambda: self.move_item("up"))
        self.popup_menu.add_command(label="Move Down", command=lambda: self.move_item("down"))
        self.popup_menu.add_separator()

        self.copy_menu = tk.Menu(self.popup_menu, tearoff=0)
        self.popup_menu.add_cascade(label="Copy to...", menu=self.copy_menu)
        if self.favorites:
            for name, path in self.favorites.items():
                self.copy_menu.add_command(label=name, command=lambda p=path: self.copy_item_to_db(p))
        else:
            self.copy_menu.add_command(label="(No favorites)", state="disabled")

        self.popup_menu.add_separator()
        self.popup_menu.add_command(label="Delete", command=self.delete_item)

        if len(selection) == 1:
            self.popup_menu.add_command(label="Copy URL", command=self.copy_url)

        self.popup_menu.add_separator()

        can_paste = False
        try:
            if self.root.clipboard_get().strip(): can_paste = True
        except: pass
        self.popup_menu.add_command(label="Paste", command=self.on_paste, state="normal" if can_paste else "disabled")

        self.popup_menu.post(event.x_root, event.y_root)

    # --- CORE LOGIC ---
    def move_item(self, direction):
        if not self.db_manager: return
        sel = list(self.tree.selection())
        if not sel: return

        sel_ids = [str(self.tree.item(i, "values")[0]) for i in sel]
        sel.sort(key=lambda x: self.tree.index(x))

        if direction == "top":
            for item in reversed(sel):
                self.db_manager.move_to_top(self.tree.item(item, "values")[0])
        elif direction == "bottom":
            for item in sel:
                self.db_manager.move_to_bottom(self.tree.item(item, "values")[0])
        elif direction == "up":
            target = self.tree.prev(sel[0])
            if not target: return
            target_id = self.tree.item(target, "values")[0]
            for item in sel:
                self.db_manager.swap_rows(self.tree.item(item, "values")[0], target_id)
        elif direction == "down":
            target = self.tree.next(sel[-1])
            if not target: return
            target_id = self.tree.item(target, "values")[0]
            for item in reversed(sel):
                self.db_manager.swap_rows(self.tree.item(item, "values")[0], target_id)

        self.refresh_data()

        new_sel = []
        for child in self.tree.get_children():
            if str(self.tree.item(child, "values")[0]) in sel_ids:
                new_sel.append(child)
        self.tree.selection_set(new_sel)
        if new_sel: self.tree.see(new_sel[0])

    def move_up_keyboard(self, event):
        self.move_item("up")
        return "break"

    def move_down_keyboard(self, event):
        self.move_item("down")
        return "break"

    def add_item(self, add_edit):
        item = self.tree.selection()
        values = self.tree.item(item[0], "values") if item else []

        add_window = tk.Toplevel(self.root)
        add_window.title("Item Details")

        self.root.update_idletasks()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_w = self.root.winfo_width()
        new_x = root_x + root_w + 10

        add_window.geometry(f"600x500+{new_x}+{root_y}")
        add_window.configure(bg='#2c2f33')
        add_window.transient(self.root)

        form_frame = tk.Frame(add_window, bg='#2c2f33')
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(form_frame, text="Description:", bg='#2c2f33', fg="white", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=5)
        desc_e = ttk.Entry(form_frame, font=("Arial", 10))
        desc_e.grid(row=0, column=1, sticky="ew", pady=5, padx=10)

        tk.Label(form_frame, text="URL / Path:", bg='#2c2f33', fg="white", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w", pady=5)
        url_e = ttk.Entry(form_frame, font=("Arial", 10))
        url_e.grid(row=1, column=1, sticky="ew", pady=5, padx=10)

        tk.Label(form_frame, text="Tags:", bg='#2c2f33', fg="white", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky="w", pady=5)
        tags_e = ttk.Entry(form_frame, font=("Arial", 10))
        tags_e.grid(row=2, column=1, sticky="ew", pady=5, padx=10)

        tk.Label(form_frame, text="Info:", bg='#2c2f33', fg="white", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky="nw", pady=5)
        info_t = scrolledtext.ScrolledText(form_frame, wrap=tk.WORD, width=40, height=12)
        info_t.grid(row=3, column=1, sticky="ew", pady=5, padx=10)

        form_frame.columnconfigure(1, weight=1)

        if add_edit == "edit" and values:
            desc_e.insert(0, values[1])
            url_e.insert(0, values[8])
            info_t.insert("1.0", values[9])
            if len(values) > 13: tags_e.insert(0, values[13])
        elif add_edit == "paste":
            try:
                clip = self.root.clipboard_get().strip()
                url_e.insert(0, clip)
                desc_e.insert(0, f"Paste: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            except: pass

        def save(as_new=False):
            data = {"Description": desc_e.get(), "URL": url_e.get(), "INFO": info_t.get("1.0", tk.END).strip(), "Searchwords": tags_e.get(), "System": "URL"}
            if as_new or add_edit != "edit":
                self.db_manager.add_record(**data)
            else:
                self.db_manager.update_record(values[0], **data)
            self.refresh_data()
            add_window.destroy()

        btn_frame = tk.Frame(add_window, bg='#2c2f33')
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=10)

        # "Add as New" ligger nu till vänster
        if add_edit == "edit":
            ttk.Button(btn_frame, text="Add as New", command=lambda: save(as_new=True)).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="Save", command=lambda: save(as_new=False)).pack(side=tk.RIGHT, padx=5)

    def set_common_tags(self):
        sel = self.tree.selection()
        if not sel: return

        tag_win = tk.Toplevel(self.root)
        tag_win.title("Set Common Tag")

        self.root.update_idletasks()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_w = self.root.winfo_width()
        new_x = root_x + root_w + 10

        tag_win.geometry(f"300x150+{new_x}+{root_y}")
        tag_win.configure(bg='#2c2f33')
        tag_win.transient(self.root)

        frame = tk.Frame(tag_win, bg='#2c2f33')
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text=f"Enter tag for {len(sel)} selected items:", bg='#2c2f33', fg="white", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 10))

        tag_e = ttk.Entry(frame, font=("Arial", 10))
        tag_e.pack(fill=tk.X)
        tag_e.focus_set()

        def apply_tag():
            new_tag = tag_e.get().strip()
            if new_tag is not None:
                ids = [self.tree.item(i, "values")[0] for i in sel]
                self.db_manager.update_multiple_tags(ids, new_tag)
                self.refresh_data()
            tag_win.destroy()

        btn_frame = tk.Frame(tag_win, bg='#2c2f33')
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=10)
        ttk.Button(btn_frame, text="Apply", command=apply_tag).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Cancel", command=tag_win.destroy).pack(side=tk.RIGHT)

    def start_program(self):
        sel = self.tree.selection()
        if not sel: return
        url = self.tree.item(sel[0], "values")[8]
        if url:
            try:
                if url.lower().startswith("http"): os.startfile(url)
                else: subprocess.Popen(url)
            except: os.startfile(url)

    def refresh_data(self):
        if not self.file_path or not os.path.exists(self.file_path): return

        # Spara scroll-position och markeringar
        selected_ids = [str(self.tree.item(i, "values")[0]) for i in self.tree.selection()]
        scroll_pos = self.tree.yview()

        self.db_manager = DatabaseManager(self.file_path)
        self.data_copy = self.db_manager.fetch_data()
        self.last_mtime = os.path.getmtime(self.file_path)

        self.filter_treeview()
        self.bottom_label.config(text=f"DB: {os.path.basename(self.file_path)}")

        # Återställ markeringar
        new_sel = []
        for child in self.tree.get_children():
            if str(self.tree.item(child, "values")[0]) in selected_ids:
                new_sel.append(child)
        if new_sel:
            self.tree.selection_set(new_sel)

        # Återställ scroll-position
        if scroll_pos:
            self.tree.yview_moveto(scroll_pos[0])

    def filter_treeview(self, event=None):
        q = self.search_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        for row in self.data_copy:
            if q in str(row).lower(): self.tree.insert("", tk.END, values=row)

    def open_database(self):
        p = filedialog.askopenfilename(filetypes=[("DB", "*.db")])
        if p:
            self.file_path = p
            self.search_var.set("")
            self.refresh_data()
            self.save_config()
            self.rebuild_favorites_menu()

    def create_new_database(self):
        p = filedialog.asksaveasfilename(defaultextension=".db")
        if p:
            conn = sqlite3.connect(p)
            conn.execute('''CREATE TABLE info (id INTEGER PRIMARY KEY AUTOINCREMENT, Description TEXT, System TEXT, Software TEXT, IP_Address TEXT, VSM_Server_1 TEXT, VSM_Server_2 TEXT, VSM_Panel TEXT, URL TEXT, INFO TEXT, DRAWIO TEXT, Created TEXT, Edited TEXT, Searchwords TEXT, sort_order INTEGER)''')
            conn.close()
            self.file_path = p
            self.search_var.set("")
            self.refresh_data()
            self.save_config()
            self.rebuild_favorites_menu()

    def add_to_favorites(self):
        if self.file_path:
            self.favorites[os.path.basename(self.file_path)] = self.file_path
            self.rebuild_favorites_menu()
            self.save_config()

    def rebuild_favorites_menu(self):
        self.favorites_menu.delete(0, tk.END)
        self.favorites_menu.add_command(label="Manage Favorites...", command=self.manage_favorites)
        self.favorites_menu.add_separator()
        for name, path in self.favorites.items():
            # Checkmark for the active database
            if self.file_path and os.path.abspath(path).lower() == os.path.abspath(self.file_path).lower():
                display_label = f"✓  {name}"
            else:
                display_label = f"    {name}"

            self.favorites_menu.add_command(label=display_label, command=lambda n=name: self.open_favorite(n))

    def open_favorite(self, name):
        p = self.favorites.get(name)
        if p and os.path.exists(p):
            self.file_path = p
            self.search_var.set("")
            self.refresh_data()
            self.save_config()
            self.rebuild_favorites_menu()

    def manage_favorites(self):
        win = tk.Toplevel(self.root)
        win.title("Manage Favorites")

        self.root.update_idletasks()
        w, h = 350, 300
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_w = self.root.winfo_width()
        new_x = root_x + root_w + 10

        win.geometry(f"{w}x{h}+{new_x}+{root_y}")
        win.configure(bg='#2c2f33')
        win.transient(self.root)

        list_frame = tk.Frame(win, bg='#2c2f33')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        lb = tk.Listbox(list_frame, font=("Arial", 10))
        lb.pack(fill=tk.BOTH, expand=True)

        def refresh_list():
            lb.delete(0, tk.END)
            for n in self.favorites: lb.insert(tk.END, n)

        refresh_list()

        def add_fav():
            p = filedialog.askopenfilename(filetypes=[("DB", "*.db")])
            if p:
                name = os.path.basename(p)
                self.favorites[name] = p
                self.save_config()
                self.rebuild_favorites_menu()
                refresh_list()

        def rem_fav():
            if lb.curselection():
                name = lb.get(lb.curselection())
                del self.favorites[name]
                self.save_config()
                self.rebuild_favorites_menu()
                refresh_list()

        btn_frame = tk.Frame(win, bg='#2c2f33')
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(btn_frame, text="Add", command=add_fav).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        ttk.Button(btn_frame, text="Remove", command=rem_fav).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))

    def save_config(self):
        cfg = configparser.ConfigParser()
        cfg.optionxform = str  # Bevarar stora/små bokstäver
        cfg['Settings'] = {'FilePath': self.file_path or ""}
        cfg['Favorites'] = self.favorites
        with open(CONFIG_FILE, 'w') as f: cfg.write(f)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            cfg = configparser.ConfigParser()
            cfg.optionxform = str  # Bevarar stora/små bokstäver
            cfg.read(CONFIG_FILE)
            if 'Settings' in cfg: self.file_path = cfg['Settings'].get('FilePath'); self.refresh_data()
            if 'Favorites' in cfg: self.favorites = dict(cfg['Favorites']); self.rebuild_favorites_menu()

    def on_paste(self, event=None):
        try:
            url = self.root.clipboard_get().strip()
            if not url: return
        except: return

        if self.db_manager:
            existing = self.db_manager.get_record_by_url(url)
            if existing:
                if messagebox.askyesno("Duplicate Found", f"This URL already exists in: '{existing[1]}'\nDo you want to edit the existing entry?"):
                    self.refresh_data()
                    for child in self.tree.get_children():
                        if str(self.tree.item(child, "values")[0]) == str(existing[0]):
                            self.tree.selection_set(child); self.tree.see(child)
                            self.add_item("edit")
                            return
                else: return
        self.add_item("paste")

    def copy_url(self):
        sel = self.tree.selection()
        if sel: self.root.clipboard_clear(); self.root.clipboard_append(self.tree.item(sel[0], "values")[8])

    def delete_item(self):
        sel = self.tree.selection()
        if not sel: return
        msg = "Are you sure?" if len(sel) == 1 else f"Delete {len(sel)} items. Are you sure?"
        if messagebox.askyesno("Delete", msg):
            for item in sel:
                self.db_manager.delete_record(self.tree.item(item, "values")[0])
            self.refresh_data()

    def copy_item_to_db(self, path):
        sel = self.tree.selection()
        if not sel: return
        other_db = DatabaseManager(path)
        cols = self.db_manager.get_columns()
        for item in sel:
            data = dict(zip(cols, self.tree.item(item, "values")))
            data.pop('id', None); data.pop('sort_order', None)
            other_db.add_record(**data)
        messagebox.showinfo("Success", f"Copied {len(sel)} items to {os.path.basename(path)}")

    def monitor_database_changes(self):
        if self.file_path and os.path.exists(self.file_path):
            try:
                current_mtime = os.path.getmtime(self.file_path)
                if current_mtime > self.last_mtime:
                    self.refresh_data()
            except: pass
        self.root.after(1000, self.monitor_database_changes)

if __name__ == "__main__":
    root = tk.Tk(); app = App(root); root.mainloop()