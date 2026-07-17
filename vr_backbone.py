"""
VTK + OpenXR (WiVRn / Quest 3) backbone test.

Purpose: verify the render/interaction pipeline end-to-end with a single
rotating cone, using a structure you can grow into your real project:

  - SceneState        -> replace with your own computed positions/orientations
  - pedal_reader_loop  -> stub for USB pedal input (runs in background thread)
  - timer_callback     -> per-frame hook where your modules plug in

Run with the WiVRn dashboard already showing the Quest 3 as connected.
"""

import threading
import time

from vtkmodules.vtkRenderingOpenXR import (
    vtkOpenXRRenderer,
    vtkOpenXRRenderWindow,
    vtkOpenXRRenderWindowInteractor,
)
from vtkmodules.vtkFiltersSources import vtkConeSource
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper


# ---------------------------------------------------------------------------
# 1. Shared state -- this is what your own logic will eventually populate.
#    Keep it thread-safe since the pedal thread writes to it and the VTK
#    render thread reads from it.
# ---------------------------------------------------------------------------
class SceneState:
    def __init__(self):
        self.lock = threading.Lock()
        self.pedal_value = 0.0     # 0.0 - 1.0, updated by pedal_reader_loop
        self.rotation_deg = 0.0    # example: driven by pedal in this test

    def update_from_pedal(self, value):
        with self.lock:
            self.pedal_value = value

    def snapshot(self):
        with self.lock:
            return self.pedal_value, self.rotation_deg

    def advance_rotation(self, delta_deg):
        with self.lock:
            self.rotation_deg = (self.rotation_deg + delta_deg) % 360.0


state = SceneState()


# ---------------------------------------------------------------------------
# 2. USB pedal stub. Swap the body of this loop for real evdev reads once
#    you know the device path (see notes below the script).
# ---------------------------------------------------------------------------
def pedal_reader_loop(stop_event):
    """
    Placeholder pedal loop. Replace with evdev reads, e.g.:

        from evdev import InputDevice, ecodes
        dev = InputDevice('/dev/input/eventX')
        for event in dev.read_loop():
            if stop_event.is_set():
                break
            if event.type == ecodes.EV_ABS:
                normalized = event.value / dev.absinfo(event.code).max
                state.update_from_pedal(normalized)

    For now this just oscillates a fake value so you can see the loop
    is alive and feeding the render callback.
    """
    t = 0.0
    while not stop_event.is_set():
        fake_value = (1 + __import__("math").sin(t)) / 2.0
        state.update_from_pedal(fake_value)
        t += 0.05
        time.sleep(0.02)


# ---------------------------------------------------------------------------
# 3. Per-frame callback. This is where you'll call into your own modules
#    to compute positions/orientations and push them onto VTK actors.
# ---------------------------------------------------------------------------
class TimerCallback:
    def __init__(self, actor, render_window):
        self.actor = actor
        self.render_window = render_window

    def execute(self, obj, event):
        pedal_value, _ = state.snapshot()

        # Example: drive rotation speed with the (fake, for now) pedal value.
        state.advance_rotation(pedal_value * 5.0)
        _, rotation = state.snapshot()

        self.actor.SetOrientation(0, 0, 0)
        self.actor.RotateY(rotation)

        # --- your own modules would go here instead, e.g.: ---
        # positions = my_module.compute_frame(pedal_value)
        # self.actor.SetPosition(*positions.origin)
        # self.actor.SetOrientation(*positions.orientation_deg)

        self.render_window.Render()


def main():
    # --- VTK OpenXR pipeline setup ---
    renderer = vtkOpenXRRenderer()
    renderer.SetBackground(0.1, 0.1, 0.15)

    render_window = vtkOpenXRRenderWindow()
    render_window.AddRenderer(renderer)

    interactor = vtkOpenXRRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)

    interactor.SetActionManifestDirectory("/home/raslab/Documents/02_vtk-wivrn/pyvr-vtk/xr_config/")

    # --- Minimal test geometry ---
    cone = vtkConeSource()
    cone.SetResolution(24)
    cone.SetHeight(0.3)
    cone.SetRadius(0.15)

    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(cone.GetOutputPort())

    actor = vtkActor()
    actor.SetMapper(mapper)
    # Place it ~1 meter in front of, and at, typical standing eye height
    actor.SetPosition(0.0, 1.4, -1.0)
    renderer.AddActor(actor)

    # --- Pedal reader thread ---
    stop_event = threading.Event()
    pedal_thread = threading.Thread(
        target=pedal_reader_loop, args=(stop_event,), daemon=True
    )
    pedal_thread.start()

    # --- Per-frame render callback ---
    callback = TimerCallback(actor, render_window)
    interactor.AddObserver("TimerEvent", callback.execute)

    print("Initializing OpenXR session... put on the headset now.")
    render_window.Render()
    interactor.Initialize()
    interactor.CreateRepeatingTimer(11)  # ~90 Hz target

    try:
        interactor.Start()
    finally:
        stop_event.set()
        pedal_thread.join(timeout=1.0)
        print("Shut down cleanly.")


if __name__ == "__main__":
    main()