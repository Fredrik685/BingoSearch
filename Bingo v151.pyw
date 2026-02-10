import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sqlite3
import os
import subprocess
import configparser
from datetime import datetime
import sys

# --- KONFIGURATION ---
# Räkna ut var den här .py-filen ligger på hårddisken just nu
APP_PATH = os.path.dirname(os.path.abspath(__file__))

# Säg åt programmet att config.ini Alltid ska ligga i den mappen
CONFIG_FILE = os.path.join(APP_PATH, 'config.ini')

# ==========================================
#   DEL 1: DATABASE MANAGER
# ==========================================
class DatabaseManager:
    def __init__(self, db_name):
        self.db_name = db_name
        self.check_and_migrate_db()

    def check_and_migrate_db(self):
        """Kollar om sort_order finns, annars skapas den."""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(info)")
            columns = [row[1] for row in cursor.fetchall()]

            if "sort_order" not in columns:
                # print("Migrating database: Adding sort_order column...")
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
            cursor.execute("PRAGMA table_info(info)")
            columns = [row[1] for row in cursor.fetchall()]

            # Sortera alltid efter sort_order om det finns
            if "sort_order" in columns:
                cursor.execute("SELECT * FROM info ORDER BY sort_order ASC")
            else:
                cursor.execute("SELECT * FROM info")

            data = cursor.fetchall()
            conn.close()
            return columns, data
        except sqlite3.Error:
            return [], []

    def update_record(self, record_id, **kwargs):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        columns = self.get_columns()
        set_clause = ', '.join([f"{col} = ?" for col in kwargs.keys() if col in columns])
        query = f"UPDATE info SET {set_clause} WHERE id = ?"
        values = list(kwargs.values()) + [record_id]
        cursor.execute(query, values)
        conn.commit()
        conn.close()

    def delete_record(self, record_id):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM info WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()

    def add_record(self, **kwargs):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        columns = self.get_columns()
        valid_kwargs = {k: v for k, v in kwargs.items() if k in columns}

        # Sätt sort_order sist i listan
        if "sort_order" in columns and "sort_order" not in valid_kwargs:
            cursor.execute("SELECT MAX(sort_order) FROM info")
            row = cursor.fetchone()
            max_val = row[0] if row and row[0] is not None else 0
            valid_kwargs["sort_order"] = max_val + 1

        cols = ', '.join(valid_kwargs.keys())
        placeholders = ', '.join(['?' for _ in valid_kwargs])
        query = f"INSERT INTO info ({cols}) VALUES ({placeholders})"
        values = list(valid_kwargs.values())

        cursor.execute(query, values)
        conn.commit()
        conn.close()

    def swap_rows(self, id1, id2):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT sort_order FROM info WHERE id=?", (id1,))
            order1 = cursor.fetchone()[0]
            cursor.execute("SELECT sort_order FROM info WHERE id=?", (id2,))
            order2 = cursor.fetchone()[0]

            cursor.execute("UPDATE info SET sort_order=? WHERE id=?", (order2, id1))
            cursor.execute("UPDATE info SET sort_order=? WHERE id=?", (order1, id2))
            conn.commit()
        except Exception as e:
            print(f"Swap error: {e}")
        finally:
            conn.close()

    def get_columns(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(info)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return columns


# ==========================================
#   DEL 2: HUVUDAPPLIKATIONEN (GUI)
# ==========================================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Bingo Search v1.5")
        self.root.configure(bg='#2c2f33')
        self.root.geometry("300x450")

        self.data_copy = []

        self.db_manager = None
        self.file_path = None
        self.last_mtime = 0
        self.favorites = {}

        self.show_window()
        self.load_config()
        self.monitor_database_changes()

    def show_window(self):
        # Styles
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.style.configure("Treeview", background="black", foreground="white", fieldbackground="black", font=("Helvetica", 10, "bold"))
        self.style.configure("Treeview.Heading", background="gray", foreground="black", font=("Helvetica", 12, "bold"))
        self.style.map('Treeview', background=[('selected', 'green')], foreground=[('selected', 'white')])

        # Sökfält
        search_frame = tk.Frame(self.root, bg='#2c2f33')
        search_frame.pack(pady=10, padx=10, fill=tk.X)
        tk.Label(search_frame, text="Search:", font=("Arial", 12, "bold"), fg="white", bg='#2c2f33').pack(side=tk.LEFT, padx=5)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Arial", 12,"bold"), width=50, bg="white", fg='#2c2f33', insertbackground="white")
        self.search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self.filter_treeview)

        # Treeview
        self.tree = ttk.Treeview(self.root, columns=("Column1", "Column2", "Column3"), show="headings")
        self.tree.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.tree.bind("<Double-1>", self.on_treeview_item_double_click)
        self.tree.bind("<Button-3>", self.show_popup_menu)
        self.tree.bind('<Control-v>', self.on_paste)

        # Menyer
        self.menu = tk.Menu(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.config(menu=self.menu)

        self.file_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Open Database", command=self.open_database)
        self.file_menu.add_command(label="Create new database", command=self.create_new_database)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Add current to favorites", command=self.add_to_favorites)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.on_closing)

        self.favorites_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Favorites", menu=self.favorites_menu)
        # OBS: Favorites-menyn fylls i av load_config / rebuild_favorites_menu

        self.about_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="About", menu=self.about_menu)
        self.about_menu.add_command(label="Manual / About", command=self.show_about)

        # Popup
        self.popup_menu = tk.Menu(self.root, tearoff=0)
        self.popup_menu.add_command(label="Edit", command=lambda: self.add_item("edit"))
        self.popup_menu.add_command(label="Go", command=self.start_program)
        self.popup_menu.add_separator()

        self.popup_menu.add_command(label="Move Up", command=lambda: self.move_item("up"))
        self.popup_menu.add_command(label="Move Down", command=lambda: self.move_item("down"))
        self.popup_menu.add_separator()

        self.copy_menu = tk.Menu(self.popup_menu, tearoff=0)
        self.popup_menu.add_cascade(label="Copy to...", menu=self.copy_menu)

        self.popup_menu.add_separator()
        self.popup_menu.add_command(label="Delete", command=self.delete_item)
        self.popup_menu.add_command(label="Copy URL", command=self.copy_url)

        # Kolumner
        self.tree.column("Column1", width=0, stretch=False)
        self.tree.heading("Column1", text="")
        self.tree.column("Column2", width=250)
        self.tree.heading("Column2", text="Description")
        self.tree.column("Column3", width=0, stretch=False)
        self.tree.heading("Column3", text="System")

        self.bottom_label = tk.Label(self.root, text="No database loaded", bg='#2c2f33', fg="white", anchor="w")
        self.bottom_label.pack(side=tk.BOTTOM, fill=tk.X, pady=4)

    def monitor_database_changes(self):
        if self.file_path and os.path.exists(self.file_path):
            try:
                current_mtime = os.path.getmtime(self.file_path)
                if current_mtime > self.last_mtime:
                    self.last_mtime = current_mtime
                    self.refresh_data()
            except OSError: pass
        self.root.after(2000, self.monitor_database_changes)

    def refresh_data(self):
        if not self.file_path: return
        try:
            self.db_manager = DatabaseManager(self.file_path)
            self.update_treeview()
            self.filter_treeview()
            self.bottom_label.config(text=f"Current database: {os.path.basename(self.file_path)}")
        except Exception as e: print(f"Error refreshing: {e}")

    # --- FAVORITES LOGIC ---
    def rebuild_favorites_menu(self):
        """Bygger om favoritmenyn dynamiskt"""
        self.favorites_menu.delete(0, tk.END)

        # 1. Manage-knappen först
        self.favorites_menu.add_command(label="Manage Favorites...", command=self.manage_favorites)
        self.favorites_menu.add_separator()

        # 2. Lista alla favoriter
        if not self.favorites:
            self.favorites_menu.add_command(label="(No favorites)", state="disabled")
        else:
            for key in self.favorites:
                self.favorites_menu.add_command(label=key, command=lambda k=key: self.open_favorite(k))

    def manage_favorites(self):
        """Öppnar fönster för att ta bort favoriter"""
        manage_win = tk.Toplevel(self.root)
        manage_win.title("Manage Favorites")
        manage_win.geometry("300x300")
        manage_win.configure(bg='#2c2f33')

        tk.Label(manage_win, text="Select favorite to remove:", bg='#2c2f33', fg="white").pack(pady=5)

        listbox = tk.Listbox(manage_win, bg="#1e2124", fg="white", selectbackground="green")
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        for name in self.favorites:
            listbox.insert(tk.END, name)

        def delete_selected():
            selection = listbox.curselection()
            if not selection: return

            name = listbox.get(selection[0])
            if name in self.favorites:
                del self.favorites[name]

            listbox.delete(selection[0])

            # Spara och uppdatera menyn direkt
            self.save_config()
            self.rebuild_favorites_menu()

        btn_frame = tk.Frame(manage_win, bg='#2c2f33')
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Remove", command=delete_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=manage_win.destroy).pack(side=tk.LEFT, padx=5)

    def add_to_favorites(self):
        if self.file_path:
            name = os.path.basename(self.file_path)
            self.favorites[name] = self.file_path

            self.rebuild_favorites_menu() # Uppdatera menyn
            self.save_config()
            messagebox.showinfo("Favorites", f"Added '{name}' to favorites.")

    def open_favorite(self, key):
        if key in self.favorites and os.path.exists(self.favorites[key]):
            self.file_path = self.favorites[key]
            self.last_mtime = os.path.getmtime(self.file_path)
            self.refresh_data()
            self.save_config()

    # --- ADD / EDIT ---
    def add_item(self, add_edit):
            root_x = self.root.winfo_x()
            root_y = self.root.winfo_y()
            x = root_x + self.root.winfo_width() + 10
            y = root_y

            item = self.tree.selection()
            values = []
            if item: values = self.tree.item(item, "values")

            if add_edit == "edit" and not values:
                messagebox.showwarning("Warning", "Please select an item to edit.")
                return

            add_window = tk.Toplevel(self.root)
            add_window.title("Item Details")
            add_window.configure(bg='#2c2f33')
            add_window.geometry(f"600x500+{x}+{y}")
            add_window.transient(self.root)

            style = ttk.Style(add_window)
            style.theme_use("clam")
            style.configure("TEntry", fieldbackground="white", background="white", foreground="black")
            style.configure("TLabel", background="#2c2f33", foreground="white", font=("Arial", 11, "bold"))

            form_frame = tk.Frame(add_window, bg='#2c2f33')
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            form_frame.columnconfigure(1, weight=1)

            ttk.Label(form_frame, text="Description:").grid(row=0, column=0, sticky="w", pady=5)
            description_entry = ttk.Entry(form_frame, font=("Arial", 10))
            description_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 0))

            ttk.Label(form_frame, text="URL / Path:").grid(row=1, column=0, sticky="w", pady=5)
            url_entry = ttk.Entry(form_frame, font=("Arial", 10))
            url_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=(10, 0))

            ttk.Label(form_frame, text="Tags:").grid(row=2, column=0, sticky="w", pady=5)
            searchwords_entry = ttk.Entry(form_frame, font=("Arial", 10))
            searchwords_entry.grid(row=2, column=1, sticky="ew", pady=5, padx=(10, 0))

            ttk.Label(form_frame, text="Info:").grid(row=3, column=0, sticky="nw", pady=5)
            text_area = scrolledtext.ScrolledText(form_frame, wrap=tk.WORD, width=40, height=15, font=("Arial", 10))
            text_area.grid(row=3, column=1, sticky="ew", pady=5, padx=(10, 0))

            button_frame = tk.Frame(add_window, bg='#2c2f33')
            button_frame.pack(fill=tk.X, padx=20, pady=10)

            def save_record(new_record=False):
                data = {
                    "Description": description_entry.get(),
                    "System": "URL",
                    "Software": "",
                    "IP_Address": "",
                    "VSM_Server_1": "",
                    "VSM_Server_2": "",
                    "VSM_Panel": "",
                    "URL": url_entry.get(),
                    "Searchwords": searchwords_entry.get(),
                    "INFO": text_area.get("1.0", tk.END).strip()
                }
                if not self.db_manager: return
                if add_edit == "edit" and not new_record:
                    self.db_manager.update_record(values[0], **data)
                else:
                    self.db_manager.add_record(**data)

                self.refresh_data()
                if self.file_path: self.last_mtime = os.path.getmtime(self.file_path)
                add_window.destroy()

            if add_edit == "edit" and values:
                description_entry.insert(0, values[1] if values[1] else "")
                url_entry.insert(0, values[8] if values[8] else "")
                try:
                    text_area.insert("1.0", values[9] if values[9] else "")
                    if len(values) > 13: searchwords_entry.insert(0, values[13] if values[13] else "")
                except: pass

                ttk.Button(button_frame, text="Add as new", command=lambda: save_record(new_record=True)).pack(side=tk.LEFT)

            elif add_edit == "paste":
                try:
                    content = self.root.clipboard_get().strip()
                    # Inga replace('"','') här, vi behåller citattecken för argument
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                    description_entry.insert(0, f"Paste: {current_time}")
                    url_entry.insert(0, content)
                except: pass

            ttk.Button(button_frame, text="Save", command=lambda: save_record(new_record=False)).pack(side=tk.RIGHT)

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            self.create_default_config()
            return
        config = configparser.ConfigParser()
        try:
            config.read(CONFIG_FILE)
            if 'Settings' in config and 'FilePath' in config['Settings']:
                path = config['Settings']['FilePath']
                if path and os.path.exists(path):
                    self.file_path = path
                    self.last_mtime = os.path.getmtime(self.file_path)
                    self.refresh_data()

            self.favorites = {}
            if 'Favorites' in config:
                for key, value in config['Favorites'].items():
                    if value and os.path.exists(value):
                        self.favorites[key] = value

            # Bygg menyn när konfigurationen är laddad
            self.rebuild_favorites_menu()

        except: pass

    def create_default_config(self):
        self.save_config()

    def save_config(self):
            config = configparser.ConfigParser()
            config['Settings'] = {
                'FilePath': self.file_path or "",
                'Geometry': self.root.geometry()
            }
            config['Favorites'] = {k: v or "" for k, v in self.favorites.items()}

            try:
                with open(CONFIG_FILE, 'w') as f:
                    config.write(f)
            except PermissionError:
                # Detta meddelande kommer dyka upp om de lagt filen på ett dumt ställe
                messagebox.showerror("Write Error",
                    f"Permission denied!\nCannot write to: {CONFIG_FILE}\n\n"
                    "Please move the script to a folder where you have write permissions\n"
                    "(like Desktop or Documents).")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save config:\n{e}")

    def start_program(self):
        item = self.tree.selection()
        if not item: return
        values = self.tree.item(item, "values")
        url = values[8]

        if not url: return

        try:
            # Enkel koll: är det webb eller filsystem?
            if url.lower().startswith("http") or url.lower().startswith("www"):
                os.startfile(url)
            else:
                # Subprocess hanterar .exe med argument (t.ex. -id=99)
                subprocess.Popen(url)
        except Exception as e:
            # Fallback
            try:
                os.startfile(url)
            except:
                messagebox.showerror("Error", f"Failed to launch:\n{e}")

    def update_treeview(self):
        if self.db_manager:
            try:
                cols, data = self.db_manager.fetch_data()
                self.data_copy = data
                self.tree.delete(*self.tree.get_children())
                for item in data: self.tree.insert("", tk.END, values=item)
            except: pass

    def filter_treeview(self, event=None):
        if not self.data_copy: return
        search = self.search_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        for row in self.data_copy:
            search_indices = [0, 1, 2, 8, 13]
            row_str = " ".join([str(row[i]).lower() for i in search_indices if i < len(row) and row[i] is not None])
            if search in row_str: self.tree.insert("", tk.END, values=row)

    def open_database(self):
        p = filedialog.askopenfilename(filetypes=[("DB", "*.db")])
        if p:
            self.file_path = p
            self.last_mtime = os.path.getmtime(p)
            self.refresh_data()
            self.save_config()

    def create_new_database(self):
        p = filedialog.asksaveasfilename(defaultextension=".db")
        if p:
            conn = sqlite3.connect(p)
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                Description TEXT, System TEXT, Software TEXT, IP_Address TEXT,
                VSM_Server_1 TEXT, VSM_Server_2 TEXT, VSM_Panel TEXT, URL TEXT,
                INFO TEXT, DRAWIO TEXT, Created TEXT, Edited TEXT, Searchwords TEXT,
                sort_order INTEGER
            );''')
            conn.commit()
            conn.close()
            self.file_path = p
            self.last_mtime = os.path.getmtime(p)
            self.refresh_data()
            self.save_config()

    def on_paste(self, event):
        try:
            if self.root.clipboard_get(): self.add_item("paste")
        except: pass

    def on_treeview_item_double_click(self, event): self.start_program()

    def show_popup_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.copy_menu.delete(0, tk.END)
            if not self.favorites:
                self.copy_menu.add_command(label="(No favorites added)", state="disabled")
            else:
                for name, path in self.favorites.items():
                    self.copy_menu.add_command(label=name, command=lambda p=path: self.copy_item_to_db(p))
            self.popup_menu.post(event.x_root, event.y_root)

    def delete_item(self):
        item = self.tree.selection()
        if item and self.db_manager:
            if messagebox.askyesno("Delete", "Are you sure?"):
                val = self.tree.item(item, "values")
                self.db_manager.delete_record(val[0])
                self.refresh_data()
                self.last_mtime = os.path.getmtime(self.file_path)

    def copy_url(self):
        item = self.tree.selection()
        if item:
            val = self.tree.item(item, "values")
            self.root.clipboard_clear()
            self.root.clipboard_append(val[8])

    def move_item(self, direction):
        if not self.db_manager: return
        if self.search_var.get():
             messagebox.showinfo("Note", "Moving items while searching might act unexpectedly.\nClear search to see true order.")

        current_item = self.tree.selection()
        if not current_item: return

        target_item = None
        if direction == "up":
            target_item = self.tree.prev(current_item)
        elif direction == "down":
            target_item = self.tree.next(current_item)

        if target_item:
            current_vals = self.tree.item(current_item, "values")
            target_vals = self.tree.item(target_item, "values")

            id1 = current_vals[0]
            id2 = target_vals[0]

            self.db_manager.swap_rows(id1, id2)
            self.refresh_data()

            for child in self.tree.get_children():
                if str(self.tree.item(child, "values")[0]) == str(id1):
                    self.tree.selection_set(child)
                    self.tree.focus(child)
                    break
            self.last_mtime = os.path.getmtime(self.file_path)

    def copy_item_to_db(self, target_db_path):
        item = self.tree.selection()
        if not item: return
        values = self.tree.item(item, "values")
        if not self.db_manager: return
        columns = self.db_manager.get_columns()
        data_to_copy = dict(zip(columns, values))

        if 'id' in data_to_copy: del data_to_copy['id']
        if 'sort_order' in data_to_copy: del data_to_copy['sort_order']

        try:
            target_mgr = DatabaseManager(target_db_path)
            target_mgr.add_record(**data_to_copy)
            target_name = os.path.basename(target_db_path)
            #messagebox.showinfo("Success", f"Item copied to {target_name}!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")

    def show_about(self):
        about_window = tk.Toplevel(self.root)
        about_window.title("Manual - Bingo Search v1.5")
        about_window.geometry("550x650")
        about_window.configure(bg='#2c2f33')

        tk.Label(about_window, text="Bingo Search v1.5", font=("Arial", 16, "bold"),
                 bg='#2c2f33', fg="#ffffff").pack(pady=15)

        text_area = scrolledtext.ScrolledText(about_window, wrap=tk.WORD, width=60, height=30,
                                              font=("Consolas", 10), bg="#1e2124", fg="#dddddd", bd=0)
        text_area.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

        manual_text = """
=== BASIC USAGE ===
Double-Click:  Launch the URL or Command.
Right-Click:   Open the context menu (Edit, Move, Delete, Copy).
Search Bar:    Filters list by Description, System, URL, or Tags.

=== ADDING & EDITING ===
Right-Click -> Edit:  Modify an existing item.
File -> Create New:   Start a fresh database.
Paste (Ctrl+V):       Quickly add clipboard content as a new item.

=== COMMANDS & ARGUMENTS ===
You can paste file paths or full commands.
Example: "C:\\App\\vsmPanel.exe" -id=99 -host=vsm01
The program automatically detects if it should run a file or open a web link.

=== FAVORITES & COPYING ===
1. Load a database you use often.
2. Go to File -> "Add current to favorites".
3. To REMOVE: Favorites -> Manage Favorites.
4. To COPY: Right-Click an item -> "Copy to..." -> Select target database.
   (This copies the item to the other database without ID conflicts).

=== ORGANIZING ===
Right-Click -> Move Up/Down: Reorder items in the list.
Note: Clear the search bar before moving items to see the real order.

=== KEY SHORTCUTS ===
Ctrl+V:   Paste text/path as new entry
        """

        text_area.insert(tk.INSERT, manual_text.strip())
        text_area.configure(state='disabled')
        ttk.Button(about_window, text="Close", command=about_window.destroy).pack(pady=15)

    def on_closing(self):
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()