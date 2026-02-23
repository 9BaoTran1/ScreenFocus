import cv2
import numpy as np
import mediapipe as mp


# region agent log
def _agent_debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    """Lightweight NDJSON logger for debug-mode instrumentation."""
    import json
    import os
    import time
    log_entry = {
        "id": f"log_{int(time.time() * 1000)}",
        "timestamp": int(time.time() * 1000),
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
    }
    log_dir = r"c:\Users\Thinkpad\Documents\screen_control\.cursor"
    log_path = os.path.join(log_dir, "debug.log")
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        # Logging must never break the main program
        pass


_agent_debug_log(
    run_id="initial",
    hypothesis_id="H1",
    location="gaze_phase1.py:imports",
    message="mediapipe module introspection",
    data={
        "module_type": str(type(mp)),
        "has_solutions_attr": hasattr(mp, "solutions"),
        "dir_sample": sorted([name for name in dir(mp) if not name.startswith("_")])[:20],
    },
)
# endregion


class GazeTracker:
    """
    Phase 1: simple gaze visualization.

    - Uses MediaPipe FaceMesh to get facial landmarks.
    - Extracts eye-region landmarks.
    - Estimates a rough gaze point in normalized screen coordinates.
    - Visualizes gaze as a moving dot in a window.
    """

    def __init__(self, camera_index: int = 0):
        # region agent log
        _agent_debug_log(
            run_id="initial",
            hypothesis_id="H2",
            location="gaze_phase1.py:GazeTracker.__init__",
            message="Entering GazeTracker.__init__",
            data={"camera_index": camera_index},
        )
        # endregion

        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open webcam. Check camera permissions or index.")

        # Configure MediaPipe FaceMesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,  # enables iris landmarks
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # Drawing utilities (for debugging / visualization)
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        # Store last valid gaze for smoothing
        self.last_gaze = None
        self.smoothing_factor = 0.15  # smaller = smoother, larger = more responsive

        # Calibration state
        # We map raw gaze (eye-relative) -> normalized screen coords via affine transform.
        self.calibration_active = False
        self.calibration_points = [
            (0.1, 0.1),
            (0.9, 0.1),
            (0.9, 0.9),
            (0.1, 0.9),
            (0.5, 0.5),
        ]  # normalized screen positions
        self.calibration_samples_per_point = 30
        self._reset_calibration_state()
        self.calibration_matrix = None  # 3x2 affine matrix

        # Landmark indices for iris and eye region (MediaPipe FaceMesh)
        # Using right eye (from user's perspective) as an example.
        # These are standard indices from MediaPipe's face mesh topology.
        self.right_iris_indices = [474, 475, 476, 477]
        self.right_eye_indices = [33, 160, 158, 133, 153, 144, 159, 145]

    def _smooth_gaze(self, new_gaze):
        if self.last_gaze is None:
            self.last_gaze = new_gaze
        else:
            self.last_gaze = (
                (1 - self.smoothing_factor) * np.array(self.last_gaze)
                + self.smoothing_factor * np.array(new_gaze)
            )
        return tuple(self.last_gaze)

    def _reset_calibration_state(self):
        self.current_calib_index = 0
        self.current_raw_samples = []
        self.calib_inputs = []
        self.calib_targets = []

    def _start_calibration(self):
        self.calibration_active = True
        self._reset_calibration_state()

    def _apply_calibration(self, raw_gaze):
        """Apply learned affine mapping if available; otherwise return raw gaze."""
        if self.calibration_matrix is None or raw_gaze is None:
            return raw_gaze
        v = np.array([raw_gaze[0], raw_gaze[1], 1.0])
        out = v @ self.calibration_matrix  # shape (2,)
        return float(out[0]), float(out[1])

    def _maybe_collect_calibration_sample(self, raw_gaze):
        if not self.calibration_active or raw_gaze is None:
            return
        if self.current_calib_index >= len(self.calibration_points):
            return

        self.current_raw_samples.append(raw_gaze)
        if len(self.current_raw_samples) >= self.calibration_samples_per_point:
            # Average current point samples
            avg = tuple(np.mean(self.current_raw_samples, axis=0))
            self.calib_inputs.append(avg)
            self.calib_targets.append(self.calibration_points[self.current_calib_index])
            self.current_calib_index += 1
            self.current_raw_samples = []

            if self.current_calib_index >= len(self.calibration_points):
                # Compute affine mapping: [gx, gy, 1] -> [sx, sy]
                A = np.hstack(
                    [np.array(self.calib_inputs), np.ones((len(self.calib_inputs), 1))]
                )  # (N,3)
                B = np.array(self.calib_targets)  # (N,2)
                try:
                    M, _, _, _ = np.linalg.lstsq(A, B, rcond=None)  # (3,2)
                    self.calibration_matrix = M  # store as (3,2)
                    self.calibration_active = False
                except Exception as e:
                    print(f"Calibration failed: {e}")
                    self.calibration_active = False

    def _estimate_gaze_from_landmarks(self, landmarks, image_shape):
        h, w, _ = image_shape

        # Get iris center (right eye)
        iris_pts = [
            np.array(
                [
                    landmarks[i].x * w,
                    landmarks[i].y * h,
                ]
            )
            for i in self.right_iris_indices
        ]
        iris_center = np.mean(iris_pts, axis=0)

        # Get eye region points for visualization (right eye)
        eye_pts = [
            np.array(
                [
                    landmarks[i].x * w,
                    landmarks[i].y * h,
                ]
            )
            for i in self.right_eye_indices
        ]
        eye_pts = np.array(eye_pts)

        # Normalize iris position within the full frame to [0, 1] range.
        # This tends to correlate better with where you look on the screen
        # than normalizing inside the small eye box.
        gaze_x = float(np.clip(iris_center[0] / w, 0.0, 1.0))
        gaze_y = float(np.clip(iris_center[1] / h, 0.0, 1.0))

        return gaze_x, gaze_y, iris_center, eye_pts

    def run(self):
        window_name = "Gaze Phase 1 - Press 'q' to quit"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to grab frame from webcam.")
                break

            frame = cv2.flip(frame, 1)  # mirror for natural interaction
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            results = self.face_mesh.process(rgb)

            raw_gaze = None
            gaze_point = None
            iris_center = None
            eye_pts = None

            if results.multi_face_landmarks:
                face_landmarks = results.multi_face_landmarks[0].landmark

                try:
                    gx, gy, iris_center, eye_pts = self._estimate_gaze_from_landmarks(
                        face_landmarks, frame.shape
                    )
                    raw_gaze = (gx, gy)
                    # Collect calibration samples if needed
                    self._maybe_collect_calibration_sample(raw_gaze)
                    # Apply calibration (if available), then smooth
                    calibrated = self._apply_calibration(raw_gaze)
                    gaze_point = self._smooth_gaze(calibrated) if calibrated is not None else None
                except Exception as e:
                    # In case landmarks are missing / index issues
                    print(f"Gaze estimation error: {e}")

            # Visualization
            vis = frame.copy()

            if eye_pts is not None:
                for pt in eye_pts.astype(int):
                    cv2.circle(vis, (pt[0], pt[1]), 1, (0, 255, 0), -1)

            if iris_center is not None:
                cv2.circle(
                    vis,
                    (int(iris_center[0]), int(iris_center[1])),
                    2,
                    (0, 0, 255),
                    -1,
                )

            # Draw gaze dot and (optionally) calibration target
            h, w, _ = vis.shape
            overlay = np.zeros_like(vis)

            if gaze_point is not None:
                gx, gy = gaze_point
                dot_x = int(np.clip(gx, 0.0, 1.0) * w)
                dot_y = int(np.clip(gy, 0.0, 1.0) * h)
                cv2.circle(overlay, (dot_x, dot_y), 10, (255, 0, 0), -1)

            # If calibrating, draw current calibration target on overlay
            if self.calibration_active and self.current_calib_index < len(self.calibration_points):
                tx, ty = self.calibration_points[self.current_calib_index]
                cx = int(tx * w)
                cy = int(ty * h)
                cv2.circle(overlay, (cx, cy), 12, (0, 255, 255), 2)

            alpha = 0.6
            vis = cv2.addWeighted(vis, 1.0, overlay, alpha, 0)

            # Display help text
            status_text = (
                "Calibrating... look at the yellow circle"
                if self.calibration_active
                else "Press 'c' to calibrate, 'q' to quit"
            )
            cv2.putText(
                vis,
                status_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(window_name, vis)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c") and not self.calibration_active:
                self._start_calibration()

        self.cap.release()
        cv2.destroyAllWindows()


def main():
    tracker = GazeTracker(camera_index=0)
    tracker.run()


if __name__ == "__main__":
    main()

