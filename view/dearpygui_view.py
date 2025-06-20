"""
DearPyGuiView: DearPyGui-based UI for Photo Sorter

This file implements the DearPyGuiView class, which provides a modern, responsive graphical user interface for the photo sorter application using the Dear PyGui library. The class is designed to be modular and maintainable, and implements the BaseView interface so that the UI backend can be swapped if needed. It manages the main application window, image display, category buttons, status updates, and user interactions such as folder selection, navigation, and category assignment. The UI aims for a clean, modern look and a smooth user experience.

Key responsibilities:
- Build and manage all DearPyGui widgets and windows for the photo sorter app
- Handle user interactions (button clicks, keyboard shortcuts, folder selection, etc.)
- Display images and update UI elements in response to user actions
- Provide visual feedback for navigation and category selection
- Support modular callbacks for controller integration
"""
from pathlib import Path
import dearpygui.dearpygui as dpg
from view.base_view import BaseView
import numpy as np
from PIL import Image
from typing import Optional, Callable, Dict, List
import threading

# Main DearPyGui-based view class for the photo sorter application
class DearPyGuiView(BaseView):
    _instance = None  # Singleton instance for global access

    # --- UI Tags and Layout Parameters ---
    TAG_MAIN_WINDOW = "main_window"
    TAG_MENU_BAR = "menu_bar"
    TAG_TOP_CONTROLS = "top_controls"
    TAG_RESET_BUTTON = "reset_button"
    TAG_STATUS_TEXT = "status_text"
    TAG_IMAGE_DISPLAY = "image_display"
    TAG_IMAGE_TEXTURE = "image_texture"
    TAG_PLACEHOLDER_TEXTURE = "placeholder_texture"
    TAG_IMAGE_AREA = "image_area_group"
    TAG_PREV_BUTTON = "prev_button"
    TAG_NEXT_BUTTON = "next_button"
    TAG_CATEGORIES_CONTAINER = "categories_container"

    # Layout parameters for window and widgets
    DEFAULT_WIDTH = 1200
    DEFAULT_HEIGHT = 730
    IMAGE_DISPLAY_WIDTH = 576
    IMAGE_DISPLAY_HEIGHT = 360
    CATEGORY_BUTTON_WIDTH = 231

    def __init__(self):
        # --- Initialize Dear PyGui context and compute viewport position/size ---
        DearPyGuiView._instance = self  # Set singleton instance
        dpg.create_context()
        # --- Load and bind font globally ---
        font_path = str(Path(__file__).parent / "Roboto-Regular.ttf")
        with dpg.font_registry():
            default_font = dpg.add_font(font_path, 18)  # 18 is a good default size
        dpg.bind_font(default_font)

        self.width = self.DEFAULT_WIDTH
        self.height = self.DEFAULT_HEIGHT

        # Compute centered position for the viewport on the primary monitor
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            root.destroy()
            x_pos = max((screen_width - self.width) // 2, 0)
            y_pos = max((screen_height - self.height) // 2, 0)
        except Exception:
            x_pos, y_pos = 0, 0

        icon_path = Path(__file__).parent / "icon.ico"
        # Store viewport parameters for later creation
        self._viewport_params = {
            "title": "Photo Sorter",
            "width": self.width,
            "height": self.height,
            "small_icon": str(icon_path),
            "large_icon": str(icon_path),
            "x_pos": x_pos,
            "y_pos": y_pos
        }

        # Create and configure the viewport before building UI to avoid blank initial frame
        dpg.create_viewport(**self._viewport_params)
        dpg.setup_dearpygui()

        # --- Build all UI widgets and windows, with viewport parameters ready ---
        with dpg.texture_registry() as self.texture_registry:
            dpg.add_dynamic_texture(
                width=1,
                height=1,
                default_value=[0.0, 0.0, 0.0, 0.0],
                tag=self.TAG_PLACEHOLDER_TEXTURE
            )
            initial_texture_data = [0.0] * (self.IMAGE_DISPLAY_WIDTH * self.IMAGE_DISPLAY_HEIGHT * 4)
            dpg.add_dynamic_texture(
                width=self.IMAGE_DISPLAY_WIDTH,
                height=self.IMAGE_DISPLAY_HEIGHT,
                default_value=initial_texture_data,
                tag=self.TAG_IMAGE_TEXTURE
            )

        # --- Theme creation (optimized) ---
        self._themes = self._create_all_themes()
        self._category_button_ids = dict()
        self._feedback_timers = dict()
        self._nav_button_ids = dict()

        # --- Build main window and layout ---
        with dpg.window(label="", tag=self.TAG_MAIN_WINDOW, no_close=True, no_collapse=True, no_move=True, no_title_bar=True, no_resize=True, width=self.width, height=self.height, pos=[0,0]):
            self._build_menu_bar()
            btn_reset = dpg.add_button(label="Reset", tag=self.TAG_RESET_BUTTON, pos=[self.width-70, 30])
            dpg.bind_item_theme(btn_reset, self._themes['reset'])
            dpg.add_spacer(height=20)
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=0, tag="left_spacer")
                with dpg.group(tag="center_content"):
                    self._build_top_controls()
                    dpg.add_spacer(height=10)
                    self._build_status_text()
                    dpg.add_spacer(height=20)
                    self._build_image_area()
                    dpg.add_spacer(height=20)
                    self._build_categories_container()
                dpg.add_spacer(width=0, tag="right_spacer")
            dpg.add_spacer(height=20)

        # --- Responsive centering on viewport resize ---
        def _on_viewport_resize():
            vp_width = dpg.get_viewport_client_width()
            content_width = 2 * 40 + self.IMAGE_DISPLAY_WIDTH + 120
            side_space = max((vp_width - content_width) // 2, 0)
            dpg.configure_item("left_spacer", width=side_space)
            dpg.configure_item("right_spacer", width=side_space)
            dpg.configure_item(self.TAG_MAIN_WINDOW, width=vp_width, height=dpg.get_viewport_client_height(), pos=[0, 0])
            dpg.configure_item(self.TAG_RESET_BUTTON, pos=[vp_width-70, 30])
        dpg.set_viewport_resize_callback(_on_viewport_resize)

        # --- Initialize callback and state dictionaries ---
        self._callbacks: Dict[str, Callable] = {}
        self._category_callbacks: Dict[int, Dict[str, Callable]] = {}
        self._modal_open = False  # Track if a modal dialog is open

    def _create_theme(self, button_color, hover_color, active_color, padding=(12, 8)):
        """Helper function to create a theme with consistent styling."""
        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, button_color)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, hover_color)
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, active_color)
                dpg.add_theme_color(dpg.mvThemeCol_Text, [220, 220, 220, 255])
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, *padding)
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 4, 4)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 4, 4)
        return theme

    def _create_all_themes(self):
        """Create all themes at once to improve performance."""
        themes = {}
        # Base theme colors
        base = {
            'button': [55, 58, 64, 255],
            'text': [220, 220, 220, 255],
            'blue_hover': [44, 90, 130, 255],
            'blue_active': [33, 70, 110, 255],
            'red_hover': [180, 60, 60, 255],
            'red_active': [130, 40, 40, 255],
            'gray_hover': [90, 90, 90, 255],
            'gray_active': [70, 70, 70, 255],
            'cat_defined': [48, 50, 54, 255]
        }
        themes['select_folder'] = self._create_theme(base['button'], base['blue_hover'], base['blue_active'], (12, 2))
        themes['select_folder_feedback'] = self._create_theme(base['blue_active'], base['blue_active'], base['blue_active'], (12, 2))
        themes['reset'] = self._create_theme(base['button'], base['red_hover'], base['red_active'])
        themes['reset_feedback'] = self._create_theme(base['red_active'], base['red_active'], base['red_active'])
        themes['prev'] = self._create_theme(base['button'], base['gray_hover'], base['gray_active'])
        themes['prev_feedback'] = self._create_theme(base['gray_active'], base['gray_active'], base['gray_active'])
        themes['next'] = self._create_theme(base['button'], base['gray_hover'], base['gray_active'])
        themes['next_feedback'] = self._create_theme(base['gray_active'], base['gray_active'], base['gray_active'])
        themes['category'] = self._create_theme(base['button'], base['blue_hover'], base['blue_active'])
        themes['category_defined'] = self._create_theme(base['cat_defined'], base['blue_hover'], base['blue_active'])
        themes['category_feedback'] = self._create_theme(base['blue_active'], base['blue_active'], base['blue_active'])
        return themes

    # --- UI Construction Methods ---
    def _build_menu_bar(self):
        """Build the menu bar with How to and About menu items."""
        from view.dialogs import show_how_to, show_about
        with dpg.menu_bar(tag=self.TAG_MENU_BAR):
            with dpg.menu(label="Menu"):
                dpg.add_menu_item(label="How to", callback=lambda: show_how_to())
                dpg.add_menu_item(label="About", callback=lambda: show_about())

    def _build_top_controls(self):
        """Build the top controls: select folder button and folder path display."""
        with dpg.group(horizontal=True, tag=self.TAG_TOP_CONTROLS):
            # Set explicit width and height to prevent visual change on enable/disable
            btn1 = dpg.add_button(
                label="Select Source Folder",
                callback=self._on_select_folder,
                tag="select_folder_button",
                width=170,  # Fixed width for visual consistency
                height=30   # Fixed height for visual consistency
            )
            dpg.bind_item_theme(btn1, self._themes['select_folder'])
            dpg.add_spacer(width=10)
            dpg.add_text("No folder selected", tag="selected_folder_path", wrap=400)

    def _build_status_text(self):
        """Build the status text area."""
        dpg.add_text("Select a source folder", tag=self.TAG_STATUS_TEXT)

    def _build_image_area(self):
        """Build the image display area with navigation buttons."""
        with dpg.group(horizontal=True, tag=self.TAG_IMAGE_AREA):
            btn_prev = dpg.add_button(label="<", callback=self._on_prev, tag=self.TAG_PREV_BUTTON, width=40, height=self.IMAGE_DISPLAY_HEIGHT)
            dpg.bind_item_theme(btn_prev, self._themes['prev'])
            self._nav_button_ids['prev'] = btn_prev
            dpg.add_spacer(width=10)
            dpg.add_image(texture_tag=self.TAG_IMAGE_TEXTURE, tag=self.TAG_IMAGE_DISPLAY, width=self.IMAGE_DISPLAY_WIDTH, height=self.IMAGE_DISPLAY_HEIGHT)
            dpg.add_spacer(width=10)
            btn_next = dpg.add_button(label=">", callback=self._on_next, tag=self.TAG_NEXT_BUTTON, width=40, height=self.IMAGE_DISPLAY_HEIGHT)
            dpg.bind_item_theme(btn_next, self._themes['next'])
            self._nav_button_ids['next'] = btn_next

    def _build_categories_container(self):
        """Build the container for category buttons."""
        dpg.add_group(tag=self.TAG_CATEGORIES_CONTAINER)

    # --- Event Handlers and Callback Registration ---
    def _on_select_folder(self) -> None:
        """Internal event handler for folder selection button. Prevents multiple dialogs."""
        if getattr(self, '_modal_open', False):
            return  # Prevent folder dialog if a modal is open
        self.set_select_folder_button_enabled(False)
        try:
            if self._callbacks.get("select_folder"):
                self._callbacks["select_folder"]()
        finally:
            self.set_select_folder_button_enabled(True)

    def _on_next(self) -> None:
        """Internal event handler for next image button."""
        if self._callbacks.get("next"):
            self._callbacks["next"]()

    def _on_prev(self) -> None:
        """Internal event handler for previous image button."""
        if self._callbacks.get("prev"):
            self._callbacks["prev"]()

    def protocol(self, protocol_name: str, callback: Optional[Callable] = None) -> None:
        """Register a protocol callback (e.g., for window close events)."""
        if protocol_name == "WM_DELETE_WINDOW" and callback:
            self._callbacks["close"] = callback

    def on_select_folder(self, callback: Callable) -> None:
        """Register callback for folder selection."""
        self._callbacks["select_folder"] = callback

    def on_next(self, callback: Callable) -> None:
        """Register callback for next image."""
        self._callbacks["next"] = callback

    def on_prev(self, callback: Callable) -> None:
        """Register callback for previous image."""
        self._callbacks["prev"] = callback

    def add_reset_button(self, callback: Callable) -> None:
        """Register callback for reset button."""
        self._callbacks["reset"] = callback
        dpg.set_item_callback("reset_button", self._on_reset)

    def _on_reset(self) -> None:
        """Internal event handler for reset button."""
        if self._callbacks.get("reset"):
            self._callbacks["reset"]()

    # --- Folder Selection Dialog ---
    def ask_for_folder(self) -> str:
        """Show a native folder selection dialog and return the selected path."""
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        folder_selected = filedialog.askdirectory(title="Select Source Folder")
        root.destroy()
        return folder_selected or ""

    # --- Image Display ---
    def show_image(self, photo: Optional[Image.Image]) -> None:
        """Display a PIL image in the DearPyGui window."""
        FIXED_WIDTH, FIXED_HEIGHT = self.IMAGE_DISPLAY_WIDTH, self.IMAGE_DISPLAY_HEIGHT
        if photo is None:
            if dpg.does_item_exist(self.TAG_IMAGE_DISPLAY):
                dpg.configure_item(self.TAG_IMAGE_DISPLAY, texture_tag=self.TAG_PLACEHOLDER_TEXTURE, width=FIXED_WIDTH, height=FIXED_HEIGHT)
            return
        if photo.mode != "RGBA":
            photo = photo.convert("RGBA")
        # Efficient conversion to numpy array and ensure 4 channels
        img_array = np.asarray(photo, dtype=np.float32) / 255.0
        if img_array.ndim == 2:
            img_array = np.stack([img_array, img_array, img_array, np.ones_like(img_array)], axis=-1)
        elif img_array.shape[2] == 3:
            alpha = np.ones((*img_array.shape[:2], 1), dtype=np.float32)
            img_array = np.concatenate((img_array, alpha), axis=-1)
        elif img_array.shape[2] > 4:
            img_array = img_array[:, :, :4]
        if not img_array.flags['C_CONTIGUOUS']:
            img_array = np.ascontiguousarray(img_array)
        img_list = img_array.flatten().tolist()
        dpg.set_value(self.TAG_IMAGE_TEXTURE, img_list)
        if dpg.does_item_exist(self.TAG_IMAGE_DISPLAY):
            dpg.configure_item(self.TAG_IMAGE_DISPLAY, 
                               texture_tag=self.TAG_IMAGE_TEXTURE, 
                               width=FIXED_WIDTH, 
                               height=FIXED_HEIGHT)
        dpg.set_item_label(self.TAG_IMAGE_DISPLAY, f"{FIXED_WIDTH}x{FIXED_HEIGHT}")
    
    # --- Cleanup and Main Loop ---
    def destroy(self) -> None:
        """Clean up DearPyGui resources and close the window."""
        if self._callbacks.get("close"):
            self._callbacks["close"]()
        dpg.destroy_context()
    
    def mainloop(self, n: int = 0, **kwargs) -> None:
        """Start the DearPyGui main loop."""
        dpg.show_viewport()
        dpg.start_dearpygui()
    
    def quit(self) -> None:
        """Exit the application."""
        dpg.stop_dearpygui()
        self.destroy()
    
    # --- Status and UI Updates ---
    def update_status(self, text: str, file_size_kb: Optional[float] = None) -> None:
        """Update the status text in the UI."""
        status = text
        if file_size_kb is not None:
            status += f" [{file_size_kb:.1f} KB]"
        dpg.set_value("status_text", status)
    
    # --- Category Button Creation and Management ---
    def _create_category_button(self, idx: int, cat: Dict[str, str], parent: str) -> None:
        """Helper function to create a single category button with all handlers, theme, and tooltip."""
        name = cat.get("name", "")
        path = cat.get("path", "")
        button_text = f"{idx + 1}: {name}" if name else f"{idx + 1}: [Empty]"
        btn_id = dpg.generate_uuid()
        btn = dpg.add_button(
            label=button_text,
            callback=lambda s, a, u: self._on_category_click(u),
            user_data=idx,
            width=self.CATEGORY_BUTTON_WIDTH,
            tag=btn_id,
            parent=str(parent)
        )
        # Use defined theme if both name and path are set, else use default
        theme = self._themes['category_defined'] if (name and path) else self._themes['category']
        dpg.bind_item_theme(btn, theme)
        self._category_button_ids[idx] = btn_id
        if path:
            with dpg.tooltip(btn_id):
                dpg.add_text(path)
        with dpg.item_handler_registry() as handler_id:
            dpg.add_item_clicked_handler(
                button=dpg.mvMouseButton_Right,
                callback=lambda s, a, u: self._on_category_right_click(u),
                user_data=idx
            )
        dpg.bind_item_handler_registry(btn_id, handler_id)

    def set_categories(self, categories: List[Dict[str, str]]) -> None:
        """Set up category buttons for image sorting."""
        if dpg.does_item_exist(self.TAG_CATEGORIES_CONTAINER):
            dpg.delete_item(self.TAG_CATEGORIES_CONTAINER, children_only=True)
        self._category_callbacks.clear()
        if hasattr(self, '_category_button_ids'):
            self._category_button_ids.clear()  # Clear button IDs when rebuilding
        # Arrange buttons in a 3x3 grid (3 rows, 3 buttons per row)
        for row in range(3):
            group_id = str(dpg.generate_uuid())
            with dpg.group(parent=self.TAG_CATEGORIES_CONTAINER, horizontal=True, tag=group_id):
                pass  # Just to create the group and get its tag
            for col in range(3):
                idx = row * 3 + col
                cat = categories[idx] if idx < len(categories) else {"name": "", "path": ""}
                self._create_category_button(idx, cat, group_id)

    def _on_category_click(self, idx: int) -> None:
        """Handle left-click on a category button."""
        # Show visual feedback for both mouse and keyboard triggers using the same theme
        DearPyGuiView._show_button_feedback(self, idx)
        if idx in self._category_callbacks:
            self._category_callbacks[idx]["click"](idx)
    
    def _on_category_right_click(self, idx: int) -> None:
        """Handle right-click on a category button."""
        if idx in self._category_callbacks:
            self._category_callbacks[idx]["right"](idx)
    
    def bind_category(self, idx: int, on_click: Callable[[int], None], on_right_click: Callable[[int], None]) -> None:
        """Bind callbacks for category button clicks and right-clicks."""
        self._category_callbacks[idx] = {
            "click": on_click,
            "right": on_right_click
        }
    
    # --- Keyboard Shortcuts ---
    def bind_keyboard_shortcuts(self) -> None:
        """Bind keyboard shortcuts for navigation and category selection."""
        if hasattr(self, '_keyboard_handlers_registered') and self._keyboard_handlers_registered:
            return
        self._keyboard_handlers_registered = True
        with dpg.handler_registry():
            for i in range(9):
                dpg.add_key_press_handler(
                    dpg.mvKey_1 + i,
                    callback=lambda s, a, u: self._handle_keyboard_category(u),
                    user_data=i
                )
            dpg.add_key_press_handler(dpg.mvKey_Left, callback=self._handle_keyboard_prev)
            dpg.add_key_press_handler(dpg.mvKey_Right, callback=self._handle_keyboard_next)

    def _handle_keyboard_prev(self):
        """Handle left arrow key for previous image navigation."""
        self._show_nav_button_feedback('prev')
        self._on_prev()

    def _handle_keyboard_next(self):
        """Handle right arrow key for next image navigation."""
        self._show_nav_button_feedback('next')
        self._on_next()

    def _handle_keyboard_category(self, idx: int) -> None:
        """Handle number key for category selection (if no modal is open)."""
        if getattr(self, "_modal_open", False):
            return
        DearPyGuiView._show_button_feedback(self, idx)
        self._on_category_click(idx)

    # --- UI State Updates ---
    def update_select_folder_button(self, folder_selected: bool) -> None:
        """Update the select folder button label based on selection state."""
        label = "Change Source Folder" if folder_selected else "Select Source Folder"
        if dpg.does_item_exist("select_folder_button"):
            dpg.set_item_label("select_folder_button", label)

    def set_selected_folder_path(self, folder_path: str) -> None:
        """Update the displayed selected folder path next to the Select Folder button."""
        if not folder_path:
            dpg.set_value("selected_folder_path", "No folder selected")
            self.update_select_folder_button(False)
        else:
            import os
            folder_path = os.path.normpath(folder_path)
            dpg.set_value("selected_folder_path", folder_path)
            self.update_select_folder_button(True)

    # --- Visual Feedback for Category and Navigation Buttons ---
    def _show_button_feedback(self, idx: int, duration: float = 0.05) -> None:
        """Show visual feedback for a category button by temporarily changing its theme."""
        if not hasattr(self, '_category_button_ids') or idx not in self._category_button_ids:
            return
        button_id = self._category_button_ids[idx]
        # Cancel any existing timer for this button
        if hasattr(self, '_feedback_timers') and idx in self._feedback_timers:
            timer = self._feedback_timers[idx]
            if timer:
                try:
                    timer.cancel()
                except Exception:
                    pass
            self._feedback_timers[idx] = None
        # Use a temporary feedback theme
        dpg.bind_item_theme(button_id, self._themes['category_feedback'])
        def restore_theme():
            if dpg.does_item_exist(button_id):
                label = dpg.get_item_label(button_id)
                is_empty = '[Empty]' in label if label else True
                theme = self._themes['category'] if is_empty else self._themes['category_defined']
                dpg.bind_item_theme(button_id, theme)
            if idx in self._feedback_timers:
                del self._feedback_timers[idx]
        timer = threading.Timer(duration, restore_theme)
        self._feedback_timers[idx] = timer
        timer.start()

    def _show_nav_button_feedback(self, which: str, duration: float = 0.05) -> None:
        """Show visual feedback for a navigation button by temporarily changing its theme."""
        if which not in self._nav_button_ids:
            return
        button_id = self._nav_button_ids[which]
        if not hasattr(self, '_feedback_timers'):
            self._feedback_timers = dict()
        nav_key = f'nav_{which}'
        if nav_key in self._feedback_timers:
            self._feedback_timers[nav_key] = None
        # Use the correct independent feedback theme
        if which == 'prev':
            dpg.bind_item_theme(button_id, self._themes['prev_feedback'])
        elif which == 'next':
            dpg.bind_item_theme(button_id, self._themes['next_feedback'])
        def restore_theme():
            if self._feedback_timers.get(nav_key) is not None:
                if which == 'prev':
                    dpg.bind_item_theme(button_id, self._themes['prev'])
                elif which == 'next':
                    dpg.bind_item_theme(button_id, self._themes['next'])
                if nav_key in self._feedback_timers:
                    del self._feedback_timers[nav_key]
        self._feedback_timers[nav_key] = True
        threading.Timer(duration, restore_theme).start()

    def set_modal_open(self, is_open: bool):
        """Set the modal open state (True if a modal dialog is open)."""
        self._modal_open = is_open

    def set_select_folder_button_enabled(self, enabled: bool) -> None:
        """Enable or disable the Select Source Folder button."""
        if dpg.does_item_exist("select_folder_button"):
            dpg.configure_item("select_folder_button", enabled=enabled)
