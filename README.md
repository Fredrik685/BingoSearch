BINGO SEARCH v1.51
DESCRIPTION
-----------
Bingo Search is a lightweight database tool designed to organize 
URLs, file paths, and system commands. It allows for quick searching, 
launching of applications with arguments, and managing favorites.

PREREQUISITES
-------------
1. Python 3.x installed on your computer.
   - Download from: https://www.python.org/downloads/
   - During installation, make sure to check "Add Python to PATH".

DEPENDENCIES
------------
This program uses only standard Python libraries. 
No external installation (pip install) is required.
Used libraries: tkinter, sqlite3, os, subprocess, configparser, datetime.

HOW TO INSTALL
--------------
1. Create a folder on your computer (e.g., "C:\Users\nXXXXX\Bingo").
2. Place the python script (e.g., "BingoSearch.py") in this folder.
3. That's it!

HOW TO RUN
----------
Option 1 (Double-click):
   If .py files are associated with Python, simply double-click 
   "BingoSearch.py".

Option 2 (Command Line):
   Open Command Prompt (cmd) or PowerShell, navigate to the folder, 
   and type:
   python BingoSearch.py

GETTING STARTED (FIRST RUN)
---------------------------
1. When you start the program, it will say "No database loaded".
2. Go to the menu: File -> Create new database.
3. Choose a location and name for your database (e.g., "MyLinks.db").
4. The database is now created and ready to use.
5. Right-click in the list to "Edit" (Add new items) or "Add" via menu.

FEATURES OVERVIEW
-----------------
* Add/Edit: Add descriptions, tags, and URLs/Commands.
* Launch: Double-click a row to open the URL or run the command.
* Favorites: Save frequently used databases in the Favorites menu.
* Copy to...: Right-click an item to copy it to another database.
* Move Up/Down: Right-click to reorder items.

FILES
-----
* BingoSearch.py: The main application.
* config.ini:     Auto-generated file that stores your settings 
                  and favorites path.
* *.db:           Your database files (SQLite).

TROUBLESHOOTING
---------------
* If the program closes immediately: Try running it via Command Prompt 
  to see any error messages.
* "Move Up/Down" behaving weirdly: Clear the search bar first. 
  Sorting only works correctly when the full list is visible.

===================================================================
