# main_window.py
# Defines the MainWindow class, which builds the main Tkinter UI for the app.
# This file contains all the code for the main window, keeping UI code organized and separate from logic and data.

import tkinter as tk
from tkinter import filedialog
import os

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Photo Sorter')
        self.geometry('800x600')

        # Main layout
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(fill='both', expand=True)

        # Status label
        self.status_label = tk.Label(self.main_frame, text='Select a source folder.')
        self.status_label.pack(pady=20)

        # Image display
        self.image_label = tk.Label(self.main_frame)
        self.image_label.pack(pady=10)

        # Navigation buttons
        nav_frame = tk.Frame(self.main_frame)
        nav_frame.pack(pady=10)
        self.prev_btn = tk.Button(nav_frame, text='Previous')
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        self.next_btn = tk.Button(nav_frame, text='Next')
        self.next_btn.pack(side=tk.LEFT, padx=5)

        # Folder selection
        self.select_btn = tk.Button(self.main_frame, text='Select a source folder')
        self.select_btn.pack(pady=10)

        # Category buttons frame
        self.cat_btn_frame = tk.Frame(self.main_frame)
        self.cat_btn_frame.pack(pady=10, fill='both', expand=True)
        self.cat_buttons = []
        
        # Store category callbacks for keyboard bindings
        self.category_click_callback = None
        self.category_right_callback = None
        
        # Track current button layout
        self.current_columns = 9
        
        # Bind window resize event
        self.bind('<Configure>', self._on_window_resize)

    def on_next(self, callback):
        self.next_btn.config(command=callback)

    def on_prev(self, callback):
        self.prev_btn.config(command=callback)

    def on_select_folder(self, callback):
        self.select_btn.config(command=callback)

    def ask_for_folder(self):
        return filedialog.askdirectory()

    def show_image(self, photo):
        if photo:
            self.image_label.config(image=photo)
            # Attach reference to the label widget's dictionary to prevent garbage collection
            self.image_label.__dict__['photo_ref'] = photo
        else:
            self.image_label.config(image='')
            self.image_label.__dict__['photo_ref'] = None

    def update_status(self, text, file_size_kb=None):
        """
        Update the status label. If file_size_kb is provided, show it between filename and image counter.
        """
        if file_size_kb is not None:
            # Try to split filename and counter, then insert size
            import re
            m = re.match(r'^(.*?)(\s*\(\d+/\d+\))$', text)
            if m:
                name = m.group(1).strip()
                counter = m.group(2)
                size_str = f" [{file_size_kb:.0f} KB]"
                text = f"{name}{size_str} {counter}"
            else:
                # Fallback: just append
                text = f"{text} [{file_size_kb:.0f} KB]"
        self.status_label.config(text=text)
        
    def set_categories(self, categories):
        # Remove old buttons
        for btn in self.cat_buttons:
            btn.destroy()
        self.cat_buttons.clear()
        
        # Create new buttons with dynamic layout
        self._rebuild_category_grid(categories, self.current_columns)

    def bind_category(self, idx, on_click, on_right_click):
        btn = self.cat_buttons[idx]
        # ---
        # Fix: Ensure button relief is always reset after dialog closes, even if cancelled.
        # This prevents the button from staying visually 'pressed' (sunken) if the dialog steals focus.
        def handle_click(event=None, which='left'):
            btn.config(relief='sunken')  # Visually press the button
            try:
                if which == 'left':
                    on_click(idx)
                else:
                    on_right_click(idx)
            finally:
                # Always reset relief after the dialog closes (after idle to ensure dialog is gone)
                btn.after_idle(lambda: btn.config(relief='raised'))
        btn.bind('<Button-1>', lambda e: handle_click(e, 'left'))
        btn.bind('<Button-3>', lambda e: handle_click(e, 'right'))
        # Store callbacks for keyboard bindings
        self.category_click_callback = on_click
        self.category_right_callback = on_right_click

    def bind_keyboard_shortcuts(self):
        # Bind keys 1-9 for category assignment
        for i in range(9):
            self.bind(str(i+1), lambda e, idx=i: self.category_click_callback(idx) if self.category_click_callback else None)
        # Bind Left/Right Arrow keys for image navigation
        # Left Arrow triggers Previous button action
        self.bind('<Left>', lambda e: self.prev_btn.invoke())  # Clear, direct binding
        # Right Arrow triggers Next button action
        self.bind('<Right>', lambda e: self.next_btn.invoke())  # Clear, direct binding
            
    def _rebuild_category_grid(self, categories, columns):
        """Rebuild the category grid with the specified number of columns"""
        # Reset all grid configurations
        for i in range(9):  # Max 9 categories
            self.cat_btn_frame.grid_columnconfigure(i, weight=0)
        
        # Configure grid weights for current columns
        for i in range(min(columns, 9)):  # Max 9 columns
            self.cat_btn_frame.grid_columnconfigure(i, weight=1)
            
        # Add buttons in a grid with calculated columns
        for i in range(9):  # Always 9 category buttons
            row = i // columns
            col = i % columns
            
            # Determine button text based on category configuration
            if i < len(categories) and categories[i].get('name') and categories[i].get('path'):
                btn_text = f'{i+1}: {categories[i]["name"]}'
            else:
                btn_text = f'{i+1}: Select a category'
                
            # Set a fixed height (in text lines) and prevent vertical stretching
            btn = tk.Button(self.cat_btn_frame, text=btn_text, width=18, height=2)
            btn.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
            self.cat_buttons.append(btn)
            
        # Configure row weights for responsive layout, but set to 0 to avoid vertical stretching
        rows_needed = (9 + columns - 1) // columns  # Ceiling division
        for r in range(rows_needed):
            self.cat_btn_frame.grid_rowconfigure(r, weight=0)
            
    def _on_window_resize(self, event):
        """Handle window resize events to adjust button layout"""
        # Only respond to main window resize events, not child widget events
        if event.widget != self:
            return
            
        # Minimum width for a button
        min_btn_width = 110
        
        # Calculate available width (accounting for some padding)
        available_width = event.width - 40  # Subtract some padding
        
        # Calculate how many columns can fit
        columns = max(1, min(9, available_width // min_btn_width))
        
        # Only rebuild if the column count changed
        if columns != self.current_columns:
            self.current_columns = columns
            
            # Get current categories
            categories = []
            for i, btn in enumerate(self.cat_buttons):
                btn_text = btn.cget('text')
                if 'Select a category' not in btn_text:
                    name = btn_text[3:]  # Remove '1: ' prefix
                    categories.append({'name': name, 'path': ''})  # Path isn't visible in UI
                else:
                    categories.append({'name': '', 'path': ''})
            
            # Schedule rebuild to avoid flickering during resize
            self.after_idle(lambda: self.set_categories(categories))
            
    def add_reset_button(self, callback):
        """Add a reset button to the top right corner and bind it to the callback."""
        reset_btn = tk.Button(self.main_frame, text='Reset', command=callback)
        reset_btn.place(relx=1.0, anchor='ne', x=-10, y=10)  # Top right with padding
        self.reset_btn = reset_btn
