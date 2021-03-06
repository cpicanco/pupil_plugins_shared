# -*- coding: utf-8 -*-
'''
  Pupil Player Third Party Plugins by cpicanco
  Copyright (C) 2016-2017 Rafael Picanço.

  The present file is distributed under the terms of the GNU General Public License (GPL v3.0).

  You should have received a copy of the GNU General Public License
  along with this program. If not, see <http://www.gnu.org/licenses/>.
'''
# modified version of marker_detector

import os
import sys

# base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join('..','pupil_shared_modules'))

del sys
del os

import cv2
import numpy as np

from pyglui import ui
from methods import normalize
from glfw import glfwGetCurrentContext, glfwGetCursorPos, glfwGetWindowSize

#logging
import logging
logger = logging.getLogger(__name__)

from surface_tracker import Surface_Tracker
from square_marker_detect import draw_markers,m_marker_to_screen
from screen_detector_methods import detect_screens
from reference_surface import Reference_Surface

class Screen_Tracker(Surface_Tracker):
    """docstring
    """
    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        for p in self.g_pool.plugins:
            if p.class_name == 'Marker_Detector':
                p.alive = False
                break

    def init_gui(self):
        if self.g_pool.app == "player":
            self.alive = False
            logger.error('For capture only.')
            return
        self.menu = ui.Growing_Menu('Screen Tracker')
        self.g_pool.sidebar.append(self.menu)

        self.button = ui.Thumb('running',self,label='T',hotkey='t')
        self.button.on_color[:] = (.1,.2,1.,.8)
        self.g_pool.quickbar.append(self.button)
        self.add_button = ui.Thumb('add_surface',setter=self.add_surface,getter=lambda:False,label='A',hotkey='a')
        self.g_pool.quickbar.append(self.add_button)
        self.update_gui_markers()

    def update_gui_markers(self):

        def close():
            self.alive = False

        self.menu.elements[:] = []
        self.menu.append(ui.Button('Close',close))
        self.menu.append(ui.Info_Text('This plugin detects the outmost screen visible in the scene. Ideal screen is white rect in a black backgroud. You can define a surface using 1 visible screen within the world view by clicking *add surface*.'))
        self.menu.append(ui.Switch('robust_detection',self,label='Robust detection'))
        self.menu.append(ui.Slider('min_marker_perimeter',self,step=1,min=10,max=500))
        self.menu.append(ui.Switch('locate_3d',self,label='3D localization'))
        self.menu.append(ui.Selector('mode',self,label="Mode",selection=['Show Markers and Surfaces','Show marker IDs'] ))
        self.menu.append(ui.Button("Add surface", lambda:self.add_surface('_'),))

        for s in self.surfaces:
            idx = self.surfaces.index(s)
            s_menu = ui.Growing_Menu("Surface %s"%idx)
            s_menu.collapsed=True
            s_menu.append(ui.Text_Input('name',s))
            s_menu.append(ui.Text_Input('x',s.real_world_size,label='X size'))
            s_menu.append(ui.Text_Input('y',s.real_world_size,label='Y size'))
            s_menu.append(ui.Button('Open Debug Window',s.open_close_window))
            #closure to encapsulate idx
            def make_remove_s(i):
                return lambda: self.remove_surface(i)
            remove_s = make_remove_s(idx)
            s_menu.append(ui.Button('remove',remove_s))
            self.menu.append(s_menu)

    def recent_events(self,events):
        if 'frame' in events:
            frame = events['frame']
            self.img_shape = frame.height,frame.width,3

            if self.running:
                gray = frame.gray

                # hack "self.markers" instead "self.screens" is keeped for inheritence compatibility
                self.markers = detect_screens(gray)

                if self.mode == "Show marker IDs":
                    draw_markers(frame.img,self.markers)
                    events['frame'] = frame

            # locate surfaces, map gaze
            for s in self.surfaces:
                s.locate(self.markers,self.camera_calibration,self.min_marker_perimeter,self.min_id_confidence, self.locate_3d)
                if s.detected:
                    s.gaze_on_srf = s.map_data_to_surface(events.get('gaze_positions',[]),s.m_from_screen)
                else:
                    s.gaze_on_srf =[]

            events['surface'] = []
            for s in self.surfaces:
                if s.detected:
                    events['surface'].append({
                        'name':s.name,
                        'uid':s.uid,
                        'm_to_screen':s.m_to_screen.tolist(),
                        'm_from_screen':s.m_from_screen.tolist(),
                        'gaze_on_srf': s.gaze_on_srf,
                        'timestamp':frame.timestamp,
                        'camera_pose_3d':s.camera_pose_3d.tolist() if s.camera_pose_3d is not None else None
                    })

            if self.running:
                self.button.status_text = '{}/{}'.format(len([s for s in self.surfaces if s.detected]), len(self.surfaces))
            else:
                self.button.status_text = 'tracking paused'

            if self.mode == 'Show Markers and Surfaces':
                # edit surfaces by user
                if self.edit_surf_verts:
                    window = glfwGetCurrentContext()
                    pos = glfwGetCursorPos(window)
                    pos = normalize(pos,glfwGetWindowSize(window),flip_y=True)
                    for s,v_idx in self.edit_surf_verts:
                        if s.detected:
                            new_pos = s.img_to_ref_surface(np.array(pos))
                            s.move_vertex(v_idx,new_pos)

logging.disable(logging.WARNING)

del Surface_Tracker