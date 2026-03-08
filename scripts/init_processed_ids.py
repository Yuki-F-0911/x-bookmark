import os
import json
import sys
from src.bookmark_loader import load_bookmarks, save_processed_ids

def init_processed_ids():
    bookmarks_file = "bookmarks.json"
    processed_ids_file = "processed_ids.json"
    
    print(f"Loading {bookmarks_file}...")
    try:
        all_bookmarks = load_bookmarks(bookmarks_file)
        ids = {bm.id for bm in all_bookmarks}
        print(f"Found {len(ids)} unique IDs in {bookmarks_file}.")
        
        save_processed_ids(ids, processed_ids_file)
        print("Successfully initialized processed_ids.json.")
        
    except Exception as e:
        print(f"Error initializing processed_ids.json: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_processed_ids()
