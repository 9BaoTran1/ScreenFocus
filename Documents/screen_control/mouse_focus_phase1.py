import cv2
import numpy as np
import pyautogui


def run_mouse_focus():
    """
    Phase 1 (mouse variant): visualize a focus point that follows the mouse.

    This ignores gaze tracking and instead uses the OS mouse position as the
    "attention" point. Useful when the webcam/eye tracking quality is not good.
    """

    # Get screen size so we can normalize mouse coordinates
    screen_w, screen_h = pyautogui.size()

    # Choose a window size (you can resize it manually as well)
    win_w, win_h = 800, 600

    window_name = "Mouse Focus Phase 1 - Press 'q' to quit"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, win_w, win_h)

    while True:
        # Blank background
        frame = np.zeros((win_h, win_w, 3), dtype=np.uint8)

        # Current mouse position in screen coordinates
        mx, my = pyautogui.position()

        # Normalize and map into window coordinates
        gx = np.clip(mx / screen_w, 0.0, 1.0)
        gy = np.clip(my / screen_h, 0.0, 1.0)
        dot_x = int(gx * win_w)
        dot_y = int(gy * win_h)

        # Draw the focus dot
        cv2.circle(frame, (dot_x, dot_y), 12, (255, 0, 0), -1)

        # Draw crosshair lines for reference
        cv2.line(frame, (dot_x, 0), (dot_x, win_h), (80, 80, 80), 1)
        cv2.line(frame, (0, dot_y), (win_w, dot_y), (80, 80, 80), 1)

        # Info text
        cv2.putText(
            frame,
            "Mouse focus demo - move the mouse, press 'q' to quit",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1,
            cv2.LINE_AA,
        )

        cv2.imshow(window_name, frame)

        key = cv2.waitKey(10) & 0xFF
        if key == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_mouse_focus()

