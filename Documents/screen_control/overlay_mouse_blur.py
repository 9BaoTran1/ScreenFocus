import time

import cv2
import keyboard
import mss
import numpy as np
import pyautogui
import win32con
import win32gui
import win32api


# --- Double-tap state ---
DOUBLE_TAP_INTERVAL = 0.4
_last_press_time = {}
_pending_actions = []

def _on_key_press(event):
    """Detect double-tap and queue actions."""
    if event.event_type != keyboard.KEY_DOWN:
        return
    key = event.name
    now = time.time()
    
    if key in ('q', 'z', 'w'):
        last = _last_press_time.get(key, 0)
        if now - last < DOUBLE_TAP_INTERVAL:
            _pending_actions.append(key)
            _last_press_time[key] = 0  # reset
        else:
            _last_press_time[key] = now

# Register globally
keyboard.on_press(_on_key_press)

WINDOW_NAME = "Mouse Blur Overlay - Double press 'q' to quit"


def get_overlay_hwnd():
    """Get the HWND of the OpenCV overlay window."""
    return win32gui.FindWindow(None, WINDOW_NAME)


def set_window_topmost(hwnd=None):
    """Make the OpenCV window always-on-top."""
    if hwnd is None:
        hwnd = get_overlay_hwnd()
    if hwnd:
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )


def make_window_click_through(hwnd=None):
    """
    Make the overlay ignore mouse clicks so you can still interact with
    the underlying windows. Keyboard input (e.g. pressing 'q') will still
    work when this window has focus.
    """
    if hwnd is None:
        hwnd = get_overlay_hwnd()
    if not hwnd:
        return

    GWL_EXSTYLE = -20
    ex_style = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
    ex_style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
    win32gui.SetWindowLong(hwnd, GWL_EXSTYLE, ex_style)
    # Ensure the window is fully opaque but still a layered window.
    win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)


def run_overlay():
    """
    Phase 2: OS-wide blur preview using mouse as focus.

    - Captures the primary monitor.
    - Blurs the whole image.
    - Keeps a clear circular region around the mouse cursor.
    - Shows result in a full-screen, always-on-top window.

    NOTE: This first version is NOT click-through yet; it demonstrates
    the visual effect and timing. You can press 'q' to close it.
    """

    screen_w, screen_h = pyautogui.size()

    # Capture screen BEFORE creating overlay window to avoid any flashing
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        img = np.array(sct.grab(monitor))
        frame_base = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    # Create the overlay window
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # Give the window a moment to appear, then make it topmost
    time.sleep(0.2)
    hwnd = get_overlay_hwnd()
    set_window_topmost(hwnd)

    # Exclude overlay from screen capture so update_background() captures actual desktop
    try:
        import ctypes
        WDA_EXCLUDEFROMCAPTURE = 0x00000011
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    except Exception as e:
        print(f"Warning: Could not set window display affinity: {e}")

    # Setup Chroma Key (Green)
    # Windows renders this color as fully transparent (visual + input)
    # provided we use LWA_COLORKEY.
    key_color_bgr = (0, 255, 0)
    key_color_int = win32api.RGB(0, 255, 0)  # win32 expects RGB, not BGR

    # Apply extended window styles for transparency
    GWL_EXSTYLE = -20
    ex_style = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
    
    # We REMOVE WS_EX_TRANSPARENT so the opaque parts (blur) BLOCK clicks.
    # The transparent parts (hole) will let clicks through automatically via LWA_COLORKEY.
    ex_style |= win32con.WS_EX_LAYERED
    # ex_style |= win32con.WS_EX_TRANSPARENT  <-- Removed to allow blocking background clicks
    
    win32gui.SetWindowLong(hwnd, GWL_EXSTYLE, ex_style)
    # Set the Chroma Key. 
    # Note: COLORREF is 0x00bbggrr, win32api.RGB returns this format.
    win32gui.SetLayeredWindowAttributes(hwnd, key_color_int, 0, win32con.LWA_COLORKEY)

    focus_w = 800
    focus_h = 600
    # Strong blur kernel
    blur_kernel = (81, 81)

    # Pre-compute blurred version
    # IMPORTANT: We must ensure the blurred image doesn't accidentally contain the key color.
    # A simple hack is to perform a tiny color shift on the key color pixels if they exist,
    # or just assume the probability is low. 
    # Better: modifying the base image slightly to avoid pure green is safer, but ignoring for now for speed.
    blurred_base = cv2.GaussianBlur(frame_base, blur_kernel, 0)

    # Mouse position state
    last_mx, last_my = pyautogui.position()
    
    # Modes State
    smart_focus_mode = False
    dark_mode = False

    print("Controls:")
    print("  'q' + 'q': Quit")
    print("  'r': Refresh (Manual)")
    print("  'w' + 'w': Toggle Smart Focus (Auto-Window)")
    print("  'z' + 'z': Toggle Dark Mode")
    print("  '[' / ']': Resize focus area")

    def update_background(sct, monitor):
        """Captures screen and updates the blurred/dark background base."""
        img = np.array(sct.grab(monitor))
        new_frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        if dark_mode:
            # Pure black overlay
            new_blurred = np.zeros_like(new_frame)
        else:
            # Standard Blur
            new_blurred = cv2.GaussianBlur(new_frame, blur_kernel, 0)
            
        return new_frame, new_blurred

    # Initial capture check (we already have frame_base/blurred_base from setup, 
    # but let's re-run through our new function to respect spotlight default if we wanted, 
    # though default is off so existing match is fine. We'll just start the loop.)

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        
        while True:

            # Ensure we have data (sanity check)
            frame = frame_base
            blurred = blurred_base
            
            if smart_focus_mode:
                try:
                    # Get active window details
                    fg_window = win32gui.GetForegroundWindow()
                    if fg_window:
                        rect = win32gui.GetWindowRect(fg_window)
                        x, y, r, b = rect
                        w = r - x
                        h = b - y
                        
                        # Only follow if it's a valid window (not the overlay itself or empty)
                        # We also skip the taskbar or desktop if possible, but basic check first
                        if w > 0 and h > 0 and fg_window != hwnd:
                            # Center on window
                            mx = x + w // 2
                            my = y + h // 2
                            # Set size to window size + padding
                            padding = 20
                            focus_w = w + padding
                            focus_h = h + padding
                except Exception:
                    pass # Fallback to last known or mouse if error
            else:
                # Normal mouse mode
                # NO SMOOTHING: Direct assignment
                mx, my = pyautogui.position()
            
            # Calculate rectangle coordinates centered on mouse/window center
            x1 = mx - focus_w // 2
            y1 = my - focus_h // 2
            x2 = mx + focus_w // 2
            y2 = my + focus_h // 2
            
            composed = blurred.copy()

            # Draw the transparency hole (Rectangle)
            # Instead of copying the clear frame, we draw the KEY COLOR.
            # Windows will render this as transparent.
            cv2.rectangle(composed, (x1, y1), (x2, y2), key_color_bgr, -1)

            # Optional: white border visual
            cv2.rectangle(
                composed,
                (x1, y1),
                (x2, y2),
                (255, 255, 255),
                2,
                lineType=cv2.LINE_AA,
            )

            cv2.imshow(WINDOW_NAME, composed)

            # Process double-tap actions
            running = True
            while _pending_actions:
                action = _pending_actions.pop(0)
                if action == 'q':
                    running = False
                elif action == 'w':
                    smart_focus_mode = not smart_focus_mode
                    if not smart_focus_mode:
                        # Reset to default size when turning off
                        focus_w = 800
                        focus_h = 600
                    print(f"Smart Focus: {'ON' if smart_focus_mode else 'OFF'}")
                elif action == 'z':
                    dark_mode = not dark_mode
                    print(f"Dark Mode: {'ON' if dark_mode else 'OFF'}")
                    # Must update immediately to show the new visual style
                    frame_base, blurred_base = update_background(sct, monitor)

            if not running:
                break
                
            # 'r' to Refresh (Manual) - single press
            if keyboard.is_pressed('r'):
                frame_base, blurred_base = update_background(sct, monitor)
                time.sleep(0.3)

            # Adjust size with '[' and ']' (Only works in manual mode ideally, or overrides auto temp)
            if not smart_focus_mode:
                if keyboard.is_pressed(']'):
                    focus_w += 10
                    focus_h += 10
                    time.sleep(0.01) # fast repeat
                if keyboard.is_pressed('['):
                    focus_w = max(50, focus_w - 10)
                    focus_h = max(50, focus_h - 10)
                    time.sleep(0.01)
            
            cv2.waitKey(1)

    keyboard.unhook_all()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_overlay()

