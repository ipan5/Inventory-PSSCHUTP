import sqlite3
import pandas as pd
from datetime import datetime
import requests  # Required for sending Telegram notifications

# --- TELEGRAM CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8977371486:AAFTjSdBPSnq2JWzX0bzVWj2Zc_GlfnYDUo"  # Paste your BotFather token inside the quotes
TELEGRAM_CHAT_ID = "828215103"      # Paste your UserInfobot Chat ID inside the quotes

def send_telegram_alert(message):
    """Sends a push notification to your Telegram chat."""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or TELEGRAM_CHAT_ID == "YOUR_CHAT_ID_HERE":
        return  # Skip if credentials haven't been entered yet
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")


def get_connection():
    return sqlite3.connect("inventory.db", check_same_thread=False)

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO categories (category_name) VALUES ('Alat Persilatan')")
        cursor.execute("INSERT INTO categories (category_name) VALUES ('General')")
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            total_quantity INTEGER NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            borrower_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            request_time TEXT NOT NULL,
            approved_time TEXT,
            returned_time TEXT,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY(item_id) REFERENCES items(id)
        )
    ''')
    conn.commit()
    conn.close()

def add_category(name):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (category_name) VALUES (?)", (name,))
        conn.commit()
    except:
        pass
    finally:
        conn.close()

def get_categories():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM categories", conn)
    conn.close()
    return df['category_name'].tolist()

def add_item(name, category, location, quantity):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO items (item_name, category, location, total_quantity) VALUES (?, ?, ?, ?)", 
                   (name, category, location, quantity))
    conn.commit()
    conn.close()

def log_request(item_id, borrower, phone, qty):
    conn = get_connection()
    cursor = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute('''
        INSERT INTO requests (item_id, borrower_name, phone_number, quantity, request_time, status)
        VALUES (?, ?, ?, ?, ?, 'Pending')
    ''', (item_id, borrower, phone, qty, current_time))
    conn.commit()
    
    # Fetch item details to include in the notification message
    cursor.execute("SELECT item_name, location FROM items WHERE id = ?", (item_id,))
    item_row = cursor.fetchone()
    conn.close()
    
    if item_row:
        item_name, location = item_row
        # Trigger the Telegram alert!
        alert_msg = (
            f"🚨 *New Inventory Request!*\n\n"
            f"👤 *Borrower:* {borrower}\n"
            f"📞 *Phone:* {phone}\n"
            f"📦 *Item:* {qty}x {item_name}\n"
            f"📍 *Location:* {location}\n"
            f"⏱️ *Time:* {current_time}"
        )
        send_telegram_alert(alert_msg)

def approve_request(request_id):
    conn = get_connection()
    cursor = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE requests SET status = 'Approved', approved_time = ? WHERE id = ?", (current_time, request_id))
    conn.commit()
    conn.close()

def return_request(request_id):
    conn = get_connection()
    cursor = conn.cursor()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE requests SET status = 'Returned', returned_time = ? WHERE id = ?", (current_time, request_id))
    conn.commit()
    conn.close()

def reject_request(request_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE requests SET status = 'Rejected' WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()

def get_all_items():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM items", conn)
    conn.close()
    return df

def get_requests(status_filter):
    conn = get_connection()
    query = f'''
        SELECT r.id as request_id, i.id as item_id, i.item_name, i.category, i.location, 
               r.borrower_name, r.phone_number, r.quantity, r.request_time, r.approved_time, r.returned_time, r.status
        FROM requests r
        JOIN items i ON r.item_id = i.id
        WHERE r.status = '{status_filter}'
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
def update_item_quantity(item_id, amount_change):
    """Adds or reduces an item's total quantity."""
    conn = get_connection()
    cursor = conn.cursor()
    # Ensure quantity doesn't drop below 0
    cursor.execute('''
        UPDATE items 
        SET total_quantity = MAX(0, total_quantity + ?) 
        WHERE id = ?
    ''', (amount_change, item_id))
    conn.commit()
    conn.close()

def delete_item(item_id):
    """Deletes an item from the inventory master list."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
def split_or_move_item_location(item_id, target_location, move_quantity):
    """Moves a specific quantity of an item to a new location."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current item details
    cursor.execute("SELECT item_name, category, location, total_quantity FROM items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return "Item not found"
        
    name, category, current_location, total_qty = row
    
    if move_quantity >= total_qty:
        # If moving all of them, just update the location directly
        cursor.execute("UPDATE items SET location = ? WHERE id = ?", (target_location, item_id))
    else:
        # If splitting them, reduce the quantity of the current row
        cursor.execute("UPDATE items SET total_quantity = total_quantity - ? WHERE id = ?", (move_quantity, item_id))
        
        # Check if the target location already has this exact item name and category
        cursor.execute("SELECT id, total_quantity FROM items WHERE item_name = ? AND category = ? AND location = ?", 
                       (name, category, target_location))
        existing_target = cursor.fetchone()
        
        if existing_target:
            # If it already exists at the target location, just add to its quantity
            target_id, target_qty = existing_target
            cursor.execute("UPDATE items SET total_quantity = ? WHERE id = ?", (target_qty + move_quantity, target_id))
        else:
            # Otherwise, create a brand new row for the target location
            cursor.execute("INSERT INTO items (item_name, category, location, total_quantity) VALUES (?, ?, ?, ?)",
                           (name, category, target_location, move_quantity))
                           
    conn.commit()
    conn.close()
    return "Success"