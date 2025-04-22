# To Do before V1.0
# -----------------------------------------------------------------------------------
# * Fjern drag and drop
# * Spara passord?
# * 
# * Skapar programmet en .ini fil om det inte finns någon?
# * try and exception när man laddar en databas/favorit
# * Delete favorites, uppdatera config.ini. uppdatera meny
# * Add as new (under edit) borde byta ut id till den nya. 
# * Icon
# * Paste URL i contextmenyn

# To Do V1.x
# -----------------------------------------------------------------------------------
# * Møjligt med copy/paste på elementer i en treeview? Can man bruke ID till detta? Så att man kopierar ID från treeview och så hämtar info från db1 och add_record på db2?
#   Måste ju gå an? Vad får man när man väljer flera element i en treeview (view selection)
# * Møjlighet før copy/paste mellan databaser?
# * När man lägger till något nytt, fyll i program automatiskt om man väljer vsm eller url.
# * När man skapar en database, ladda den. Løst men finns nu 3 olika funktioner som laddar en databas. Rydd i detta. (open_new_database, open_database og open_favorites)

# Done
# -----------------------------------------------------------------------------------
# * Info-vindu till varje item, med en editerbar text-box som sparas i databasen.
# * Sätt stor bokstav på favoriter
# * Lägg till searchwords i databasen
# * Kolonne før "date created" och "date edited" och kanske ett versionsnummer? V1.00 och så øka med 0.01 før varje edit som gørs?
# * OM man tar bort ett element, inte fjern søket
# * Copy url to clipboard
# * About vindu?
# * Uppdatera config.ini med den sista file_path som är øppnad
# * Lägg till knapp på edit "Add as new"
# * Lägg favoriter i listan, uppdatera meny och config.ini. Inte lägg till dubletter
# * Lag ett vindu før konfig av .exe
# * Clean up all prints


import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
from database_manager import DatabaseManager
import sqlite3
import os
import subprocess
import threading
import configparser
from datetime import datetime
from urllib.parse import urlparse
from tkinterdnd2 import TkinterDnD, DND_FILES
import pylnk3

#Søkväg till config-fil
config_file = 'config.ini'


class App:
    data_copy = []          # Copy of selected database data
    def __init__(self, root):
        self.db_manager = None
        self.root = root
        self.root.title("Bingo Search v0.85")
        self.root.configure(bg='#2c2f33')
        self.show_window()
        self.load_config()
        self.current_version = os.path.getmtime(self.file_path)
        self.check_for_new_versions()

        self.valid_riedel_programs=[]
        for keys,labels in self.riedel_paths.items():
            self.valid_riedel_programs.append(keys)

        #This information should come from the config file
        self.valid_browser_programs = ["Chrome", "Edge","Firefox","Explorer"]

    def check_for_new_versions(self):
        #print(self.current_version)
        self.latest_version = os.path.getmtime(self.file_path)
        if self.latest_version>self.current_version:
            print("There is a new version available")
            self.current_version = self.latest_version
            self.db_manager = DatabaseManager(self.file_path)
            self.update_treeview()
            self.filter_treeview()
        self.root.after(1000,self.check_for_new_versions)

    def show_window(self):
        # Configure style
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        self.style.configure("Treeview", 
                             background="black", 
                             foreground="white", 
                             fieldbackground="black", 
                             font=("Helvetica", 10,"bold"))
        self.style.configure("Treeview.Heading", 
                             background="gray", 
                             foreground="black", 
                             font=("Helvetica", 12, "bold"))

        self.style.map('Treeview', background=[('selected', 'green')], foreground=[('selected', 'white')])

        # Create search field
        search_frame = tk.Frame(self.root, bg='#2c2f33')
        search_frame.pack(pady=10, padx=10, fill=tk.X)

        tk.Label(search_frame, text="Search:", font=("Arial", 12, "bold"), fg="white", bg='#2c2f33').pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Arial", 12,"bold"), width=50, bg="white", fg='#2c2f33', insertbackground="white")
        self.search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self.filter_treeview)

        # Create treeview placeholder
        self.tree = ttk.Treeview(self.root, columns=("Column1", "Column2", "Column3"), show="headings")
        self.tree.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Bind double-click and right-click events
        self.tree.bind("<Double-1>", self.on_treeview_item_double_click)
        self.tree.bind("<Button-3>", self.show_popup_menu)
        self.tree.bind('<Control-v>', self.on_paste)
        # Set up drag-and-drop functionality
        self.tree.drop_target_register(DND_FILES)
        self.tree.dnd_bind('<<Drop>>', self.drop)

        #self.tree.bind('<Right>', self.show_popup_menu)

        # Create File menu
        self.menu = tk.Menu(self.root)
        self.root.protocol("WM_DELETE_WINDOW",self.on_closing)
        self.root.config(menu=self.menu)
        self.file_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Open Database", command=self.open_database)
        #self.file_menu.add_command(label="Configure Program", command=self.configure_program)
        self.file_menu.add_command(label="Create new database", command=self.create_new_database)
        self.file_menu.add_command(label="Add current database to favorites", command=self.add_to_favorites)
        self.file_menu.add_command(label="Save config (For test only)", command=self.save_config)
        self.file_menu.add_command(label="Exit", command=self.on_closing)

        # Create Favorites menu
        self.favorites_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Favorites", menu=self.favorites_menu)
        # This should be filled out from the config.ini file

        # Create Configure menu
        self.setup_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Configure", menu=self.setup_menu)
        self.setup_menu.add_command(label="Setup .exe files", command=self.config_exe)

        # Create About menu
        self.about_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="About", menu=self.about_menu)
        self.about_menu.add_command(label="About", command=self.show_about)

        # Create popup menu
        self.popup_menu = tk.Menu(self.root, tearoff=0)
        self.popup_menu.add_command(label="Edit", command=lambda: self.add_item("edit"))
        self.popup_menu.add_command(label="Start", command=self.start_program)
        self.popup_menu.add_command(label="Add new", command=lambda: self.add_item("add"))
        self.popup_menu.add_command(label="Delete", command=self.delete_item)
        self.popup_menu.add_command(label="Copy URL to clipboard", command=self.copy_url)
        #self.popup_menu.add_command(label="Paste URL from clipboard", command=self.on_paste)
        self.popup_menu.add_command(label="TEST: Copy", command=self.edit_item)
        self.popup_menu.add_command(label="TEST: Paste", command=self.edit_item)

        # Define treeview columns
        self.tree.heading("Column1", text="ID")
        self.tree.heading("Column2", text="Description")
        self.tree.heading("Column3", text="System")

        # Adjust column widths
        self.tree.column("Column1", width=10)  
        self.tree.column("Column2", width=250)
        self.tree.column("Column3", width=50)

        self.bottom_label = tk.Label(root, text="Current database: ", bg='#2c2f33',fg="white",anchor="w")
        self.bottom_label.pack(side=tk.BOTTOM, fill=tk.X,pady=4)

    def on_closing(self):
        self.root.destroy()

    def on_paste(self,event):
        # Generate the paste event
        event.widget.event_generate('<<Paste>>')
    
        # Retrieve the pasted text
        pasted_text = root.clipboard_get()
        self.add_item("paste")

    def configure_program(self):
        # Open up window and specify all the .exe files to all the programs in db-file
        self.db_manager.update_record(2,System="x2x")
        if self.file_path:
            self.db_manager = DatabaseManager(self.file_path)
            self.update_treeview()

    def create_new_database(self):
        db_name=self.get_database_name()
        if db_name:
            self.create_database(db_name)
            self.open_new_database(db_name)

    def create_database(self,db_name):
        # Connect to SQLite database (or create it if it doesn't exist)
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        # SQL statement to create a new table
        create_table_sql = '''
        CREATE TABLE IF NOT EXISTS info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Description TEXT,
            System TEXT,
            Software TEXT,
            IP_Address TEXT,
            VSM_Server_1 TEXT,
            VSM_Server_2 TEXT,
            VSM_Panel TEXT,
            URL TEXT,
            INFO TEXT,
            DRAWIO TEXT,
            Created TEXT,
            Edited TEXT,
            Searchwords TEXT
        );
        '''
        
        # Execute the SQL statement
        cursor.execute(create_table_sql)
        # Commit the changes and close the connection
        conn.commit()
        conn.close()

    def get_database_name(self):
        # Open a file save dialog to select the location and name of the new database
        root = tk.Tk()
        root.withdraw()  # Hide the root window
        file_path = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database Files", "*.db"), ("All Files", "*.*")],
            title="Save As"
        )
        return file_path

    def start_program(self):
        #This shoudld start the programs with the right parameters
        item = self.tree.selection()  # Get selected item
        if item:
            values = self.tree.item(item, "values")
        system = values[2]
        program = values[3]
        ip = values[4]
        server1 = values[5]
        server2 = values[6]
        panel = values[7]
        url = values[8]
        if system == "VSM":
            def run_subprocess():
                args2 = [f"-id={panel}", f"-host={server1}", f"-host2={server2}"]
                try:
                    subprocess.run([self.vsm_panel_path.get(program)] + args2, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error launching {self.vsm_panel_path}: {e}")
                except Exception as e:
                    print(f"Unexpected error: {e}")

            thread = threading.Thread(target=run_subprocess)
            thread.start()

        elif system == "Riedel":
            executable_path=self.riedel_paths.get(program)
            def run_subprocess():
                args = [f"-LocalNodeIP:{ip}", "-NoSplash", "-EnableNetwork", "-OpenConfigFromArtist"]
                try:
                    subprocess.run([executable_path] + args, check=True)
                except subprocess.CalledProcessError as e:
                    print(f"Error launching Director: {e}")
            thread = threading.Thread(target=run_subprocess)
            thread.start()

        elif system == "Webpage":
            #print("Start Browser")
            pass
        elif system == "File Explorer" or system == "URL":
            #print("Start File Explorer")
            os.startfile(url)
        else:
            print("Not a valid system")

    def open_database(self):
        # Prompt for a database and fill the data in "data"
        self.file_path = filedialog.askopenfilename(filetypes=[("Database files", "*.db")])
        if self.file_path:
            self.db_manager = DatabaseManager(self.file_path)
            self.update_treeview()
        self.bottom_label.config(text=f"Current database: {os.path.basename(self.file_path)}")

    def show_popup_menu(self, event):
        """Show the popup menu at the cursor position."""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.tree.focus(item)
        self.popup_menu.post(event.x_root, event.y_root)

    def update_treeview(self):
        """Update the Treeview with data."""
        if self.db_manager:
            columns, data = self.db_manager.fetch_data()
            App.data_copy = data
        self.tree.delete(*self.tree.get_children())  # Clear existing data
        for item in data:  # Access class attribute
            self.tree.insert("", tk.END, values=item)

    def on_treeview_item_double_click(self,event):
        item = self.tree.selection()  # Get selected item
        self.start_program()

    def edit_item(self):
        item = self.tree.selection()  # Get selected item
        pass

    def delete_item(self):
        """Delete a record from the database."""
        item = self.tree.selection()  # Get selected item
        if item:
            values = self.tree.item(item, "values")
            description = values[1]
            result = messagebox.askokcancel("Confirm Deletion",f"You are about to delete: {description}. Are you sure?")
            if result:
                values = self.tree.item(item, "values")
                record_id = values[0]
                self.db_manager.delete_record(record_id)
                #self.search_entry.delete(0, tk.END)
                self.update_treeview()
                self.filter_treeview()
        else:
            messagebox.showwarning("No Database", "Please open a database first.")

    def add_item(self,add_edit):
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        x= root_x + root_width+10
        y = root_y

        item = self.tree.selection()  # Get selected item
        if item:
            values = self.tree.item(item, "values")

        """Open a window for adding vsm info."""
        def on_system_change(event):
            selected_system = system_combobox.get()
            if selected_system == "VSM":
                software_combobox['values'] = ["VSM_Panel"]
                ip_entry.config(state="disabled",background="lightgray")
                server1_entry.config(state="normal")
                server2_entry.config(state="normal")
                panel_entry.config(state="normal")
                url_entry.config(state="readonly")
                # This line doesnt work? Why
                root.after(100,software_combobox.set(software_combobox['values'][0]))

            elif selected_system == "Riedel":
                software_combobox['values'] = self.valid_riedel_programs
                ip_entry.config(state="normal")
                server1_entry.config(state="disabled")
                server2_entry.config(state="disabled")
                panel_entry.config(state="disabled")
                url_entry.config(state="disabled")
            elif selected_system == "Webpage":
                software_combobox['values'] = self.valid_browser_programs
                ip_entry.config(state="disabled")
                server1_entry.config(state="disabled")
                server2_entry.config(state="disabled")
                panel_entry.config(state="disabled")
                url_entry.config(state="normal")
            elif selected_system == "File Explorer" or selected_system == "URL":
                software_combobox['values'] = ["Standard Program"]
                ip_entry.config(state="disabled")
                server1_entry.config(state="disabled")
                server2_entry.config(state="disabled")
                panel_entry.config(state="disabled")
                url_entry.config(state="normal")
            else:
                software_combobox['values'] = []
            software_combobox.set('')
            software_combobox.config(state='readonly')

        def add_as_new():
            self.db_manager.add_record(
            Description = description_entry.get(),
            System = system_combobox.get(),
            Software = software_combobox.get(),
            IP_Address = ip_entry.get(),
            VSM_Server_1 = server1_entry.get(),
            VSM_Server_2=server2_entry.get(),
            VSM_Panel=panel_entry.get(),
            URL = url_entry.get(),
            Searchwords = searchwords_entry.get(),
            INFO = text_area.get("1.0",tk.END))
            self.update_treeview()
            self.filter_treeview()

        def on_submit():
            #Description,System,Software,IP_Address,VSM_Server_1,VSM_Server_2,VSM_Panel,URL,INFO
            if add_edit == "edit":
                self.db_manager.update_record(values[0],
                Description = description_entry.get(),
                System = system_combobox.get(),
                Software = software_combobox.get(),
                IP_Address = ip_entry.get(),
                VSM_Server_1 = server1_entry.get(),
                VSM_Server_2=server2_entry.get(),
                VSM_Panel=panel_entry.get(),
                URL = url_entry.get(),
                Searchwords = searchwords_entry.get(),
                INFO = text_area.get("1.0",tk.END))
            else:
                self.db_manager.add_record(
                Description = description_entry.get(),
                System = system_combobox.get(),
                Software = software_combobox.get(),
                IP_Address = ip_entry.get(),
                VSM_Server_1 = server1_entry.get(),
                VSM_Server_2=server2_entry.get(),
                VSM_Panel=panel_entry.get(),
                URL = url_entry.get(),
                Searchwords = searchwords_entry.get(),
                INFO = text_area.get("1.0",tk.END))

            if add_edit=="edit" or add_edit=="paste":
                add_window.destroy()
            #self.search_entry.delete(0, tk.END)
            self.update_treeview()
            self.filter_treeview()

        add_window = tk.Toplevel(self.root)
        add_window.title("Add Item")
        if add_edit == "edit":
            add_window.title("Edit Item")

        add_window.configure(bg='#2c2f33')
        #add_window.geometry("500x550")
        add_window.geometry(f"500x540+{x}+{y}")
        style = ttk.Style(add_window)
        style.theme_use("clam")

        # Configure styles
        style.configure("TEntry", background="white", foreground="black", fieldbackground="white", font=("Arial", 12, "bold"))
        style.configure("TCombobox", background="white", foreground="black", fieldbackground="white", font=("Arial", 12, "bold"))
        style.configure("TLabel", background="#2c2f33", foreground="white", font=("Arial", 12, "bold"))
        style.map('TCombobox', background=[('readonly', 'black')], foreground=[('readonly', 'black')])

        # Create a frame for the labels on the left side
        labels_frame = tk.Frame(add_window, bg='#2c2f33')
        labels_frame.pack(side=tk.LEFT, padx=10, pady=10, anchor=tk.N)

        # Create a frame for the entry/comboboxes on the right side
        entries_frame = tk.Frame(add_window, bg='#2c2f33')
        entries_frame.pack(side=tk.LEFT, padx=10, pady=10, anchor=tk.N)

        # Add labels to the labels_frame
        ttk.Label(labels_frame, text="Description:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="System:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Software:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="IP-Adress:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Server 1:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Server 2:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Panel:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="URL:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Tags:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Info:").pack(anchor=tk.W, pady=4)

        # Add entry/comboboxes to the entries_frame
        description_entry = ttk.Entry(entries_frame)
        description_entry.pack(fill=tk.X, pady=5)

        system_combobox = ttk.Combobox(entries_frame, values=["VSM", "Riedel", "URL"], state='readonly')
        system_combobox.bind("<<ComboboxSelected>>", on_system_change)
        system_combobox.pack(fill=tk.X, pady=5)

        software_combobox = ttk.Combobox(entries_frame, state='disabled')
        software_combobox.pack(fill=tk.X, pady=5)
        ip_entry = ttk.Entry(entries_frame)
        ip_entry.pack(fill=tk.X, pady=5)

        server1_entry = ttk.Entry(entries_frame,width=40)
        server1_entry.pack(fill=tk.X, pady=5)

        server2_entry = ttk.Entry(entries_frame)
        server2_entry.pack(fill=tk.X, pady=5)

        panel_entry = ttk.Entry(entries_frame)
        panel_entry.pack(fill=tk.X, pady=5)

        url_entry = ttk.Entry(entries_frame)
        url_entry.pack(fill=tk.X, pady=5)

        searchwords_entry = ttk.Entry(entries_frame)
        searchwords_entry.pack(fill=tk.X, pady=5)

        text_area = tk.scrolledtext.ScrolledText(entries_frame, wrap=tk.WORD, width=40, height=10)
        text_area.pack(fill=tk.X, pady=5)

        # Add button at the bottom right
        if add_edit == "edit":
            description_entry.insert(0,values[1])
            system_combobox.set(values[2])
            software_combobox.set(values[3])
            ip_entry.insert(0,values[4])
            server1_entry.insert(0,values[5])
            server2_entry.insert(0,values[6])
            panel_entry.insert(0,values[7])
            url_entry.insert(0,values[8])
            text_area.delete(1.0,tk.END)
            text_area.insert("1.0",values[9])
            searchwords_entry.insert(0,values[13])
        elif add_edit =="paste":
            #parsed_url = urlparse(root.clipboard_get())
            #host_name = parsed_url.hostname
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            description_entry.insert(0,f"From clipboard: {current_time}")
            system_combobox.set("URL")
            software_combobox.set("Standard Program")
            url_entry.insert(0,root.clipboard_get())
            description_entry.selection_range(0,tk.END)
            description_entry.focus_set()

        if add_edit == "edit":
            add_as_new_button = ttk.Button(entries_frame, text="Add as new", command=add_as_new)
            add_as_new_button.pack(side=tk.LEFT, pady=10)


        add_button = ttk.Button(entries_frame, text="Ok", command=on_submit)
        add_button.pack(side=tk.RIGHT, pady=10)

    def filter_treeview(self, event=None):
        """Filter the Treeview based on search text."""
        search_text = self.search_var.get().lower()
        columns_to_filter = [0, 1, 2,13]  # Columns 1, 2, and 3 (0-indexed)

        # Perform filtering based on specific columns
        filtered_data = [
            row for row in App.data_copy
            if any(search_text in str(row[col]).lower() for col in columns_to_filter)
        ]
        self.tree.delete(*self.tree.get_children())  # Clear existing data
        for row in filtered_data:
            self.tree.insert("", tk.END, values=row)

    def open_favorite(self,argum):
        self.file_path = self.favorites[argum]
        if self.file_path:
            self.db_manager = DatabaseManager(self.file_path)
            self.update_treeview()
        self.bottom_label.config(text=f"Current database: {os.path.basename(self.file_path)}")

    def open_new_database(self,argum):
        self.file_path = argum
        if self.file_path:
            self.db_manager = DatabaseManager(self.file_path)
            self.update_treeview()
        self.bottom_label.config(text=f"Current database: {os.path.basename(self.file_path)}")

    def load_config(self):
        self.file_path = None
        self.vsm_panel_path={}
        self.riedel_paths = {}
        self.favorites = {}
#        self.vsm_panel_path = None
        if os.path.exists(config_file):
            config = configparser.ConfigParser()
            config.read(config_file)
            if 'Settings' in config:
                self.file_path = config['Settings'].get('FilePath')
                self.db_manager = DatabaseManager(self.file_path)
                self.update_treeview()
                self.bottom_label.config(text=f"Current database: {os.path.basename(self.file_path)}")
                self.vsm_panel_path_dont_use_yet = config['VSM_Panel'].get('vsm_panel')
                self.vsm_panel_path = {"VSM_Panel":self.vsm_panel_path_dont_use_yet}
                for key, value in config['Director'].items():
                    if key.startswith('dir') and value:
                        self.riedel_paths[key] = value
                for key, value in config['Favorites'].items():
                    if value:
                        self.favorites[key] = value
                        menu_label = key.capitalize()
                        self.favorites_menu.add_command(label=menu_label, command=lambda k=key: self.open_favorite(k))

        else:
            self.vsm_panel_path={'VSM_Panel':''}
            self.riedel_paths={'director_v860':'',
                               'director_v850':'',
                               'director_v840':'',
                               'director_v820':'',
                               'director_v720':''}
            self.save_config()

    def save_config(self):
        # Store the config_file.
        config = configparser.ConfigParser()
        config['Settings'] = {'FilePath': self.file_path or ""}

        if 'Director' not in config:
            config['Director']={}
        for version, path in self.riedel_paths.items():
            config['Director'][version] = path or ""

        config['VSM_Panel'] = self.vsm_panel_path or ""

        if 'Favorites' not in config:
            config['Favorites']={}
        for version,path in self.favorites.items():
            config['Favorites'][version] = path or ""

        with open(config_file, 'w') as configfile:
            config.write(configfile)

    def copy_url(self):
        item = self.tree.selection()  # Get selected item
        if item and item is not None:
            values = self.tree.item(item, "values")
            root.clipboard_append(values[8])

    def show_about(self):
        messagebox.showinfo("About","Bingo Search V0.85 by Fredrik Åhfelt")

    def config_exe(self):
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        x= root_x + root_width+10
        y = root_y

        add_window = tk.Toplevel(self.root)
        add_window.title("Configure EXE files")
        add_window.configure(bg='#2c2f33')
#        add_window.geometry("600x270")
        add_window.geometry(f"560x270+{x}+{y}")
        style = ttk.Style(add_window)
        style.theme_use("clam")
        # Configure styles
        style.configure("TEntry", background="white", foreground="black", fieldbackground="white", font=("Arial", 12, "bold"))
        style.configure("TLabel", background="#2c2f33", foreground="white", font=("Arial", 12, "bold"))
        style.configure("TButton", background="#2c2fa0", foreground="white", font=("Arial", 12, "bold"))

        # Create a frame for the labels on the left side
        labels_frame = tk.Frame(add_window, bg='#2c2f33')
        labels_frame.pack(side=tk.LEFT, padx=10, pady=10, anchor=tk.N)
        entries_frame = tk.Frame(add_window, bg='#2c2f33')
        entries_frame.pack(fill=tk.X, padx=10, pady=10, anchor=tk.N,expand=True)
        buttons_frame = tk.Frame(add_window, bg='#2c2f33')
        buttons_frame.pack(side=tk.LEFT, padx=10, pady=10, anchor=tk.N)


        ttk.Label(labels_frame, text="VSM Panel:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Director V8.60:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Director V8.50:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Director V8.40:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Director V8.20:").pack(anchor=tk.W, pady=4)
        ttk.Label(labels_frame, text="Director V7.20:").pack(anchor=tk.W, pady=4)

        def create_entry(parent, bind_value):
            entry = ttk.Entry(parent)
            entry.pack(fill=tk.X, pady=5)
            #entry.insert(0,"Right click to define")
            entry.bind("<Button-3>", lambda event: on_right_click(event, bind_value))
            return entry

        def on_right_click(event,ent):
            file_path = filedialog.askopenfilename(title="Select a file")
            if file_path:
                entries[ent].delete(0, tk.END)
                entries[ent].insert(0,file_path)

        def on_submit():
            self.vsm_panel_path['VSM_Panel'] = entries[0].get()
            self.riedel_paths['director_v860'] = entries[1].get()
            self.riedel_paths['director_v850'] = entries[2].get()
            self.riedel_paths['director_v840'] = entries[3].get()
            self.riedel_paths['director_v820'] = entries[4].get()
            self.riedel_paths['director_v720'] = entries[5].get()
            self.save_config()
            add_window.destroy()
            pass

        entries = []
        for i in range(0,6):
            entries.append(create_entry(entries_frame,i))

        entries[0].insert(0,self.vsm_panel_path['VSM_Panel'])
        entries[1].insert(0,self.riedel_paths['director_v860'])
        entries[2].insert(0,self.riedel_paths['director_v850'])
        entries[3].insert(0,self.riedel_paths['director_v840'])
        entries[4].insert(0,self.riedel_paths['director_v820'])
        entries[5].insert(0,self.riedel_paths['director_v720'])

        add_button = ttk.Button(entries_frame, text="Ok", command=on_submit)
        add_button.pack(anchor=tk.E, pady=10)

    def add_to_favorites(self):
        self.favorites[os.path.basename(self.file_path)] = self.file_path
        self.favorites_menu.delete(0,'end')
        for key, value in self.favorites.items():
            if value:
                self.favorites[key] = value
                menu_label = key.capitalize()
                self.favorites_menu.add_command(label=menu_label, command=lambda k=key: self.open_favorite(k))
        self.save_config()

    def drop(self,event):
        shortcut_path = event.data.strip('{}')
        
        if shortcut_path.lower().endswith('.lnk'):
            try:
                # Get the name of the shortcut file
#                shortcut_name = os.path.basename(shortcut_path)
                shortcut_name = os.path.splitext(os.path.basename(shortcut_path))[0]
                
                # Parse the .lnk file using pylnk3 to extract the target path
                lnk = pylnk3.parse(shortcut_path)
                
                # Initialize display text with shortcut name
                display_text = f"Shortcut Name: {shortcut_name}\n"
                
                # Check if the target path is available and add it to the display text
                if hasattr(lnk.link_info, 'local_base_path') and lnk.link_info.local_base_path:
                    target = lnk.link_info.local_base_path
                    display_text += f"Target Path: {target}"
                    self.db_manager.add_record(
                    Description = shortcut_name,
                    System = "URL",
                    URL = target)


                else:
                    display_text += "Target Path: Not available"
                
                # Update the label with the collected information
                print(display_text)
            except Exception as e:
                print(f"Error reading shortcut: {e}")
        else:
            print("Please drop a valid .lnk shortcut")



if __name__ == "__main__":
    #root = tk.Tk()
    root = TkinterDnD.Tk()
    app = App(root)
    root.mainloop()

