import sqlite3
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox

DB_NAME = 'war_attacks.db'

def on_row_select(event):
    selected = tree.focus()
    if not selected:
        return
    values = tree.item(selected, 'values')
    if values:
        attacker_tag_var.set(values[0])
        attacker_name_var.set(values[1])
        defender_name_var.set(values[2])
        destruction_percentage_var.set(values[3])
        attack_order_var.set(values[4])
        new_attack_order_var.set(values[4])

def clear_fields():
    attacker_tag_var.set("")
    attacker_name_var.set("")
    defender_name_var.set("")
    destruction_percentage_var.set("")
    attack_order_var.set("")
    new_attack_order_var.set("")

def refresh_tree(filter_text=""):
    for row in tree.get_children():
        tree.delete(row)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if filter_text:
        c.execute('''
            SELECT attacker_tag, attacker_name, defender_name, destruction_percentage, attack_order
            FROM logged_attacks
            WHERE attacker_tag LIKE ? OR attacker_name LIKE ? OR defender_name LIKE ?
        ''', (f'%{filter_text}%', f'%{filter_text}%', f'%{filter_text}%'))
    else:
        c.execute('''
            SELECT attacker_tag, attacker_name, defender_name, destruction_percentage, attack_order
            FROM logged_attacks
        ''')
    for row in c.fetchall():
        formatted_row = list(row)
        formatted_row[3] = f"{formatted_row[3]}%" if not str(formatted_row[3]).endswith('%') else formatted_row[3]
        tree.insert('', 'end', values=formatted_row)

    conn.close()

def create_attack():
    if not attacker_tag_var.get() or not attacker_name_var.get() or not defender_name_var.get() or not destruction_percentage_var.get() or not attack_order_var.get():
        messagebox.showerror("Error", "All fields are required.")
        return

    try:
        data = (
            attacker_tag_var.get(),
            attacker_name_var.get(),
            defender_name_var.get(),
            destruction_percentage_var.get(),
            int(attack_order_var.get())  # Ensure attack order is an integer
        )
    except ValueError:
        messagebox.showerror("Error", "Attack Order must be an integer.")
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    try:
        c.execute('INSERT INTO logged_attacks VALUES (?, ?, ?, ?, ?)', data)
        conn.commit()
        messagebox.showinfo("Success", "Attack added.")
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
        attack_order = int(attack_order_var.get())
    except ValueError:
        messagebox.showerror("Error", "All fields must be filled correctly with integers for Attack Orders.")
        return

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        c.execute('''UPDATE logged_attacks
                    SET attacker_tag=?,attacker_name=?,defender_name=?,destruction_percentage=? WHERE attack_order=?''',
                  (attacker_tag, attacker_name, defender_name, destruction_percentage, attack_order))
        conn.commit()
        
        if c.rowcount > 0:
            messagebox.showinfo("Updated", "Attack updated successfully.")
            refresh_tree()
            clear_fields()
        else:
            messagebox.showwarning("No Changes", "No record was updated. Please check if the data exists.")
    
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"An error occurred: {e}")
    
    finally:
        conn.close()

def delete_attack():
    selected = tree.focus()  # Get the selected row in the Treeview
    if not selected:
        messagebox.showerror("Error", "No row selected.")
        return
    
    # Extract values from the selected row
    values = tree.item(selected, 'values')
    if values:
        attacker_tag = values[0]
        defender_name = values[2]
        attack_order_str = values[4]
        
        # Confirm the deletion action
        confirm = messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete this attack:\n{attacker_tag} vs {defender_name}?")
        if not confirm:
            return
        
        # Delete from the database
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''DELETE FROM logged_attacks WHERE attacker_tag = ? AND defender_name = ? AND attack_order = ?''',
                  (attacker_tag, defender_name, attack_order_str))
        conn.commit()
        conn.close()

        # Show a confirmation message and refresh the tree
        messagebox.showinfo("Deleted", "Attack deleted.")
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
    messagebox.showinfo("Purged", "All data has been deleted.")
    refresh_tree()
    clear_fields()

def search_attacks(*args):
    query = search_var.get()
    refresh_tree(query)

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
attack_order_var = ttk.StringVar()
new_attack_order_var = ttk.StringVar()

ttk.Label(frame, text="Attacker Tag").grid(row=0, column=0, padx=5, pady=5)
ttk.Entry(frame, textvariable=attacker_tag_var, width=20).grid(row=0, column=1)

ttk.Label(frame, text="Attacker Name").grid(row=0, column=2, padx=5, pady=5)
ttk.Entry(frame, textvariable=attacker_name_var, width=20).grid(row=0, column=3)

ttk.Label(frame, text="Defender Name").grid(row=1, column=0, padx=5, pady=5)
ttk.Entry(frame, textvariable=defender_name_var, width=20).grid(row=1, column=1)

ttk.Label(frame, text="Destruction %").grid(row=1, column=2, padx=5, pady=5)
ttk.Entry(frame, textvariable=destruction_percentage_var, width=10).grid(row=1, column=3)

ttk.Label(frame, text="Attack Order").grid(row=1, column=4, padx=5, pady=5)
ttk.Entry(frame, textvariable=attack_order_var, width=10).grid(row=1, column=5)

ttk.Label(frame, text="New Attack Order").grid(row=1, column=6, padx=5, pady=5)
ttk.Entry(frame, textvariable=new_attack_order_var, width=10).grid(row=1, column=7)


ttk.Button(frame, text="Create", bootstyle=SUCCESS, command=create_attack).grid(row=2, column=0, pady=10)
ttk.Button(frame, text="Update", bootstyle=WARNING, command=update_attack).grid(row=2, column=1)
ttk.Button(frame, text="Delete", bootstyle=DANGER, command=delete_attack).grid(row=2, column=2)
ttk.Button(frame, text="Purge", bootstyle=DANGER, command=purge_attack).grid(row=2, column=3)

# Search Box
search_var = ttk.StringVar()
ttk.Label(app, text="Search").pack(anchor="w", padx=10)
ttk.Entry(app, textvariable=search_var, width=30).pack(anchor="w", padx=10)
search_var.trace_add("write", search_attacks)

# Treeview to display data
tree = ttk.Treeview(app, columns=('attacker_tag', 'attacker_name', 'defender_name', 'destruction_percentage', 'attack_order'), show='headings', bootstyle="info")
tree.heading('attacker_tag', text='Attacker Tag')
tree.heading('attacker_name', text='Attacker Name')
tree.heading('defender_name', text='Defender Name')
tree.heading('destruction_percentage', text='Destruction %')
tree.heading('attack_order', text='Attack Order')
tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

tree.bind("<<TreeviewSelect>>", on_row_select)

refresh_tree()
app.mainloop()
