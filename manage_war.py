import sqlite3
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox, Listbox, END

DB_NAME = 'war_attacks.db'

def on_row_select(event):
    selected = tree.focus()
    if not selected:
        return
    values = tree.item(selected, 'values')
    if values: 
        attacker_tag_var.set(values[0])
        defender_name_var.set(values[1])
        attack_order_var.set(values[2])
        new_attack_order_var.set(values[2])
        attacker_name_var.set(values[3])
        destruction_percentage_var.set(values[4])
        opponent_clan_var.set(values[5]) # Last column in database: last index

def clear_fields():
    attacker_tag_var.set("")
    attacker_name_var.set("")
    defender_name_var.set("")
    destruction_percentage_var.set("")
    opponent_clan_var.set("")
    attack_order_var.set("")
    new_attack_order_var.set("")

def refresh_tree(filter_text=""):
    for row in tree.get_children():
        tree.delete(row)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get current columns in the table
    c.execute("PRAGMA table_info(logged_attacks)")
    columns = [col[1] for col in c.fetchall()]
    
    # Reconfigure treeview columns
    tree['columns'] = columns
    for col in tree['columns']:
        tree.heading(col, text=col)
        tree.column(col, width=100)
    
    # Build query based on available columns
    if filter_text:
        query = f'''
            SELECT {', '.join(columns)}
            FROM logged_attacks
            WHERE attacker_tag LIKE ? OR attacker_name LIKE ? OR defender_name LIKE ?
        '''
        params = (f'%{filter_text}%', f'%{filter_text}%', f'%{filter_text}%')
    else:
        query = f'''
            SELECT {', '.join(columns)}
            FROM logged_attacks
        '''
        params = ()
    
    c.execute(query, params)
    for row in c.fetchall():
        formatted_row = list(row)
        # Format destruction percentage if the column exists
        if 'destruction_percentage' in columns:
            index = columns.index('destruction_percentage')
            formatted_row[index] = f"{formatted_row[index]}%" if not str(formatted_row[index]).endswith('%') else formatted_row[index]
        tree.insert('', 'end', values=formatted_row)

    conn.close()

def create_attack():
    if not attacker_tag_var.get() or not attacker_name_var.get() or not defender_name_var.get() or not destruction_percentage_var.get() or not opponent_clan_var.get() or not attack_order_var.get():
        messagebox.showerror("Error", "All fields are required.")
        return

    try:
        data = (
            attacker_tag_var.get(),
            attacker_name_var.get(),
            defender_name_var.get(),
            destruction_percentage_var.get(),
            opponent_clan_var.get(),
            int(attack_order_var.get()) 
        )
    except ValueError:
        messagebox.showerror("Error", "Attack Order must be an integer.")
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    try:
        c.execute('INSERT INTO logged_attacks VALUES (?, ?, ?, ?, ?, ?)', data)
        conn.commit()
        # messagebox.showinfo("Success", "Attack added.")
        refresh_tree()
        clear_fields()
    except sqlite3.IntegrityError:
        messagebox.showwarning("Duplicate", "This attack already exists.")
    conn.close()

def update_attack():
    try:
        attacker_tag = attacker_tag_var.get()
        attacker_name = attacker_name_var.get()
        defender_name = defender_name_var.get()
        destruction_percentage = destruction_percentage_var.get()
        opponent_clan = opponent_clan_var.get()
        attack_order = int(attack_order_var.get())
    except ValueError:
        messagebox.showerror("Error", "All fields must be filled correctly with integers for Attack Orders.")
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        c.execute('''UPDATE logged_attacks
                    SET attacker_tag=?,attacker_name=?,defender_name=?,destruction_percentage=?, opponent_clan=? WHERE attack_order=?''',
                  (attacker_tag, attacker_name, defender_name, destruction_percentage, opponent_clan, attack_order))
        conn.commit()
        
        if c.rowcount > 0:
            # messagebox.showinfo("Updated", "Attack updated successfully.")
            refresh_tree()
            clear_fields()
        else:
            messagebox.showwarning("No Changes", "No record was updated. Please check if the data exists.")
    
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"An error occurred: {e}")
    
    finally:
        conn.close()

def delete_attack():
    selected = tree.focus()
    if not selected:
        messagebox.showerror("Error", "No row selected.")
        return
    
    values = tree.item(selected, 'values')
    if values:
        attacker_tag = values[0]
        defender_name = values[2]
        attack_order_str = values[4]
        
        confirm = messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete this attack:\n{attacker_tag} vs {defender_name}?")
        if not confirm:
            return
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''DELETE FROM logged_attacks WHERE attacker_tag = ? AND defender_name = ? AND attack_order = ?''',
                  (attacker_tag, defender_name, attack_order_str))
        conn.commit()
        conn.close()

        # messagebox.showinfo("Deleted", "Attack deleted.")
        refresh_tree()
        clear_fields()

def purge_attack():
    confirm = messagebox.askyesno("Confirm Purge", "Are you sure you want to delete ALL attack records? This action cannot be undone.")
    if not confirm:
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM logged_attacks')
    conn.commit()
    conn.close()
    # messagebox.showinfo("Purged", "All data has been deleted.")
    refresh_tree()
    clear_fields()

def search_attacks(*args):
    query = search_var.get()
    refresh_tree(query)

def manage_columns():
    def refresh_columns_list():
        # Clear current list
        columns_listbox.delete(0, END)
        
        # Get current columns from database
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("PRAGMA table_info(logged_attacks)")
        columns = c.fetchall()
        conn.close()
        
        # Populate listbox with columns
        for col in columns:
            col_info = f"{col[1]} ({col[2]})"  # name (type)
            columns_listbox.insert(END, col_info)
    
    def add_column():
        column_name = column_name_var.get().strip()
        column_type = column_type_var.get()
        
        if not column_name:
            messagebox.showerror("Error", "Column name cannot be empty")
            return
            
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            # Check if column already exists
            c.execute("PRAGMA table_info(logged_attacks)")
            existing_columns = [col[1] for col in c.fetchall()]
            if column_name in existing_columns:
                messagebox.showerror("Error", f"Column '{column_name}' already exists")
                return
                
            # Add the new column
            c.execute(f"ALTER TABLE logged_attacks ADD COLUMN {column_name} {column_type}")
            conn.commit()
            messagebox.showinfo("Success", f"Column '{column_name}' added successfully")
            refresh_columns_list()
            column_name_var.set("")
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to add column: {e}")
        finally:
            conn.close()
    
    def alter_column():
        selected = columns_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Please select a column to modify")
            return
            
        old_name = columns_listbox.get(selected).split()[0]
        new_name = new_column_name_var.get().strip()
        new_type = new_column_type_var.get()
        
        if not new_name:
            messagebox.showerror("Error", "New column name cannot be empty")
            return
            
        # Check if we're actually making changes
        current_col_info = columns_listbox.get(selected)
        current_type = current_col_info.split('(')[1].rstrip(')')
        if old_name == new_name and new_type == current_type:
            messagebox.showwarning("No Changes", "Column specifications are identical")
            return
            
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            conn.execute("BEGIN TRANSACTION")
            
            # Modern SQLite approach (version 3.35.0+)
            if sqlite3.sqlite_version_info >= (3, 35, 0):
                # Case 1: Only changing type (keeping same name)
                if old_name == new_name:
                    # Add temporary column
                    temp_name = f"{old_name}_temp"
                    c.execute(f"ALTER TABLE logged_attacks ADD COLUMN {temp_name} {new_type}")
                    # Copy data
                    c.execute(f"UPDATE logged_attacks SET {temp_name} = {old_name}")
                    # Drop old column
                    c.execute(f"ALTER TABLE logged_attacks DROP COLUMN {old_name}")
                    # Rename temp column
                    c.execute(f"ALTER TABLE logged_attacks RENAME COLUMN {temp_name} TO {new_name}")
                
                # Case 2: Changing name (and optionally type)
                else:
                    # Add new column
                    c.execute(f"ALTER TABLE logged_attacks ADD COLUMN {new_name} {new_type}")
                    # Copy data
                    c.execute(f"UPDATE logged_attacks SET {new_name} = {old_name}")
                    # Drop old column
                    c.execute(f"ALTER TABLE logged_attacks DROP COLUMN {old_name}")
            
            # Fallback for older SQLite versions
            else:
                # Get all columns
                c.execute("PRAGMA table_info(logged_attacks)")
                columns = c.fetchall()
                
                # Build new table structure
                new_columns = []
                for col in columns:
                    if col[1] == old_name:
                        new_columns.append(f"{new_name} {new_type}")
                    else:
                        new_columns.append(f"{col[1]} {col[2]}")
                
                # Create new table
                c.execute(f"""
                    CREATE TABLE new_logged_attacks (
                        {', '.join(new_columns)}
                    )
                """)
                
                # Copy data with column mapping
                old_cols = [col[1] for col in columns]
                new_cols = [new_name if col == old_name else col for col in old_cols]
                c.execute(f"""
                    INSERT INTO new_logged_attacks ({', '.join(new_cols)})
                    SELECT {', '.join(old_cols)} FROM logged_attacks
                """)
                
                # Drop old table and rename new one
                c.execute("DROP TABLE logged_attacks")
                c.execute("ALTER TABLE new_logged_attacks RENAME TO logged_attacks")
            
            conn.commit()
            messagebox.showinfo("Success", f"Column '{old_name}' modified to '{new_name}' ({new_type})")
            refresh_columns_list()
            new_column_name_var.set("")
            
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to modify column: {e}")
        finally:
            conn.close()
    
    def drop_column():
        selected = columns_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Please select a column to drop")
            return
            
        column_name = columns_listbox.get(selected).split()[0]
        
        if not messagebox.askyesno("Confirm", f"Are you sure you want to drop column '{column_name}'?"):
            return
            
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        try:
            conn.execute("BEGIN TRANSACTION")
            
            # Modern SQLite approach (version 3.35.0+)
            if sqlite3.sqlite_version_info >= (3, 35, 0):
                c.execute(f"ALTER TABLE logged_attacks DROP COLUMN {column_name}")
            
            # Fallback for older SQLite versions
            else:
                # Get all columns except the one to drop
                c.execute("PRAGMA table_info(logged_attacks)")
                columns = [col for col in c.fetchall() if col[1] != column_name]
                
                # Build new table structure
                new_columns = [f"{col[1]} {col[2]}" for col in columns]
                
                # Create new table
                c.execute(f"""
                    CREATE TABLE new_logged_attacks (
                        {', '.join(new_columns)}
                    )
                """)
                
                # Copy data (except dropped column)
                col_names = [col[1] for col in columns]
                c.execute(f"""
                    INSERT INTO new_logged_attacks ({', '.join(col_names)})
                    SELECT {', '.join(col_names)} FROM logged_attacks
                """)
                
                # Drop old table and rename new one
                c.execute("DROP TABLE logged_attacks")
                c.execute("ALTER TABLE new_logged_attacks RENAME TO logged_attacks")
            
            conn.commit()
            messagebox.showinfo("Success", f"Column '{column_name}' dropped successfully")
            refresh_columns_list()
            
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to drop column: {e}")
        finally:
            conn.close()
    
    # Create new window for column management
    column_window = ttk.Toplevel(app)
    column_window.title("Manage Database Columns")
    column_window.geometry("500x600")
    
    # Center the window relative to the main app window
    window_width = 500
    window_height = 600
    screen_width = app.winfo_screenwidth()
    screen_height = app.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    column_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    # Notebook for tabs
    notebook = ttk.Notebook(column_window)
    notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
    
    # View Columns Tab
    view_tab = ttk.Frame(notebook)
    notebook.add(view_tab, text="View Columns")
    
    ttk.Label(view_tab, text="Current Columns:").pack(pady=(10, 5))
    columns_listbox = Listbox(view_tab, height=10)
    columns_listbox.pack(fill=BOTH, expand=True, padx=10, pady=5)
    
    # Add Column Tab
    add_tab = ttk.Frame(notebook)
    notebook.add(add_tab, text="Add Column")
    
    column_name_var = ttk.StringVar()
    column_type_var = ttk.StringVar(value="TEXT")
    
    ttk.Label(add_tab, text="Column Name:").pack(pady=(10, 5))
    ttk.Entry(add_tab, textvariable=column_name_var).pack(fill=X, padx=10, pady=5)
    
    ttk.Label(add_tab, text="Data Type:").pack(pady=(10, 5))
    ttk.Combobox(add_tab, textvariable=column_type_var, 
                values=["TEXT", "INTEGER", "REAL", "BLOB"], state="readonly").pack(fill=X, padx=10, pady=5)
    
    ttk.Button(add_tab, text="Add Column", bootstyle=SUCCESS, command=add_column).pack(pady=10)
    
    # Modify Column Tab
    modify_tab = ttk.Frame(notebook)
    notebook.add(modify_tab, text="Modify Column")
    
    new_column_name_var = ttk.StringVar()
    new_column_type_var = ttk.StringVar(value="TEXT")
    
    ttk.Label(modify_tab, text="Select a column to modify from the View tab").pack(pady=(10, 5))
    ttk.Label(modify_tab, text="New Column Name:").pack(pady=(10, 5))
    ttk.Entry(modify_tab, textvariable=new_column_name_var).pack(fill=X, padx=10, pady=5)
    
    ttk.Label(modify_tab, text="New Data Type:").pack(pady=(10, 5))
    ttk.Combobox(modify_tab, textvariable=new_column_type_var, 
                values=["TEXT", "INTEGER", "REAL", "BLOB"], state="readonly").pack(fill=X, padx=10, pady=5)
    
    ttk.Button(modify_tab, text="Modify Column", bootstyle=WARNING, command=alter_column).pack(pady=10)
    
    # Drop Column Tab
    drop_tab = ttk.Frame(notebook)
    notebook.add(drop_tab, text="Drop Column")
    
    ttk.Label(drop_tab, text="Select a column to drop from the View tab").pack(pady=(10, 5))
    ttk.Label(drop_tab, text="Warning: This action cannot be undone!", foreground="red").pack(pady=5)
    ttk.Button(drop_tab, text="Drop Selected Column", bootstyle=DANGER, command=drop_column).pack(pady=20)
    
    # Refresh button
    ttk.Button(column_window, text="Refresh List", command=refresh_columns_list).pack(pady=10)
    
    # Initial refresh
    refresh_columns_list()

# Setup the ttkbootstrap window
app = ttk.Window(themename="cosmo")
app.title("War Attack Logger (Styled CRUD)")
app.geometry("1100x550")

# Frame for inputs
frame = ttk.Frame(app, padding=10)
frame.pack(fill=X)

attacker_tag_var = ttk.StringVar()
attacker_name_var = ttk.StringVar()
defender_name_var = ttk.StringVar()
destruction_percentage_var = ttk.StringVar()
opponent_clan_var = ttk.StringVar()
attack_order_var = ttk.StringVar()
new_attack_order_var = ttk.StringVar()

# Row 0
ttk.Label(frame, text="Attacker Tag").grid(row=0, column=0, padx=5, pady=5, sticky="w")
ttk.Entry(frame, textvariable=attacker_tag_var, width=20).grid(row=0, column=1, padx=5, pady=5)

ttk.Label(frame, text="Attacker Name").grid(row=0, column=2, padx=5, pady=5, sticky="w")
ttk.Entry(frame, textvariable=attacker_name_var, width=20).grid(row=0, column=3, padx=5, pady=5)

# Row 1
ttk.Label(frame, text="Defender Name").grid(row=1, column=0, padx=5, pady=5, sticky="w")
ttk.Entry(frame, textvariable=defender_name_var, width=20).grid(row=1, column=1, padx=5, pady=5)

ttk.Label(frame, text="Destruction %").grid(row=1, column=2, padx=5, pady=5, sticky="w")
ttk.Entry(frame, textvariable=destruction_percentage_var, width=10).grid(row=1, column=3, padx=5, pady=5)

# Row 2
ttk.Label(frame, text="Opponent Clan").grid(row=2, column=0, padx=5, pady=5, sticky="w")
ttk.Entry(frame, textvariable=opponent_clan_var, width=20).grid(row=2, column=1, padx=5, pady=5)

ttk.Label(frame, text="Attack Order").grid(row=2, column=2, padx=5, pady=5, sticky="w")
ttk.Entry(frame, textvariable=attack_order_var, width=10).grid(row=2, column=3, padx=5, pady=5)

ttk.Label(frame, text="New Attack Order").grid(row=2, column=4, padx=5, pady=5, sticky="w")
ttk.Entry(frame, textvariable=new_attack_order_var, width=10).grid(row=2, column=5, padx=5, pady=5)

# Buttons frame
button_frame = ttk.Frame(frame)
button_frame.grid(row=3, column=0, columnspan=8, pady=10)

ttk.Button(button_frame, text="Create", bootstyle=SUCCESS, command=create_attack).pack(side=LEFT, padx=5)
ttk.Button(button_frame, text="Update", bootstyle=WARNING, command=update_attack).pack(side=LEFT, padx=5)
ttk.Button(button_frame, text="Delete", bootstyle=DANGER, command=delete_attack).pack(side=LEFT, padx=5)
ttk.Button(button_frame, text="Purge", bootstyle=DANGER, command=purge_attack).pack(side=LEFT, padx=5)
ttk.Button(button_frame, text="Add Column", bootstyle=PRIMARY, command=manage_columns).pack(side=LEFT, padx=5)

# Search Box
search_var = ttk.StringVar()
ttk.Label(app, text="Search").pack(anchor="w", padx=10)
ttk.Entry(app, textvariable=search_var, width=30).pack(anchor="w", padx=10)
search_var.trace_add("write", search_attacks)

tree = ttk.Treeview(app, 
                   columns=('attacker_tag', 'attacker_name', 'defender_name', 
                           'destruction_percentage', 'opponent_clan', 'attack_order'), 
                   show='headings', 
                   bootstyle="primary")

tree.heading('attacker_tag', text='Attacker Tag')
tree.heading('attacker_name', text='Attacker Name')
tree.heading('defender_name', text='Defender Name')
tree.heading('destruction_percentage', text='Destruction %')
tree.heading('opponent_clan', text='Opponent Clan') 
tree.heading('attack_order', text='Attack Order')
tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

tree.bind("<<TreeviewSelect>>", on_row_select)

# Initialize with current columns
refresh_tree()
app.mainloop()